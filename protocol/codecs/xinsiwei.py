#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""协议 xinsiwei 的帧编码、位映射与流水号规则。"""

from typing import List, Tuple
from ..definitions import (
    PROTOCOL_CHANGZHOU_XINSIWEI,
)
from ..models import StatusBits


class XinsiweiCodec:
    """由兼容处理器提供共享状态，本模块不保存界面或串口对象。"""

    def get_current_xinsiwei_sequence(self) -> int:
        """获取当前常州新思维序号。"""

        return self._xinsiwei_sequence_counter

    def get_next_xinsiwei_sequence(self) -> int:
        """获取下一常州新思维序号并递增。"""

        current_seq = self._xinsiwei_sequence_counter
        self._xinsiwei_sequence_counter = (self._xinsiwei_sequence_counter % 4095) + 1
        return current_seq

    def reset_xinsiwei_sequence(self, start_value: int = 1):
        """重置常州新思维序号。"""

        if not (1 <= start_value <= 4095):
            raise ValueError("常州新思维序号起始值必须在 1-4095 范围内")
        self._xinsiwei_sequence_counter = start_value

    def xinsiwei_pluscode_encrypt(self, data_bytes: List[int]) -> int:
        """常州新思维协议 8 步 PlusCode 算法。"""

        if len(data_bytes) != 12:
            raise ValueError("常州新思维数据长度必须为 12 字节")

        step1 = data_bytes[0] ^ data_bytes[6]
        step2 = data_bytes[1] ^ data_bytes[7]
        step3 = data_bytes[2] ^ data_bytes[8]
        step4 = data_bytes[3] ^ data_bytes[9]
        step5 = data_bytes[4] ^ data_bytes[10]
        step6 = data_bytes[5] ^ data_bytes[11]
        step7 = (step1 + step2 + step3 + step4 + step5 + step6) & 0xFF
        step8 = sum(data_bytes) & 0xFF

        plus_code = 0
        for step in (step1, step2, step3, step4, step5, step6, step7, step8):
            plus_code ^= step
        return plus_code & 0xFF

    def generate_xinsiwei_frame_for_preview(self, status: StatusBits) -> Tuple[bool, List[int], str]:
        """生成常州新思维预览帧，不递增序号。"""

        preview_status = self._copy_status(status)
        preview_status.protocol_name = PROTOCOL_CHANGZHOU_XINSIWEI
        preview_status.xinsiwei_protocol = True
        preview_status.xinsiwei_sequence = self.get_current_xinsiwei_sequence()
        return self.generate_xinsiwei_frame(preview_status)

    def generate_xinsiwei_frame_with_auto_sequence(
        self, status: StatusBits
    ) -> Tuple[bool, List[int], str]:
        """生成常州新思维发送帧，自动递增序号。"""

        auto_status = self._copy_status(status)
        auto_status.protocol_name = PROTOCOL_CHANGZHOU_XINSIWEI
        auto_status.xinsiwei_protocol = True
        auto_status.xinsiwei_sequence = self.get_next_xinsiwei_sequence()
        return self.generate_xinsiwei_frame(auto_status)

    def generate_xinsiwei_frame(self, status: StatusBits) -> Tuple[bool, List[int], str]:
        """生成常州新思维完整帧。"""

        is_valid, error_msg = self.validate_status_bits(status)
        if not is_valid:
            return False, [], error_msg

        frame = [0] * 12
        frame[0] = 0x30
        frame[1] = status.xinsiwei_sequence & 0xFF
        frame[2] = ((status.xinsiwei_sequence >> 8) & 0x0F) << 4
        frame[2] |= self._encode_xinsiwei_status1(status)
        frame[3] = self._encode_generic_status2(status)
        frame[4] = self._encode_generic_status3(status, PROTOCOL_CHANGZHOU_XINSIWEI)
        frame[5] = self._encode_generic_status4(status, PROTOCOL_CHANGZHOU_XINSIWEI)
        frame[6] = self._encode_signed_current(status.current_a)
        frame[7] = (status.xinsiwei_hall_count >> 8) & 0xFF
        frame[8] = status.xinsiwei_hall_count & 0xFF
        frame[9] = (
            self._encode_soc_fault(PROTOCOL_CHANGZHOU_XINSIWEI)
            if status.soc_fault
            else (status.soc_percent & 0xFF)
        )
        frame[10] = self._encode_voltage_mask(status)
        frame[11] = self._xor_checksum(frame[:11])

        plus_code = self.xinsiwei_pluscode_encrypt(frame)
        for index in (3, 4, 5, 7, 8, 9, 10):
            frame[index] = (frame[index] + plus_code) & 0xFF
        frame[11] = self._xor_checksum(frame[:11])
        return True, frame, ""

    def _encode_xinsiwei_status1(self, status: StatusBits) -> int:
        """处理本协议数据，保持原有字段编码、校验和调用行为。"""

        value = 0
        if status.xinsiwei_reserved_d3:
            value |= 0x08
        if status.xinsiwei_reserved_d2:
            value |= 0x04
        if status.xinsiwei_reserved_d1:
            value |= 0x02
        if status.xinsiwei_reserved_d0:
            value |= 0x01
        return value
