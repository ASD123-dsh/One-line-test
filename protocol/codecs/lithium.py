#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""协议 lithium 的帧编码、位映射与流水号规则。"""

from typing import List, Tuple
from ..models import StatusBits


class LithiumCodec:
    """由兼容处理器提供共享状态，本模块不保存界面或串口对象。"""

    def _generate_lithium_bms_frame(self, status: StatusBits) -> Tuple[bool, List[int], str]:
        """处理本协议数据，保持原有字段编码、校验和调用行为。"""

        is_valid, error_msg = self.validate_status_bits(status)
        if not is_valid:
            return False, [], error_msg

        frame = [0] * 12
        frame[0] = 0x03
        frame[1] = 0x01
        frame[2] = self._encode_lithium_bms_status1(status)
        frame[3] = self._encode_lithium_bms_cell_voltage(status.lithium_bms_max_cell_voltage_v)
        frame[4] = status.soc_percent & 0xFF
        frame[5] = max(0, min(255, int(round(status.lithium_bms_total_voltage_v))))
        frame[6] = self._encode_lithium_bms_temperature(status.lithium_bms_max_temp_c)
        frame[7] = self._encode_lithium_bms_temperature(status.lithium_bms_min_temp_c)
        frame[8] = (status.lithium_bms_cycle_count >> 8) & 0xFF
        frame[9] = status.lithium_bms_cycle_count & 0xFF
        frame[10] = self._encode_lithium_bms_cell_voltage(status.lithium_bms_min_cell_voltage_v)
        frame[11] = self._xor_checksum(frame[:11])
        return True, frame, ""

    def _encode_lithium_bms_status1(self, status: StatusBits) -> int:
        """处理本协议数据，保持原有字段编码、校验和调用行为。"""

        value = 0
        if status.lithium_bms_alarm_enable:
            value |= 0x80
        if status.lithium_bms_high_temp_alarm:
            value |= 0x40
        if status.lithium_bms_low_temp_alarm:
            value |= 0x20
        if status.lithium_bms_soh_low:
            value |= 0x10
        if status.lithium_bms_mos_fault:
            value |= 0x08
        if status.lithium_bms_short_circuit_fault:
            value |= 0x04
        return value

    def _is_lithium_bms_cell_voltage_encodable(self, voltage_v: float) -> bool:
        """处理本协议数据，保持原有字段编码、校验和调用行为。"""

        raw_value = int(round(voltage_v * 100)) - 185
        return 0 <= raw_value <= 255

    def _encode_lithium_bms_cell_voltage(self, voltage_v: float) -> int:
        """处理本协议数据，保持原有字段编码、校验和调用行为。"""

        raw_value = int(round(voltage_v * 100)) - 185
        return max(0, min(255, raw_value))

    def _encode_lithium_bms_temperature(self, temp_c: int) -> int:
        """处理本协议数据，保持原有字段编码、校验和调用行为。"""

        return self._encode_sign_magnitude_byte(temp_c)
