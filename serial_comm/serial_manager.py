#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Serial communication management.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Tuple

import serial
import serial.tools.list_ports
import time
from PyQt5.QtCore import QObject, QTimer, pyqtSignal


SEND_MODE_UART = "uart"
SEND_MODE_BATTERY_SINGLE_WIRE = "battery_single_wire"


@dataclass
class SerialPortInfo:
    port: str
    description: str
    hwid: str

    def __str__(self) -> str:
        return f"{self.port} ({self.description})"


class SerialManager(QObject):
    port_connected = pyqtSignal(str)
    port_disconnected = pyqtSignal(str)
    data_sent = pyqtSignal(list, str)
    send_error = pyqtSignal(str)
    connection_error = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.serial_port: Optional[serial.Serial] = None
        self.is_connected = False
        self.send_timer = QTimer()
        self.send_timer.timeout.connect(self._send_cyclic_data)

        self.cyclic_data: Optional[List[int]] = None
        self.cyclic_frame_sequence: List[List[int]] = []
        self.cyclic_frame_index = 0
        self.cyclic_send_mode = SEND_MODE_UART
        self.send_interval_ms = 1000
        self.tosc_us = 100

        self.send_count = 0
        self.ui_update_interval = 10

    def scan_ports(self) -> List[SerialPortInfo]:
        ports: List[SerialPortInfo] = []
        try:
            for port_info in serial.tools.list_ports.comports():
                ports.append(
                    SerialPortInfo(
                        port=port_info.device,
                        description=port_info.description,
                        hwid=port_info.hwid or "",
                    )
                )
        except Exception:
            pass
        return ports

    def connect_port(self, port_name: str, baud_rate: int = 9600) -> Tuple[bool, str]:
        try:
            if self.is_connected:
                self.disconnect_port()

            self.serial_port = serial.Serial(
                port=port_name,
                baudrate=baud_rate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=1.0,
                write_timeout=1.0,
            )

            if self.serial_port.is_open:
                self.is_connected = True
                self.port_connected.emit(port_name)
                return True, ""
            return False, "串口打开失败"
        except serial.SerialException as e:
            error_msg = f"串口连接失败: {e}"
            self.connection_error.emit(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"未知错误: {e}"
            self.connection_error.emit(error_msg)
            return False, error_msg

    def disconnect_port(self) -> bool:
        try:
            self.stop_cyclic_send()
            if self.serial_port and self.serial_port.is_open:
                port_name = self.serial_port.port
                self._set_tx_low(False)
                self.serial_port.close()
                self.is_connected = False
                self.port_disconnected.emit(port_name)
                return True

            self.is_connected = False
            return True
        except Exception:
            return False

    def send_single_frame(
        self,
        frame_data: List[int],
        skip_ui_update: bool = False,
        send_mode: str = SEND_MODE_UART,
    ) -> Tuple[bool, str]:
        if not self.is_connected or not self.serial_port:
            return False, "串口未连接"

        expected_length = len(frame_data)
        if expected_length == 0:
            return False, "数据不能为空"

        if send_mode == SEND_MODE_BATTERY_SINGLE_WIRE:
            return self._send_battery_single_wire_frame(frame_data, skip_ui_update)
        if send_mode != SEND_MODE_UART:
            return False, f"不支持的发送模式: {send_mode}"

        try:
            self._set_tx_low(False)
            data_bytes = bytes(frame_data)
            bytes_written = self.serial_port.write(data_bytes)

            if bytes_written == expected_length:
                idle_time_ms = (32 * self.tosc_us) / 1000.0
                if idle_time_ms > 0:
                    QTimer.singleShot(int(idle_time_ms), lambda: None)

                if not skip_ui_update:
                    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                    self.data_sent.emit(frame_data, timestamp)
                return True, ""

            error_msg = f"数据发送不完整，期望{expected_length}字节，实际发送{bytes_written}字节"
            if not skip_ui_update:
                self.send_error.emit(error_msg)
            return False, error_msg
        except serial.SerialTimeoutException:
            error_msg = "串口发送超时"
            if not skip_ui_update:
                self.send_error.emit(error_msg)
            return False, error_msg
        except serial.SerialException as e:
            error_msg = f"串口发送失败: {e}"
            if not skip_ui_update:
                self.send_error.emit(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"发送数据时发生未知错误: {e}"
            if not skip_ui_update:
                self.send_error.emit(error_msg)
            return False, error_msg

    def _send_battery_single_wire_frame(
        self, frame_data: List[int], skip_ui_update: bool = False
    ) -> Tuple[bool, str]:
        if len(frame_data) != 6:
            return False, "电池单线通讯协议帧长度必须为 6 字节"

        try:
            self._set_tx_low(True)
            self._sleep_ms(62)
            self._set_tx_low(False)
            self._sleep_ms(2)

            for byte_value in frame_data:
                for bit_index in range(8):
                    bit_value = (byte_value >> bit_index) & 0x01
                    low_ms = 2 if bit_value else 4
                    high_ms = 4 if bit_value else 2
                    self._set_tx_low(True)
                    self._sleep_ms(low_ms)
                    self._set_tx_low(False)
                    self._sleep_ms(high_ms)

            self._set_tx_low(True)
            self._sleep_ms(20)

            if not skip_ui_update:
                timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                self.data_sent.emit(frame_data, timestamp)
            return True, ""
        except Exception as e:
            error_msg = f"电池单线通讯协议发送失败: {e}"
            if not skip_ui_update:
                self.send_error.emit(error_msg)
            return False, error_msg

    def _set_tx_low(self, is_low: bool):
        if self.serial_port is not None:
            self.serial_port.break_condition = bool(is_low)

    def _sleep_ms(self, duration_ms: int):
        time.sleep(duration_ms / 1000.0)

    def start_cyclic_send(
        self,
        frame_data: List[int],
        interval_ms: int = 1000,
        send_mode: str = SEND_MODE_UART,
    ) -> Tuple[bool, str]:
        return self.start_cyclic_send_sequence([frame_data], interval_ms, send_mode)

    def start_cyclic_send_sequence(
        self,
        frame_sequence: List[List[int]],
        interval_ms: int = 1000,
        send_mode: str = SEND_MODE_UART,
    ) -> Tuple[bool, str]:
        if not self.is_connected:
            return False, "串口未连接"
        if not frame_sequence:
            return False, "循环数据包组不能为空"
        if send_mode not in {SEND_MODE_UART, SEND_MODE_BATTERY_SINGLE_WIRE}:
            return False, f"不支持的发送模式: {send_mode}"

        normalized_frames: List[List[int]] = []
        for index, frame_data in enumerate(frame_sequence, start=1):
            if len(frame_data) == 0:
                return False, f"第{index}组数据包不能为空"
            normalized_frames.append(frame_data.copy())

        if send_mode == SEND_MODE_BATTERY_SINGLE_WIRE:
            if not (1000 <= interval_ms <= 2000):
                return False, "电池单线通讯协议发送间隔必须在1000ms-2000ms范围内"
        elif not (500 <= interval_ms <= 5000):
            return False, "发送间隔必须在500ms-5000ms范围内"

        self.cyclic_data = normalized_frames[0].copy()
        self.cyclic_frame_sequence = normalized_frames
        self.cyclic_frame_index = 0
        self.cyclic_send_mode = send_mode
        self.send_interval_ms = interval_ms
        self.send_count = 0

        self.send_timer.start(interval_ms)
        return True, ""

    def stop_cyclic_send(self):
        self.send_timer.stop()
        self.cyclic_data = None
        self.cyclic_frame_sequence = []
        self.cyclic_frame_index = 0
        self.cyclic_send_mode = SEND_MODE_UART

    def _get_next_cyclic_frame(self) -> Optional[List[int]]:
        if not self.cyclic_frame_sequence:
            return None

        frame_data = self.cyclic_frame_sequence[self.cyclic_frame_index].copy()
        self.cyclic_frame_index = (self.cyclic_frame_index + 1) % len(self.cyclic_frame_sequence)
        self.cyclic_data = frame_data.copy()
        return frame_data

    def _send_cyclic_data(self):
        if not self.cyclic_frame_sequence or not self.is_connected:
            return

        self.send_count += 1
        skip_ui = False
        if self.send_interval_ms < 200:
            skip_ui = (self.send_count % self.ui_update_interval) != 0

        frame_data = self._get_next_cyclic_frame()
        if frame_data is None:
            self.stop_cyclic_send()
            return

        success, error_msg = self.send_single_frame(
            frame_data,
            skip_ui_update=skip_ui,
            send_mode=self.cyclic_send_mode,
        )

        if skip_ui and not success:
            self.send_error.emit(error_msg)

        if self.send_count >= 100:
            self.send_count = 0

        if not success:
            self.stop_cyclic_send()

    def is_cyclic_sending(self) -> bool:
        return self.send_timer.isActive()

    def set_tosc_value(self, tosc_us: int) -> bool:
        if 32 <= tosc_us <= 320:
            self.tosc_us = tosc_us
            return True
        return False

    def get_port_status(self) -> dict:
        return {
            "connected": self.is_connected,
            "port_name": self.serial_port.port if self.serial_port else None,
            "baud_rate": self.serial_port.baudrate if self.serial_port else None,
            "cyclic_sending": self.is_cyclic_sending(),
            "cyclic_frame_count": len(self.cyclic_frame_sequence),
            "send_interval_ms": self.send_interval_ms,
            "tosc_us": self.tosc_us,
        }


class SerialPortDetector(QObject):
    ports_changed = pyqtSignal(list)

    def __init__(self):
        super().__init__()
        self.last_ports: List[SerialPortInfo] = []
        self.detection_timer = QTimer()
        self.detection_timer.timeout.connect(self._check_ports)

    def start_detection(self, interval_ms: int = 2000):
        self._check_ports()
        self.detection_timer.start(interval_ms)

    def stop_detection(self):
        self.detection_timer.stop()

    def _check_ports(self):
        try:
            current_ports: List[SerialPortInfo] = []
            for port_info in serial.tools.list_ports.comports():
                current_ports.append(
                    SerialPortInfo(
                        port=port_info.device,
                        description=port_info.description,
                        hwid=port_info.hwid or "",
                    )
                )

            if len(current_ports) != len(self.last_ports) or any(
                p1.port != p2.port for p1, p2 in zip(current_ports, self.last_ports)
            ):
                self.last_ports = current_ports
                self.ports_changed.emit(current_ports)
        except Exception:
            pass
