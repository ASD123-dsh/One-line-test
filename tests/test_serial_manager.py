import unittest
from unittest.mock import patch

from PyQt5.QtCore import QCoreApplication

from serial_comm.serial_manager import SerialManager


_APP = QCoreApplication.instance() or QCoreApplication([])


class FakeSerialPort:
    def __init__(self, bytes_written=None):
        self.bytes_written = bytes_written
        self.last_payload = None

    def write(self, payload):
        self.last_payload = payload
        if self.bytes_written is not None:
            return self.bytes_written
        return len(payload)


class SerialManagerTests(unittest.TestCase):
    def setUp(self):
        self.manager = SerialManager()
        self.manager.is_connected = True
        self.manager.serial_port = FakeSerialPort()
        self.manager.tosc_us = 0

    def test_send_single_frame_accepts_10_byte_frame(self):
        frame_data = [0x3A, 0xC0, 0x50, 0x7E, 0x00, 0x1C, 0x1F, 0x02, 0x12, 0x17]

        success, error = self.manager.send_single_frame(frame_data, skip_ui_update=True)

        self.assertTrue(success, error)
        self.assertEqual(error, "")
        self.assertEqual(self.manager.serial_port.last_payload, bytes(frame_data))

    def test_send_single_frame_reports_actual_expected_length(self):
        frame_data = [0x3A, 0xC0, 0x50, 0x7E, 0x00, 0x1C, 0x1F, 0x02, 0x12, 0x17]
        self.manager.serial_port = FakeSerialPort(bytes_written=8)

        success, error = self.manager.send_single_frame(frame_data, skip_ui_update=True)

        self.assertFalse(success)
        self.assertEqual(error, "数据发送不完整，期望10字节，实际发送8字节")

    def test_start_cyclic_send_accepts_10_byte_frame(self):
        frame_data = [0x3A, 0xC0, 0x50, 0x7E, 0x00, 0x1C, 0x1F, 0x02, 0x12, 0x17]

        with patch.object(self.manager.send_timer, "start") as mock_start:
            success, error = self.manager.start_cyclic_send(frame_data, 1000)

        self.assertTrue(success, error)
        self.assertEqual(error, "")
        self.assertEqual(self.manager.cyclic_data, frame_data)
        self.assertEqual(self.manager.send_interval_ms, 1000)
        mock_start.assert_called_once_with(1000)


if __name__ == "__main__":
    unittest.main()
