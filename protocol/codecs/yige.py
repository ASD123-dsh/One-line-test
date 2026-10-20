#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""协议 yige 的帧编码、位映射与流水号规则。"""

from typing import List, Tuple
from ..definitions import (
    PROTOCOL_WUXI_YIGE,
)
from ..models import StatusBits


class YigeCodec:
    """由兼容处理器提供共享状态，本模块不保存界面或串口对象。"""

    def _generate_wuxi_yige_frame(self, status: StatusBits) -> Tuple[bool, List[int], str]:
        """处理本协议数据，保持原有字段编码、校验和调用行为。"""

        is_valid, error_msg = self.validate_status_bits(status)
        if not is_valid:
            return False, [], error_msg

        hall_count = self._resolve_hall_count(status)
        frame = [0] * 12
        frame[0] = 0x10
        frame[1] = 0x95
        frame[2] = self._encode_yige_status1(status)
        frame[3] = self._encode_generic_status2(status, include_walk_mode=True)
        frame[4] = self._encode_generic_status3(status, PROTOCOL_WUXI_YIGE)
        frame[5] = self._encode_generic_status4(status, PROTOCOL_WUXI_YIGE)
        frame[6] = self._encode_signed_current(status.current_a)
        frame[7] = (hall_count >> 8) & 0xFF
        frame[8] = hall_count & 0xFF
        frame[9] = self._encode_yige_soc(status)
        frame[10] = self._encode_voltage_mask(status)
        frame[11] = self._xor_checksum(frame[:11])
        return True, frame, ""

    def _encode_yige_status1(self, status: StatusBits) -> int:
        """处理本协议数据，保持原有字段编码、校验和调用行为。"""

        value = 0
        if status.side_stand:
            value |= 0x08
        if status.p_gear_protect:
            value |= 0x02
        return value

    def _encode_yige_soc(self, status: StatusBits) -> int:
        """处理本协议数据，保持原有字段编码、校验和调用行为。"""

        if status.lithium_soc_mode:
            return 0x80 | (status.soc_percent & 0x7F)
        return 0x00
