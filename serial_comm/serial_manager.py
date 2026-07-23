#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""串口通信、循环发送和自定义 SIF 波形管理。"""

import ctypes
import time
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Tuple

import serial
import serial.tools.list_ports
from PyQt5.QtCore import QObject, QTimer, pyqtSignal

from protocol.frame_utils import normalize_frame


SEND_MODE_UART = "uart"
SEND_MODE_BATTERY_SINGLE_WIRE = "battery_single_wire"
SEND_MODE_LUYUAN_BMS_SIF = "luyuan_bms_sif"
SEND_MODE_JINGXIAN_SIF = "jingxian_sif"
SUPPORTED_SEND_MODES = frozenset(
    {
        SEND_MODE_UART,
        SEND_MODE_BATTERY_SINGLE_WIRE,
        SEND_MODE_LUYUAN_BMS_SIF,
        SEND_MODE_JINGXIAN_SIF,
    }
)
SEND_MODE_FRAME_LENGTHS = {
    SEND_MODE_BATTERY_SINGLE_WIRE: 6,
    SEND_MODE_LUYUAN_BMS_SIF: 15,
    SEND_MODE_JINGXIAN_SIF: 12,
}
MIN_SEND_INTERVAL_MS = 500
MAX_SEND_INTERVAL_MS = 5000


@dataclass
class SerialPortInfo:
    port: str
    description: str
    hwid: str

    def __str__(self) -> str:
        return f"{self.port} ({self.description})"


