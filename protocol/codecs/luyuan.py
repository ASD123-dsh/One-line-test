#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""协议 luyuan 的帧编码、位映射与流水号规则。"""

from typing import List, Tuple
from ..models import StatusBits


class LuyuanCodec:
    """由兼容处理器提供共享状态，本模块不保存界面或串口对象。"""

    def _generate_luyuan_bms_frame(self, status: StatusBits) -> Tuple[bool, List[int], str]:
        """处理本协议数据，保持原有字段编码、校验和调用行为。"""

        is_valid, error_msg = self.validate_status_bits(status)
        if not is_valid:
            return False, [], error_msg

        current_raw = self._encode_luyuan_current(status.luyuan_current_a)

        frame = [0] * 15
        frame[0] = 0x3A
        frame[1] = self._encode_luyuan_status0(status)
        frame[2] = status.soc_percent & 0xFF
        frame[3] = status.luyuan_cycle_count & 0xFF
        frame[4] = (status.luyuan_cycle_count >> 8) & 0xFF
        frame[5] = self._encode_signed_byte(status.luyuan_temperature_c)
        frame[6] = status.luyuan_max_cell_voltage_mv & 0xFF
        frame[7] = (status.luyuan_max_cell_voltage_mv >> 8) & 0xFF
        frame[8] = status.luyuan_min_cell_voltage_mv & 0xFF
        frame[9] = (status.luyuan_min_cell_voltage_mv >> 8) & 0xFF
        frame[10] = current_raw & 0xFF
        frame[11] = (current_raw >> 8) & 0xFF
        frame[12] = status.luyuan_total_voltage_v & 0xFF
        frame[13] = status.luyuan_soh_percent & 0xFF
        frame[14] = self._sum_checksum(frame[:14])
        return True, frame, ""

    def _encode_luyuan_status0(self, status: StatusBits) -> int:
        """处理本协议数据，保持原有字段编码、校验和调用行为。"""

        value = 0
        if status.luyuan_charge_mos:
            value |= 0x80
        if status.luyuan_discharge_mos:
            value |= 0x40
        if status.luyuan_predischarge_mos:
            value |= 0x20
        if status.luyuan_charge_enable:
            value |= 0x10
        if status.luyuan_charger_connected:
            value |= 0x08
        return value

    def _is_luyuan_current_encodable(self, current_a: float) -> bool:
        """处理本协议数据，保持原有字段编码、校验和调用行为。"""

        magnitude = int(round(abs(current_a) * 100))
        return magnitude <= 0x7FFF

    def _encode_luyuan_current(self, current_a: float) -> int:
        """处理本协议数据，保持原有字段编码、校验和调用行为。"""

        magnitude = min(0x7FFF, int(round(abs(current_a) * 100)))
        if current_a < 0:
            return 0x8000 | magnitude
        return magnitude
