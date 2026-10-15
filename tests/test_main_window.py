import os
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication

from gui.main_window import MainWindow
from protocol.protocol_handler import (
    PROTOCOL_BATTERY_SINGLE_WIRE,
    PROTOCOL_CHANGZHOU_XINSIWEI,
    PROTOCOL_HANGZHOU_ANXIAN,
    PROTOCOL_JINGXIAN,
    PROTOCOL_SHENZHOUXING,
    PROTOCOL_SXSY,
    PROTOCOL_XINCHI,
    PROTOCOL_XINRI,
    SUPPORTED_PROTOCOLS,
    StatusBits,
)
from serial_comm.serial_manager import SerialPortDetector


_APP = QApplication.instance() or QApplication([])


class MainWindowIntervalTests(unittest.TestCase):
    def setUp(self):
        detector_patch = patch.object(SerialPortDetector, "start_detection", autospec=True)
        detector_patch.start()
        self.addCleanup(detector_patch.stop)

        self.window = MainWindow()
        self.window.history_update_timer.stop()
        self.addCleanup(self.window.history_update_timer.stop)
        self.addCleanup(self.window.port_detector.stop_detection)
        self.addCleanup(self.window.close)

    def test_interval_spin_updates_running_packet_sequence(self):
        self.window.active_send_mode = "sequence"
        self.window.serial_manager.is_cyclic_sending = Mock(return_value=True)
        self.window.serial_manager.update_cyclic_send_interval = Mock(return_value=(True, ""))

        self.window.interval_spin.setValue(10)

        self.window.serial_manager.update_cyclic_send_interval.assert_called_once_with(10)

    def test_interval_spin_keeps_500_default_and_allows_10ms(self):
        self.assertEqual(self.window.interval_spin.minimum(), 10)
        self.assertEqual(self.window.interval_spin.maximum(), 5000)
        self.assertEqual(self.window.interval_spin.value(), 500)

    def test_xinchi_protocol_resets_interval_to_500ms(self):
        self.window.current_protocol = PROTOCOL_BATTERY_SINGLE_WIRE
        self.window.apply_send_interval_constraints()
        self.assertEqual(self.window.interval_spin.value(), 500)

        self.window.current_protocol = PROTOCOL_XINCHI
        self.window.apply_send_interval_constraints()

        self.assertEqual(self.window.interval_spin.minimum(), 10)
        self.assertEqual(self.window.interval_spin.maximum(), 5000)
        self.assertEqual(self.window.interval_spin.value(), 500)

    def test_interval_spin_ignores_idle_sender(self):
        self.window.serial_manager.is_cyclic_sending = Mock(return_value=False)
        self.window.serial_manager.update_cyclic_send_interval = Mock(return_value=(True, ""))

        self.window.interval_spin.setValue(1500)

        self.window.serial_manager.update_cyclic_send_interval.assert_not_called()


