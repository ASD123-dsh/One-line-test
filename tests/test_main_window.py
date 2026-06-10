import os
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication

from gui.main_window import MainWindow
from protocol.protocol_handler import PROTOCOL_BATTERY_SINGLE_WIRE, PROTOCOL_XINCHI
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
        self.assertEqual(self.window.interval_spin.value(), 2000)

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


if __name__ == "__main__":
    unittest.main()