def _enumerate_serial_ports() -> List[SerialPortInfo]:
    """枚举系统串口并转换为统一的数据对象。"""

    return [
        SerialPortInfo(
            port=port_info.device,
            description=port_info.description,
            hwid=port_info.hwid or "",
        )
        for port_info in serial.tools.list_ports.comports()
    ]


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
        self.send_timer = QTimer(self)
        self.send_timer.timeout.connect(self._send_cyclic_data)

        self.cyclic_data: Optional[List[int]] = None
        self.cyclic_frame_sequence: List[List[int]] = []
        self.cyclic_frame_index = 0
        self.cyclic_send_mode = SEND_MODE_UART
        self.send_interval_ms = 500
        self.cyclic_min_interval_ms = MIN_SEND_INTERVAL_MS
        self.cyclic_max_interval_ms = MAX_SEND_INTERVAL_MS
        self.tosc_us = 100

        self.send_count = 0
        self.ui_update_interval = 10

    def scan_ports(self) -> List[SerialPortInfo]:
        """返回当前可用串口；枚举失败时保持 UI 可用并返回空列表。"""

        try:
            return _enumerate_serial_ports()
        except Exception:
            return []

    def connect_port(self, port_name: str, baud_rate: int = 9600) -> Tuple[bool, str]:
        """连接指定串口，并确保失败后不会遗留假连接状态。"""

        if not isinstance(port_name, str) or not port_name.strip():
            error_msg = "串口名称不能为空"
            self.connection_error.emit(error_msg)
            return False, error_msg
        if isinstance(baud_rate, bool) or not isinstance(baud_rate, int) or baud_rate <= 0:
            error_msg = "波特率必须是正整数"
            self.connection_error.emit(error_msg)
            return False, error_msg

        try:
            if self.is_connected and not self.disconnect_port():
                error_msg = "原串口未能安全断开，请重试"
                self.connection_error.emit(error_msg)
                return False, error_msg

            self.serial_port = serial.Serial(
                port=port_name.strip(),
                baudrate=baud_rate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=1.0,
                write_timeout=1.0,
            )

            if self.serial_port.is_open:
                self.is_connected = True
                self.port_connected.emit(port_name.strip())
                return True, ""

            self.serial_port.close()
            self.serial_port = None
            self.is_connected = False
            error_msg = "串口打开失败"
            self.connection_error.emit(error_msg)
            return False, error_msg
        except serial.SerialException as e:
            self.serial_port = None
            self.is_connected = False
            error_msg = f"串口连接失败: {e}"
            self.connection_error.emit(error_msg)
            return False, error_msg
        except Exception as e:
            self.serial_port = None
            self.is_connected = False
            error_msg = f"未知错误: {e}"
            self.connection_error.emit(error_msg)
            return False, error_msg

    def disconnect_port(self) -> bool:
        """断开当前串口；即使底层关闭异常也强制清理软件状态。"""

        port = self.serial_port
        was_connected = self.is_connected
        port_name = getattr(port, "port", "") if port is not None else ""
        success = True

        try:
            self.stop_cyclic_send()
            if port is not None and getattr(port, "is_open", False):
                try:
                    self._set_tx_low(False)
                finally:
                    port.close()
        except Exception:
            success = False
        finally:
            self.is_connected = False
            self.serial_port = None
            if was_connected and port_name:
                self.port_disconnected.emit(str(port_name))

        return success

    def _normalize_frame_for_mode(
        self,
        frame_data,
        send_mode: str,
        label: str = "发送数据",
    ) -> Tuple[Optional[List[int]], str]:
        """统一校验帧字节和发送模式要求的固定长度。"""

        if not isinstance(send_mode, str) or send_mode not in SUPPORTED_SEND_MODES:
            return None, f"不支持的发送模式: {send_mode}"

        try:
            normalized = normalize_frame(frame_data, label=label)
        except ValueError as exc:
            return None, str(exc)

        expected_length = SEND_MODE_FRAME_LENGTHS.get(send_mode)
        if expected_length is not None and len(normalized) != expected_length:
            return None, f"{label}长度必须为 {expected_length} 字节"

        return normalized, ""

    def send_single_frame(
        self,
        frame_data: List[int],
        skip_ui_update: bool = False,
        send_mode: str = SEND_MODE_UART,
    ) -> Tuple[bool, str]:
        if not self.is_connected or not self.serial_port:
            return False, "串口未连接"

        normalized_frame, error_msg = self._normalize_frame_for_mode(
            frame_data,
            send_mode,
        )
        if normalized_frame is None:
            return False, error_msg

        if send_mode == SEND_MODE_BATTERY_SINGLE_WIRE:
            return self._send_battery_single_wire_frame(normalized_frame, skip_ui_update)
        if send_mode == SEND_MODE_LUYUAN_BMS_SIF:
            return self._send_luyuan_bms_sif_frame(normalized_frame, skip_ui_update)
        if send_mode == SEND_MODE_JINGXIAN_SIF:
            return self._send_jingxian_sif_frame(normalized_frame, skip_ui_update)

        frame_data = normalized_frame
        expected_length = len(frame_data)
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
            self.disconnect_port()
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

        return self._send_sif_frame(
            frame_data,
            bit_indices=range(8),
            sync_low_ms=62,
            sync_high_ms=2,
            stop_low_ms=20,
            release_after_stop=True,
            protocol_label="电池单线通讯协议",
            skip_ui_update=skip_ui_update,
        )

    def _send_luyuan_bms_sif_frame(
        self, frame_data: List[int], skip_ui_update: bool = False
    ) -> Tuple[bool, str]:
        if len(frame_data) != 15:
            return False, "绿源BMS一线通协议帧长度必须为 15 字节"

        return self._send_sif_frame(
            frame_data,
            bit_indices=range(7, -1, -1),
            sync_low_ms=40,
            sync_high_ms=2,
            stop_low_ms=10,
            release_after_stop=True,
            protocol_label="绿源BMS一线通协议",
            skip_ui_update=skip_ui_update,
        )

    def _send_jingxian_sif_frame(
        self, frame_data: List[int], skip_ui_update: bool = False
    ) -> Tuple[bool, str]:
        if len(frame_data) != 12:
            return False, "精显一线通协议帧长度必须为 12 字节"

        return self._send_sif_frame(
            frame_data,
            bit_indices=range(8),
            sync_low_ms=50,
            sync_high_ms=1,
            stop_low_ms=0,
            release_after_stop=False,
            protocol_label="精显一线通协议",
            skip_ui_update=skip_ui_update,
            zero_low_ms=1,
            zero_high_ms=0.5,
            one_low_ms=0.5,
            one_high_ms=1,
        )

    def _send_sif_frame(
        self,
        frame_data: List[int],
        bit_indices,
        sync_low_ms: float,
        sync_high_ms: float,
        stop_low_ms: float,
        release_after_stop: bool,
        protocol_label: str,
        skip_ui_update: bool = False,
        zero_low_ms: float = 4,
        zero_high_ms: float = 2,
        one_low_ms: float = 2,
        one_high_ms: float = 4,
    ) -> Tuple[bool, str]:
        self._begin_precise_timing()
        try:
            self._set_tx_low(True)
            self._sleep_ms(sync_low_ms)
            self._set_tx_low(False)
            self._sleep_ms(sync_high_ms)

            for byte_value in frame_data:
                for bit_index in bit_indices:
                    bit_value = (byte_value >> bit_index) & 0x01
                    low_ms = one_low_ms if bit_value else zero_low_ms
                    high_ms = one_high_ms if bit_value else zero_high_ms
                    self._set_tx_low(True)
                    self._sleep_ms(low_ms)
                    self._set_tx_low(False)
                    self._sleep_ms(high_ms)

            self._set_tx_low(True)
            self._sleep_ms(stop_low_ms)
            if release_after_stop:
                self._set_tx_low(False)

            if not skip_ui_update:
                timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                self.data_sent.emit(frame_data, timestamp)
            return True, ""
        except Exception as e:
            self._set_tx_low(False)
            error_msg = f"{protocol_label}发送失败: {e}"
            if not skip_ui_update:
                self.send_error.emit(error_msg)
            return False, error_msg
        finally:
            self._end_precise_timing()

    def _set_tx_low(self, is_low: bool):
        if self.serial_port is not None:
            self.serial_port.break_condition = bool(is_low)

    def _begin_precise_timing(self):
        try:
            ctypes.windll.winmm.timeBeginPeriod(1)
        except Exception:
            pass

    def _end_precise_timing(self):
        try:
            ctypes.windll.winmm.timeEndPeriod(1)
        except Exception:
            pass

    def _sleep_ms(self, duration_ms: float):
        if duration_ms <= 0:
            return

        duration_s = duration_ms / 1000.0
        deadline = time.perf_counter() + duration_s

        if duration_ms <= 10:
            while time.perf_counter() < deadline:
                pass
            return

        coarse_sleep_s = duration_s - 0.001
        if coarse_sleep_s > 0:
            # Leave a short busy-wait tail to reduce overshoot on custom SIF pulses.
            time.sleep(coarse_sleep_s)
        while time.perf_counter() < deadline:
            pass

    def _validate_send_interval(
        self,
        interval_ms: int,
        min_interval_ms: int,
        max_interval_ms: int,
    ) -> str:
        """校验协议声明的循环发送间隔及当前输入值。"""

        if (
            isinstance(min_interval_ms, bool)
            or not isinstance(min_interval_ms, int)
            or isinstance(max_interval_ms, bool)
            or not isinstance(max_interval_ms, int)
            or min_interval_ms <= 0
            or max_interval_ms < min_interval_ms
        ):
            return "发送间隔约束配置无效"

        if (
            isinstance(interval_ms, bool)
            or not isinstance(interval_ms, int)
            or not (min_interval_ms <= interval_ms <= max_interval_ms)
        ):
            return f"发送间隔必须在{min_interval_ms}ms-{max_interval_ms}ms范围内"

        return ""

    def start_cyclic_send(
        self,
        frame_data: List[int],
        interval_ms: int = 500,
        send_mode: str = SEND_MODE_UART,
        min_interval_ms: int = MIN_SEND_INTERVAL_MS,
        max_interval_ms: int = MAX_SEND_INTERVAL_MS,
    ) -> Tuple[bool, str]:
        return self.start_cyclic_send_sequence(
            [frame_data],
            interval_ms,
            send_mode,
            min_interval_ms,
            max_interval_ms,
        )

    def start_cyclic_send_sequence(
        self,
        frame_sequence: List[List[int]],
        interval_ms: int = 500,
        send_mode: str = SEND_MODE_UART,
        min_interval_ms: int = MIN_SEND_INTERVAL_MS,
        max_interval_ms: int = MAX_SEND_INTERVAL_MS,
    ) -> Tuple[bool, str]:
        if not self.is_connected or self.serial_port is None:
            return False, "串口未连接"
        if not isinstance(frame_sequence, (list, tuple)):
            return False, "循环数据包组必须是帧列表"
        if not frame_sequence:
            return False, "循环数据包组不能为空"
        if not isinstance(send_mode, str) or send_mode not in SUPPORTED_SEND_MODES:
            return False, f"不支持的发送模式: {send_mode}"

        normalized_frames: List[List[int]] = []
        for index, frame_data in enumerate(frame_sequence, start=1):
            normalized_frame, error_msg = self._normalize_frame_for_mode(
                frame_data,
                send_mode,
                label=f"第{index}组数据包",
            )
            if normalized_frame is None:
                return False, error_msg
            normalized_frames.append(normalized_frame)

        interval_error = self._validate_send_interval(
            interval_ms,
            min_interval_ms,
            max_interval_ms,
        )
        if interval_error:
            return False, interval_error

        self.cyclic_data = normalized_frames[0].copy()
        self.cyclic_frame_sequence = normalized_frames
        self.cyclic_frame_index = 0
        self.cyclic_send_mode = send_mode
        self.send_interval_ms = interval_ms
        self.cyclic_min_interval_ms = min_interval_ms
        self.cyclic_max_interval_ms = max_interval_ms
        self.send_count = 0

        self.send_timer.start(interval_ms)
        return True, ""

    def update_cyclic_send_interval(self, interval_ms: int) -> Tuple[bool, str]:
        if not self.is_cyclic_sending():
            return False, "当前没有正在运行的循环发送"

        interval_error = self._validate_send_interval(
            interval_ms,
            self.cyclic_min_interval_ms,
            self.cyclic_max_interval_ms,
        )
        if interval_error:
            return False, interval_error

        self.send_interval_ms = interval_ms
        self.send_timer.start(interval_ms)
        return True, ""

    def stop_cyclic_send(self):
        self.send_timer.stop()
        self.cyclic_data = None
        self.cyclic_frame_sequence = []
        self.cyclic_frame_index = 0
        self.cyclic_send_mode = SEND_MODE_UART
        self.cyclic_min_interval_ms = MIN_SEND_INTERVAL_MS
        self.cyclic_max_interval_ms = MAX_SEND_INTERVAL_MS

    def _get_next_cyclic_frame(self) -> Optional[List[int]]:
        if not self.cyclic_frame_sequence:
            return None

        frame_data = self.cyclic_frame_sequence[self.cyclic_frame_index].copy()
        self.cyclic_frame_index = (self.cyclic_frame_index + 1) % len(self.cyclic_frame_sequence)
        self.cyclic_data = frame_data.copy()
        return frame_data

    def _send_cyclic_data(self):
        if not self.cyclic_frame_sequence:
            self.stop_cyclic_send()
            return
        if not self.is_connected:
            self.stop_cyclic_send()
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
        if (
            not isinstance(tosc_us, bool)
            and isinstance(tosc_us, int)
            and 32 <= tosc_us <= 320
        ):
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
        self.detection_timer = QTimer(self)
        self.detection_timer.timeout.connect(self._check_ports)

    def start_detection(self, interval_ms: int = 2000):
        self._check_ports()
        self.detection_timer.start(interval_ms)

    def stop_detection(self):
        self.detection_timer.stop()

    def _check_ports(self):
        try:
            current_ports = _enumerate_serial_ports()

            if len(current_ports) != len(self.last_ports) or any(
                p1.port != p2.port for p1, p2 in zip(current_ports, self.last_ports)
            ):
                self.last_ports = current_ports
                self.ports_changed.emit(current_ports)
        except Exception:
            pass