class MainWindowShenzhouxingTests(unittest.TestCase):
    def setUp(self):
        detector_patch = patch.object(SerialPortDetector, "start_detection", autospec=True)
        detector_patch.start()
        self.addCleanup(detector_patch.stop)

        self.window = MainWindow()
        self.window.history_update_timer.stop()
        self.addCleanup(self.window.history_update_timer.stop)
        self.addCleanup(self.window.port_detector.stop_detection)
        self.addCleanup(self.window.close)

    def test_shenzhouxing_status1_labels_match_protocol_doc(self):
        self.window.on_protocol_changed(PROTOCOL_SHENZHOUXING)

        self.assertEqual(self.window.distance_mode_cb.text(), "侧撑指示 (D3)")
        self.assertEqual(self.window.speed_alarm_cb.text(), "HDC(陡坡缓降) (D2)")
        self.assertEqual(self.window.p_gear_protect_cb.text(), "P挡 (D1)")
        self.assertEqual(self.window.tcs_status_cb.text(), "HHC(坡道驻车) (D0)")

    def test_shenzhouxing_bluetooth_round_trip_uses_d7_checkbox(self):
        self.window.on_protocol_changed(PROTOCOL_SHENZHOUXING)
        status = StatusBits(protocol_name=PROTOCOL_SHENZHOUXING)
        status.shenzhouxing_bluetooth = True

        self.window.current_status = status
        self.window.update_ruilun_ui_from_status()
        self.assertTrue(self.window.current_70_flag_cb.isChecked())

        derived = self.window.get_ruilun_status_from_ui()
        self.assertTrue(derived.shenzhouxing_bluetooth)
        self.assertFalse(derived.current_70_flag)

    def test_shenzhouxing_status4_special_bits_round_trip_to_frame(self):
        self.window.on_protocol_changed(PROTOCOL_SHENZHOUXING)
        status = StatusBits(protocol_name=PROTOCOL_SHENZHOUXING)
        status.shenzhouxing_bluetooth = True
        status.shenzhouxing_time_display = True
        status.shenzhouxing_4g_signal_indicator = True
        status.shenzhouxing_position_indicator = True
        status.stall_protect = True
        status.reverse = True
        status.brake = True
        status.speed_limit = True

        self.window.current_status = status
        self.window.update_ruilun_ui_from_status()
        self.assertTrue(self.window.current_70_flag_cb.isChecked())
        self.assertTrue(self.window.one_key_enable_cb.isChecked())
        self.assertTrue(self.window.ekk_enable_cb.isChecked())
        self.assertTrue(self.window.over_current_cb.isChecked())
        self.assertTrue(self.window.stall_protect_cb.isChecked())
        self.assertTrue(self.window.reverse_cb.isChecked())
        self.assertTrue(self.window.electronic_brake_cb.isChecked())
        self.assertTrue(self.window.speed_limit_cb.isChecked())

        derived = self.window.get_ruilun_status_from_ui()
        self.assertTrue(derived.shenzhouxing_bluetooth)
        self.assertTrue(derived.shenzhouxing_time_display)
        self.assertTrue(derived.shenzhouxing_4g_signal_indicator)
        self.assertTrue(derived.shenzhouxing_position_indicator)
        self.assertTrue(derived.stall_protect)
        self.assertTrue(derived.reverse)
        self.assertTrue(derived.brake)
        self.assertTrue(derived.speed_limit)
        self.assertFalse(derived.electronic_brake)

        success, frame, error = self.window.generate_protocol_frame_for_preview(derived)
        self.assertTrue(success, error)
        self.assertEqual(frame[5], 0xFF)


