#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""协议 xinri 的帧编码、位映射与流水号规则。"""

from typing import List, Tuple
from ..models import StatusBits


class XinriCodec:
    """由兼容处理器提供共享状态，本模块不保存界面或串口对象。"""

    def _generate_xinri_frame(self, status: StatusBits) -> Tuple[bool, List[int], str]:
        """处理本协议数据，保持原有字段编码、校验和调用行为。"""

        is_valid, error_msg = self.validate_status_bits(status)
        if not is_valid:
            return False, [], error_msg

        hall_count = self._resolve_hall_count(status)
        frame = [0] * 12
        frame[0] = 0x08
        frame[1] = 0x61
        frame[2] = self._encode_xinri_status1(status)
        frame[3] = self._encode_xinri_status2(status)
        frame[4] = self._encode_xinri_status3(status)
        frame[5] = self._encode_xinri_status4(status)
        frame[6] = self._encode_xinri_current(status.current_a)
        frame[7] = (hall_count >> 8) & 0xFF
        frame[8] = hall_count & 0xFF
        frame[9] = 0x00
        frame[10] = 0x00
        frame[11] = self._xor_checksum(frame[:11])
        return True, frame, ""

    def _encode_xinri_current(self, current_a: float) -> int:
        """处理本协议数据，保持原有字段编码、校验和调用行为。"""

        raw_value = round(abs(current_a) * 5)
        return max(0, min(255, raw_value))

    def _encode_xinri_status1(self, status: StatusBits) -> int:
        """处理本协议数据，保持原有字段编码、校验和调用行为。"""

        value = 0
        if status.p_gear_protect:
            value |= 0x08
        if status.low_voltage_alarm or status.under_voltage:
            value |= 0x04
        return value

    def _encode_xinri_status2(self, status: StatusBits) -> int:
        """处理本协议数据，保持原有字段编码、校验和调用行为。"""

        value = 0
        if status.hall_fault:
            value |= 0x40
        if status.throttle_fault:
            value |= 0x20
        if status.controller_fault:
            value |= 0x10
        if status.cruise:
            value |= 0x04
        return value

    def _encode_xinri_status3(self, status: StatusBits) -> int:
        """处理本协议数据，保持原有字段编码、校验和调用行为。"""

        value = 0
        if status.speed_mode & 0x04:
            value |= 0x80
        if status.brake:
            value |= 0x20
        value |= status.speed_mode & 0x03
        return value

    def _encode_xinri_status4(self, status: StatusBits) -> int:
        """处理本协议数据，保持原有字段编码、校验和调用行为。"""

        return 0x40 if status.one_key_enable else 0x00
