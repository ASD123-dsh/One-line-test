#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""协议 shenzhouxing 的帧编码、位映射与流水号规则。"""

from typing import List, Tuple
from ..models import StatusBits


class ShenzhouxingCodec:
    """由兼容处理器提供共享状态，本模块不保存界面或串口对象。"""

    def _generate_shenzhouxing_frame(self, status: StatusBits) -> Tuple[bool, List[int], str]:
        """处理本协议数据，保持原有字段编码、校验和调用行为。"""

        is_valid, error_msg = self.validate_status_bits(status)
        if not is_valid:
            return False, [], error_msg

        hall_count = self._resolve_hall_count(status)
        frame = [0] * 15
        frame[0] = 0x1F
        frame[1] = 0xEE
        frame[2] = self._encode_shenzhouxing_status1(status)
        frame[3] = self._encode_shenzhouxing_status2(status)
        frame[4] = self._encode_shenzhouxing_status3(status)
        frame[5] = self._encode_shenzhouxing_status4(status)
        frame[6] = self._encode_signed_current(status.current_a)
        frame[7] = (hall_count >> 8) & 0xFF
        frame[8] = hall_count & 0xFF
        frame[9] = self._encode_shenzhouxing_status8(status)
        frame[10] = self._encode_voltage_mask(status)
        frame[11] = self._encode_shenzhouxing_data11(status)
        frame[12] = self._encode_shenzhouxing_data12(status)
        frame[13] = self._encode_shenzhouxing_data13(status)
        frame[14] = self._xor_checksum(frame[:14])
        return True, frame, ""

    def _encode_shenzhouxing_status1(self, status: StatusBits) -> int:
        """处理本协议数据，保持原有字段编码、校验和调用行为。"""

        value = 0
        if status.side_stand:
            value |= 0x08
        if status.shenzhouxing_hdc:
            value |= 0x04
        if status.p_gear_protect:
            value |= 0x02
        if status.shenzhouxing_hhc:
            value |= 0x01
        return value

    def _encode_shenzhouxing_status2(self, status: StatusBits) -> int:
        """处理本协议数据，保持原有字段编码、校验和调用行为。"""

        value = 0
        if status.shenzhouxing_tcs:
            value |= 0x80
        if status.hall_fault:
            value |= 0x40
        if status.throttle_fault:
            value |= 0x20
        if status.controller_fault:
            value |= 0x10
        if status.under_voltage:
            value |= 0x08
        if status.cruise:
            value |= 0x04
        if status.assist:
            value |= 0x02
        if status.motor_phase_loss:
            value |= 0x01
        return value

    def _encode_shenzhouxing_status3(self, status: StatusBits) -> int:
        """处理本协议数据，保持原有字段编码、校验和调用行为。"""

        value = 0
        if status.gear_four:
            value |= 0x80
        if status.motor_running:
            value |= 0x40
        if status.shenzhouxing_brake_fault:
            value |= 0x20
        if status.controller_protect:
            value |= 0x10
        if status.regen_charging:
            value |= 0x08
        if status.anti_runaway:
            value |= 0x04
        value |= status.speed_mode & 0x03
        return value

    def _encode_shenzhouxing_status4(self, status: StatusBits) -> int:
        """处理本协议数据，保持原有字段编码、校验和调用行为。"""

        value = 0
        if status.shenzhouxing_bluetooth:
            value |= 0x80
        if status.shenzhouxing_time_display:
            value |= 0x40
        if status.shenzhouxing_4g_signal_indicator:
            value |= 0x20
        if status.shenzhouxing_position_indicator:
            value |= 0x10
        if status.stall_protect:
            value |= 0x08
        if status.reverse:
            value |= 0x04
        if status.brake:
            value |= 0x02
        if status.speed_limit:
            value |= 0x01
        return value

    def _encode_shenzhouxing_status8(self, status: StatusBits) -> int:
        """处理本协议数据，保持原有字段编码、校验和调用行为。"""

        if status.lithium_soc_mode:
            return 0x80 | (status.soc_percent & 0x7F)
        return status.shenzhouxing_real_time_voltage_v & 0x7F

    def _encode_shenzhouxing_data11(self, status: StatusBits) -> int:
        """处理本协议数据，保持原有字段编码、校验和调用行为。"""

        hour = status.shenzhouxing_time_hour & 0x1F
        return ((status.shenzhouxing_signal_strength & 0x1F) << 3) | ((hour >> 2) & 0x07)

    def _encode_shenzhouxing_data12(self, status: StatusBits) -> int:
        """处理本协议数据，保持原有字段编码、校验和调用行为。"""

        hour = status.shenzhouxing_time_hour & 0x1F
        return ((hour & 0x03) << 6) | (status.shenzhouxing_time_minute & 0x3F)

    def _encode_shenzhouxing_data13(self, status: StatusBits) -> int:
        """处理本协议数据，保持原有字段编码、校验和调用行为。"""

        value = 0
        if status.shenzhouxing_push_assist:
            value |= 0x80
        if status.shenzhouxing_p_blink:
            value |= 0x40
        return value
