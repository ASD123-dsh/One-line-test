#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""协议 tailing 的帧编码、位映射与流水号规则。"""

from typing import List, Tuple
from ..definitions import PROTOCOL_TAILING_Y34B
from ..models import StatusBits


class TailingCodec:
    """由兼容处理器提供共享状态，本模块不保存界面或串口对象。"""

    def _generate_tailing_y34b_frame(self, status: StatusBits) -> Tuple[bool, List[int], str]:
        """处理本协议数据，保持原有字段编码、校验和调用行为。"""

        is_valid, error_msg = self.validate_status_bits(status)
        if not is_valid:
            return False, [], error_msg

        speed_word = self._resolve_tailing_data67_word(status)
        frame = [0] * 13
        frame[0] = 0x08
        frame[1] = 0x61
        frame[2] = self._encode_tailing_status1(status)
        frame[3] = self._encode_generic_status2(status, include_walk_mode=True)
        frame[4] = self._encode_generic_status3(status, PROTOCOL_TAILING_Y34B)
        frame[5] = self._encode_tailing_y34b_status4(status)
        frame[6] = self._encode_signed_current(status.current_a)
        frame[7] = (speed_word >> 8) & 0xFF
        frame[8] = speed_word & 0xFF
        frame[9] = self._encode_yige_soc(status)
        frame[10] = self._encode_voltage_mask(status)
        frame[11] = self._encode_tailing_status11(status)
        frame[12] = self._xor_checksum(frame[:12])
        return True, frame, ""

    def _generate_tailing_y34f_frame(self, status: StatusBits) -> Tuple[bool, List[int], str]:
        """处理本协议数据，保持原有字段编码、校验和调用行为。"""

        is_valid, error_msg = self.validate_status_bits(status)
        if not is_valid:
            return False, [], error_msg

        speed_word = self._resolve_tailing_data67_word(status)
        voltage_raw = max(0, min(65535, int(round(status.tailing_real_time_voltage_v * 10))))

        frame = [0] * 15
        frame[0] = 0x08
        frame[1] = 0x61
        frame[2] = self._encode_tailing_status1(status)
        frame[3] = self._encode_tailing_y34f_status2(status)
        frame[4] = self._encode_tailing_y34f_status3(status)
        frame[5] = self._encode_tailing_y34f_status4(status)
        frame[6] = self._encode_signed_current(status.current_a)
        frame[7] = (speed_word >> 8) & 0xFF
        frame[8] = speed_word & 0xFF
        frame[9] = self._encode_yige_soc(status)
        frame[10] = self._encode_voltage_mask(status)
        frame[11] = self._encode_tailing_y34f_status11(status)
        frame[12] = (voltage_raw >> 8) & 0xFF
        frame[13] = voltage_raw & 0xFF
        frame[14] = self._xor_checksum(frame[:14])
        return True, frame, ""

    def _encode_tailing_status1(self, status: StatusBits) -> int:
        """处理本协议数据，保持原有字段编码、校验和调用行为。"""

        value = 0
        if status.side_stand:
            value |= 0x08
        if status.p_gear_protect:
            value |= 0x02
        if status.tailing_national_standard:
            value |= 0x01
        return value

    def _encode_tailing_y34b_status4(self, status: StatusBits) -> int:
        """处理本协议数据，保持原有字段编码、校验和调用行为。"""

        value = 0
        if status.cloud_power_mode:
            value |= 0x80
        if status.tailing_actual_speed_mode:
            value |= 0x40
        if status.ekk_enable:
            value |= 0x20
        if status.over_current:
            value |= 0x10
        if status.stall_protect:
            value |= 0x08
        if status.reverse:
            value |= 0x04
        if status.electronic_brake:
            value |= 0x02
        return value

    def _encode_tailing_y34f_status2(self, status: StatusBits) -> int:
        """处理本协议数据，保持原有字段编码、校验和调用行为。"""

        value = 0
        if status.walk_mode:
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
        if status.tailing_tire_pressure_low:
            value |= 0x02
        return value

    def _encode_tailing_y34f_status3(self, status: StatusBits) -> int:
        """处理本协议数据，保持原有字段编码、校验和调用行为。"""

        value = 0
        if status.gear_four:
            value |= 0x80
        if status.tailing_tcs_indicator:
            value |= 0x40
        if status.brake:
            value |= 0x20
        if status.tailing_hdc_indicator:
            value |= 0x10
        if status.regen_charging:
            value |= 0x08
        value |= status.speed_mode & 0x03
        return value

    def _encode_tailing_y34f_status4(self, status: StatusBits) -> int:
        """处理本协议数据，保持原有字段编码、校验和调用行为。"""

        value = 0
        if status.cloud_power_mode:
            value |= 0x80
        if status.tailing_actual_speed_mode:
            value |= 0x40
        if status.tailing_dual_undervoltage:
            value |= 0x20
        if status.over_current:
            value |= 0x10
        if status.stall_protect:
            value |= 0x08
        if status.reverse:
            value |= 0x04
        value |= status.tailing_seat_state & 0x03
        return value

    def _encode_tailing_status11(self, status: StatusBits) -> int:
        """处理本协议数据，保持原有字段编码、校验和调用行为。"""

        value = 0
        if status.tailing_dual_soc:
            value |= 0x08
        if status.tailing_display_sleep:
            value |= 0x04
        if status.tailing_speed_15kmh_warning:
            value |= 0x02
        if status.tailing_brake_fault:
            value |= 0x01
        return value

    def _encode_tailing_y34f_status11(self, status: StatusBits) -> int:
        """处理本协议数据，保持原有字段编码、校验和调用行为。"""

        value = 0
        if status.tailing_display_voltage_from_data:
            value |= 0x80
        if status.tailing_battery_over_temp:
            value |= 0x40
        if status.tailing_battery_over_current:
            value |= 0x20
        if status.tailing_battery_over_voltage:
            value |= 0x10
        value |= self._encode_tailing_status11(status)
        return value

    def _resolve_tailing_data67_word(self, status: StatusBits) -> int:
        """处理本协议数据，保持原有字段编码、校验和调用行为。"""

        if status.tailing_actual_speed_mode:
            return max(0, min(65535, int(round(status.speed_kmh * 10))))
        return self._resolve_hall_count(status)
