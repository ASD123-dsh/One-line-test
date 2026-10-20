#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
一线通协议处理模块

负责不同厂商协议的帧生成、校验和基础场景预设。
"""

from typing import List, Tuple

from .definitions import (
    DEFAULT_PROTOCOL_DEFINITION,
    PROTOCOL_BATTERY_SINGLE_WIRE,
    PROTOCOL_CHANGZHOU_XINSIWEI,
    PROTOCOL_DEFINITIONS,
    PROTOCOL_DONGWEI_GTXH,
    PROTOCOL_FZ_SIF,
    PROTOCOL_HANGZHOU_ANXIAN,
    PROTOCOL_JINGXIAN,
    PROTOCOL_LITHIUM_BMS,
    PROTOCOL_LUYUAN_BMS,
    PROTOCOL_RUILUN,
    PROTOCOL_SHENZHOUXING,
    PROTOCOL_SXSY,
    PROTOCOL_TAILING_Y34B,
    PROTOCOL_TAILING_Y34F,
    PROTOCOL_WUXI_YIGE,
    PROTOCOL_XINCHI,
    PROTOCOL_XINRI,
    PROTOCOL_YADEA,
    PROTOCOL_YOUYIBAO,
    SUPPORTED_PROTOCOLS,
)
from .models import ProtocolConfig, StatusBits

from .codecs import (
    RuilunCodec,
    FzSifCodec,
    XinriCodec,
    HangzhouCodec,
    SxsyCodec,
    XinsiweiCodec,
    YigeCodec,
    TailingCodec,
    ShenzhouxingCodec,
    YadeaCodec,
    YouyibaoCodec,
    JingxianCodec,
    DongweiCodec,
    XinchiCodec,
    LuyuanCodec,
    LithiumCodec,
    BatteryCodec,
)
from .constants import SXSY_P_GEAR_STATES, VOLTAGE_OPTIONS
from .descriptions import get_byte_descriptions as _get_byte_descriptions
from .presets import PresetScenarios
from .validation import StatusValidation


class ProtocolHandler(
    RuilunCodec,
    FzSifCodec,
    XinriCodec,
    HangzhouCodec,
    SxsyCodec,
    XinsiweiCodec,
    YigeCodec,
    TailingCodec,
    ShenzhouxingCodec,
    YadeaCodec,
    YouyibaoCodec,
    JingxianCodec,
    DongweiCodec,
    XinchiCodec,
    LuyuanCodec,
    LithiumCodec,
    BatteryCodec,
    StatusValidation,
):
    """保持旧接口的协议门面；各协议实现与公共调度分开维护。"""

    def __init__(self):
        self.config = ProtocolConfig()
        self.status = StatusBits()
        self._xinsiwei_sequence_counter = 1
        self._hangzhou_sequence_counter = 1
        self._sxsy_sequence_counter = 1
        self._jingxian_sequence_counter = 1

    def resolve_protocol_name(self, status: StatusBits) -> str:
        """从状态对象解析当前协议。"""

        if getattr(status, "xinsiwei_protocol", False):
            return PROTOCOL_CHANGZHOU_XINSIWEI
        protocol_name = getattr(status, "protocol_name", "") or PROTOCOL_RUILUN
        if protocol_name not in SUPPORTED_PROTOCOLS:
            return PROTOCOL_RUILUN
        return protocol_name

    def get_protocol_frame_length(self, protocol_name: str) -> int:
        """获取协议帧长度。"""

        definition = PROTOCOL_DEFINITIONS.get(
            protocol_name, DEFAULT_PROTOCOL_DEFINITION
        )
        return definition.frame_length

    def get_protocol_checksum_mode(self, protocol_name: str) -> str:
        """获取协议校验模式。"""

        definition = PROTOCOL_DEFINITIONS.get(
            protocol_name, DEFAULT_PROTOCOL_DEFINITION
        )
        return definition.checksum_mode

    def get_protocol_send_mode(self, protocol_name: str) -> str:
        """获取协议的串口发送模式。"""

        definition = PROTOCOL_DEFINITIONS.get(
            protocol_name, DEFAULT_PROTOCOL_DEFINITION
        )
        return definition.send_mode

    def generate_frame(self, status: StatusBits) -> Tuple[bool, List[int], str]:
        """根据协议生成发送帧。"""

        return self._dispatch_frame_generation(status, preview=False)

    def generate_frame_for_preview(self, status: StatusBits) -> Tuple[bool, List[int], str]:
        """根据协议生成预览帧。"""

        return self._dispatch_frame_generation(status, preview=True)

    def _dispatch_frame_generation(
        self, status: StatusBits, preview: bool
    ) -> Tuple[bool, List[int], str]:
        """按注册表选择发送或预览帧生成入口。"""

        if not isinstance(status, StatusBits):
            return False, [], "协议状态必须是 StatusBits 对象"

        protocol_name = self.resolve_protocol_name(status)
        definition = PROTOCOL_DEFINITIONS.get(
            protocol_name, DEFAULT_PROTOCOL_DEFINITION
        )
        generator_method = definition.generator_method
        if preview and definition.preview_generator_method is not None:
            generator_method = definition.preview_generator_method
        try:
            return getattr(self, generator_method)(status)
        except (AttributeError, OverflowError, TypeError, ValueError) as exc:
            return False, [], f"协议状态参数无效：{exc}"

    def _encode_generic_status2(self, status: StatusBits, include_walk_mode: bool = False) -> int:
        value = 0
        if include_walk_mode and status.walk_mode:
            value |= 0x80
        if status.hall_fault:
            value |= 0x40
        if status.throttle_fault:
            value |= 0x20
        if status.controller_fault:
            value |= 0x10
        if status.under_voltage:
            value |= 0x08
        if status.cruise:
            value |= 0x04
        if status.assist:
            value |= 0x02
        if status.motor_phase_loss:
            value |= 0x01
        return value

    def _encode_generic_status3(self, status: StatusBits, protocol_name: str) -> int:
        value = 0
        if protocol_name in {PROTOCOL_YADEA, PROTOCOL_JINGXIAN, PROTOCOL_DONGWEI_GTXH}:
            if status.speed_mode & 0x04:
                value |= 0x80
        elif status.gear_four:
            value |= 0x80

        if status.motor_running:
            value |= 0x40
        if status.brake:
            value |= 0x20
        if status.controller_protect:
            value |= 0x10
        if status.regen_charging:
            value |= 0x08
        if status.anti_runaway:
            value |= 0x04
        value |= status.speed_mode & 0x03
        return value

    def _encode_generic_status4(self, status: StatusBits, protocol_name: str) -> int:
        value = 0
        if protocol_name in {PROTOCOL_WUXI_YIGE, PROTOCOL_FZ_SIF}:
            if status.cloud_power_mode:
                value |= 0x80
        elif protocol_name in {
            PROTOCOL_RUILUN,
            PROTOCOL_YOUYIBAO,
            PROTOCOL_JINGXIAN,
            PROTOCOL_DONGWEI_GTXH,
        }:
            if status.current_70_flag:
                value |= 0x80

        if protocol_name == PROTOCOL_DONGWEI_GTXH:
            if status.side_stand:
                value |= 0x40
        elif status.one_key_enable:
            value |= 0x40
        if status.ekk_enable:
            value |= 0x20
        if status.over_current:
            value |= 0x10
        if status.stall_protect:
            value |= 0x08
        if status.reverse:
            value |= 0x04
        if status.electronic_brake:
            value |= 0x02
        if status.speed_limit:
            value |= 0x01
        return value

    def _encode_soc_fault(self, protocol_name: str) -> int:
        """从协议定义读取并返回 SOC 故障编码。"""

        fault_value = PROTOCOL_DEFINITIONS[protocol_name].soc_fault_value
        if fault_value is None:
            raise ValueError(f"{protocol_name} 未定义 SOC 故障编码")
        return fault_value

    def _encode_voltage_mask(self, status: StatusBits) -> int:
        mask = 0
        for field_name, bit_mask in VOLTAGE_OPTIONS:
            if getattr(status, field_name, False):
                mask |= bit_mask
        return mask & 0xFF

    def _encode_signed_current(self, current_a: int) -> int:
        return int(current_a) & 0xFF

    def _is_point_two_amp_current_in_range(
        self,
        current_a: float,
        minimum_raw: int,
        maximum_raw: int,
        use_absolute: bool = False,
    ) -> bool:
        """判断电流按 0.2A/字节换算后是否处于指定原始值范围。"""

        try:
            scaled_value = float(current_a) * 5
        except (TypeError, ValueError):
            return False

        if use_absolute:
            scaled_value = abs(scaled_value)
        return minimum_raw <= scaled_value <= maximum_raw

    def _encode_sign_magnitude_byte(self, value: int) -> int:
        magnitude = min(127, abs(int(value)))
        if value < 0:
            return 0x80 | magnitude
        return magnitude & 0x7F

    def _encode_signed_byte(self, value: int) -> int:
        return int(value) & 0xFF

    def _resolve_hall_count(self, status: StatusBits) -> int:
        if status.hall_count > 0:
            return status.hall_count & 0xFFFF
        return max(0, min(65535, int(round(status.speed_kmh * 10))))

    def _xor_checksum(self, payload: List[int]) -> int:
        checksum = 0
        for value in payload:
            checksum ^= value
        return checksum & 0xFF

    def _sum_checksum(self, payload: List[int]) -> int:
        return sum(payload) & 0xFF

    def _copy_status(self, status: StatusBits) -> StatusBits:
        copied = StatusBits()
        for field_name in status.__dataclass_fields__:
            setattr(copied, field_name, getattr(status, field_name))
        return copied

    def get_byte_descriptions(self, protocol_name: str) -> List[str]:
        """返回本协议的字节说明，兼容原有公开入口。"""
        return _get_byte_descriptions(protocol_name)

    def format_frame_display(self, frame: List[int]) -> str:
        """格式化显示帧数据。"""

        if not frame:
            return "无效帧数据"

        display_lines = [
            "协议帧数据 (十六进制):",
            " ".join(f"{byte:02X}" for byte in frame),
            "",
            "字节信息:",
        ]
        for index, value in enumerate(frame):
            display_lines.append(f"DATA{index:<2} = 0x{value:02X} ({value})")
        return "\n".join(display_lines)
