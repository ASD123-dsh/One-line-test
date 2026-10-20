#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""协议 jingxian 的帧编码、位映射与流水号规则。"""

from typing import List, Tuple
from ..definitions import (
    PROTOCOL_JINGXIAN,
)
from ..models import StatusBits


class JingxianCodec:
    """由兼容处理器提供共享状态，本模块不保存界面或串口对象。"""

    def get_current_jingxian_sequence(self) -> int:
        """获取当前精显协议序号。"""

        return self._jingxian_sequence_counter

    def get_next_jingxian_sequence(self) -> int:
        """获取下一精显协议序号并递增。"""

        current_seq = self._jingxian_sequence_counter
        self._jingxian_sequence_counter = (self._jingxian_sequence_counter + 1) & 0xFF
        return current_seq

    def reset_jingxian_sequence(self, start_value: int = 1):
        """重置精显协议序号。"""

        if not (0 <= start_value <= 255):
            raise ValueError("精显协议序号起始值必须在 0-255 范围内")
        self._jingxian_sequence_counter = start_value

    def jingxian_pluscode_encrypt(self, sequence: int) -> int:
        """精显协议 PlusCod 加密算法。"""

        plus_code = (sequence + 0x9C) & 0xFF
        plus_code ^= 0xF7
        plus_code = (plus_code + 0xCF) & 0xFF
        plus_code ^= 0xCA
        plus_code ^= 0xBB
        plus_code = (plus_code + 0x0B) & 0xFF
        plus_code ^= 0xAA
        return plus_code & 0x7F

    def _generate_jingxian_frame_for_send(
        self, status: StatusBits
    ) -> Tuple[bool, List[int], str]:
        """生成精显发送帧，并按原规则递增序号。"""

        return self._generate_jingxian_frame(status, preview=False)

    def _generate_jingxian_frame_for_preview(
        self, status: StatusBits
    ) -> Tuple[bool, List[int], str]:
        """生成精显预览帧，不递增序号。"""

        return self._generate_jingxian_frame(status, preview=True)

    def _generate_jingxian_frame(
        self, status: StatusBits, preview: bool
    ) -> Tuple[bool, List[int], str]:
        """处理本协议数据，保持原有字段编码、校验和调用行为。"""

        is_valid, error_msg = self.validate_status_bits(status)
        if not is_valid:
            return False, [], error_msg

        sequence = (
            self.get_current_jingxian_sequence() if preview else self.get_next_jingxian_sequence()
        )
        plus_code = self.jingxian_pluscode_encrypt(sequence & 0xFF)
        hall_count = self._resolve_hall_count(status)

        frame = [0] * 12
        frame[0] = 0x07
        frame[1] = sequence & 0xFF
        frame[2] = self._encode_jingxian_status1(status)
        frame[3] = (self._encode_generic_status2(status, include_walk_mode=True) + plus_code) & 0xFF
        frame[4] = (self._encode_generic_status3(status, PROTOCOL_JINGXIAN) + plus_code) & 0xFF
        frame[5] = (self._encode_generic_status4(status, PROTOCOL_JINGXIAN) + plus_code) & 0xFF
        frame[6] = self._encode_signed_current(status.current_a)
        frame[7] = (((hall_count >> 8) & 0xFF) + plus_code) & 0xFF
        frame[8] = ((hall_count & 0xFF) + plus_code) & 0xFF
        frame[9] = ((status.voltage_percentage & 0xFF) + plus_code) & 0xFF
        frame[10] = ((status.current_percentage & 0xFF) + plus_code) & 0xFF
        frame[11] = self._xor_checksum(frame[:11])
        return True, frame, ""

    def _encode_jingxian_status1(self, status: StatusBits) -> int:
        """处理本协议数据，保持原有字段编码、校验和调用行为。"""

        value = 0
        if status.side_stand:
            value |= 0x08
        if status.p_gear_protect:
            value |= 0x02
        return value
