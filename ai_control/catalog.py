#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AI可发现的协议和参数元数据；帧编码与最终校验仍由原协议组件负责。"""

from dataclasses import asdict, fields

from protocol.definitions import (
    PROTOCOL_BATTERY_SINGLE_WIRE, PROTOCOL_DEFINITIONS, PROTOCOL_LISHEN_BMS,
    PROTOCOL_LITHIUM_BMS, PROTOCOL_LUYUAN_BMS, PROTOCOL_XINCHI, PROTOCOL_XINGHENG_BMS,
)
from protocol.models import StatusBits
from protocol.xingheng import xingheng_fields

READ_OPERATIONS = frozenset(("status", "protocols", "ports", "parameters", "preview", "results"))
WRITE_OPERATIONS = frozenset(("select_protocol", "configure", "set_raw_frame", "connect", "disconnect", "send_once", "start_cycle", "start_sequence"))
CONNECTION_OPERATIONS = frozenset(("request_connection", "connection_status", "close_connection"))
OPERATIONS = READ_OPERATIONS | WRITE_OPERATIONS | CONNECTION_OPERATIONS | {"stop"}
READ_ONLY_FIELDS = frozenset(("protocol_name", "xinsiwei_protocol", "xinsiwei_sequence", "sequence_number", "protocol_identifier", "backup_power"))


def protocol_catalog():
    """新协议自动进入查询列表，不复制编码器或新增另一份协议注册表。"""
    return [{"name": name, "default_frame_length": spec.frame_length,
             "checksum": spec.checksum_mode, "send_mode": spec.send_mode,
             "min_interval_ms": spec.min_send_interval_ms, "max_interval_ms": spec.max_send_interval_ms,
             "default_interval_ms": spec.default_send_interval_ms}
            for name, spec in PROTOCOL_DEFINITIONS.items()]


def parameter_schema(protocol, status):
    """给出模型字段和当前值；原校验及UI回读共同拒绝无效、舍入或未映射参数。"""
    values = asdict(status)
    specs = {}
    if protocol == PROTOCOL_XINGHENG_BMS:
        for item in xingheng_fields(status.xingheng_message_id):
            specs["xingheng_" + item.name] = {"title": item.label, "minimum": item.minimum, "maximum": item.maximum, "step": item.step}
        specs["xingheng_message_id"] = {"enum": [0x01, 0x3A], "title": "报文类型；切换类型会先停止旧循环"}
    result = {}
    bms_prefix = {PROTOCOL_XINCHI: "xinchi_", PROTOCOL_LUYUAN_BMS: "luyuan_",
                  PROTOCOL_LITHIUM_BMS: "lithium_bms_", PROTOCOL_LISHEN_BMS: "lishen_"}
    private_prefixes = tuple(bms_prefix.values()) + ("xingheng_",)
    for item in fields(StatusBits):
        name = item.name
        if name in READ_ONLY_FIELDS or (protocol == PROTOCOL_XINGHENG_BMS and name not in specs):
            continue
        if protocol != PROTOCOL_XINGHENG_BMS and name.startswith("xingheng_"):
            continue
        if protocol == PROTOCOL_BATTERY_SINGLE_WIRE and name != "soc_percent":
            continue
        if protocol in bms_prefix and name != "soc_percent" and not name.startswith(bms_prefix[protocol]):
            continue
        if protocol not in bms_prefix and protocol != PROTOCOL_XINGHENG_BMS and name.startswith(private_prefixes):
            continue
        result[name] = {"type": "boolean" if item.type is bool else "integer" if item.type is int else "number",
                        "value": values[name], **specs.get(name, {})}
    return {"protocol": protocol, "fields": result,
            "validation": "字段必须通过现有协议校验及当前UI精确回读；未映射字段拒绝，不静默舍入。预览不会消耗流水号。"}
