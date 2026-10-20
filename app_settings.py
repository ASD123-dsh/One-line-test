#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""带版本和参数校验的配置存取，不包含授权内容或自动连接、发送指令。"""

import json
import math
import os
import uuid
from dataclasses import asdict, fields
from pathlib import Path

from app_info import APP_ID
from protocol.definitions import PROTOCOL_DEFINITIONS
from protocol.frame_utils import normalize_frame
from protocol.models import StatusBits
from protocol.protocol_handler import ProtocolHandler

MAX_CONFIG_BYTES = 1024 * 1024
MAX_PACKET_FRAMES = 256
BAUD_RATES = (9600, 19200, 38400, 57600, 115200)


def read_config(path):
    """受限读取 JSON，拒绝超大、损坏或其他软件的配置。"""
    with Path(path).open("rb") as source:
        raw = source.read(MAX_CONFIG_BYTES + 1)
    if len(raw) > MAX_CONFIG_BYTES:
        raise ValueError("配置文件超过 1 MiB")
    try:
        return validate_config(json.loads(raw.decode("utf-8")))
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ValueError("配置文件无法解析") from exc


def validate_config(data):
    """按白名单验证全部配置，导入前一次性拒绝非法字段和值。"""
    if not isinstance(data, dict) or data.get("app_id") != APP_ID or type(data.get("schema")) is not int or data["schema"] != 1:
        raise ValueError("不是本工具支持的配置格式")
    allowed = {"schema", "app_id", "remember", "protocol", "baud_rate", "tosc_us", "interval_ms", "scenario_id", "status", "custom_frame", "packet_sequences"}
    if set(data) - allowed or not isinstance(data.get("remember", False), bool):
        raise ValueError("配置包含未知字段或无效记忆选项")
    name = data.get("protocol")
    if not isinstance(name, str) or name not in PROTOCOL_DEFINITIONS:
        raise ValueError("配置中的协议不受支持")
    definition = PROTOCOL_DEFINITIONS[name]
    for key, minimum, maximum in (("tosc_us", 32, 320), ("interval_ms", definition.min_send_interval_ms, definition.max_send_interval_ms), ("scenario_id", 0, 4)):
        value = data.get(key)
        if type(value) is not int or not minimum <= value <= maximum:
            raise ValueError(f"配置参数 {key} 必须在 {minimum}～{maximum} 范围内")
    if type(data.get("baud_rate")) is not int or data["baud_rate"] not in BAUD_RATES:
        raise ValueError("配置中的波特率不受支持")
    status = data.get("status")
    defaults = asdict(StatusBits())
    field_types = {item.name: item.type for item in fields(StatusBits)}
    if not isinstance(status, dict) or set(status) - set(defaults):
        raise ValueError("协议状态包含未知字段")
    for key, value in status.items():
        default = defaults[key]
        if isinstance(default, bool):
            valid = isinstance(value, bool)
        elif isinstance(default, (int, float)):
            valid = type(value) in (int, float) and -1e12 <= value <= 1e12 and math.isfinite(value)
            if field_types[key] is int:
                valid = valid and type(value) is int
        else:
            valid = isinstance(value, str)
        if not valid:
            raise ValueError(f"协议状态字段类型无效：{key}")
    state = StatusBits(**status)
    if state.protocol_name != name or ProtocolHandler().resolve_protocol_name(state) != name:
        raise ValueError("协议状态与所选协议不一致")
    success, _, error = ProtocolHandler().generate_frame_for_preview(state)
    if not success:
        raise ValueError(error)
    custom = data.get("custom_frame")
    if custom is not None:
        custom = normalize_frame(custom, expected_length=definition.frame_length)
    if data["scenario_id"] == 4 and custom is None:
        raise ValueError("全部自定义配置缺少完整帧")
    sequences = data.get("packet_sequences", {})
    if not isinstance(sequences, dict) or len(sequences) > len(PROTOCOL_DEFINITIONS):
        raise ValueError("包组配置无效")
    normalized = {}
    for protocol, frames in sequences.items():
        if protocol not in PROTOCOL_DEFINITIONS or not isinstance(frames, list) or not 1 <= len(frames) <= MAX_PACKET_FRAMES:
            raise ValueError("包组协议或帧数无效")
        normalized[protocol] = [normalize_frame(frame, expected_length=PROTOCOL_DEFINITIONS[protocol].frame_length) for frame in frames]
    return {**data, "remember": data.get("remember", False), "status": asdict(state), "custom_frame": custom, "packet_sequences": normalized}


def write_config(path, data):
    """原子保存已校验的配置，仅替换指定文件，不清理或搬动其他内容。"""
    data = validate_config(data)
    raw = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
    if len(raw) > MAX_CONFIG_BYTES:
        raise ValueError("配置过大，未保存")
    path = Path(path)
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise ValueError("配置路径不是普通文件")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with temporary.open("xb") as output:
            output.write(raw)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


class SettingsStore:
    """专属设置存储；不传路径时仅保存在内存，便于测试隔离。"""

    def __init__(self, path=None):
        """保存精确文件位置，不在构造时写盘。"""
        self.path = Path(path) if path is not None else None
        self._data = None

    def load(self):
        """不存在或未开启记忆时不自动应用配置。"""
        if self.path is None:
            return validate_config(self._data) if self._data is not None else None
        if not self.path.exists():
            return None
        return read_config(self.path)

    def save(self, data):
        """保存一份独立配置，内存模式不触碰客户文件。"""
        data = validate_config(data)
        if self.path is not None:
            write_config(self.path, data)
        self._data = data
