#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""星恒公有/明文及原始帧回归；参考客户截图，不用真串口、网络或客户授权。"""

from dataclasses import asdict, replace
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import time
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt5.QtCore import QSignalBlocker
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication, QDialog
from app_settings import SettingsStore, read_config, validate_config, write_config
from gui.frame_config_dialog import FrameConfigDialog
from gui.main_window import MainWindow
from gui.protocol_search import protocol_search_keys
from protocol.definitions import PROTOCOL_DEFINITIONS, PROTOCOL_RUILUN, PROTOCOL_XINGHENG_BMS
from protocol.models import StatusBits
from protocol.protocol_handler import ProtocolHandler
from protocol.xingheng import normalize_xingheng_test_frame, xingheng_fields
from serial_comm.serial_manager import SerialManager, SerialPortDetector

_APP = QApplication.instance() or QApplication([])
# 客户原截图逐字节抄录；不从被测编码器生成“期望值”。
REFERENCE = bytes.fromhex("3A 13 1B C8 24 03 88 13 40 40 3F 00 00 4A 02 00 29 0D 04 0D 15 05 00 60 03 FA 00 01 2F 9E 89")


class XinghengEncodingTests(unittest.TestCase):
    """独立检查长度、字段位置、比例、累加覆盖范围和不实施加密的边界。"""

    def setUp(self):
        """每项测试使用独立状态和处理器。"""
        self.handler = ProtocolHandler()
        self.status = StatusBits(protocol_name=PROTOCOL_XINGHENG_BMS)

    def frame(self, status=None):
        """提取成功帧，并独立检查累加和与完整字节范围。"""
        success, frame, error = self.handler.generate_frame(self.status if status is None else status)
        self.assertTrue(success, error)
        self.assertTrue(all(type(value) is int and 0 <= value <= 255 for value in frame))
        self.assertEqual(frame[-1], sum(frame[:-1]) % 256)
        return frame

    def test_customer_capture_matches_every_byte(self):
        """3A 13 1B、索引3的C8及索引30的89必须和客户参考完全一致。"""
        self.assertEqual(bytes(self.frame()), REFERENCE)
        self.assertEqual((len(REFERENCE), REFERENCE[2], REFERENCE[3]), (31, 27, 200))
        self.assertEqual(sum(REFERENCE[:30]) % 256, 0x89)
        definition = PROTOCOL_DEFINITIONS[PROTOCOL_XINGHENG_BMS]
        self.assertEqual((definition.frame_length, definition.checksum_mode, definition.send_mode), (31, "sum", "uart"))
        self.assertEqual((definition.min_send_interval_ms, definition.max_send_interval_ms, definition.default_send_interval_ms), (10, 5000, 1000))

    def test_public_layout_has_no_private_length_byte(self):
        """按表A.2独立计算20字节公有帧，防止把3A的len或字段偏移套进来。"""
        status = replace(self.status, xingheng_message_id=1, xingheng_soc_percent=50,
                         xingheng_voltage_v=53.2, xingheng_current_a=0,
                         xingheng_max_temperature_c=25, xingheng_min_temperature_c=20,
                         xingheng_mos_temperature_c=30, xingheng_rated_voltage_v=48,
                         xingheng_rated_capacity_ah=20, xingheng_material=2)
        expected = [1, 0x13, 1, 0, 2, 0xE0, 1, 0xC8, 0, 0x64,
                    0x14, 2, 0x88, 0x13, 65, 60, 70, 0, 0]
        expected.append(sum(expected) % 256)
        self.assertEqual(self.frame(status), expected)
        self.assertEqual(self.handler.get_protocol_frame_length(PROTOCOL_XINGHENG_BMS, status), 20)
        self.assertEqual(len(self.handler.get_byte_descriptions(PROTOCOL_XINGHENG_BMS, status)), 20)

    def test_every_half_percent_soc_uses_correct_position(self):
        """枚举201个半百分比值，两格式分别写索引3/9，不改变原始保护字段。"""
        for kind, index in ((0x3A, 3), (1, 9)):
            for raw in range(201):
                status = replace(self.status, xingheng_message_id=kind, xingheng_soc_percent=raw / 2)
                frame = self.frame(status)
                self.assertEqual(frame[index], raw)
                if kind == 0x3A:
                    self.assertEqual((frame[13], frame[27:30]), (0x4A, [1, 0x2F, 0x9E]))

    def test_voltage_current_and_temperature_endpoints(self):
        """零电流带偏移，正负电流不使用补码或符号原码，温度范围按偏移编码。"""
        for current, raw in ((-500, 0), (-0.1, 4999), (0, 5000), (0.1, 5001), (500, 10000)):
            frame = self.frame(replace(self.status, xingheng_current_a=current))
            self.assertEqual(bytes(frame[6:8]), raw.to_bytes(2, "little"))
        for voltage, raw in ((0, 0), (0.1, 1), (80.4, 804), (1000, 10000)):
            frame = self.frame(replace(self.status, xingheng_voltage_v=voltage))
            self.assertEqual(bytes(frame[4:6]), raw.to_bytes(2, "little"))
        for temperature, raw in ((-40, 0), (0, 40), (150, 190)):
            frame = self.frame(replace(self.status, xingheng_max_temperature_c=temperature,
                                       xingheng_min_temperature_c=temperature))
            self.assertEqual(frame[8:10], [raw, raw])

    def test_status_bits_and_8bit_current_precision(self):
        """请求应答占D5～D7，FA是25A，不将250A截断到单字节。"""
        frame = self.frame(replace(self.status, xingheng_work_state=2, xingheng_response_device=2,
                                   xingheng_regen_current_a=25.4, xingheng_charge_current_a=25))
        self.assertEqual((frame[12], frame[22], frame[25]), (0x42, 0xFE, 0xFA))
        for field in ("xingheng_regen_current_a", "xingheng_charge_current_a"):
            success, _, _ = self.handler.generate_frame(replace(self.status, **{field: 250}))
            self.assertFalse(success)

    def test_fault_alarm_codes_are_not_clipped_to_decimal_25(self):
        """表A.4的报警及预警码能原样进入两种报文。"""
        for kind, index in ((0x3A, 11), (1, 17)):
            for code in (0x14, 0x15, 0x22, 0x24, 0x29):
                self.assertEqual(self.frame(replace(self.status, xingheng_message_id=kind, xingheng_fault_code=code))[index], code)

    def test_invalid_fields_are_rejected_without_rounding(self):
        """两类报文的全部有效字段拒绝布尔、非数、无穷和越界；小数精度不能被舍入。"""
        for kind in (1, 0x3A):
            for spec in xingheng_fields(kind):
                for value in (True, None, "1", float("nan"), float("inf"), 10 ** 5000, spec.minimum - 1, spec.maximum + 1):
                    with self.subTest(kind=kind, field=spec.name, value=value):
                        status = replace(self.status, xingheng_message_id=kind, **{"xingheng_" + spec.name: value})
                        self.assertFalse(self.handler.generate_frame(status)[0])
        for field, value in (("xingheng_soc_percent", 50.1), ("xingheng_voltage_v", 80.45),
                             ("xingheng_current_a", 0.01), ("xingheng_cycle_count", 2.0),
                             ("xingheng_version", 0x1F), ("xingheng_message_id", True),
                             ("xingheng_message_id", 0x3B)):
            self.assertFalse(self.handler.generate_frame(replace(self.status, **{field: value}))[0])

    def test_minimum_cannot_exceed_maximum(self):
        """拒绝颠倒的最低/最高温度或单体电压，不悄悄交换数值。"""
        for values in ({"xingheng_min_temperature_c": 25}, {"xingheng_min_cell_mv": 4000}):
            self.assertFalse(self.handler.generate_frame(replace(self.status, **values))[0])

    def test_preview_is_stable_and_opaque_fields_stay_manual(self):
        """预览不消耗key或重算密文，返回值是独立快照。"""
        first = self.handler.generate_frame_for_preview(self.status)
        self.assertEqual(bytes(first[1]), REFERENCE)
        first[1][28] = 0
        self.assertEqual(bytes(self.frame()), REFERENCE)
        changed = self.frame(replace(self.status, xingheng_soc_percent=50,
                                     xingheng_bms_status_raw=0xA5, xingheng_key_raw=2,
                                     xingheng_result0_raw=0x11, xingheng_result1_raw=0x22))
        self.assertEqual((changed[3], changed[13], changed[27:30]), (100, 0xA5, [2, 0x11, 0x22]))

    def test_raw_test_keeps_malformed_header_length_and_checksum(self):
        """原始测试允许故意错误的字段，但不允许非法字节或未知帧长。"""
        raw = [0xFF] * 31
        self.assertEqual(normalize_xingheng_test_frame(raw, 0x3A), raw)
        for invalid in ([0] * 30, [0] * 32, [0] * 33, [0] * 19, [True] * 31, [256] * 31):
            with self.assertRaises(ValueError):
                normalize_xingheng_test_frame(invalid)
        with self.assertRaises(ValueError):
            normalize_xingheng_test_frame(raw, 1)


