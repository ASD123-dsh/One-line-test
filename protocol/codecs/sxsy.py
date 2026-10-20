#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""协议 sxsy 的帧编码、位映射与流水号规则。"""

from typing import List, Tuple
from ..definitions import (
    PROTOCOL_SXSY,
)
from ..models import StatusBits


class SxsyCodec:
    """由兼容处理器提供共享状态，本模块不保存界面或串口对象。"""

    def get_current_sxsy_sequence(self) -> int:
        """获取当前 SXSY 12 位流水号。"""

        return self._sxsy_sequence_counter

    def get_next_sxsy_sequence(self) -> int:
        """获取当前 SXSY 流水号，并按 12 位规则递增。"""

        current_seq = self._sxsy_sequence_counter
        self._sxsy_sequence_counter = (current_seq + 1) & 0x0FFF
        return current_seq

    def reset_sxsy_sequence(self, start_value: int = 1):
        """重置 SXSY 流水号。"""

        if (
            isinstance(start_value, bool)
            or not isinstance(start_value, int)
            or not (0 <= start_value <= 0x0FFF)
        ):
            raise ValueError("SXSY 流水号起始值必须在 0-4095 范围内")
        self._sxsy_sequence_counter = start_value

    def sxsy_pluscode_encrypt(self, sequence: int) -> int:
        """根据 SXSY 12 位流水号生成 7 位 PlusCode。"""

        if (
            isinstance(sequence, bool)
            or not isinstance(sequence, int)
            or not (0 <= sequence <= 0x0FFF)
        ):
            raise ValueError("SXSY 流水号必须在 0-4095 范围内")

        seq_low = sequence & 0xFF
        seq_high = (sequence >> 8) & 0x0F
        plus_code = (seq_low + 0x13) & 0xFF
        plus_code ^= 0x95
        plus_code = (plus_code + 0x97) & 0xFF
        plus_code ^= 0x6A
        plus_code = (plus_code + seq_high) & 0xFF
        plus_code ^= 0xFB
        plus_code = (plus_code + 0x45) & 0xFF
        plus_code ^= 0xAA
        return plus_code & 0x7F

    def _generate_sxsy_frame_for_send(
        self, status: StatusBits
    ) -> Tuple[bool, List[int], str]:
        """生成 SXSY 发送帧，并在成功校验后递增流水号。"""

        return self._generate_sxsy_frame(status, preview=False)

    def _generate_sxsy_frame_for_preview(
        self, status: StatusBits
    ) -> Tuple[bool, List[int], str]:
        """生成 SXSY 预览帧，不消耗流水号。"""

        return self._generate_sxsy_frame(status, preview=True)

    def _generate_sxsy_frame(
        self, status: StatusBits, preview: bool
    ) -> Tuple[bool, List[int], str]:
        """按 SXSY 规格生成 12 字节应用层载荷。"""

        is_valid, error_msg = self.validate_status_bits(status)
        if not is_valid:
            return False, [], error_msg

        sequence = self.get_current_sxsy_sequence()
        plus_code = self.sxsy_pluscode_encrypt(sequence)
        hall_count = self._resolve_hall_count(status)

        frame = [0] * 12
        frame[0] = 0x30
        frame[1] = sequence & 0xFF
        frame[2] = (
            (((sequence >> 8) & 0x0F) << 4)
            | self._encode_sxsy_status1(status)
        )
        frame[3] = (self._encode_generic_status2(status) + plus_code) & 0xFF
        frame[4] = (self._encode_sxsy_status3(status) + plus_code) & 0xFF
        frame[5] = (
            self._encode_generic_status4(status, PROTOCOL_SXSY) + plus_code
        ) & 0xFF
        # 文档仅给出最高位符号规则，此处按“符号位 + 7 位幅值”编码。
        frame[6] = self._encode_sign_magnitude_byte(status.current_a)
        frame[7] = (((hall_count >> 8) & 0xFF) + plus_code) & 0xFF
        frame[8] = ((hall_count & 0xFF) + plus_code) & 0xFF
        frame[9] = ((status.voltage_percentage & 0xFF) + plus_code) & 0xFF
        frame[10] = ((status.soc_percent & 0xFF) + plus_code) & 0xFF
        frame[11] = self._xor_checksum(frame[:11])
        if not preview:
            # 仅在整帧成功生成后提交流水号，畸形参数不得消耗发送序号。
            self.get_next_sxsy_sequence()
        return True, frame, ""

    def _encode_sxsy_status1(self, status: StatusBits) -> int:
        """编码 SXSY P 档枚举；0x00 用于兼容规格书示例。"""

        return status.sxsy_p_gear_state & 0x0F

    def _encode_sxsy_status3(self, status: StatusBits) -> int:
        """编码 SXSY 三速、运行状态和档位组合。"""

        value = 0
        if status.sxsy_three_speed:
            value |= 0x80
        if status.motor_running:
            value |= 0x40
        if status.brake:
            value |= 0x20
        if status.controller_protect:
            value |= 0x10
        if status.regen_charging:
            value |= 0x08
        if status.anti_runaway:
            value |= 0x04
        value |= status.speed_mode & 0x03
        return value