class MainWindowSxsyTests(unittest.TestCase):
    """验证 SXSY 专用字段和通用状态页的往返映射。"""

    def setUp(self):
        detector_patch = patch.object(
            SerialPortDetector,
            "start_detection",
            autospec=True,
        )
        detector_patch.start()
        self.addCleanup(detector_patch.stop)

        self.window = MainWindow()
        self.window.history_update_timer.stop()
        self.addCleanup(self.window.history_update_timer.stop)
        self.addCleanup(self.window.port_detector.stop_detection)
        self.addCleanup(self.window.close)
        self.window.on_protocol_changed(PROTOCOL_SXSY)

    def test_sxsy_ui_exposes_documented_p_gear_and_data_fields(self):
        self.assertEqual(
            self.window.distance_mode_cb.text(),
            "示例默认/未指定 (0x00)",
        )
        self.assertEqual(self.window.speed_alarm_cb.text(), "无P档 (0x0F)")
        self.assertEqual(self.window.p_gear_protect_cb.text(), "P档常亮 (0x0D)")
        self.assertEqual(self.window.tcs_status_cb.text(), "P档闪烁 (0x0E)")
        self.assertTrue(self.window.sxsy_p_gear_group.exclusive())
        self.assertEqual(self.window.sxsy_p_gear_group.checkedId(), 0x00)
        self.assertFalse(self.window.status2_d7_cb.isEnabled())
        self.assertEqual(self.window.gear_four_cb.text(), "三速功能 (D7)")
        self.assertFalse(self.window.current_70_flag_cb.isEnabled())
        self.assertEqual(self.window.current_spin.minimum(), -127)
        self.assertEqual(self.window.current_spin.maximum(), 127)
        self.assertIn("电压比例", self.window.status8_label.text())
        self.assertEqual(self.window.sxsy_soc_spin.minimum(), 0)
        self.assertEqual(self.window.sxsy_soc_spin.maximum(), 100)
        self.assertFalse(hasattr(self.window, "voltage_group"))

    def test_sxsy_ui_round_trip_matches_protocol_bytes(self):
        self.window.sxsy_p_gear_group.button(0x0E).setChecked(True)
        self.window.gear_four_cb.setChecked(True)
        self.window.hall_fault_cb.setChecked(True)
        self.window.motor_running_cb.setChecked(True)
        self.window.speed_mode_spin.setValue(3)
        self.window.current_spin.setValue(-5)
        self.window.hall_count_spin.setValue(0x1234)
        self.window.soc_spin.setValue(80)
        self.window.sxsy_soc_spin.setValue(70)

        status = self.window.get_current_status_from_ui()
        self.assertEqual(status.protocol_name, PROTOCOL_SXSY)
        self.assertEqual(status.sxsy_p_gear_state, 0x0E)
        self.assertTrue(status.sxsy_three_speed)
        self.assertEqual(status.voltage_percentage, 80)
        self.assertEqual(status.soc_percent, 70)

        self.window.protocol_handler.reset_sxsy_sequence(1)
        success, frame, error = self.window.generate_protocol_frame_for_preview(
            status
        )

        self.assertTrue(success, error)
        self.assertEqual(frame[0:3], [0x30, 0x01, 0x0E])
        self.assertEqual(frame[6], 0x85)
        self.assertEqual(frame[7:11], [0x76, 0x98, 0xB4, 0xAA])
        self.assertEqual(self.window.protocol_handler.get_current_sxsy_sequence(), 1)