class XinghengWindowTests(unittest.TestCase):
    """专属页面、配置、原始帧和后台动态循环的离屏回归。"""

    def setUp(self):
        """隔离端口扫描、用户配置和恢复提示，不连接真实设备。"""
        with patch.object(SerialPortDetector, "start_detection"), patch.object(SerialManager, "scan_ports", return_value=[]), patch.object(MainWindow, "refresh_recovery_notice"):
            self.window = MainWindow(settings_store=SettingsStore())
        self.window.history_update_timer.stop()
        self.addCleanup(self.window.close)
        self.manager = self.window.serial_manager
        self.window.protocol_combo.setCurrentText(PROTOCOL_XINGHENG_BMS)

    def select_kind(self, kind):
        """按真实控件切换报文，验证重建后仍保留数据自定义状态。"""
        self.window.custom_radio.click()
        combo = self.window.xingheng_message_combo
        combo.setCurrentIndex(combo.findData(kind))
        _APP.processEvents()

    def install_fake_port(self):
        """记录实际提交给串口write的字节，不把生成成功等同于已写入。"""
        self.port = Mock()
        self.port.port = "COM_TEST"
        self.port.baudrate = 9600
        self.port.out_waiting = 0
        self.port.write.side_effect = len
        self.manager.serial_port = self.port
        self.manager.is_connected = True

    def tick(self):
        """仅投递一个周期，等待后台完成并确认，避免自动定时器干扰断言。"""
        self.manager.send_timer.timeout.emit()
        blocker = QSignalBlocker(self.manager.send_timer)
        deadline = time.monotonic() + 1.5
        while self.manager._worker is not None and self.manager._worker.busy:
            self.assertLess(time.monotonic(), deadline)
            QTest.qWait(1)
        del blocker

    def test_default_preview_search_and_parameter_readonly(self):
        """默认3A参考帧及1000ms，未新增全局控件或解密状态伪选项。"""
        window = self.window
        self.assertEqual(window.frame_preview.hex_text.text(), REFERENCE.hex(" ").upper())
        self.assertEqual((window.status_tabs.count(), window.interval_spin.value()), (3, 1000))
        self.assertFalse(window.xingheng_controls["soc_percent"].isEnabled())
        self.assertIn("未实现加密", window.xingheng_protocol_note.text())
        self.assertTrue(any("xingheng" in key for key in protocol_search_keys(PROTOCOL_XINGHENG_BMS)))
        window.custom_radio.click()
        self.assertTrue(window.xingheng_controls["soc_percent"].isEnabled())

    def test_message_switch_rebuilds_length_descriptions_and_keeps_values(self):
        """公有/实时预览分别20/31字节，半百分比不会丢失，隐藏的原始字段保留。"""
        window = self.window
        window.custom_radio.click()
        window.xingheng_controls["soc_percent"].setValue(50.5)
        window.xingheng_controls["result0_raw"].setValue(0x12)
        self.select_kind(1)
        self.assertEqual(window.status_tabs.count(), 2)
        self.assertEqual(window.frame_preview.table.rowCount(), 20)
        self.assertEqual(window._make_default_custom_frame()[9], 101)
        self.assertEqual(len(window.protocol_handler.get_byte_descriptions(PROTOCOL_XINGHENG_BMS, window.current_status)), 20)
        self.select_kind(0x3A)
        self.assertEqual(window._make_default_custom_frame()[28], 0x12)
        self.assertEqual(window._make_default_custom_frame()[3], 101)

    def test_presets_keep_selected_message_and_match_readback(self):
        """切换场景不将公有格式强制退回3A，UI状态与实际编码一致。"""
        for kind in (1, 0x3A):
            self.select_kind(kind)
            for scenario in (0, 1, 2):
                self.window.scenario_group.button(scenario).click()
                self.assertEqual(self.window.current_status.xingheng_message_id, kind)
                self.assertEqual(self.window.get_current_status_from_ui(), self.window.current_status)
                self.assertEqual(self.window.frame_preview.hex_text.text(), bytes(self.window._get_current_cyclic_frame()).hex(" ").upper())

    def test_original_editor_uses_latest_values_and_preserves_raw_checksum(self):
        """两种长度都能用现有原始编辑器，回放不会强制改写用户的错误校验。"""
        for kind, length, soc_index in ((0x3A, 31, 3), (1, 20, 9)):
            self.select_kind(kind)
            self.window.xingheng_controls["soc_percent"].setValue(50.5)
            self.window.frame_custom_radio.click()
            self.assertEqual((len(self.window.custom_frame_data), self.window.custom_frame_data[soc_index]), (length, 101))
            dialog = FrameConfigDialog(initial_frame=self.window.custom_frame_data, checksum_mode="sum")
            self.addCleanup(dialog.close)
            self.assertEqual(len(dialog.byte_editors), length)
            raw = [255] * length
            self.window.on_custom_frame_changed(raw)
            self.assertEqual(self.window._get_current_cyclic_frame(), raw)
            self.assertEqual(self.window.frame_preview.hex_text.text(), bytes(raw).hex(" ").upper())

    def test_configuration_round_trip_and_both_packet_types_survive(self):
        """保存两格式包组并恢复公有参数，不自动连接或发送，旧配置仍可读取。"""
        window = self.window
        realtime = list(REFERENCE)
        self.select_kind(1)
        window.xingheng_controls["soc_percent"].setValue(50.5)
        public = window._make_default_custom_frame()
        window.packet_sequence_frames[PROTOCOL_XINGHENG_BMS] = [realtime, public]
        configuration = window.capture_configuration()
        with TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            write_config(path, configuration)
            loaded = read_config(path)
        window.protocol_combo.setCurrentText(PROTOCOL_RUILUN)
        window.apply_configuration(loaded)
        self.assertEqual(window.capture_configuration(), loaded)
        self.assertEqual(window._get_packet_sequence_frames(), [public])
        self.select_kind(0x3A)
        self.assertEqual(window._get_packet_sequence_frames(), [realtime])
        window.store_xingheng_packet_frames([realtime, realtime])
        self.select_kind(1)
        self.assertEqual(window._get_packet_sequence_frames(), [public])
        self.assertFalse(window.serial_manager.is_connected)
        self.assertFalse(window.serial_manager.is_cyclic_sending())
        legacy = window.capture_configuration()
        legacy["protocol"] = PROTOCOL_RUILUN
        legacy["status"] = {key: value for key, value in asdict(StatusBits()).items() if not key.startswith("xingheng_")}
        legacy["packet_sequences"] = {}
        self.assertEqual(validate_config(legacy)["protocol"], PROTOCOL_RUILUN)

    def test_invalid_configuration_lengths_and_values_are_rejected(self):
        """合法原始坏校验可保存，未确认的32/33字节不能绕过配置校验。"""
        self.window.frame_custom_radio.click()
        self.window.on_custom_frame_changed([255] * 31)
        configuration = self.window.capture_configuration()
        self.assertEqual(configuration["custom_frame"], [255] * 31)
        for length in (19, 20, 30, 32, 33):
            with self.assertRaises(ValueError):
                validate_config({**configuration, "custom_frame": [0] * length})
        for length in (19, 30, 32, 33):
            with self.assertRaises(ValueError):
                validate_config({**configuration, "packet_sequences": {PROTOCOL_XINGHENG_BMS: [[0] * length]}})

    def test_dialog_routes_use_current_length_without_overwriting_other_type(self):
        """实际主窗口对话框入口按当前长度编辑，接受或取消均不丢另一格式包组。"""
        realtime = list(REFERENCE)
        self.select_kind(1)
        public = self.window._make_default_custom_frame()
        self.window.packet_sequence_frames[PROTOCOL_XINGHENG_BMS] = [realtime, public]
        dialog = Mock()
        dialog.exec_.return_value = QDialog.Accepted
        dialog.get_frames.return_value = [public, public]
        with patch("gui.main_window.PacketSequenceDialog", return_value=dialog) as create:
            self.window.open_packet_sequence_config()
        self.assertEqual(create.call_args.kwargs["initial_frames"], [public])
        self.assertEqual(len(create.call_args.kwargs["byte_descriptions"]), 20)
        self.assertEqual(self.window.packet_sequence_frames[PROTOCOL_XINGHENG_BMS], [realtime, public, public])
        dialog.exec_.return_value = QDialog.Rejected
        with patch("gui.main_window.PacketSequenceDialog", return_value=dialog):
            self.window.open_packet_sequence_config()
        self.assertEqual(self.window.packet_sequence_frames[PROTOCOL_XINGHENG_BMS], [realtime, public, public])
        self.window.frame_custom_radio.click()
        with patch("gui.main_window.FrameConfigDialog", return_value=dialog) as create:
            self.window.open_frame_config()
        self.assertEqual(len(create.call_args.args[1]), 20)
        self.assertEqual(len(create.call_args.kwargs["byte_descriptions"]), 20)

    def test_single_frame_writes_exact_customer_capture(self):
        """单次发送通过原UART路径，不能多加XOR、协议外壳或保护字节。"""
        self.install_fake_port()
        self.window.send_single_frame()
        deadline = time.monotonic() + 1.5
        while self.manager._worker.busy:
            self.assertLess(time.monotonic(), deadline)
            QTest.qWait(1)
        self.port.write.assert_called_once_with(REFERENCE)

    def test_live_soc_edit_changes_next_write_without_restart_or_encryption(self):
        """循环中动态改变SOC，下一真实写入帧更新SOC和累加和，原始保护字段不变。"""
        self.install_fake_port()
        window = self.window
        window.custom_radio.click()
        window.interval_spin.setValue(10)
        with patch.object(self.manager.send_timer, "start", wraps=self.manager.send_timer.start) as start:
            window.toggle_cyclic_send()
            self.tick()
            first = bytes(self.port.write.call_args.args[0])
            window.xingheng_controls["soc_percent"].setValue(50.5)
            self.tick()
        second = bytes(self.port.write.call_args.args[0])
        self.assertEqual(first, REFERENCE)
        self.assertEqual(second[3], 101)
        self.assertEqual((second[13], second[27:30]), (first[13], first[27:30]))
        self.assertEqual(second[-1], sum(second[:-1]) % 256)
        self.assertTrue(self.manager.is_cyclic_sending())
        start.assert_called_once_with(10)

    def test_message_switch_stops_old_cycle_before_length_changes(self):
        """切换格式只停止旧循环，不自动开始新长度发送；切回旧协议仍可预览。"""
        self.install_fake_port()
        self.window.custom_radio.click()
        self.window.interval_spin.setValue(5000)
        self.window.toggle_cyclic_send()
        self.tick()
        with patch.object(self.manager, "stop_cyclic_send", wraps=self.manager.stop_cyclic_send) as stop:
            self.select_kind(1)
        stop.assert_called_once_with()
        self.assertFalse(self.manager.is_cyclic_sending())
        self.assertIsNone(self.window.active_send_mode)
        self.assertEqual(self.port.write.call_count, 1)
        self.assertEqual(self.window.frame_preview.table.rowCount(), 20)
        self.window.protocol_combo.setCurrentText(PROTOCOL_RUILUN)
        self.assertEqual(self.window.frame_preview.table.rowCount(), 12)

    def test_raw_and_packet_send_keep_selected_length(self):
        """原始单帧和当前类型包组复用同一后台写入，另一类型不会混入循环。"""
        self.install_fake_port()
        self.select_kind(1)
        public = self.window._make_default_custom_frame()
        self.window.packet_sequence_frames[PROTOCOL_XINGHENG_BMS] = [list(REFERENCE), public]
        self.window.interval_spin.setValue(5000)
        self.window.toggle_packet_sequence_send()
        self.tick()
        self.port.write.assert_called_once_with(bytes(public))
        self.assertEqual(self.window.active_send_mode, "sequence")
        self.window.toggle_packet_sequence_send()
        self.window.frame_custom_radio.click()
        raw = [255] * 20
        self.window.on_custom_frame_changed(raw)
        self.window.toggle_cyclic_send()
        self.tick()
        self.port.write.assert_called_with(bytes(raw))


if __name__ == "__main__":
    unittest.main()
