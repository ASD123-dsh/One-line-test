#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""协议 battery 的帧编码、位映射与流水号规则。"""

from typing import List, Tuple
from ..models import StatusBits


class BatteryCodec:
    """由兼容处理器提供共享状态，本模块不保存界面或串口对象。"""

    def _generate_battery_single_wire_frame(
        self, status: StatusBits
    ) -> Tuple[bool, List[int], str]:
        """生成电池单线测试帧，保持 0x00 数据头并区分累加和与异或校验。"""

        is_valid, error_msg = self.validate_status_bits(status)
        if not is_valid:
            return False, [], error_msg

        frame = [0] * 6
        # 数据头保持规格书要求的 0x00，避免非零头影响设备识别。
        frame[0] = 0x00
        frame[1] = status.soc_percent & 0xFF
        # 仅 BYTE3-5 默认填 0x01，解决其他数据全零时 SUM 与 XOR 相同的问题。
        # SOC 为 0-100 时，SUM = SOC + 3，XOR = SOC ^ 1，两者始终不同。
        frame[2] = 0x01
        frame[3] = 0x01
        frame[4] = 0x01
        frame[5] = self._sum_checksum(frame[:5])
        return True, frame, ""
