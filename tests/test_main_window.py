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


if __name__ == "__main__":
    unittest.main()
