import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication

from serial_comm.serial_manager import (
    SEND_MODE_BATTERY_SINGLE_WIRE,
    SEND_MODE_JINGXIAN_SIF,
    SEND_MODE_LUYUAN_BMS_SIF,
    SerialManager,
)


_APP = QApplication.instance() or QApplication([])


class FakeSerialPort:
    def __init__(self, bytes_written=None):
        self.bytes_written = bytes_written
        self.last_payload = None
        self.break_history = []
        self._break_condition = False

    def write(self, payload):
        self.last_payload = payload
        if self.bytes_written is not None:
            return self.bytes_written
        return len(payload)

    @property
    def break_condition(self):
        return self._break_condition

    @break_condition.setter
    def break_condition(self, value):
        self._break_condition = value
        self.break_history.append(value)


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

    def test_start_cyclic_send_sequence_accepts_multiple_frames(self):
        frame_sequence = [
            [0x3A, 0xC0, 0x50, 0x7E, 0x00, 0x1C, 0x1F, 0x02, 0x12, 0x17],
            [0x3A, 0xC1, 0x51, 0x7F, 0x01, 0x1D, 0x20, 0x03, 0x13, 0x1A],
        ]

        with patch.object(self.manager.send_timer, "start") as mock_start:
            success, error = self.manager.start_cyclic_send_sequence(frame_sequence, 1200)

        self.assertTrue(success, error)
        self.assertEqual(error, "")
        self.assertEqual(self.manager.cyclic_frame_sequence, frame_sequence)
        self.assertEqual(self.manager.cyclic_data, frame_sequence[0])
        self.assertEqual(self.manager.cyclic_frame_index, 0)
        mock_start.assert_called_once_with(1200)

    def test_update_cyclic_send_interval_restarts_active_timer(self):
        self.manager.cyclic_frame_sequence = [[0x3A, 0xC0, 0x50, 0x7E, 0x00, 0x1C, 0x1F, 0x02, 0x12, 0x17]]
        self.manager.cyclic_send_mode = "uart"

        with patch.object(self.manager.send_timer, "isActive", return_value=True):
            with patch.object(self.manager.send_timer, "start") as mock_start:
                success, error = self.manager.update_cyclic_send_interval(1500)

        self.assertTrue(success, error)
        self.assertEqual(error, "")
        self.assertEqual(self.manager.send_interval_ms, 1500)
        mock_start.assert_called_once_with(1500)

    def test_update_cyclic_send_interval_rejects_invalid_battery_single_wire_value(self):
        self.manager.cyclic_frame_sequence = [[0x00, 0x50, 0x00, 0x00, 0x00, 0x50]]
        self.manager.cyclic_send_mode = SEND_MODE_BATTERY_SINGLE_WIRE

        with patch.object(self.manager.send_timer, "isActive", return_value=True):
            with patch.object(self.manager.send_timer, "start") as mock_start:
                success, error = self.manager.update_cyclic_send_interval(500)

        self.assertFalse(success)
        self.assertEqual(error, "电池单线通讯协议发送间隔必须在1000ms-2000ms范围内")
        mock_start.assert_not_called()

    def test_send_cyclic_data_rotates_packet_sequence(self):
        frame_sequence = [
            [0x3A, 0xC0, 0x50, 0x7E, 0x00, 0x1C, 0x1F, 0x02, 0x12, 0x17],
            [0x3A, 0xC1, 0x51, 0x7F, 0x01, 0x1D, 0x20, 0x03, 0x13, 0x1A],
        ]
        self.manager.cyclic_frame_sequence = [frame.copy() for frame in frame_sequence]
        self.manager.cyclic_send_mode = "uart"
        self.manager.send_interval_ms = 1000

        sent_frames = []

        def fake_send(frame_data, skip_ui_update=False, send_mode="uart"):
            sent_frames.append((frame_data.copy(), skip_ui_update, send_mode))
            return True, ""

        with patch.object(self.manager, "send_single_frame", side_effect=fake_send):
            self.manager._send_cyclic_data()
            self.manager._send_cyclic_data()
            self.manager._send_cyclic_data()

        self.assertEqual([item[0] for item in sent_frames], [
            frame_sequence[0],
            frame_sequence[1],
            frame_sequence[0],
        ])
        self.assertTrue(all(item[2] == "uart" for item in sent_frames))

    def test_battery_single_wire_cyclic_send_requires_protocol_interval(self):
        frame_data = [0x00, 0x50, 0x00, 0x00, 0x00, 0x50]

        success, error = self.manager.start_cyclic_send(
            frame_data,
            500,
            send_mode=SEND_MODE_BATTERY_SINGLE_WIRE,
        )

        self.assertFalse(success)
        self.assertEqual(error, "电池单线通讯协议发送间隔必须在1000ms-2000ms范围内")

        with patch.object(self.manager.send_timer, "start") as mock_start:
            success, error = self.manager.start_cyclic_send(
                frame_data,
                2000,
                send_mode=SEND_MODE_BATTERY_SINGLE_WIRE,
            )

        self.assertTrue(success, error)
        self.assertEqual(self.manager.cyclic_send_mode, SEND_MODE_BATTERY_SINGLE_WIRE)
        mock_start.assert_called_once_with(2000)

    def test_battery_single_wire_mode_uses_break_condition_pulses_and_releases_after_stop(self):
        frame_data = [0x00, 0x01, 0x00, 0x00, 0x00, 0x01]

        with patch.object(self.manager, "_sleep_ms") as mock_sleep:
            success, error = self.manager.send_single_frame(
                frame_data,
                skip_ui_update=True,
                send_mode=SEND_MODE_BATTERY_SINGLE_WIRE,
            )

        self.assertTrue(success, error)
        self.assertEqual(error, "")
        self.assertIsNone(self.manager.serial_port.last_payload)
        self.assertEqual(self.manager.serial_port.break_history[:4], [True, False, True, False])
        self.assertEqual(self.manager.serial_port.break_history[-1], False)
        self.assertEqual([call.args[0] for call in mock_sleep.call_args_list[:4]], [62, 2, 4, 2])
        self.assertEqual(mock_sleep.call_args_list[-1].args[0], 20)

    def test_luyuan_bms_mode_uses_msb_first_pulses_and_releases_after_stop(self):
        frame_data = [0x3A, 0xD8, 0x58, 0x34, 0x12, 0x85, 0x72, 0x10, 0xF8, 0x0F, 0xD2, 0x04, 0x36, 0x61, 0x2B]

        with patch.object(self.manager, "_sleep_ms") as mock_sleep:
            success, error = self.manager.send_single_frame(
                frame_data,
                skip_ui_update=True,
                send_mode=SEND_MODE_LUYUAN_BMS_SIF,
            )

        self.assertTrue(success, error)
        self.assertEqual(error, "")
        self.assertIsNone(self.manager.serial_port.last_payload)
        self.assertEqual(self.manager.serial_port.break_history[:4], [True, False, True, False])
        self.assertEqual(self.manager.serial_port.break_history[-1], False)
        self.assertEqual([call.args[0] for call in mock_sleep.call_args_list[:6]], [40, 2, 4, 2, 4, 2])
        self.assertEqual(mock_sleep.call_args_list[-1].args[0], 10)

    def test_jingxian_mode_uses_lsb_first_pulses_and_holds_low_after_stop(self):
        frame_data = [0x07] + [0x00] * 11

        with patch.object(self.manager, "_sleep_ms") as mock_sleep:
            success, error = self.manager.send_single_frame(
                frame_data,
                skip_ui_update=True,
                send_mode=SEND_MODE_JINGXIAN_SIF,
            )

        self.assertTrue(success, error)
        self.assertEqual(error, "")
        self.assertIsNone(self.manager.serial_port.last_payload)
        self.assertEqual(self.manager.serial_port.break_history[:4], [True, False, True, False])
        self.assertEqual(self.manager.serial_port.break_history[-1], True)
        self.assertEqual([call.args[0] for call in mock_sleep.call_args_list[:6]], [50, 1, 0.5, 1, 0.5, 1])
        self.assertEqual(mock_sleep.call_args_list[-1].args[0], 0)


if __name__ == "__main__":
    unittest.main()
