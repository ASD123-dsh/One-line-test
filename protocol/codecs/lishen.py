#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""锂神单线 BMS V1.1.1 的六字节编码；单线波形由转码硬件生成。"""

from typing import List, Tuple

from ..models import StatusBits


class LishenBmsCodec:
    """独立维护锂神字段，不复用旧电池协议的非零测试保留位。"""

    def _generate_lishen_bms_frame(self, status: StatusBits) -> Tuple[bool, List[int], str]:
        """按规格书第 2 页编码，温度使用有符号八位补码，校验取累加和低八位。"""
        is_valid, error_msg = self.validate_status_bits(status)
        if not is_valid:
            return False, [], error_msg

        frame = [
            0x00,  # Byte1 保留，必须固定为 00，不能套用其他协议的数据头。
            status.soc_percent,
            status.lishen_total_voltage_v,
            status.lishen_temperature_c & 0xFF,  # 例如 -10℃ 编码为 F6，不是原码 8A。
            0x00,  # Byte5 保留，自动生成帧时不能使用旧电池协议的测试默认值。
        ]
        frame.append(self._sum_checksum(frame))
        return True, frame, ""
