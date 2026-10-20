#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""协议 xinchi 的帧编码、位映射与流水号规则。"""

from typing import List, Tuple
from ..models import StatusBits


class XinchiCodec:
    """由兼容处理器提供共享状态，本模块不保存界面或串口对象。"""

    def _generate_xinchi_frame(self, status: StatusBits) -> Tuple[bool, List[int], str]:
        """处理本协议数据，保持原有字段编码、校验和调用行为。"""

        is_valid, error_msg = self.validate_status_bits(status)
        if not is_valid:
            return False, [], error_msg

        voltage_raw = max(0, min(65535, int(round(status.xinchi_total_voltage_v * 10))))

        frame = [0] * 10
        frame[0] = 0x3A
        frame[1] = self._encode_xinchi_status0(status)
        frame[2] = status.soc_percent & 0xFF
        frame[3] = status.xinchi_cycle_count & 0xFF
        frame[4] = (status.xinchi_cycle_count >> 8) & 0xFF
        frame[5] = status.xinchi_temperature_c & 0xFF
        frame[6] = voltage_raw & 0xFF
        frame[7] = (voltage_raw >> 8) & 0xFF
        frame[8] = status.xinchi_total_current_a & 0xFF
        frame[9] = self._sum_checksum(frame[:9])
        return True, frame, ""

    def _encode_xinchi_status0(self, status: StatusBits) -> int:
        """处理本协议数据，保持原有字段编码、校验和调用行为。"""

        value = 0
        if status.xinchi_charge_mos:
            value |= 0x80
        if status.xinchi_discharge_mos:
            value |= 0x40
        if status.xinchi_high_temp_fault:
            value |= 0x20
        if status.xinchi_low_temp_fault:
            value |= 0x10
        if status.xinchi_over_voltage_fault:
            value |= 0x08
        if status.xinchi_under_voltage_fault:
            value |= 0x04
        if status.xinchi_bms_fault:
            value |= 0x01
        return value
