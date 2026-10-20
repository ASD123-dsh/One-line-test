#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""协议 dongwei 的帧编码、位映射与流水号规则。"""

from typing import List, Tuple
from ..definitions import (
    PROTOCOL_DONGWEI_GTXH,
)
from ..models import StatusBits


class DongweiCodec:
    """由兼容处理器提供共享状态，本模块不保存界面或串口对象。"""

    def _generate_dongwei_gtxh_frame(self, status: StatusBits) -> Tuple[bool, List[int], str]:
        """处理本协议数据，保持原有字段编码、校验和调用行为。"""

        is_valid, error_msg = self.validate_status_bits(status)
        if not is_valid:
            return False, [], error_msg

        hall_count = self._resolve_hall_count(status)
        frame = [0] * 12
        frame[0] = 0x08
        frame[1] = 0x61
        frame[2] = self._encode_dongwei_status1(status)
        frame[3] = self._encode_generic_status2(status)
        frame[4] = self._encode_generic_status3(status, PROTOCOL_DONGWEI_GTXH)
        frame[5] = self._encode_generic_status4(status, PROTOCOL_DONGWEI_GTXH)
        frame[6] = self._encode_dongwei_current(status.current_a)
        frame[7] = (hall_count >> 8) & 0xFF
        frame[8] = hall_count & 0xFF
        frame[9] = status.soc_percent & 0xFF
        frame[10] = status.current_percentage & 0xFF
        frame[11] = self._xor_checksum(frame[:11])
        return True, frame, ""

    def _encode_dongwei_status1(self, status: StatusBits) -> int:
        """处理本协议数据，保持原有字段编码、校验和调用行为。"""

        value = 0
        if status.p_gear_protect:
            value |= 0x08
        value |= self._encode_dongwei_voltage_state(status)
        return value

    def _encode_dongwei_current(self, current_a: float) -> int:
        """处理本协议数据，保持原有字段编码、校验和调用行为。"""

        scaled_value = round(current_a * 5)
        scaled_value = max(-128, min(127, scaled_value))
        return scaled_value & 0xFF

    def _encode_dongwei_voltage_state(self, status: StatusBits) -> int:
        """处理本协议数据，保持原有字段编码、校验和调用行为。"""

        if status.voltage_48v:
            return 0x02
        if status.voltage_60v:
            return 0x01
        if status.voltage_72v:
            return 0x03
        if status.voltage_80v:
            return 0x04
        if status.voltage_96v:
            return 0x05
        return 0x00
