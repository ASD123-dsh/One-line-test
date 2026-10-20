#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""编码与参数校验共享的协议固定常量，不持有运行状态。"""

VOLTAGE_OPTIONS = (
    ("voltage_36v", 0x01),
    ("voltage_48v", 0x02),
    ("voltage_60v", 0x04),
    ("voltage_64v", 0x08),
    ("voltage_72v", 0x10),
    ("voltage_80v", 0x20),
    ("voltage_84v", 0x40),
    ("voltage_96v", 0x80),
)
SXSY_P_GEAR_STATES = frozenset((0x00, 0x0D, 0x0E, 0x0F))