class MainWindowProtocolSwitchTests(unittest.TestCase):
    """验证协议切换安全性及新日规格字段映射。"""

    def setUp(self):
        detector_patch = patch.object(SerialPortDetector, "start_detection", autospec=True)
        detector_patch.start()
        self.addCleanup(detector_patch.stop)

        self.window = MainWindow()
        self.window.history_update_timer.stop()
        self.addCleanup(self.window.history_update_timer.stop)
        self.addCleanup(self.window.port_detector.stop_detection)
        self.addCleanup(self.window.close)

    def test_protocol_switch_stops_existing_cyclic_send(self):
        self.window.serial_manager.is_cyclic_sending = Mock(return_value=True)
        self.window.serial_manager.stop_cyclic_send = Mock()
        self.window.active_send_mode = "single"

        self.window.on_protocol_changed(PROTOCOL_XINRI)

        self.window.serial_manager.stop_cyclic_send.assert_called_once_with()
        self.assertIsNone(self.window.active_send_mode)
        self.assertEqual(self.window.send_status.text(), "就绪")

    def test_protocol_combo_is_driven_by_supported_protocol_registry(self):
        combo_protocols = [
            self.window.protocol_combo.itemText(index)
            for index in range(self.window.protocol_combo.count())
        ]

        self.assertEqual(combo_protocols, SUPPORTED_PROTOCOLS)

    def test_xinri_ui_exposes_only_encoded_fields(self):
        self.window.on_protocol_changed(PROTOCOL_XINRI)

        self.assertEqual(self.window.distance_mode_cb.text(), "P档 (D3)")
        self.assertEqual(self.window.speed_alarm_cb.text(), "低压报警 (D2)")
        self.assertFalse(self.window.p_gear_protect_cb.isEnabled())
        self.assertFalse(self.window.motor_running_cb.isEnabled())
        self.assertFalse(self.window.controller_protect_cb.isEnabled())
        self.assertFalse(self.window.speed_spin.isEnabled())
        self.assertFalse(hasattr(self.window, "soc_spin"))
        self.assertEqual(self.window.current_spin.minimum(), 0.0)
        self.assertEqual(self.window.current_spin.maximum(), 51.0)

    def test_xinri_ui_round_trip_matches_protocol_bytes(self):
        self.window.on_protocol_changed(PROTOCOL_XINRI)
        self.window.distance_mode_cb.setChecked(True)
        self.window.speed_alarm_cb.setChecked(True)
        self.window.hall_fault_cb.setChecked(True)
        self.window.throttle_fault_cb.setChecked(True)
        self.window.controller_fault_cb.setChecked(True)
        self.window.cruise_cb.setChecked(True)
        self.window.brake_cb.setChecked(True)
        self.window.speed_mode_spin.setValue(5)
        self.window.one_key_enable_cb.setChecked(True)
        self.window.current_spin.setValue(10.2)
        self.window.hall_count_spin.setValue(0x1234)

        status = self.window.get_current_status_from_ui()
        success, frame, error = self.window.generate_protocol_frame_for_preview(status)

        self.assertTrue(success, error)
        self.assertEqual(frame[2], 0x0C)
        self.assertEqual(frame[3], 0x74)
        self.assertEqual(frame[4], 0xA1)
        self.assertEqual(frame[5], 0x40)
        self.assertEqual(frame[6], 0x33)
        self.assertEqual(frame[7:11], [0x12, 0x34, 0x00, 0x00])

    def test_legacy_xinri_entry_points_delegate_to_spec_backed_ui(self):
        self.window.current_protocol = PROTOCOL_XINRI
        self.window.show_xinri_status_config()
        self.window.current_status = StatusBits(
            protocol_name=PROTOCOL_XINRI,
            p_gear_protect=True,
            low_voltage_alarm=True,
            current_a=5.2,
            hall_count=123,
        )

        self.window.update_xinri_ui_from_status()
        status = self.window.get_xinri_status_from_ui()

        self.assertTrue(status.p_gear_protect)
        self.assertTrue(status.low_voltage_alarm)
        self.assertEqual(status.current_a, 5.2)
        self.assertEqual(status.hall_count, 123)

    def test_send_history_has_bounded_document(self):
        self.assertEqual(self.window.history_text.document().maximumBlockCount(), 10000)

    def test_default_custom_frame_does_not_hide_generation_failure_as_zero_frame(self):
        self.window.protocol_handler.generate_frame_for_preview = Mock(
            return_value=(False, [], "规格字段无效")
        )

        with self.assertRaisesRegex(ValueError, "规格字段无效"):
            self.window._make_default_custom_frame()

    def test_battery_single_wire_generated_paths_use_nonzero_test_defaults(self):
        """验证数据自定义预览、发送及全自定义和包组初始帧使用同一测试数据。"""
        self.window.on_protocol_changed(PROTOCOL_BATTERY_SINGLE_WIRE)
        self.window.custom_radio.click()
        self.window.battery_single_wire_soc_spin.setValue(80)
        self.window.update_current_frame_display()
        expected_frame = [0, 80, 1, 1, 1, 83]

        self.assertIn(
            "00 50 01 01 01 53", self.window.current_frame_text.toPlainText()
        )
        self.assertEqual(self.window._make_default_custom_frame(), expected_frame)
        self.assertEqual(self.window._get_packet_sequence_frames(), [expected_frame])
        self.window.serial_manager.send_single_frame = Mock(return_value=(True, ""))
        self.window.send_single_frame()
        self.window.serial_manager.send_single_frame.assert_called_once_with(
            expected_frame, send_mode="uart"
        )
        self.window.frame_custom_radio.click()
        self.assertEqual(self.window.custom_frame_data, expected_frame)

    def test_battery_single_wire_preserves_explicit_custom_frames(self):
        """验证手动自定义帧和已有包组不会被新的默认字节覆盖。"""
        self.window.on_protocol_changed(PROTOCOL_BATTERY_SINGLE_WIRE)
        self.window.frame_custom_radio.click()
        original_frame = [0, 80, 0, 0, 0, 80]
        self.window.on_custom_frame_changed(original_frame)
        self.window.packet_sequence_frames[PROTOCOL_BATTERY_SINGLE_WIRE] = [
            original_frame.copy()
        ]
        self.window.serial_manager.send_single_frame = Mock(return_value=(True, ""))

        self.window.send_single_frame()

        self.window.serial_manager.send_single_frame.assert_called_once_with(
            original_frame, send_mode="uart"
        )
        self.assertEqual(self.window.custom_frame_data, original_frame)
        self.assertIn(
            "00 50 00 00 00 50", self.window.current_frame_text.toPlainText()
        )
        self.assertEqual(self.window._get_packet_sequence_frames(), [original_frame])

    def test_send_error_remains_visible_after_disconnect_stopped_timer(self):
        self.window.active_send_mode = "single"
        self.window.on_port_disconnected("COM1")
        self.window.serial_manager.is_cyclic_sending = Mock(return_value=False)

        self.window.on_send_error("串口写入失败")

        self.assertEqual(self.window.send_status.text(), "发送失败")
        self.assertIsNone(self.window.active_send_mode)

    def test_every_registered_protocol_can_switch_read_and_preview(self):
        for protocol_name in SUPPORTED_PROTOCOLS:
            with self.subTest(protocol=protocol_name):
                self.window.on_protocol_changed(protocol_name)
                _APP.processEvents()

                status = self.window.get_current_status_from_ui()
                success, frame, error = self.window.generate_protocol_frame_for_preview(status)

                self.assertTrue(success, error)
                self.assertEqual(
                    len(frame),
                    self.window.protocol_handler.get_protocol_frame_length(protocol_name),
                )


