#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
协议定义注册表。

集中维护协议名称、帧长度、校验方式、发送方式和帧生成入口。
"""

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping, Optional


PROTOCOL_RUILUN = "瑞轮协议"
PROTOCOL_FZ_SIF = "FZ-sif协议"
PROTOCOL_XINRI = "新日协议"
PROTOCOL_HANGZHOU_ANXIAN = "杭州安显协议"
PROTOCOL_CHANGZHOU_XINSIWEI = "常州新思维协议"
PROTOCOL_WUXI_YIGE = "无锡一格Y67协议"
PROTOCOL_TAILING_Y34B = "无锡台铃Y34B协议"
PROTOCOL_TAILING_Y34F = "无锡台铃Y34F协议"
PROTOCOL_SHENZHOUXING = "神州行协议"
PROTOCOL_YADEA = "雅迪协议"
PROTOCOL_YOUYIBAO = "优仪宝一线通协议"
PROTOCOL_JINGXIAN = "精显一线通协议"
PROTOCOL_DONGWEI_GTXH = "东威GTXH协议"
PROTOCOL_XINCHI = "芯驰BMS协议"
PROTOCOL_LUYUAN_BMS = "绿源BMS一线通协议"
PROTOCOL_LITHIUM_BMS = "一线通--锂电池BMS"
PROTOCOL_BATTERY_SINGLE_WIRE = "电池单线通讯协议"


@dataclass(frozen=True)
class ProtocolDefinition:
    """描述一个协议的不变元数据及帧生成入口。"""

    name: str
    frame_length: int
    checksum_mode: str
    send_mode: str
    generator_method: str
    preview_generator_method: Optional[str] = None
    soc_fault_value: Optional[int] = None
    min_send_interval_ms: int = 500
    max_send_interval_ms: int = 5000
    default_send_interval_ms: int = 500
    reset_send_interval_on_switch: bool = False

    def __post_init__(self):
        """在注册阶段拒绝不完整或自相矛盾的协议元数据。"""

        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("协议名称不能为空")
        if (
            isinstance(self.frame_length, bool)
            or not isinstance(self.frame_length, int)
            or self.frame_length <= 0
        ):
            raise ValueError("协议帧长度必须是正整数")
        if not all(
            isinstance(value, str) and bool(value.strip())
            for value in (self.checksum_mode, self.send_mode, self.generator_method)
        ):
            raise ValueError("协议校验、发送方式和生成入口不能为空")
        if (
            self.preview_generator_method is not None
            and (
                not isinstance(self.preview_generator_method, str)
                or not self.preview_generator_method.strip()
            )
        ):
            raise ValueError("协议预览生成入口必须是非空字符串")
        if (
            self.soc_fault_value is not None
            and (
                isinstance(self.soc_fault_value, bool)
                or not isinstance(self.soc_fault_value, int)
                or not (0 <= self.soc_fault_value <= 0xFF)
            )
        ):
            raise ValueError("SOC 故障编码必须是 0-255 的整数")
        if not isinstance(self.reset_send_interval_on_switch, bool):
            raise ValueError("协议切换周期复位策略必须是布尔值")
        interval_values = (
            self.min_send_interval_ms,
            self.max_send_interval_ms,
            self.default_send_interval_ms,
        )
        if (
            any(
                isinstance(value, bool) or not isinstance(value, int)
                for value in interval_values
            )
            or self.min_send_interval_ms <= 0
            or self.max_send_interval_ms < self.min_send_interval_ms
            or not (
                self.min_send_interval_ms
                <= self.default_send_interval_ms
                <= self.max_send_interval_ms
            )
        ):
            raise ValueError("协议发送间隔配置无效")


# 保持既有主机侧发送契约：发送方式仍为 UART，不在协议层推断下游波形。
PROTOCOL_DEFINITIONS: Mapping[str, ProtocolDefinition] = MappingProxyType({
    PROTOCOL_RUILUN: ProtocolDefinition(
        name=PROTOCOL_RUILUN,
        frame_length=12,
        checksum_mode="xor",
        send_mode="uart",
        generator_method="_generate_ruilun_frame",
        soc_fault_value=0xEE,
    ),
    PROTOCOL_FZ_SIF: ProtocolDefinition(
        name=PROTOCOL_FZ_SIF,
        frame_length=12,
        checksum_mode="xor",
        send_mode="uart",
        generator_method="_generate_fz_sif_frame",
    ),
    PROTOCOL_XINRI: ProtocolDefinition(
        name=PROTOCOL_XINRI,
        frame_length=12,
        checksum_mode="xor",
        send_mode="uart",
        generator_method="_generate_xinri_frame",
    ),
    PROTOCOL_HANGZHOU_ANXIAN: ProtocolDefinition(
        name=PROTOCOL_HANGZHOU_ANXIAN,
        frame_length=12,
        checksum_mode="xor",
        send_mode="uart",
        generator_method="_generate_hangzhou_frame_for_send",
        preview_generator_method="_generate_hangzhou_frame_for_preview",
    ),
    PROTOCOL_CHANGZHOU_XINSIWEI: ProtocolDefinition(
        name=PROTOCOL_CHANGZHOU_XINSIWEI,
        frame_length=12,
        checksum_mode="xor",
        send_mode="uart",
        generator_method="generate_xinsiwei_frame_with_auto_sequence",
        preview_generator_method="generate_xinsiwei_frame_for_preview",
        soc_fault_value=0xEE,
    ),
    PROTOCOL_WUXI_YIGE: ProtocolDefinition(
        name=PROTOCOL_WUXI_YIGE,
        frame_length=12,
        checksum_mode="xor",
        send_mode="uart",
        generator_method="_generate_wuxi_yige_frame",
    ),
    PROTOCOL_TAILING_Y34B: ProtocolDefinition(
        name=PROTOCOL_TAILING_Y34B,
        frame_length=13,
        checksum_mode="xor",
        send_mode="uart",
        generator_method="_generate_tailing_y34b_frame",
    ),
    PROTOCOL_TAILING_Y34F: ProtocolDefinition(
        name=PROTOCOL_TAILING_Y34F,
        frame_length=15,
        checksum_mode="xor",
        send_mode="uart",
        generator_method="_generate_tailing_y34f_frame",
    ),
    PROTOCOL_SHENZHOUXING: ProtocolDefinition(
        name=PROTOCOL_SHENZHOUXING,
        frame_length=15,
        checksum_mode="xor",
        send_mode="uart",
        generator_method="_generate_shenzhouxing_frame",
    ),
    PROTOCOL_YADEA: ProtocolDefinition(
        name=PROTOCOL_YADEA,
        frame_length=12,
        checksum_mode="xor",
        send_mode="uart",
        generator_method="_generate_yadea_frame",
    ),
    PROTOCOL_YOUYIBAO: ProtocolDefinition(
        name=PROTOCOL_YOUYIBAO,
        frame_length=12,
        checksum_mode="xor",
        send_mode="uart",
        generator_method="_generate_youyibao_frame",
    ),
    PROTOCOL_JINGXIAN: ProtocolDefinition(
        name=PROTOCOL_JINGXIAN,
        frame_length=12,
        checksum_mode="xor",
        send_mode="uart",
        generator_method="_generate_jingxian_frame_for_send",
        preview_generator_method="_generate_jingxian_frame_for_preview",
    ),
    PROTOCOL_DONGWEI_GTXH: ProtocolDefinition(
        name=PROTOCOL_DONGWEI_GTXH,
        frame_length=12,
        checksum_mode="xor",
        send_mode="uart",
        generator_method="_generate_dongwei_gtxh_frame",
    ),
    PROTOCOL_XINCHI: ProtocolDefinition(
        name=PROTOCOL_XINCHI,
        frame_length=10,
        checksum_mode="sum",
        send_mode="uart",
        generator_method="_generate_xinchi_frame",
        reset_send_interval_on_switch=True,
    ),
    PROTOCOL_LUYUAN_BMS: ProtocolDefinition(
        name=PROTOCOL_LUYUAN_BMS,
        frame_length=15,
        checksum_mode="sum",
        send_mode="uart",
        generator_method="_generate_luyuan_bms_frame",
    ),
    PROTOCOL_LITHIUM_BMS: ProtocolDefinition(
        name=PROTOCOL_LITHIUM_BMS,
        frame_length=12,
        checksum_mode="xor",
        send_mode="uart",
        generator_method="_generate_lithium_bms_frame",
    ),
    PROTOCOL_BATTERY_SINGLE_WIRE: ProtocolDefinition(
        name=PROTOCOL_BATTERY_SINGLE_WIRE,
        frame_length=6,
        checksum_mode="sum",
        send_mode="uart",
        generator_method="_generate_battery_single_wire_frame",
        reset_send_interval_on_switch=True,
    ),
})
DEFAULT_PROTOCOL_DEFINITION = PROTOCOL_DEFINITIONS[PROTOCOL_RUILUN]
SUPPORTED_PROTOCOLS = list(PROTOCOL_DEFINITIONS)
