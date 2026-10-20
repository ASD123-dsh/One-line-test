#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""协议 hangzhou 的帧编码、位映射与流水号规则。"""

from typing import List, Tuple
from ..definitions import (
    PROTOCOL_HANGZHOU_ANXIAN,
)
from ..models import StatusBits


class HangzhouCodec:
    """由兼容处理器提供共享状态，本模块不保存界面或串口对象。"""

    def get_current_hangzhou_sequence(self) -> int:
        """获取当前杭州安显序号。"""

        return self._hangzhou_sequence_counter

    def get_next_hangzhou_sequence(self) -> int:
        """获取下一杭州安显序号并递增。"""

        current_seq = self._hangzhou_sequence_counter
        self._hangzhou_sequence_counter = (self._hangzhou_sequence_counter % 4095) + 1
        return current_seq

    def reset_hangzhou_sequence(self, start_value: int = 1):
        """重置杭州安显序号。"""

        if not (1 <= start_value <= 4095):
            raise ValueError("杭州安显序号起始值必须在 1-4095 范围内")
        self._hangzhou_sequence_counter = start_value

    def hangzhou_pluscode_encrypt(self, sequence: int) -> int:
        """杭州安显协议加密字节算法。"""

        seq_low = sequence & 0xFF
        seq_high = (sequence >> 8) & 0x0F

        pulse = (seq_low + 0x6B) & 0xFF
        pulse ^= 0x54
        pulse = (pulse + 0x19) & 0xFF
        pulse ^= 0x25
        pulse = (pulse + seq_high) & 0xFF
        pulse ^= 0x6B
        pulse = (pulse + 0x3B) & 0xFF
        pulse ^= 0x3A
        pulse &= 0x7F
        return pulse

    def _generate_hangzhou_frame_for_send(
        self, status: StatusBits
    ) -> Tuple[bool, List[int], str]:
        """生成杭州安显发送帧，并按原规则递增序号。"""

        return self._generate_hangzhou_frame(status, preview=False)

    def _generate_hangzhou_frame_for_preview(
        self, status: StatusBits
    ) -> Tuple[bool, List[int], str]:
        """生成杭州安显预览帧，不递增序号。"""

        return self._generate_hangzhou_frame(status, preview=True)

    def _generate_hangzhou_frame(
        self, status: StatusBits, preview: bool
    ) -> Tuple[bool, List[int], str]:
        """处理本协议数据，保持原有字段编码、校验和调用行为。"""

        is_valid, error_msg = self.validate_status_bits(status)
        if not is_valid:
            return False, [], error_msg

        sequence = (
            self.get_current_hangzhou_sequence() if preview else self.get_next_hangzhou_sequence()
        )
        pulse = self.hangzhou_pluscode_encrypt(sequence)
        hall_count = self._resolve_hall_count(status)

        seq_low = sequence & 0xFF
        seq_high = (sequence >> 8) & 0x0F

        frame = [0] * 12
        frame[0] = 0x08
        frame[1] = seq_low
        frame[2] = ((seq_high & 0x0F) << 4) | self._encode_hangzhou_status1(status)
        frame[3] = (self._encode_generic_status2(status) + pulse) & 0xFF
        frame[4] = (self._encode_generic_status3(status, PROTOCOL_HANGZHOU_ANXIAN) + pulse) & 0xFF
        frame[5] = (self._encode_generic_status4(status, PROTOCOL_HANGZHOU_ANXIAN) + pulse) & 0xFF
        frame[6] = self._encode_signed_current(status.current_a)
        frame[7] = (((hall_count >> 8) & 0xFF) + pulse) & 0xFF
        frame[8] = ((hall_count & 0xFF) + pulse) & 0xFF
        frame[9] = ((status.voltage_percentage & 0xFF) + pulse) & 0xFF
        frame[10] = (self._encode_voltage_mask(status) + pulse) & 0xFF
        frame[11] = self._xor_checksum(frame[:11])
        return True, frame, ""

    def _encode_hangzhou_status1(self, status: StatusBits) -> int:
        """处理本协议数据，保持原有字段编码、校验和调用行为。"""

        value = 0
        if status.protocol_speed_limit:
            value |= 0x04
        if status.p_gear_protect:
            value |= 0x02
        return value