class MainWindowLiveCyclicTests(unittest.TestCase):
    """验证界面修改能够传入下一发送周期，不依赖真实串口硬件。"""

    def setUp(self):
        """关闭端口扫描并使用模拟串口记录真正进入写接口的帧。"""
        detector_patch = patch.object(
            SerialPortDetector, "start_detection", autospec=True
        )
        detector_patch.start()
        self.addCleanup(detector_patch.stop)
        self.window = MainWindow()
        self.window.history_update_timer.stop()
        self.addCleanup(self.window.history_update_timer.stop)
        self.addCleanup(self.window.port_detector.stop_detection)
        self.addCleanup(self.window.close)
        self.manager = self.window.serial_manager
        self.addCleanup(self.manager.stop_cyclic_send)
        self.serial_port = Mock()
        self.serial_port.port = "COM1"
        self.serial_port.write.side_effect = len
        self.manager.serial_port = self.serial_port
        self.manager.is_connected = True
        self.manager.tosc_us = 0

    def test_battery_soc_edit_changes_next_frame_without_restarting_timer(self):
        """验证低周期发送中修改 SOC，下一帧立即采用新电量及累加校验。"""
        self.window.on_protocol_changed(PROTOCOL_BATTERY_SINGLE_WIRE)
        self.window.custom_radio.click()
        self.window.battery_single_wire_soc_spin.setValue(80)
        self.window.interval_spin.setValue(10)
        with patch.object(
            self.manager.send_timer, "start", wraps=self.manager.send_timer.start
        ) as timer_start:
            self.window.toggle_cyclic_send()
            self.serial_port.write.assert_not_called()
            self.manager.send_timer.timeout.emit()
            self.serial_port.write.assert_called_with(bytes([0, 80, 1, 1, 1, 83]))

            self.window.battery_single_wire_soc_spin.setValue(25)
            self.assertEqual(self.serial_port.write.call_count, 1)
            self.manager.send_timer.timeout.emit()

        self.serial_port.write.assert_called_with(bytes([0, 25, 1, 1, 1, 28]))
        self.assertTrue(self.manager.is_cyclic_sending())
        self.assertEqual(self.window.active_send_mode, "single")
        timer_start.assert_called_once_with(10)

    def test_xinri_field_edits_regenerate_payload_and_xor(self):
        """验证循环中状态位、电流和霍尔计数修改进入新帧并重新计算异或。"""
        self.window.on_protocol_changed(PROTOCOL_XINRI)
        self.window.custom_radio.click()
        self.window.hall_fault_cb.setChecked(False)
        self.window.toggle_cyclic_send()
        self.manager.send_timer.timeout.emit()
        original_frame = list(self.serial_port.write.call_args[0][0])

        self.window.hall_fault_cb.setChecked(True)
        self.window.current_spin.setValue(10.2)
        self.window.hall_count_spin.setValue(0x5678)
        self.manager.send_timer.timeout.emit()

        frame = list(self.serial_port.write.call_args[0][0])
        self.assertFalse(original_frame[3] & 0x40)
        self.assertTrue(frame[3] & 0x40)
        self.assertEqual(frame[6], 0x33)
        self.assertEqual(frame[7:9], [0x56, 0x78])
        checksum = 0
        for value in frame[:-1]:
            checksum ^= value
        self.assertEqual(frame[-1], checksum)

    def test_applied_full_custom_frame_changes_next_cyclic_write(self):
        """验证全部自定义模式已应用的帧直接生效，不被自动编码覆盖。"""
        self.window.on_protocol_changed(PROTOCOL_BATTERY_SINGLE_WIRE)
        self.window.frame_custom_radio.click()
        self.window.toggle_cyclic_send()
        self.manager.send_timer.timeout.emit()
        custom_frame = [0, 55, 5, 6, 7, 73]

        self.window.on_custom_frame_changed(custom_frame)
        self.manager.send_timer.timeout.emit()

        self.serial_port.write.assert_called_with(bytes(custom_frame))
        self.assertTrue(self.manager.is_cyclic_sending())

    def test_preset_switch_changes_next_frame_while_sending(self):
        """验证循环过程中切换预设场景时读取新的状态对象。"""
        self.window.on_protocol_changed(PROTOCOL_BATTERY_SINGLE_WIRE)
        self.window.toggle_cyclic_send()
        self.manager.send_timer.timeout.emit()
        self.serial_port.write.assert_called_with(bytes([0, 80, 1, 1, 1, 83]))

        self.window.scenario_group.button(1).click()
        self.manager.send_timer.timeout.emit()

        self.serial_port.write.assert_called_with(bytes([0, 62, 1, 1, 1, 65]))
        self.assertTrue(self.manager.is_cyclic_sending())

    def test_sequence_protocols_increment_per_tick_but_not_on_start_or_edit(self):
        """验证流水号协议启动和预览不消耗序号，每个发送周期只递增一次。"""
        for protocol_name, sequence_getter in (
            (PROTOCOL_CHANGZHOU_XINSIWEI, "get_current_xinsiwei_sequence"),
            (PROTOCOL_HANGZHOU_ANXIAN, "get_current_hangzhou_sequence"),
            (PROTOCOL_SXSY, "get_current_sxsy_sequence"),
            (PROTOCOL_JINGXIAN, "get_current_jingxian_sequence"),
        ):
            with self.subTest(protocol=protocol_name):
                self.window.on_protocol_changed(protocol_name)
                self.window.custom_radio.click()
                get_sequence = getattr(self.window.protocol_handler, sequence_getter)
                initial_sequence = get_sequence()
                status = self.window.get_current_status_from_ui()
                success, expected_frame, error = (
                    self.window.generate_protocol_frame_for_preview(status)
                )
                self.assertTrue(success, error)

                self.window.toggle_cyclic_send()
                self.assertEqual(get_sequence(), initial_sequence)
                self.manager.send_timer.timeout.emit()
                self.serial_port.write.assert_called_with(bytes(expected_frame))
                self.assertEqual(get_sequence(), initial_sequence + 1)

                self.window.hall_count_spin.setValue(0x1234)
                status = self.window.get_current_status_from_ui()
                success, expected_frame, error = (
                    self.window.generate_protocol_frame_for_preview(status)
                )
                self.assertTrue(success, error)
                self.assertEqual(get_sequence(), initial_sequence + 1)
                self.manager.send_timer.timeout.emit()
                self.serial_port.write.assert_called_with(bytes(expected_frame))
                self.assertEqual(get_sequence(), initial_sequence + 2)

    def test_invalid_live_status_stops_sending_and_keeps_error_visible(self):
        """验证动态参数无效时停发并显示原因，不继续发送上一份有效帧。"""
        self.window.on_protocol_changed(PROTOCOL_BATTERY_SINGLE_WIRE)
        self.window.custom_radio.click()
        self.window.toggle_cyclic_send()
        self.manager.send_timer.timeout.emit()
        invalid_status = StatusBits(
            protocol_name=PROTOCOL_BATTERY_SINGLE_WIRE, soc_percent=101
        )
        with patch.object(
            self.window, "get_current_status_from_ui", return_value=invalid_status
        ):
            self.manager.send_timer.timeout.emit()
            self.manager.send_timer.timeout.emit()

        self.assertEqual(self.serial_port.write.call_count, 1)
        self.assertFalse(self.manager.is_cyclic_sending())
        self.assertIsNone(self.manager.cyclic_frame_provider)
        self.assertIsNone(self.window.active_send_mode)
        self.assertEqual(self.window.send_status.text(), "发送失败")
        self.assertIn("0-100", self.window.history_text.toPlainText())

    def test_packet_sequence_keeps_configured_frames_after_ui_edit(self):
        """验证从动态循环切换到包组后，界面修改不覆盖固定包组内容。"""
        self.window.on_protocol_changed(PROTOCOL_BATTERY_SINGLE_WIRE)
        self.window.custom_radio.click()
        self.window.toggle_cyclic_send()
        frames = [[0, 80, 1, 1, 1, 83], [0, 40, 1, 1, 1, 43]]
        self.window.packet_sequence_frames[PROTOCOL_BATTERY_SINGLE_WIRE] = frames
        self.window.toggle_packet_sequence_send()
        self.window.battery_single_wire_soc_spin.setValue(10)
        payloads = []
        for _ in range(3):
            self.manager.send_timer.timeout.emit()
            payloads.append(self.serial_port.write.call_args[0][0])

        self.assertEqual(payloads, [bytes(frames[0]), bytes(frames[1]), bytes(frames[0])])
        self.assertIsNone(self.manager.cyclic_frame_provider)
        self.assertEqual(self.window.active_send_mode, "sequence")

    def test_every_registered_protocol_uses_live_generation_for_cyclic_send(self):
        """验证所有已注册协议均通过公共生成入口完成循环发送。"""
        for protocol_name in SUPPORTED_PROTOCOLS:
            with self.subTest(protocol=protocol_name):
                self.window.on_protocol_changed(protocol_name)
                self.window.custom_radio.click()
                status = self.window.get_current_status_from_ui()
                success, expected_frame, error = (
                    self.window.generate_protocol_frame_for_preview(status)
                )
                self.assertTrue(success, error)

                self.window.toggle_cyclic_send()
                self.manager.send_timer.timeout.emit()

                self.serial_port.write.assert_called_with(bytes(expected_frame))
                self.assertTrue(self.manager.is_cyclic_sending())


if __name__ == "__main__":
    unittest.main()
