#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""锂神 BMS V1.1.1 编码和界面回归；仅使用假串口，不访问真实硬件。"""

import os
import time
import unittest
from dataclasses import fields
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QPoint, QRect
from PyQt5.QtGui import QFont, QFontDatabase
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication, QScrollArea

from app_settings import SettingsStore, read_config, validate_config, write_config
from gui.frame_config_dialog import FrameConfigDialog
from gui.main_window import MainWindow
from gui.packet_sequence_dialog import build_packet_sequence_payload, load_packet_sequence_payload
from protocol.definitions import PROTOCOL_DEFINITIONS
from protocol.protocol_handler import (
    PROTOCOL_BATTERY_SINGLE_WIRE,
    PROTOCOL_LISHEN_BMS,
    PresetScenarios,
    ProtocolHandler,
    StatusBits,
)
from serial_comm.serial_manager import SerialManager, SerialPortDetector

_APP = QApplication.instance() or QApplication([])


class LishenEncodingTests(unittest.TestCase):
    """对照规格书第 2 页，独立计算六字节帧及补码边界。"""

    def setUp(self):
        """每项测试使用全新处理器，避免其他协议的流水号干扰。"""
        self.handler = ProtocolHandler()

    def test_registry_and_appended_fields(self):
        """公开名称、UART 契约、测试周期和旧模型位置参数保持明确。"""
        self.assertEqual(PROTOCOL_LISHEN_BMS, "锂神单线BMS")
        definition = PROTOCOL_DEFINITIONS[PROTOCOL_LISHEN_BMS]
        self.assertEqual((definition.frame_length, definition.checksum_mode, definition.send_mode), (6, "sum", "uart"))
        self.assertEqual((definition.min_send_interval_ms, definition.max_send_interval_ms, definition.default_send_interval_ms), (10, 5000, 1000))
        self.assertTrue(definition.reset_send_interval_on_switch)
        self.assertEqual([field.name for field in fields(StatusBits)][-2:], ["lishen_total_voltage_v", "lishen_temperature_c"])

    def test_document_table_negative_temperature_example(self):
        """规格书表格原值：00 32 30 F6 00 58，-10℃ 必须编码为 F6。"""
        status = StatusBits(protocol_name=PROTOCOL_LISHEN_BMS, soc_percent=50,
                            lishen_total_voltage_v=48, lishen_temperature_c=-10)
        self.assertEqual(self.handler.generate_frame(status), (True, [0x00, 0x32, 0x30, 0xF6, 0x00, 0x58], ""))

    def test_document_waveform_example(self):
        """规格书波形示例与下方含电压/温度的表格是两组不同数据。"""
        status = StatusBits(protocol_name=PROTOCOL_LISHEN_BMS, soc_percent=50,
                            lishen_total_voltage_v=0, lishen_temperature_c=0)
        self.assertEqual(self.handler.generate_frame(status), (True, [0, 50, 0, 0, 0, 50], ""))

    def test_default_frame_and_sum_overflow(self):
        """默认数据合法，累加超出一个字节时只保留低八位。"""
        self.assertEqual(self.handler.generate_frame(PresetScenarios.lishen_bms_normal_running()), (True, [0, 50, 48, 25, 0, 123], ""))
        status = StatusBits(protocol_name=PROTOCOL_LISHEN_BMS, soc_percent=100,
                            lishen_total_voltage_v=255, lishen_temperature_c=-1)
        self.assertEqual(self.handler.generate_frame(status), (True, [0, 100, 255, 255, 0, 98], ""))

    def test_every_signed_temperature_is_twos_complement(self):
        """枚举八位有符号全量程，负数不用其他 BMS 的符号原码。"""
        for temperature in range(-128, 128):
            with self.subTest(temperature=temperature):
                status = StatusBits(protocol_name=PROTOCOL_LISHEN_BMS,
                                    lishen_temperature_c=temperature)
                success, frame, error = self.handler.generate_frame(status)
                self.assertTrue(success, error)
                expected = int.from_bytes(temperature.to_bytes(1, "big", signed=True), "big")
                self.assertEqual(frame[3], expected)
                self.assertEqual(frame[5], (50 + 48 + expected) % 256)

    def test_every_voltage_and_soc_keeps_reserved_bytes_zero(self):
        """分别枚举 SOC 和总压量程，独立验证保留字节与校验覆盖范围。"""
        for field, values, index in (("soc_percent", range(101), 1),
                                     ("lishen_total_voltage_v", range(256), 2)):
            for value in values:
                with self.subTest(field=field, value=value):
                    status = StatusBits(protocol_name=PROTOCOL_LISHEN_BMS)
                    setattr(status, field, value)
                    success, frame, error = self.handler.generate_frame(status)
                    self.assertTrue(success, error)
                    self.assertEqual(len(frame), 6)
                    self.assertEqual((frame[0], frame[4]), (0, 0))
                    self.assertEqual(frame[index], value)
                    self.assertEqual(frame[5], sum(frame[:5]) % 256)

    def test_invalid_types_and_ranges_are_rejected_without_clipping(self):
        """拒绝布尔、小数、非数值和越界值，不能悄悄取整或截断。"""
        for field, extra_values in (
            ("soc_percent", (-1, 101)),
            ("lishen_total_voltage_v", (-1, 256)),
            ("lishen_temperature_c", (-129, 128)),
        ):
            for value in (True, False, None, "25", 25.0, 1.5, float("nan"), float("inf"), *extra_values):
                with self.subTest(field=field, value=value):
                    status = StatusBits(protocol_name=PROTOCOL_LISHEN_BMS)
                    setattr(status, field, value)
                    valid, error = self.handler.validate_status_bits(status)
                    self.assertFalse(valid)
                    self.assertTrue(error)
                    for generate in (self.handler.generate_frame, self.handler.generate_frame_for_preview):
                        success, frame, error = generate(status)
                        self.assertFalse(success)
                        self.assertEqual(frame, [])
                        self.assertTrue(error)

    def test_preview_and_send_are_stable_independent_snapshots(self):
        """该协议无流水号；预览和发送均稳定，调用方改写结果不污染下一帧。"""
        status = PresetScenarios.lishen_bms_normal_running()
        first = self.handler.generate_frame_for_preview(status)
        self.assertEqual(first, self.handler.generate_frame(status))
        first[1][0] = 255
        self.assertEqual(self.handler.generate_frame_for_preview(status)[1], [0, 50, 48, 25, 0, 123])

    def test_descriptions_and_presets_are_protocol_specific(self):
        """三个预设只有数据，无虚构的回收/故障位，说明与帧长一致。"""
        descriptions = self.handler.get_byte_descriptions(PROTOCOL_LISHEN_BMS)
        self.assertEqual(len(descriptions), 6)
        self.assertIn("补码", descriptions[3])
        self.assertIn("0x00", descriptions[4])
        descriptions[0] = "modified"
        self.assertNotEqual(self.handler.get_byte_descriptions(PROTOCOL_LISHEN_BMS)[0], "modified")
        for factory in (PresetScenarios.lishen_bms_normal_running,
                        PresetScenarios.lishen_bms_energy_recovery,
                        PresetScenarios.lishen_bms_fault_scenario):
            with self.subTest(factory=factory.__name__):
                state = factory()
                self.assertEqual(state.protocol_name, PROTOCOL_LISHEN_BMS)
                success, frame, error = self.handler.generate_frame(state)
                self.assertTrue(success, error)
                self.assertEqual((frame[0], frame[4]), (0, 0))
                self.assertFalse(state.soc_fault)

    def test_old_six_byte_battery_protocol_keeps_test_defaults(self):
        """同为六字节不代表可合并；旧协议的三个 01 测试字节完全不变。"""
        old_state = StatusBits(protocol_name=PROTOCOL_BATTERY_SINGLE_WIRE, soc_percent=80)
        self.assertEqual(self.handler.generate_frame(old_state), (True, [0, 80, 1, 1, 1, 83], ""))
        new_state = StatusBits(protocol_name=PROTOCOL_LISHEN_BMS, soc_percent=80)
        self.assertEqual(self.handler.generate_frame(new_state), (True, [0, 80, 48, 25, 0, 153], ""))


