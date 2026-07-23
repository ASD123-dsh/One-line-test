#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
协议界面路由注册表。

新增协议时在此集中声明界面构建、预设加载和状态读取入口，
避免在主窗口中维护多组容易遗漏的条件分支。
"""

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from protocol.definitions import (
    PROTOCOL_BATTERY_SINGLE_WIRE,
    PROTOCOL_CHANGZHOU_XINSIWEI,
    PROTOCOL_DONGWEI_GTXH,
    PROTOCOL_FZ_SIF,
    PROTOCOL_HANGZHOU_ANXIAN,
    PROTOCOL_JINGXIAN,
    PROTOCOL_LITHIUM_BMS,
    PROTOCOL_LUYUAN_BMS,
    PROTOCOL_RUILUN,
    PROTOCOL_SHENZHOUXING,
    PROTOCOL_TAILING_Y34B,
    PROTOCOL_TAILING_Y34F,
    PROTOCOL_WUXI_YIGE,
    PROTOCOL_XINCHI,
    PROTOCOL_XINRI,
    PROTOCOL_YADEA,
    PROTOCOL_YOUYIBAO,
    SUPPORTED_PROTOCOLS,
)


@dataclass(frozen=True)
class ProtocolUiSpec:
    """描述主窗口中一个协议的界面路由入口。"""

    switch_handler: str
    preset_loader: str
    status_reader: str


PROTOCOL_UI_SPECS: Mapping[str, ProtocolUiSpec] = MappingProxyType({
    PROTOCOL_RUILUN: ProtocolUiSpec(
        "switch_to_ruilun_protocol",
        "load_ruilun_preset_scenario",
        "get_ruilun_status_from_ui",
    ),
    PROTOCOL_FZ_SIF: ProtocolUiSpec(
        "switch_to_fz_sif_protocol",
        "load_fz_sif_preset_scenario",
        "get_ruilun_status_from_ui",
    ),
    PROTOCOL_XINRI: ProtocolUiSpec(
        "switch_to_xinri_protocol",
        "load_xinri_preset_scenario",
        "get_xinri_status_from_ui",
    ),
    PROTOCOL_HANGZHOU_ANXIAN: ProtocolUiSpec(
        "switch_to_hangzhou_anxian_protocol",
        "load_hangzhou_anxian_preset_scenario",
        "get_ruilun_status_from_ui",
    ),
    PROTOCOL_CHANGZHOU_XINSIWEI: ProtocolUiSpec(
        "switch_to_changzhou_xinsiwei_protocol",
        "load_changzhou_xinsiwei_preset_scenario",
        "get_changzhou_xinsiwei_status_from_ui",
    ),
    PROTOCOL_WUXI_YIGE: ProtocolUiSpec(
        "switch_to_wuxi_yige_protocol",
        "load_wuxi_yige_preset_scenario",
        "get_ruilun_status_from_ui",
    ),
    PROTOCOL_TAILING_Y34B: ProtocolUiSpec(
        "switch_to_tailing_y34b_protocol",
        "load_tailing_y34b_preset_scenario",
        "get_ruilun_status_from_ui",
    ),
    PROTOCOL_TAILING_Y34F: ProtocolUiSpec(
        "switch_to_tailing_y34f_protocol",
        "load_tailing_y34f_preset_scenario",
        "get_ruilun_status_from_ui",
    ),
    PROTOCOL_SHENZHOUXING: ProtocolUiSpec(
        "switch_to_shenzhouxing_protocol",
        "load_shenzhouxing_preset_scenario",
        "get_ruilun_status_from_ui",
    ),
    PROTOCOL_YADEA: ProtocolUiSpec(
        "switch_to_yadea_protocol",
        "load_yadea_preset_scenario",
        "get_ruilun_status_from_ui",
    ),
    PROTOCOL_YOUYIBAO: ProtocolUiSpec(
        "switch_to_youyibao_protocol",
        "load_youyibao_preset_scenario",
        "get_ruilun_status_from_ui",
    ),
    PROTOCOL_JINGXIAN: ProtocolUiSpec(
        "switch_to_jingxian_protocol",
        "load_jingxian_preset_scenario",
        "get_ruilun_status_from_ui",
    ),
    PROTOCOL_DONGWEI_GTXH: ProtocolUiSpec(
        "switch_to_dongwei_gtxh_protocol",
        "load_dongwei_gtxh_preset_scenario",
        "get_ruilun_status_from_ui",
    ),
    PROTOCOL_XINCHI: ProtocolUiSpec(
        "switch_to_xinchi_protocol",
        "load_xinchi_preset_scenario",
        "get_xinchi_status_from_ui",
    ),
    PROTOCOL_LUYUAN_BMS: ProtocolUiSpec(
        "switch_to_luyuan_bms_protocol",
        "load_luyuan_bms_preset_scenario",
        "get_luyuan_bms_status_from_ui",
    ),
    PROTOCOL_LITHIUM_BMS: ProtocolUiSpec(
        "switch_to_lithium_bms_protocol",
        "load_lithium_bms_preset_scenario",
        "get_lithium_bms_status_from_ui",
    ),
    PROTOCOL_BATTERY_SINGLE_WIRE: ProtocolUiSpec(
        "switch_to_battery_single_wire_protocol",
        "load_battery_single_wire_preset_scenario",
        "get_battery_single_wire_status_from_ui",
    ),
})

_missing_protocols = set(SUPPORTED_PROTOCOLS) - set(PROTOCOL_UI_SPECS)
_unknown_protocols = set(PROTOCOL_UI_SPECS) - set(SUPPORTED_PROTOCOLS)
if _missing_protocols or _unknown_protocols:
    raise RuntimeError(
        "协议界面注册表与协议核心定义不一致："
        f"缺少={sorted(_missing_protocols)}，多余={sorted(_unknown_protocols)}"
    )


def get_protocol_ui_spec(protocol_name: str) -> ProtocolUiSpec:
    """返回协议界面路由；不支持的协议给出明确异常。"""

    try:
        return PROTOCOL_UI_SPECS[protocol_name]
    except KeyError as exc:
        raise ValueError(f"不支持的协议界面：{protocol_name}") from exc
