import os
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication

from gui.main_window import MainWindow
from protocol.protocol_handler import (
    PROTOCOL_BATTERY_SINGLE_WIRE,
    PROTOCOL_SHENZHOUXING,
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

        self.window.interval_spin.setValue(1500)

        self.window.serial_manager.update_cyclic_send_interval.assert_called_once_with(1500)

    def test_interval_spin_defaults_to_500_for_regular_protocols(self):
        self.assertEqual(self.window.interval_spin.minimum(), 500)
        self.assertEqual(self.window.interval_spin.value(), 500)

    def test_xinchi_protocol_resets_interval_to_500ms(self):
        self.window.current_protocol = PROTOCOL_BATTERY_SINGLE_WIRE
        self.window.apply_send_interval_constraints()
        self.assertEqual(self.window.interval_spin.value(), 500)

        self.window.current_protocol = PROTOCOL_XINCHI
        self.window.apply_send_interval_constraints()

        self.assertEqual(self.window.interval_spin.minimum(), 500)
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


if __name__ == "__main__":
    unittest.main()