class LishenWindowTests(unittest.TestCase):
    """验证主窗口、配置存取、六字节编辑和真实 Qt 循环下的动态数据。"""

    def setUp(self):
        """隔离本机配置和串口发现，不扫描真实设备、不写客户目录。"""
        detector_patch = patch.object(SerialPortDetector, "start_detection", autospec=True)
        detector_patch.start()
        self.addCleanup(detector_patch.stop)
        scan_patch = patch.object(SerialManager, "scan_ports", return_value=[])
        scan_patch.start()
        self.addCleanup(scan_patch.stop)
        self.window = MainWindow(settings_store=SettingsStore())
        self.window.history_update_timer.stop()
        self.addCleanup(self.window.port_detector.stop_detection)
        self.addCleanup(self.window.history_update_timer.stop)
        self.addCleanup(self.window.close)
        self.window.protocol_combo.setCurrentText(PROTOCOL_LISHEN_BMS)

    def test_protocol_selection_and_three_data_controls(self):
        """协议列表实际接通专属页面，保留位没有可编辑的伪控件。"""
        window = self.window
        self.assertEqual(window.current_protocol, PROTOCOL_LISHEN_BMS)
        self.assertEqual(window.status_tabs.count(), 1)
        self.assertEqual(window.status_tabs.tabText(0), "电池数据")
        self.assertEqual((window.lishen_soc_spin.minimum(), window.lishen_soc_spin.maximum()), (0, 100))
        self.assertEqual((window.lishen_total_voltage_spin.minimum(), window.lishen_total_voltage_spin.maximum()), (0, 255))
        self.assertEqual((window.lishen_temperature_spin.minimum(), window.lishen_temperature_spin.maximum()), (-128, 127))
        self.assertIn("1000～2000ms", window.lishen_protocol_note.text())
        self.assertIn("00 32 30 19 00 7B", window.current_frame_text.toPlainText())

    def test_default_window_shows_all_three_inputs_without_scrolling(self):
        """按 Windows 实际字体检查默认窗口，避免无字体离屏后端的虚假尺寸。"""
        font_directory = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
        font_path = next((font_directory / name for name in ("msyh.ttc", "segoeui.ttf")
                          if (font_directory / name).is_file()), None)
        if font_path is None:
            self.skipTest("像素布局检查需要 Windows 系统字体；编码和数据绑定测试不受影响")
        font_id = QFontDatabase.addApplicationFont(str(font_path))
        self.assertGreaterEqual(font_id, 0)
        original_font = _APP.font()
        window = None
        try:
            # 字体必须先于控件创建，离屏后端才会使用真实的中文布局度量。
            _APP.setFont(QFont(QFontDatabase.applicationFontFamilies(font_id)[0], 9))
            window = MainWindow(settings_store=SettingsStore())
            window.history_update_timer.stop()
            window.protocol_combo.setCurrentText(PROTOCOL_LISHEN_BMS)
            window.show()
            _APP.processEvents()
            # 界面改为每个参数页独立滚动，继续校验三项实际输入完整可见。
            scroll = window.status_tabs.widget(window.status_tabs.currentIndex())
            self.assertIsInstance(scroll, QScrollArea)
            viewport = scroll.viewport()
            for control in (window.lishen_soc_spin, window.lishen_total_voltage_spin, window.lishen_temperature_spin):
                with self.subTest(control=control):
                    position = control.mapTo(viewport, QPoint(0, 0))
                    self.assertTrue(viewport.rect().contains(QRect(position, control.size())))
        finally:
            if window is not None:
                window.close()
            _APP.setFont(original_font)
            QFontDatabase.removeApplicationFont(font_id)

    def test_new_default_and_user_selected_test_interval_range(self):
        """新协议默认一秒，但按用户要求保留 10～5000ms；旧协议仍默认 500ms。"""
        window = self.window
        self.assertEqual((window.interval_spin.minimum(), window.interval_spin.maximum(), window.interval_spin.value()), (10, 5000, 1000))
        for interval in (10, 5000):
            window.interval_spin.setValue(interval)
            self.assertEqual(window.interval_spin.value(), interval)
        window.protocol_combo.setCurrentText(PROTOCOL_BATTERY_SINGLE_WIRE)
        self.assertEqual(window.interval_spin.value(), 500)
        window.protocol_combo.setCurrentText(PROTOCOL_LISHEN_BMS)
        self.assertEqual(window.interval_spin.value(), 1000)

    def test_custom_data_updates_preview_with_document_example(self):
        """三项数据都参与当前帧预览，负温度按文档生成 F6。"""
        self.window.custom_radio.click()
        self.window.lishen_temperature_spin.setValue(-10)
        status = self.window.get_current_status_from_ui()
        self.assertEqual((status.soc_percent, status.lishen_total_voltage_v, status.lishen_temperature_c), (50, 48, -10))
        self.assertIn("00 32 30 F6 00 58", self.window.current_frame_text.toPlainText())

    def test_every_preset_updates_widgets_and_frame(self):
        """预设、UI 读回与协议层编码一致，避免切换场景遗留旧数据。"""
        window = self.window
        for scenario_id in (0, 1, 2):
            window.scenario_group.button(scenario_id).click()
            state = window.get_current_status_from_ui()
            self.assertEqual(state, window.current_status)
            success, frame, error = window.protocol_handler.generate_frame(state)
            self.assertTrue(success, error)
            self.assertIn(" ".join(f"{value:02X}" for value in frame), window.current_frame_text.toPlainText())

    def test_configuration_round_trip_including_negative_temperature_and_packet(self):
        """配置导入导出与新协议包组可复用，不自动连接或启动发送。"""
        window = self.window
        window.custom_radio.click()
        window.lishen_soc_spin.setValue(88)
        window.lishen_total_voltage_spin.setValue(54)
        window.lishen_temperature_spin.setValue(-20)
        window.interval_spin.setValue(10)
        expected_frame = [0, 88, 54, 236, 0, 122]
        window.packet_sequence_frames[PROTOCOL_LISHEN_BMS] = [expected_frame]
        configuration = window.capture_configuration()
        with TemporaryDirectory() as temporary:
            path = Path(temporary) / "lishen.json"
            write_config(path, configuration)
            loaded = read_config(path)
        window.protocol_combo.setCurrentText(PROTOCOL_BATTERY_SINGLE_WIRE)
        window.apply_configuration(loaded)
        self.assertEqual(window.capture_configuration(), configuration)
        self.assertEqual(window._get_current_cyclic_frame(), expected_frame)
        self.assertFalse(window.serial_manager.is_connected)
        self.assertFalse(window.serial_manager.is_cyclic_sending())
        self.assertIsNone(window.serial_manager.serial_port)
        invalid = dict(configuration, interval_ms=9)
        with self.assertRaises(ValueError):
            validate_config(invalid)

    def test_custom_frame_editor_and_packet_use_six_bytes_and_sum(self):
        """全部自定义和包组均继承六字节元数据，不退回十二字节/XOR。"""
        window = self.window
        window.frame_custom_radio.click()
        self.assertEqual(window.custom_frame_data, [0, 50, 48, 25, 0, 123])
        editor = FrameConfigDialog(initial_frame=window.custom_frame_data,
                                   byte_descriptions=window.protocol_handler.get_byte_descriptions(PROTOCOL_LISHEN_BMS),
                                   checksum_mode=window.protocol_handler.get_protocol_checksum_mode(PROTOCOL_LISHEN_BMS))
        self.addCleanup(editor.close)
        self.assertEqual(len(editor.byte_editors), 6)
        self.assertEqual(editor.calculate_checksum([0, 50, 48, 246, 0]), 88)
        payload = build_packet_sequence_payload([window.custom_frame_data], 6, checksum_mode="sum")
        self.assertEqual(load_packet_sequence_payload(payload, 6), [window.custom_frame_data])
        with self.assertRaises(ValueError):
            load_packet_sequence_payload(payload, 12)

    def test_real_qt_cycle_uses_latest_three_values_with_fake_port(self):
        """Qt 定时器和后台线程实际运行，数据修改无需停发即写入下一份快照。"""
        window = self.window
        port = SimpleNamespace(port="FAKE-LISHEN", baudrate=9600, is_open=True,
                               out_waiting=0, break_condition=False,
                               write=Mock(side_effect=lambda payload: len(payload)), close=Mock())
        window.serial_manager.serial_port = port
        window.serial_manager.is_connected = True
        window.custom_radio.click()
        window.interval_spin.setValue(10)
        window.toggle_cyclic_send()
        self.assertTrue(window.serial_manager.is_cyclic_sending())
        self.wait_until(lambda: bool(port.write.call_args_list))
        window.lishen_soc_spin.setValue(70)
        window.lishen_total_voltage_spin.setValue(60)
        window.lishen_temperature_spin.setValue(-10)
        expected = bytes([0, 70, 60, 246, 0, 120])
        self.wait_until(lambda: any(call.args[0] == expected for call in port.write.call_args_list))
        self.assertTrue(window.serial_manager.is_cyclic_sending())
        window.serial_manager.stop_cyclic_send()

    def test_switching_protocol_stops_old_cycle_and_rebuilds_page(self):
        """切换前停止旧轮次，旧电池协议页与锂神页互不串用字段。"""
        window = self.window
        window.serial_manager.send_timer.start(500)
        window.protocol_combo.setCurrentText(PROTOCOL_BATTERY_SINGLE_WIRE)
        self.assertFalse(window.serial_manager.is_cyclic_sending())
        self.assertTrue(hasattr(window, "battery_single_wire_soc_spin"))
        window.serial_manager.send_timer.start(500)
        window.protocol_combo.setCurrentText(PROTOCOL_LISHEN_BMS)
        self.assertFalse(window.serial_manager.is_cyclic_sending())
        self.assertEqual(window.get_current_status_from_ui(), PresetScenarios.lishen_bms_normal_running())

    def wait_until(self, predicate, timeout_ms=1500):
        """保持 Qt 事件循环运行，有限等待假串口完成，避免测试线程残留。"""
        deadline = time.monotonic() + timeout_ms / 1000.0
        while not predicate() and time.monotonic() < deadline:
            QTest.qWait(5)
        self.assertTrue(predicate(), "假串口未在限定时间内完成发送")


if __name__ == "__main__":
    unittest.main()
