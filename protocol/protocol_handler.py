#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
一线通协议处理模块

负责不同厂商协议的帧生成、校验和基础场景预设。
"""

from typing import Dict, List, Tuple

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


class ProtocolHandler:
    """多协议帧生成器。"""

    def __init__(self):
        self.config = ProtocolConfig()
        self.status = StatusBits()
        self._xinsiwei_sequence_counter = 1
        self._hangzhou_sequence_counter = 1
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

    def get_current_xinsiwei_sequence(self) -> int:
        """获取当前常州新思维序号。"""

        return self._xinsiwei_sequence_counter

    def get_next_xinsiwei_sequence(self) -> int:
        """获取下一常州新思维序号并递增。"""

        current_seq = self._xinsiwei_sequence_counter
        self._xinsiwei_sequence_counter = (self._xinsiwei_sequence_counter % 4095) + 1
        return current_seq

    def reset_xinsiwei_sequence(self, start_value: int = 1):
        """重置常州新思维序号。"""

        if not (1 <= start_value <= 4095):
            raise ValueError("常州新思维序号起始值必须在 1-4095 范围内")
        self._xinsiwei_sequence_counter = start_value

    def get_current_hangzhou_sequence(self) -> int:
        """获取当前杭州安显序号。"""

        return self._hangzhou_sequence_counter

    def get_next_hangzhou_sequence(self) -> int:
        """获取下一杭州安显序号并递增。"""

        current_seq = self._hangzhou_sequence_counter
        self._hangzhou_sequence_counter = (self._hangzhou_sequence_counter % 4095) + 1
        return current_seq

    def reset_hangzhou_sequence(self, start_value: int = 1):
        """重置杭州安显序号。"""

        if not (1 <= start_value <= 4095):
            raise ValueError("杭州安显序号起始值必须在 1-4095 范围内")
        self._hangzhou_sequence_counter = start_value

    def get_current_jingxian_sequence(self) -> int:
        """获取当前精显协议序号。"""

        return self._jingxian_sequence_counter

    def get_next_jingxian_sequence(self) -> int:
        """获取下一精显协议序号并递增。"""

        current_seq = self._jingxian_sequence_counter
        self._jingxian_sequence_counter = (self._jingxian_sequence_counter + 1) & 0xFF
        return current_seq

    def reset_jingxian_sequence(self, start_value: int = 1):
        """重置精显协议序号。"""

        if not (0 <= start_value <= 255):
            raise ValueError("精显协议序号起始值必须在 0-255 范围内")
        self._jingxian_sequence_counter = start_value


    def validate_status_bits(self, status: StatusBits) -> Tuple[bool, str]:
        """校验状态字段是否合法。"""

        if not isinstance(status, StatusBits):
            return False, "协议状态必须是 StatusBits 对象"

        protocol_name = self.resolve_protocol_name(status)
        if isinstance(status.current_a, bool) or not isinstance(status.current_a, (int, float)):
            return False, "运行电流必须是数值"
        current_a = float(status.current_a)

        speed_mode_max = (
            7
            if protocol_name
            in {PROTOCOL_XINRI, PROTOCOL_YADEA, PROTOCOL_JINGXIAN, PROTOCOL_DONGWEI_GTXH}
            else 3
        )
        if not (0 <= status.speed_mode <= speed_mode_max):
            return False, f"当前协议的速度模式必须在 0-{speed_mode_max} 范围内"

        if (
            protocol_name == PROTOCOL_XINRI
            and not self._is_point_two_amp_current_in_range(
                current_a, 0, 255, use_absolute=True
            )
        ):
            # 修复新日电流超出单字节量程时被静默截断的问题。
            return False, "新日协议电流绝对值必须在 0A 到 51.0A 范围内（0.2A/字节）"

        if (
            protocol_name == PROTOCOL_DONGWEI_GTXH
            and not self._is_point_two_amp_current_in_range(
                current_a, -128, 127
            )
        ):
            # 修复东威电流超出有符号单字节量程时被静默截断的问题。
            return False, "东威协议电流必须在 -25.6A 到 25.4A 范围内（0.2A/字节）"

        if (
            protocol_name not in {PROTOCOL_XINRI, PROTOCOL_DONGWEI_GTXH}
            and not current_a.is_integer()
        ):
            return False, "当前协议的运行电流必须为整数安培"

        if not (-128 <= current_a <= 127):
            return False, "运行电流必须在 -128A 到 127A 范围内"

        if not (0 <= status.hall_count <= 65535):
            return False, "霍尔计数必须在 0-65535 范围内"

        if not (0 <= status.xinsiwei_hall_count <= 65535):
            return False, "常州新思维霍尔计数必须在 0-65535 范围内"

        if not (0 <= status.speed_kmh <= 6553.5):
            return False, "兼容速度输入必须在 0-6553.5 范围内"

        definition = PROTOCOL_DEFINITIONS.get(
            protocol_name, DEFAULT_PROTOCOL_DEFINITION
        )
        consumes_soc_fault = (
            status.soc_fault and definition.soc_fault_value is not None
        )
        if not consumes_soc_fault and not (0 <= status.soc_percent <= 100):
            # 仅真实编码 SOC 故障值的协议可以在故障态跳过百分比范围校验。
            return False, "百分比输入必须在 0-100 范围内"

        if not (0 <= status.voltage_percentage <= 100):
            return False, "电压百分比必须在 0-100 范围内"

        if not (0 <= status.current_percentage <= 100):
            return False, "电流百分比必须在 0-100 范围内"

        if not (0 <= status.tailing_seat_state <= 3):
            return False, "台铃Y34F坐垫功能状态必须在 0-3 范围内"

        if not (0.0 <= status.tailing_real_time_voltage_v <= 6553.5):
            return False, "台铃实时电压必须在 0.0V 到 6553.5V 范围内"

        if not (0 <= status.shenzhouxing_real_time_voltage_v <= 127):
            return False, "神州行实时电压必须在 0V 到 127V 范围内"
        if not (0 <= status.shenzhouxing_signal_strength <= 31):
            return False, "神州行4G信号强度必须在 0-31 范围内"
        if not (0 <= status.shenzhouxing_time_hour <= 23):
            return False, "神州行时间小时必须在 0-23 范围内"
        if not (0 <= status.shenzhouxing_time_minute <= 59):
            return False, "神州行时间分钟必须在 0-59 范围内"

        voltage_mask_count = sum(
            1 for field_name, _ in VOLTAGE_OPTIONS if getattr(status, field_name, False)
        )
        if voltage_mask_count > 1:
            return False, "协议切换电压最多只能勾选一个电压位"

        if protocol_name == PROTOCOL_DONGWEI_GTXH:
            unsupported_voltage_fields = ("voltage_36v", "voltage_64v", "voltage_84v")
            if any(getattr(status, field_name, False) for field_name in unsupported_voltage_fields):
                return False, "东威协议的电压状态仅支持默认/48V/60V/72V/80V/96V"

        if protocol_name == PROTOCOL_FZ_SIF:
            unsupported_voltage_fields = ("voltage_24v", "voltage_36v", "voltage_80v")
            if any(getattr(status, field_name, False) for field_name in unsupported_voltage_fields):
                return False, "FZ-sif协议的系统电压仅支持默认/48V/60V/64V/72V/84V/96V"

        if protocol_name in {PROTOCOL_TAILING_Y34B, PROTOCOL_TAILING_Y34F}:
            unsupported_voltage_fields = ("voltage_24v",)
            if any(getattr(status, field_name, False) for field_name in unsupported_voltage_fields):
                return False, "台铃Y34协议的系统电压仅支持默认/36V/48V/60V/64V/72V/80V/84V/96V"

        if protocol_name == PROTOCOL_SHENZHOUXING:
            unsupported_voltage_fields = ("voltage_24v",)
            if any(getattr(status, field_name, False) for field_name in unsupported_voltage_fields):
                return False, "神州行协议的系统电压仅支持默认/36V/48V/60V/64V/72V/80V/84V/96V"

        if protocol_name == PROTOCOL_CHANGZHOU_XINSIWEI and not (
            0 <= status.xinsiwei_sequence <= 4095
        ):
            return False, "常州新思维序号必须在 0-4095 范围内"

        if protocol_name == PROTOCOL_BATTERY_SINGLE_WIRE and not (
            0 <= status.soc_percent <= 100
        ):
            return False, "电池单线通讯协议 SOC 必须在 0-100 范围内"

        if protocol_name == PROTOCOL_XINCHI:
            if not (0 <= status.xinchi_cycle_count <= 65535):
                return False, "芯驰循环次数必须在 0-65535 范围内"
            if not (-40 <= status.xinchi_temperature_c <= 120):
                return False, "芯驰电池温度必须在 -40℃ 到 120℃ 范围内"
            if not (0 <= status.xinchi_total_voltage_v <= 6553.5):
                return False, "芯驰总电压必须在 0.0V 到 6553.5V 范围内"
            if not (0 <= status.xinchi_total_current_a <= 255):
                return False, "芯驰总电流必须在 0A 到 255A 范围内"

        if protocol_name == PROTOCOL_LUYUAN_BMS:
            if not (0 <= status.luyuan_cycle_count <= 65535):
                return False, "绿源BMS循环次数必须在 0-65535 范围内"
            if not (-40 <= status.luyuan_temperature_c <= 120):
                return False, "绿源BMS电池温度必须在 -40℃ 到 120℃ 范围内"
            if status.luyuan_max_cell_voltage_mv < status.luyuan_min_cell_voltage_mv:
                return False, "绿源BMS最高电芯电压不能小于最低电芯电压"
            if not (0 <= status.luyuan_max_cell_voltage_mv <= 65535):
                return False, "绿源BMS最高电芯电压必须在 0-65535mV 范围内"
            if not (0 <= status.luyuan_min_cell_voltage_mv <= 65535):
                return False, "绿源BMS最低电芯电压必须在 0-65535mV 范围内"
            if not self._is_luyuan_current_encodable(status.luyuan_current_a):
                return False, "绿源BMS电流必须在 -327.67A 到 327.67A 范围内"
            if not (0 <= status.luyuan_total_voltage_v <= 255):
                return False, "绿源BMS总电压必须在 0V 到 255V 范围内"
            if not (0 <= status.luyuan_soh_percent <= 100):
                return False, "绿源BMS健康度必须在 0-100 范围内"

        if protocol_name == PROTOCOL_LITHIUM_BMS:
            if not (0 <= status.lithium_bms_cycle_count <= 65535):
                return False, "锂电池BMS循环次数必须在 0-65535 范围内"
            if not (-127 <= status.lithium_bms_max_temp_c <= 127):
                return False, "锂电池BMS最高温度必须在 -127℃ 到 127℃ 范围内"
            if not (-127 <= status.lithium_bms_min_temp_c <= 127):
                return False, "锂电池BMS最低温度必须在 -127℃ 到 127℃ 范围内"
            if not (0 <= status.lithium_bms_total_voltage_v <= 100):
                return False, "锂电池BMS总压必须在 0V 到 100V 范围内"
            if (
                status.lithium_bms_max_cell_voltage_v
                < status.lithium_bms_min_cell_voltage_v
            ):
                return False, "锂电池BMS最高电芯电压不能小于最低电芯电压"
            if not self._is_lithium_bms_cell_voltage_encodable(
                status.lithium_bms_max_cell_voltage_v
            ):
                return False, "锂电池BMS最高电芯电压必须在 1.85V 到 4.40V 范围内"
            if not self._is_lithium_bms_cell_voltage_encodable(
                status.lithium_bms_min_cell_voltage_v
            ):
                return False, "锂电池BMS最低电芯电压必须在 1.85V 到 4.40V 范围内"

        return True, ""

    def xinsiwei_pluscode_encrypt(self, data_bytes: List[int]) -> int:
        """常州新思维协议 8 步 PlusCode 算法。"""

        if len(data_bytes) != 12:
            raise ValueError("常州新思维数据长度必须为 12 字节")

        step1 = data_bytes[0] ^ data_bytes[6]
        step2 = data_bytes[1] ^ data_bytes[7]
        step3 = data_bytes[2] ^ data_bytes[8]
        step4 = data_bytes[3] ^ data_bytes[9]
        step5 = data_bytes[4] ^ data_bytes[10]
        step6 = data_bytes[5] ^ data_bytes[11]
        step7 = (step1 + step2 + step3 + step4 + step5 + step6) & 0xFF
        step8 = sum(data_bytes) & 0xFF

        plus_code = 0
        for step in (step1, step2, step3, step4, step5, step6, step7, step8):
            plus_code ^= step
        return plus_code & 0xFF

    def hangzhou_pluscode_encrypt(self, sequence: int) -> int:
        """杭州安显协议加密字节算法。"""

        seq_low = sequence & 0xFF
        seq_high = (sequence >> 8) & 0x0F

        pulse = (seq_low + 0x6B) & 0xFF
        pulse ^= 0x54
        pulse = (pulse + 0x19) & 0xFF
        pulse ^= 0x25
        pulse = (pulse + seq_high) & 0xFF
        pulse ^= 0x6B
        pulse = (pulse + 0x3B) & 0xFF
        pulse ^= 0x3A
        pulse &= 0x7F
        return pulse

    def jingxian_pluscode_encrypt(self, sequence: int) -> int:
        """精显协议 PlusCod 加密算法。"""

        plus_code = (sequence + 0x9C) & 0xFF
        plus_code ^= 0xF7
        plus_code = (plus_code + 0xCF) & 0xFF
        plus_code ^= 0xCA
        plus_code ^= 0xBB
        plus_code = (plus_code + 0x0B) & 0xFF
        plus_code ^= 0xAA
        return plus_code & 0x7F

    def generate_xinsiwei_frame_for_preview(self, status: StatusBits) -> Tuple[bool, List[int], str]:
        """生成常州新思维预览帧，不递增序号。"""

        preview_status = self._copy_status(status)
        preview_status.protocol_name = PROTOCOL_CHANGZHOU_XINSIWEI
        preview_status.xinsiwei_protocol = True
        preview_status.xinsiwei_sequence = self.get_current_xinsiwei_sequence()
        return self.generate_xinsiwei_frame(preview_status)

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

    def _generate_ruilun_frame(self, status: StatusBits) -> Tuple[bool, List[int], str]:
        is_valid, error_msg = self.validate_status_bits(status)
        if not is_valid:
            return False, [], error_msg

        hall_count = self._resolve_hall_count(status)
        frame = [0] * 12
        frame[0] = 0x08
        frame[1] = 0x61
        frame[2] = self._encode_ruilun_status1(status)
        frame[3] = self._encode_generic_status2(status)
        frame[4] = self._encode_generic_status3(status, PROTOCOL_RUILUN)
        frame[5] = self._encode_generic_status4(status, PROTOCOL_RUILUN)
        frame[6] = self._encode_signed_current(status.current_a)
        frame[7] = (hall_count >> 8) & 0xFF
        frame[8] = hall_count & 0xFF
        frame[9] = self._encode_ruilun_soc(status)
        frame[10] = self._encode_voltage_mask(status)
        frame[11] = self._xor_checksum(frame[:11])
        return True, frame, ""

    def _generate_fz_sif_frame(self, status: StatusBits) -> Tuple[bool, List[int], str]:
        is_valid, error_msg = self.validate_status_bits(status)
        if not is_valid:
            return False, [], error_msg

        hall_count = self._resolve_hall_count(status)
        frame = [0] * 12
        frame[0] = 0x08
        frame[1] = 0x61
        frame[2] = self._encode_fz_sif_status1(status)
        frame[3] = self._encode_generic_status2(status, include_walk_mode=True)
        frame[4] = self._encode_generic_status3(status, PROTOCOL_FZ_SIF)
        frame[5] = self._encode_generic_status4(status, PROTOCOL_FZ_SIF)
        frame[6] = self._encode_signed_current(status.current_a)
        frame[7] = (hall_count >> 8) & 0xFF
        frame[8] = hall_count & 0xFF
        frame[9] = status.voltage_percentage & 0xFF
        frame[10] = self._encode_fz_sif_voltage_mask(status)
        frame[11] = self._xor_checksum(frame[:11])
        return True, frame, ""

    def _generate_hangzhou_frame_for_send(
        self, status: StatusBits
    ) -> Tuple[bool, List[int], str]:
        """生成杭州安显发送帧，并按原规则递增序号。"""

        return self._generate_hangzhou_frame(status, preview=False)

    def _generate_hangzhou_frame_for_preview(
        self, status: StatusBits
    ) -> Tuple[bool, List[int], str]:
        """生成杭州安显预览帧，不递增序号。"""

        return self._generate_hangzhou_frame(status, preview=True)

    def _generate_hangzhou_frame(
        self, status: StatusBits, preview: bool
    ) -> Tuple[bool, List[int], str]:
        is_valid, error_msg = self.validate_status_bits(status)
        if not is_valid:
            return False, [], error_msg

        sequence = (
            self.get_current_hangzhou_sequence() if preview else self.get_next_hangzhou_sequence()
        )
        pulse = self.hangzhou_pluscode_encrypt(sequence)
        hall_count = self._resolve_hall_count(status)

        seq_low = sequence & 0xFF
        seq_high = (sequence >> 8) & 0x0F

        frame = [0] * 12
        frame[0] = 0x08
        frame[1] = seq_low
        frame[2] = ((seq_high & 0x0F) << 4) | self._encode_hangzhou_status1(status)
        frame[3] = (self._encode_generic_status2(status) + pulse) & 0xFF
        frame[4] = (self._encode_generic_status3(status, PROTOCOL_HANGZHOU_ANXIAN) + pulse) & 0xFF
        frame[5] = (self._encode_generic_status4(status, PROTOCOL_HANGZHOU_ANXIAN) + pulse) & 0xFF
        frame[6] = self._encode_signed_current(status.current_a)
        frame[7] = (((hall_count >> 8) & 0xFF) + pulse) & 0xFF
        frame[8] = ((hall_count & 0xFF) + pulse) & 0xFF
        frame[9] = ((status.voltage_percentage & 0xFF) + pulse) & 0xFF
        frame[10] = (self._encode_voltage_mask(status) + pulse) & 0xFF
        frame[11] = self._xor_checksum(frame[:11])
        return True, frame, ""

    def generate_xinsiwei_frame_with_auto_sequence(
        self, status: StatusBits
    ) -> Tuple[bool, List[int], str]:
        """生成常州新思维发送帧，自动递增序号。"""

        auto_status = self._copy_status(status)
        auto_status.protocol_name = PROTOCOL_CHANGZHOU_XINSIWEI
        auto_status.xinsiwei_protocol = True
        auto_status.xinsiwei_sequence = self.get_next_xinsiwei_sequence()
        return self.generate_xinsiwei_frame(auto_status)

    def generate_xinsiwei_frame(self, status: StatusBits) -> Tuple[bool, List[int], str]:
        """生成常州新思维完整帧。"""

        is_valid, error_msg = self.validate_status_bits(status)
        if not is_valid:
            return False, [], error_msg

        frame = [0] * 12
        frame[0] = 0x30
        frame[1] = status.xinsiwei_sequence & 0xFF
        frame[2] = ((status.xinsiwei_sequence >> 8) & 0x0F) << 4
        frame[2] |= self._encode_xinsiwei_status1(status)
        frame[3] = self._encode_generic_status2(status)
        frame[4] = self._encode_generic_status3(status, PROTOCOL_CHANGZHOU_XINSIWEI)
        frame[5] = self._encode_generic_status4(status, PROTOCOL_CHANGZHOU_XINSIWEI)
        frame[6] = self._encode_signed_current(status.current_a)
        frame[7] = (status.xinsiwei_hall_count >> 8) & 0xFF
        frame[8] = status.xinsiwei_hall_count & 0xFF
        frame[9] = (
            self._encode_soc_fault(PROTOCOL_CHANGZHOU_XINSIWEI)
            if status.soc_fault
            else (status.soc_percent & 0xFF)
        )
        frame[10] = self._encode_voltage_mask(status)
        frame[11] = self._xor_checksum(frame[:11])

        plus_code = self.xinsiwei_pluscode_encrypt(frame)
        for index in (3, 4, 5, 7, 8, 9, 10):
            frame[index] = (frame[index] + plus_code) & 0xFF
        frame[11] = self._xor_checksum(frame[:11])
        return True, frame, ""

    def _generate_xinri_frame(self, status: StatusBits) -> Tuple[bool, List[int], str]:
        is_valid, error_msg = self.validate_status_bits(status)
        if not is_valid:
            return False, [], error_msg

        hall_count = self._resolve_hall_count(status)
        frame = [0] * 12
        frame[0] = 0x08
        frame[1] = 0x61
        frame[2] = self._encode_xinri_status1(status)
        frame[3] = self._encode_xinri_status2(status)
        frame[4] = self._encode_xinri_status3(status)
        frame[5] = self._encode_xinri_status4(status)
        frame[6] = self._encode_xinri_current(status.current_a)
        frame[7] = (hall_count >> 8) & 0xFF
        frame[8] = hall_count & 0xFF
        frame[9] = 0x00
        frame[10] = 0x00
        frame[11] = self._xor_checksum(frame[:11])
        return True, frame, ""

    def _generate_wuxi_yige_frame(self, status: StatusBits) -> Tuple[bool, List[int], str]:
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

    def _generate_tailing_y34b_frame(self, status: StatusBits) -> Tuple[bool, List[int], str]:
        is_valid, error_msg = self.validate_status_bits(status)
        if not is_valid:
            return False, [], error_msg

        speed_word = self._resolve_tailing_data67_word(status)
        frame = [0] * 13
        frame[0] = 0x08
        frame[1] = 0x61
        frame[2] = self._encode_tailing_status1(status)
        frame[3] = self._encode_generic_status2(status, include_walk_mode=True)
        frame[4] = self._encode_generic_status3(status, PROTOCOL_TAILING_Y34B)
        frame[5] = self._encode_tailing_y34b_status4(status)
        frame[6] = self._encode_signed_current(status.current_a)
        frame[7] = (speed_word >> 8) & 0xFF
        frame[8] = speed_word & 0xFF
        frame[9] = self._encode_yige_soc(status)
        frame[10] = self._encode_voltage_mask(status)
        frame[11] = self._encode_tailing_status11(status)
        frame[12] = self._xor_checksum(frame[:12])
        return True, frame, ""

    def _generate_tailing_y34f_frame(self, status: StatusBits) -> Tuple[bool, List[int], str]:
        is_valid, error_msg = self.validate_status_bits(status)
        if not is_valid:
            return False, [], error_msg

        speed_word = self._resolve_tailing_data67_word(status)
        voltage_raw = max(0, min(65535, int(round(status.tailing_real_time_voltage_v * 10))))

        frame = [0] * 15
        frame[0] = 0x08
        frame[1] = 0x61
        frame[2] = self._encode_tailing_status1(status)
        frame[3] = self._encode_tailing_y34f_status2(status)
        frame[4] = self._encode_tailing_y34f_status3(status)
        frame[5] = self._encode_tailing_y34f_status4(status)
        frame[6] = self._encode_signed_current(status.current_a)
        frame[7] = (speed_word >> 8) & 0xFF
        frame[8] = speed_word & 0xFF
        frame[9] = self._encode_yige_soc(status)
        frame[10] = self._encode_voltage_mask(status)
        frame[11] = self._encode_tailing_y34f_status11(status)
        frame[12] = (voltage_raw >> 8) & 0xFF
        frame[13] = voltage_raw & 0xFF
        frame[14] = self._xor_checksum(frame[:14])
        return True, frame, ""

    def _generate_shenzhouxing_frame(self, status: StatusBits) -> Tuple[bool, List[int], str]:
        is_valid, error_msg = self.validate_status_bits(status)
        if not is_valid:
            return False, [], error_msg

        hall_count = self._resolve_hall_count(status)
        frame = [0] * 15
        frame[0] = 0x1F
        frame[1] = 0xEE
        frame[2] = self._encode_shenzhouxing_status1(status)
        frame[3] = self._encode_shenzhouxing_status2(status)
        frame[4] = self._encode_shenzhouxing_status3(status)
        frame[5] = self._encode_shenzhouxing_status4(status)
        frame[6] = self._encode_signed_current(status.current_a)
        frame[7] = (hall_count >> 8) & 0xFF
        frame[8] = hall_count & 0xFF
        frame[9] = self._encode_shenzhouxing_status8(status)
        frame[10] = self._encode_voltage_mask(status)
        frame[11] = self._encode_shenzhouxing_data11(status)
        frame[12] = self._encode_shenzhouxing_data12(status)
        frame[13] = self._encode_shenzhouxing_data13(status)
        frame[14] = self._xor_checksum(frame[:14])
        return True, frame, ""

    def _generate_yadea_frame(self, status: StatusBits) -> Tuple[bool, List[int], str]:
        is_valid, error_msg = self.validate_status_bits(status)
        if not is_valid:
            return False, [], error_msg

        hall_count = self._resolve_hall_count(status)
        frame = [0] * 12
        frame[0] = 0x08
        frame[1] = 0x61
        frame[2] = self._encode_yadea_status1(status)
        frame[3] = self._encode_generic_status2(status)
        frame[4] = self._encode_generic_status3(status, PROTOCOL_YADEA)
        frame[5] = self._encode_generic_status4(status, PROTOCOL_YADEA)
        frame[6] = self._encode_signed_current(status.current_a)
        frame[7] = (hall_count >> 8) & 0xFF
        frame[8] = hall_count & 0xFF
        frame[9] = status.soc_percent & 0xFF
        frame[10] = status.current_percentage & 0xFF
        frame[11] = self._xor_checksum(frame[:11])
        return True, frame, ""

    def _generate_youyibao_frame(self, status: StatusBits) -> Tuple[bool, List[int], str]:
        is_valid, error_msg = self.validate_status_bits(status)
        if not is_valid:
            return False, [], error_msg

        hall_count = self._resolve_hall_count(status)
        frame = [0] * 12
        frame[0] = 0x08
        frame[1] = 0x61
        frame[2] = self._encode_youyibao_status1(status) & 0x0F
        frame[3] = self._encode_generic_status2(status)
        frame[4] = self._encode_generic_status3(status, PROTOCOL_YOUYIBAO)
        frame[5] = self._encode_generic_status4(status, PROTOCOL_YOUYIBAO)
        frame[6] = self._encode_signed_current(status.current_a)
        frame[7] = (hall_count >> 8) & 0xFF
        frame[8] = hall_count & 0xFF
        frame[9] = status.soc_percent & 0xFF
        frame[10] = status.current_percentage & 0xFF
        frame[11] = self._xor_checksum(frame[:11])
        return True, frame, ""

    def _generate_jingxian_frame_for_send(
        self, status: StatusBits
    ) -> Tuple[bool, List[int], str]:
        """生成精显发送帧，并按原规则递增序号。"""

        return self._generate_jingxian_frame(status, preview=False)

    def _generate_jingxian_frame_for_preview(
        self, status: StatusBits
    ) -> Tuple[bool, List[int], str]:
        """生成精显预览帧，不递增序号。"""

        return self._generate_jingxian_frame(status, preview=True)

    def _generate_jingxian_frame(
        self, status: StatusBits, preview: bool
    ) -> Tuple[bool, List[int], str]:
        is_valid, error_msg = self.validate_status_bits(status)
        if not is_valid:
            return False, [], error_msg

        sequence = (
            self.get_current_jingxian_sequence() if preview else self.get_next_jingxian_sequence()
        )
        plus_code = self.jingxian_pluscode_encrypt(sequence & 0xFF)
        hall_count = self._resolve_hall_count(status)

        frame = [0] * 12
        frame[0] = 0x07
        frame[1] = sequence & 0xFF
        frame[2] = self._encode_jingxian_status1(status)
        frame[3] = (self._encode_generic_status2(status, include_walk_mode=True) + plus_code) & 0xFF
        frame[4] = (self._encode_generic_status3(status, PROTOCOL_JINGXIAN) + plus_code) & 0xFF
        frame[5] = (self._encode_generic_status4(status, PROTOCOL_JINGXIAN) + plus_code) & 0xFF
        frame[6] = self._encode_signed_current(status.current_a)
        frame[7] = (((hall_count >> 8) & 0xFF) + plus_code) & 0xFF
        frame[8] = ((hall_count & 0xFF) + plus_code) & 0xFF
        frame[9] = ((status.voltage_percentage & 0xFF) + plus_code) & 0xFF
        frame[10] = ((status.current_percentage & 0xFF) + plus_code) & 0xFF
        frame[11] = self._xor_checksum(frame[:11])
        return True, frame, ""

    def _generate_dongwei_gtxh_frame(self, status: StatusBits) -> Tuple[bool, List[int], str]:
        is_valid, error_msg = self.validate_status_bits(status)
        if not is_valid:
            return False, [], error_msg

        hall_count = self._resolve_hall_count(status)
        frame = [0] * 12
        frame[0] = 0x08
        frame[1] = 0x61
        frame[2] = self._encode_dongwei_status1(status)
        frame[3] = self._encode_generic_status2(status)
        frame[4] = self._encode_generic_status3(status, PROTOCOL_DONGWEI_GTXH)
        frame[5] = self._encode_generic_status4(status, PROTOCOL_DONGWEI_GTXH)
        frame[6] = self._encode_dongwei_current(status.current_a)
        frame[7] = (hall_count >> 8) & 0xFF
        frame[8] = hall_count & 0xFF
        frame[9] = status.soc_percent & 0xFF
        frame[10] = status.current_percentage & 0xFF
        frame[11] = self._xor_checksum(frame[:11])
        return True, frame, ""

    def _generate_xinchi_frame(self, status: StatusBits) -> Tuple[bool, List[int], str]:
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

    def _generate_luyuan_bms_frame(self, status: StatusBits) -> Tuple[bool, List[int], str]:
        is_valid, error_msg = self.validate_status_bits(status)
        if not is_valid:
            return False, [], error_msg

        current_raw = self._encode_luyuan_current(status.luyuan_current_a)

        frame = [0] * 15
        frame[0] = 0x3A
        frame[1] = self._encode_luyuan_status0(status)
        frame[2] = status.soc_percent & 0xFF
        frame[3] = status.luyuan_cycle_count & 0xFF
        frame[4] = (status.luyuan_cycle_count >> 8) & 0xFF
        frame[5] = self._encode_signed_byte(status.luyuan_temperature_c)
        frame[6] = status.luyuan_max_cell_voltage_mv & 0xFF
        frame[7] = (status.luyuan_max_cell_voltage_mv >> 8) & 0xFF
        frame[8] = status.luyuan_min_cell_voltage_mv & 0xFF
        frame[9] = (status.luyuan_min_cell_voltage_mv >> 8) & 0xFF
        frame[10] = current_raw & 0xFF
        frame[11] = (current_raw >> 8) & 0xFF
        frame[12] = status.luyuan_total_voltage_v & 0xFF
        frame[13] = status.luyuan_soh_percent & 0xFF
        frame[14] = self._sum_checksum(frame[:14])
        return True, frame, ""

    def _generate_lithium_bms_frame(self, status: StatusBits) -> Tuple[bool, List[int], str]:
        is_valid, error_msg = self.validate_status_bits(status)
        if not is_valid:
            return False, [], error_msg

        frame = [0] * 12
        frame[0] = 0x03
        frame[1] = 0x01
        frame[2] = self._encode_lithium_bms_status1(status)
        frame[3] = self._encode_lithium_bms_cell_voltage(status.lithium_bms_max_cell_voltage_v)
        frame[4] = status.soc_percent & 0xFF
        frame[5] = max(0, min(255, int(round(status.lithium_bms_total_voltage_v))))
        frame[6] = self._encode_lithium_bms_temperature(status.lithium_bms_max_temp_c)
        frame[7] = self._encode_lithium_bms_temperature(status.lithium_bms_min_temp_c)
        frame[8] = (status.lithium_bms_cycle_count >> 8) & 0xFF
        frame[9] = status.lithium_bms_cycle_count & 0xFF
        frame[10] = self._encode_lithium_bms_cell_voltage(status.lithium_bms_min_cell_voltage_v)
        frame[11] = self._xor_checksum(frame[:11])
        return True, frame, ""

    def _generate_battery_single_wire_frame(
        self, status: StatusBits
    ) -> Tuple[bool, List[int], str]:
        is_valid, error_msg = self.validate_status_bits(status)
        if not is_valid:
            return False, [], error_msg

        frame = [0] * 6
        frame[0] = 0x00
        frame[1] = status.soc_percent & 0xFF
        frame[2] = 0x00
        frame[3] = 0x00
        frame[4] = 0x00
        frame[5] = self._sum_checksum(frame[:5])
        return True, frame, ""

    def _encode_ruilun_status1(self, status: StatusBits) -> int:
        value = 0
        if status.distance_mode:
            value |= 0x08
        if status.speed_alarm:
            value |= 0x04
        if status.p_gear_protect:
            value |= 0x02
        if status.tcs_status:
            value |= 0x01
        return value

    def _encode_fz_sif_status1(self, status: StatusBits) -> int:
        value = 0
        if status.side_stand:
            value |= 0x08
        if status.protocol_speed_limit:
            value |= 0x04
        if status.p_gear_protect:
            value |= 0x02
        return value

    def _encode_hangzhou_status1(self, status: StatusBits) -> int:
        value = 0
        if status.protocol_speed_limit:
            value |= 0x04
        if status.p_gear_protect:
            value |= 0x02
        return value

    def _encode_yige_status1(self, status: StatusBits) -> int:
        value = 0
        if status.side_stand:
            value |= 0x08
        if status.p_gear_protect:
            value |= 0x02
        return value

    def _encode_tailing_status1(self, status: StatusBits) -> int:
        value = 0
        if status.side_stand:
            value |= 0x08
        if status.p_gear_protect:
            value |= 0x02
        if status.tailing_national_standard:
            value |= 0x01
        return value

    def _encode_yadea_status1(self, status: StatusBits) -> int:
        value = 0
        if status.side_stand:
            value |= 0x08
        if status.p_gear_protect:
            value |= 0x02
        return value

    def _encode_youyibao_status1(self, status: StatusBits) -> int:
        value = 0
        if status.p_gear_protect:
            value |= 0x08
        if status.side_stand:
            value |= 0x04
        return value

    def _encode_jingxian_status1(self, status: StatusBits) -> int:
        value = 0
        if status.side_stand:
            value |= 0x08
        if status.p_gear_protect:
            value |= 0x02
        return value

    def _encode_dongwei_status1(self, status: StatusBits) -> int:
        value = 0
        if status.p_gear_protect:
            value |= 0x08
        value |= self._encode_dongwei_voltage_state(status)
        return value

    def _encode_xinchi_status0(self, status: StatusBits) -> int:
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

    def _encode_luyuan_status0(self, status: StatusBits) -> int:
        value = 0
        if status.luyuan_charge_mos:
            value |= 0x80
        if status.luyuan_discharge_mos:
            value |= 0x40
        if status.luyuan_predischarge_mos:
            value |= 0x20
        if status.luyuan_charge_enable:
            value |= 0x10
        if status.luyuan_charger_connected:
            value |= 0x08
        return value

    def _encode_lithium_bms_status1(self, status: StatusBits) -> int:
        value = 0
        if status.lithium_bms_alarm_enable:
            value |= 0x80
        if status.lithium_bms_high_temp_alarm:
            value |= 0x40
        if status.lithium_bms_low_temp_alarm:
            value |= 0x20
        if status.lithium_bms_soh_low:
            value |= 0x10
        if status.lithium_bms_mos_fault:
            value |= 0x08
        if status.lithium_bms_short_circuit_fault:
            value |= 0x04
        return value

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

    def _encode_tailing_y34b_status4(self, status: StatusBits) -> int:
        value = 0
        if status.cloud_power_mode:
            value |= 0x80
        if status.tailing_actual_speed_mode:
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
        return value

    def _encode_tailing_y34f_status2(self, status: StatusBits) -> int:
        value = 0
        if status.walk_mode:
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
        if status.tailing_tire_pressure_low:
            value |= 0x02
        return value

    def _encode_tailing_y34f_status3(self, status: StatusBits) -> int:
        value = 0
        if status.gear_four:
            value |= 0x80
        if status.tailing_tcs_indicator:
            value |= 0x40
        if status.brake:
            value |= 0x20
        if status.tailing_hdc_indicator:
            value |= 0x10
        if status.regen_charging:
            value |= 0x08
        value |= status.speed_mode & 0x03
        return value

    def _encode_tailing_y34f_status4(self, status: StatusBits) -> int:
        value = 0
        if status.cloud_power_mode:
            value |= 0x80
        if status.tailing_actual_speed_mode:
            value |= 0x40
        if status.tailing_dual_undervoltage:
            value |= 0x20
        if status.over_current:
            value |= 0x10
        if status.stall_protect:
            value |= 0x08
        if status.reverse:
            value |= 0x04
        value |= status.tailing_seat_state & 0x03
        return value

    def _encode_tailing_status11(self, status: StatusBits) -> int:
        value = 0
        if status.tailing_dual_soc:
            value |= 0x08
        if status.tailing_display_sleep:
            value |= 0x04
        if status.tailing_speed_15kmh_warning:
            value |= 0x02
        if status.tailing_brake_fault:
            value |= 0x01
        return value

    def _encode_tailing_y34f_status11(self, status: StatusBits) -> int:
        value = 0
        if status.tailing_display_voltage_from_data:
            value |= 0x80
        if status.tailing_battery_over_temp:
            value |= 0x40
        if status.tailing_battery_over_current:
            value |= 0x20
        if status.tailing_battery_over_voltage:
            value |= 0x10
        value |= self._encode_tailing_status11(status)
        return value

    def _encode_shenzhouxing_status1(self, status: StatusBits) -> int:
        value = 0
        if status.side_stand:
            value |= 0x08
        if status.shenzhouxing_hdc:
            value |= 0x04
        if status.p_gear_protect:
            value |= 0x02
        if status.shenzhouxing_hhc:
            value |= 0x01
        return value

    def _encode_shenzhouxing_status2(self, status: StatusBits) -> int:
        value = 0
        if status.shenzhouxing_tcs:
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

    def _encode_shenzhouxing_status3(self, status: StatusBits) -> int:
        value = 0
        if status.gear_four:
            value |= 0x80
        if status.motor_running:
            value |= 0x40
        if status.shenzhouxing_brake_fault:
            value |= 0x20
        if status.controller_protect:
            value |= 0x10
        if status.regen_charging:
            value |= 0x08
        if status.anti_runaway:
            value |= 0x04
        value |= status.speed_mode & 0x03
        return value

    def _encode_shenzhouxing_status4(self, status: StatusBits) -> int:
        value = 0
        if status.shenzhouxing_bluetooth:
            value |= 0x80
        if status.shenzhouxing_time_display:
            value |= 0x40
        if status.shenzhouxing_4g_signal_indicator:
            value |= 0x20
        if status.shenzhouxing_position_indicator:
            value |= 0x10
        if status.stall_protect:
            value |= 0x08
        if status.reverse:
            value |= 0x04
        if status.brake:
            value |= 0x02
        if status.speed_limit:
            value |= 0x01
        return value

    def _encode_shenzhouxing_status8(self, status: StatusBits) -> int:
        if status.lithium_soc_mode:
            return 0x80 | (status.soc_percent & 0x7F)
        return status.shenzhouxing_real_time_voltage_v & 0x7F

    def _encode_shenzhouxing_data11(self, status: StatusBits) -> int:
        hour = status.shenzhouxing_time_hour & 0x1F
        return ((status.shenzhouxing_signal_strength & 0x1F) << 3) | ((hour >> 2) & 0x07)

    def _encode_shenzhouxing_data12(self, status: StatusBits) -> int:
        hour = status.shenzhouxing_time_hour & 0x1F
        return ((hour & 0x03) << 6) | (status.shenzhouxing_time_minute & 0x3F)

    def _encode_shenzhouxing_data13(self, status: StatusBits) -> int:
        value = 0
        if status.shenzhouxing_push_assist:
            value |= 0x80
        if status.shenzhouxing_p_blink:
            value |= 0x40
        return value

    def _encode_ruilun_soc(self, status: StatusBits) -> int:
        if status.soc_fault:
            return self._encode_soc_fault(PROTOCOL_RUILUN)
        if status.lithium_soc_mode:
            return 0x80 | (status.soc_percent & 0x7F)
        return 0x00

    def _encode_soc_fault(self, protocol_name: str) -> int:
        """从协议定义读取并返回 SOC 故障编码。"""

        fault_value = PROTOCOL_DEFINITIONS[protocol_name].soc_fault_value
        if fault_value is None:
            raise ValueError(f"{protocol_name} 未定义 SOC 故障编码")
        return fault_value

    def _encode_yige_soc(self, status: StatusBits) -> int:
        if status.lithium_soc_mode:
            return 0x80 | (status.soc_percent & 0x7F)
        return 0x00

    def _encode_voltage_mask(self, status: StatusBits) -> int:
        mask = 0
        for field_name, bit_mask in VOLTAGE_OPTIONS:
            if getattr(status, field_name, False):
                mask |= bit_mask
        return mask & 0xFF

    def _encode_fz_sif_voltage_mask(self, status: StatusBits) -> int:
        if status.voltage_48v:
            return 0x02
        if status.voltage_60v:
            return 0x04
        if status.voltage_64v:
            return 0x08
        if status.voltage_72v:
            return 0x10
        if status.voltage_84v:
            return 0x20
        if status.voltage_96v:
            return 0x40
        return 0x00

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

    def _encode_xinri_current(self, current_a: float) -> int:
        raw_value = round(abs(current_a) * 5)
        return max(0, min(255, raw_value))

    def _encode_dongwei_current(self, current_a: float) -> int:
        scaled_value = round(current_a * 5)
        scaled_value = max(-128, min(127, scaled_value))
        return scaled_value & 0xFF

    def _is_luyuan_current_encodable(self, current_a: float) -> bool:
        magnitude = int(round(abs(current_a) * 100))
        return magnitude <= 0x7FFF

    def _encode_luyuan_current(self, current_a: float) -> int:
        magnitude = min(0x7FFF, int(round(abs(current_a) * 100)))
        if current_a < 0:
            return 0x8000 | magnitude
        return magnitude

    def _encode_dongwei_voltage_state(self, status: StatusBits) -> int:
        if status.voltage_48v:
            return 0x02
        if status.voltage_60v:
            return 0x01
        if status.voltage_72v:
            return 0x03
        if status.voltage_80v:
            return 0x04
        if status.voltage_96v:
            return 0x05
        return 0x00

    def _is_lithium_bms_cell_voltage_encodable(self, voltage_v: float) -> bool:
        raw_value = int(round(voltage_v * 100)) - 185
        return 0 <= raw_value <= 255

    def _encode_lithium_bms_cell_voltage(self, voltage_v: float) -> int:
        raw_value = int(round(voltage_v * 100)) - 185
        return max(0, min(255, raw_value))

    def _encode_sign_magnitude_byte(self, value: int) -> int:
        magnitude = min(127, abs(int(value)))
        if value < 0:
            return 0x80 | magnitude
        return magnitude & 0x7F

    def _encode_signed_byte(self, value: int) -> int:
        return int(value) & 0xFF

    def _encode_lithium_bms_temperature(self, temp_c: int) -> int:
        return self._encode_sign_magnitude_byte(temp_c)

    def _encode_xinsiwei_status1(self, status: StatusBits) -> int:
        value = 0
        if status.xinsiwei_reserved_d3:
            value |= 0x08
        if status.xinsiwei_reserved_d2:
            value |= 0x04
        if status.xinsiwei_reserved_d1:
            value |= 0x02
        if status.xinsiwei_reserved_d0:
            value |= 0x01
        return value

    def _encode_xinri_status1(self, status: StatusBits) -> int:
        value = 0
        if status.p_gear_protect:
            value |= 0x08
        if status.low_voltage_alarm or status.under_voltage:
            value |= 0x04
        return value

    def _encode_xinri_status2(self, status: StatusBits) -> int:
        value = 0
        if status.hall_fault:
            value |= 0x40
        if status.throttle_fault:
            value |= 0x20
        if status.controller_fault:
            value |= 0x10
        if status.cruise:
            value |= 0x04
        return value

    def _encode_xinri_status3(self, status: StatusBits) -> int:
        value = 0
        if status.speed_mode & 0x04:
            value |= 0x80
        if status.brake:
            value |= 0x20
        value |= status.speed_mode & 0x03
        return value

    def _encode_xinri_status4(self, status: StatusBits) -> int:
        return 0x40 if status.one_key_enable else 0x00

    def _resolve_hall_count(self, status: StatusBits) -> int:
        if status.hall_count > 0:
            return status.hall_count & 0xFFFF
        return max(0, min(65535, int(round(status.speed_kmh * 10))))

    def _resolve_tailing_data67_word(self, status: StatusBits) -> int:
        if status.tailing_actual_speed_mode:
            return max(0, min(65535, int(round(status.speed_kmh * 10))))
        return self._resolve_hall_count(status)

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
        """获取某个协议的字节描述。"""

        descriptions: Dict[str, List[str]] = {
            PROTOCOL_RUILUN: [
                "设备编码 (固定 0x08)",
                "流水号低 8 位 (固定 0x61)",
                "Status1",
                "Status2",
                "Status3",
                "Status4",
                "Status5 运行电流",
                "Status6 霍尔计数高字节",
                "Status7 霍尔计数低字节",
                "Status8 锂电 SOC/仪表自算",
                "Status9 协议切换电压",
                "校验和 (XOR)",
            ],
            PROTOCOL_FZ_SIF: [
                "设备编码 (固定 0x08)",
                "流水号 (固定 0x61)",
                "Status1 侧撑/限速中/驻车",
                "Status2 推行/故障/巡航/助力",
                "Status3 电机/刹车/保护/速度模式",
                "Status4 云动力/一键通/EKK/保护",
                "Status5 运行电流",
                "Status6 速度霍尔计数高字节",
                "Status7 速度霍尔计数低字节",
                "Status8 电池电量/电压比例值",
                "Status9 控制器额定工作电压",
                "校验和 (XOR)",
            ],
            PROTOCOL_HANGZHOU_ANXIAN: [
                "设备编码 (固定 0x08)",
                "流水号低 8 位 (自动递增)",
                "流水号高 4 位 + Status1",
                "Status2 + Pulse",
                "Status3 + Pulse",
                "Status4 + Pulse",
                "Status5 运行电流",
                "Status6 霍尔计数高字节 + Pulse",
                "Status7 霍尔计数低字节 + Pulse",
                "Status8 电压百分比 + Pulse",
                "Status9 协议切换电压 + Pulse",
                "校验和 (XOR)",
            ],
            PROTOCOL_XINRI: [
                "设备编码 (固定 0x08)",
                "流水号低 8 位 (固定 0x61)",
                "Status1",
                "Status2",
                "Status3",
                "Status4",
                "Status5 电流 (0.2A/LSB)",
                "Status6 霍尔计数高字节",
                "Status7 霍尔计数低字节",
                "Status8 预留",
                "Status9 预留",
                "校验和 (XOR)",
            ],
            PROTOCOL_CHANGZHOU_XINSIWEI: [
                "设备编码 (固定 0x30)",
                "流水号低 8 位",
                "流水号高 4 位 + Status1",
                "Status2 + PlusCode",
                "Status3 + PlusCode",
                "Status4 + PlusCode",
                "Status5 运行电流",
                "Status6 霍尔计数高字节 + PlusCode",
                "Status7 霍尔计数低字节 + PlusCode",
                "Status8 SOC + PlusCode",
                "Status9 协议切换电压 + PlusCode",
                "校验和 (XOR)",
            ],
            PROTOCOL_WUXI_YIGE: [
                "设备编码 (固定 0x10)",
                "流水号 (固定 0x95)",
                "Status1",
                "Status2",
                "Status3",
                "Status4",
                "Status5 运行电流",
                "Status6 霍尔计数高字节",
                "Status7 霍尔计数低字节",
                "Status8 锂电 SOC 透传",
                "Status9 协议切换电压",
                "校验和 (XOR)",
            ],
            PROTOCOL_TAILING_Y34B: [
                "设备编码 (固定 0x08)",
                "流水号 (固定 0x61)",
                "DATA2 侧撑/P档/国标轻摩状态",
                "DATA3 推行/故障/巡航/助力/缺相",
                "DATA4 四档/运行/刹车/保护/滑充/三速",
                "DATA5 云动力/速度协议/EKK/保护",
                "DATA6 运行电流",
                "DATA7 速度高字节/实际车速高字节",
                "DATA8 速度低字节/实际车速低字节",
                "DATA9 锂电 SOC/铅酸模式",
                "DATA10 控制器额定工作电压",
                "DATA11 双显SOC/休眠/15kmh预警/刹车故障",
                "DATA12 校验和 (XOR)",
            ],
            PROTOCOL_TAILING_Y34F: [
                "设备编码 (固定 0x08)",
                "流水号 (固定 0x61)",
                "DATA2 侧撑/P档/国标轻摩状态",
                "DATA3 推车/故障/巡航/胎压信号",
                "DATA4 四档/TCS/刹车/HDC/滑充/三速",
                "DATA5 云动力/速度协议/双欠压/坐垫功能",
                "DATA6 运行电流",
                "DATA7 速度高字节/实际车速高字节",
                "DATA8 速度低字节/实际车速低字节",
                "DATA9 锂电 SOC/铅酸模式",
                "DATA10 控制器额定工作电压",
                "DATA11 电压采集/团标电池故障/扩展状态",
                "DATA12 实时电压高字节 (*10)",
                "DATA13 实时电压低字节 (*10)",
                "DATA14 校验和 (XOR)",
            ],
            PROTOCOL_SHENZHOUXING: [
                "设备编码 (固定 0x1F)",
                "流水号低8位 (固定 0xEE)",
                "DATA2 流水号高4位+侧撑/HDC/P档/HHC",
                "DATA3 TCS/故障/巡航/助力/缺相",
                "DATA4 四档/运行/刹车故障/控制器保护/速度模式",
                "DATA5 蓝牙/时间/4G/定位/堵转/倒车/刹车/限速",
                "DATA6 运行电流",
                "DATA7 速度高字节/500ms霍尔计数高字节",
                "DATA8 速度低字节/500ms霍尔计数低字节",
                "DATA9 锂电SOC/实时电压",
                "DATA10 控制器额定工作电压",
                "DATA11 4G信号强度+时间小时高3位",
                "DATA12 时间小时低2位+时间分钟",
                "DATA13 推车/P档闪烁",
                "DATA14 校验和 (XOR)",
            ],
            PROTOCOL_YADEA: [
                "设备编码 (固定 0x08)",
                "流水号 (固定 0x61)",
                "Status1",
                "Status2",
                "Status3",
                "Status4",
                "Status5 运行电流",
                "Status6 霍尔计数高字节",
                "Status7 霍尔计数低字节",
                "Status8 电量百分比",
                "Status9 电流百分比",
                "校验和 (XOR)",
            ],
            PROTOCOL_YOUYIBAO: [
                "设备编码 (固定 0x08)",
                "流水号 (固定 0x61)",
                "Status1 低4位 (P挡/侧撑)",
                "Status2 故障/巡航/助力",
                "Status3 电机/刹车/保护/速度模式",
                "Status4 70%电流/一键通/EKK/保护",
                "Status5 运行电流",
                "Status6 霍尔计数高字节",
                "Status7 霍尔计数低字节",
                "Status8 电压/电量百分比",
                "Status9 电流百分比",
                "校验和 (XOR)",
            ],
            PROTOCOL_JINGXIAN: [
                "设备编码 (固定 0x07)",
                "流水号 SEQ_CODE (自动递增)",
                "Status1 (不加密，含 P档信息)",
                "Status2 + PlusCod",
                "Status3 + PlusCod",
                "Status4 + PlusCod",
                "电流值 (不加密)",
                "霍尔速度高字节 + PlusCod",
                "霍尔速度低字节 + PlusCod",
                "电压比例 + PlusCod",
                "电流比例 + PlusCod",
                "校验和 (XOR)",
            ],
            PROTOCOL_DONGWEI_GTXH: [
                "设备编码 (固定 0x08)",
                "流水号 (固定 0x61)",
                "Status1 P驻车 + 电压状态",
                "Status2",
                "Status3 档位模式",
                "Status4 侧撑/EKK/保护",
                "Status5 运行电流 (0.2A/LSB)",
                "Status6 霍尔计数高字节",
                "Status7 霍尔计数低字节",
                "Status8 电压/电量百分比",
                "Status9 电流百分比",
                "校验和 (XOR)",
            ],
            PROTOCOL_XINCHI: [
                "ID (固定 0x3A)",
                "Byte0 BMS当前状态",
                "Byte1 SOC",
                "Byte2 循环次数低字节",
                "Byte3 循环次数高字节",
                "Byte4 电池温度(有符号)",
                "Byte5 总电压低字节(0.1V)",
                "Byte6 总电压高字节(0.1V)",
                "Byte7 总电流(A)",
                "CheckSum 累加和",
            ],
            PROTOCOL_LUYUAN_BMS: [
                "ID (固定 0x3A)",
                "Byte0 BMS当前状态",
                "Byte1 SOC",
                "Byte2 循环次数低字节",
                "Byte3 循环次数高字节",
                "Byte4 电池温度(有符号8位)",
                "Byte5 最高电芯电压低字节(mV)",
                "Byte6 最高电芯电压高字节(mV)",
                "Byte7 最低电芯电压低字节(mV)",
                "Byte8 最低电芯电压高字节(mV)",
                "Byte9 电流低字节(0.01A/bit)",
                "Byte10 电流高字节(符号位)",
                "Byte11 总电压(V)",
                "Byte12 健康度 SOH",
                "CheckSum 累加和",
            ],
            PROTOCOL_LITHIUM_BMS: [
                "设备编码 (固定 0x03)",
                "通讯指令/配置 (固定 0x01)",
                "Status1 故障状态",
                "Status2 最高电芯电压 (10mV, 偏移 185)",
                "Status3 SOC 电量",
                "Status4 总压 (1V)",
                "Status5 最高电池温度",
                "Status6 最低电池温度",
                "Status7 循环次数高字节",
                "Status8 循环次数低字节",
                "Status9 最低电芯电压 (10mV, 偏移 185)",
                "校验和 (XOR)",
            ],
            PROTOCOL_BATTERY_SINGLE_WIRE: [
                "BYTE1 固定 0x00",
                "BYTE2 电池剩余容量 SOC",
                "BYTE3 固定 0x00",
                "BYTE4 固定 0x00",
                "BYTE5 固定 0x00",
                "BYTE6 8 位累加校验和",
            ],
        }
        return descriptions.get(protocol_name, descriptions[PROTOCOL_RUILUN])

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


class PresetScenarios:
    """预设场景。"""

    @staticmethod
    def normal_running() -> StatusBits:
        status = StatusBits(protocol_name=PROTOCOL_RUILUN)
        status.voltage_48v = True
        status.hall_count = 3200
        status.soc_percent = 80
        status.lithium_soc_mode = True
        status.motor_running = True
        status.current_a = 12
        return status

    @staticmethod
    def energy_recovery() -> StatusBits:
        status = StatusBits(protocol_name=PROTOCOL_RUILUN)
        status.voltage_60v = True
        status.voltage_48v = False
        status.hall_count = 2600
        status.soc_percent = 60
        status.lithium_soc_mode = True
        status.regen_charging = True
        status.current_a = -3
        return status

    @staticmethod
    def fault_scenario() -> StatusBits:
        status = StatusBits(protocol_name=PROTOCOL_RUILUN)
        status.voltage_72v = True
        status.voltage_48v = False
        status.hall_count = 0
        status.soc_fault = True
        status.hall_fault = True
        status.throttle_fault = True
        status.controller_fault = True
        status.electronic_brake = True
        status.speed_limit = True
        return status

    @staticmethod
    def fz_sif_normal_running() -> StatusBits:
        status = StatusBits(protocol_name=PROTOCOL_FZ_SIF)
        status.voltage_48v = True
        status.hall_count = 3200
        status.voltage_percentage = 80
        status.motor_running = True
        status.current_a = 12
        return status

    @staticmethod
    def fz_sif_energy_recovery() -> StatusBits:
        status = StatusBits(protocol_name=PROTOCOL_FZ_SIF)
        status.voltage_60v = True
        status.voltage_48v = False
        status.hall_count = 2600
        status.voltage_percentage = 60
        status.regen_charging = True
        status.current_a = -3
        return status

    @staticmethod
    def fz_sif_fault_scenario() -> StatusBits:
        status = StatusBits(protocol_name=PROTOCOL_FZ_SIF)
        status.voltage_72v = True
        status.voltage_48v = False
        status.hall_count = 0
        status.voltage_percentage = 15
        status.side_stand = True
        status.protocol_speed_limit = True
        status.hall_fault = True
        status.throttle_fault = True
        status.controller_fault = True
        status.under_voltage = True
        status.electronic_brake = True
        status.speed_limit = True
        return status

    @staticmethod
    def xinri_normal_running() -> StatusBits:
        status = StatusBits(protocol_name=PROTOCOL_XINRI)
        status.hall_count = 2800
        status.current_a = 8
        status.speed_mode = 2
        return status

    @staticmethod
    def xinri_energy_recovery() -> StatusBits:
        status = StatusBits(protocol_name=PROTOCOL_XINRI)
        status.hall_count = 2200
        status.current_a = 4
        status.speed_mode = 1
        status.cruise = True
        return status

    @staticmethod
    def xinri_fault_scenario() -> StatusBits:
        status = StatusBits(protocol_name=PROTOCOL_XINRI)
        status.hall_fault = True
        status.throttle_fault = True
        status.controller_fault = True
        status.brake = True
        status.low_voltage_alarm = True
        return status

    @staticmethod
    def hangzhou_anxian_normal_running() -> StatusBits:
        status = StatusBits(protocol_name=PROTOCOL_HANGZHOU_ANXIAN)
        status.voltage_48v = True
        status.hall_count = 3000
        status.voltage_percentage = 75
        status.motor_running = True
        status.speed_mode = 2
        return status

    @staticmethod
    def hangzhou_anxian_energy_recovery() -> StatusBits:
        status = StatusBits(protocol_name=PROTOCOL_HANGZHOU_ANXIAN)
        status.voltage_60v = True
        status.voltage_48v = False
        status.hall_count = 2400
        status.voltage_percentage = 90
        status.regen_charging = True
        status.current_a = -2
        return status

    @staticmethod
    def hangzhou_anxian_fault_scenario() -> StatusBits:
        status = StatusBits(protocol_name=PROTOCOL_HANGZHOU_ANXIAN)
        status.voltage_48v = True
        status.voltage_percentage = 20
        status.hall_count = 0
        status.controller_fault = True
        status.under_voltage = True
        status.over_current = True
        status.speed_limit = True
        return status

    @staticmethod
    def changzhou_xinsiwei_normal_running() -> StatusBits:
        status = StatusBits(protocol_name=PROTOCOL_CHANGZHOU_XINSIWEI)
        status.xinsiwei_protocol = True
        status.voltage_48v = True
        status.xinsiwei_hall_count = 8500
        status.soc_percent = 80
        status.motor_running = True
        status.current_a = 15
        return status

    @staticmethod
    def changzhou_xinsiwei_energy_recovery() -> StatusBits:
        status = StatusBits(protocol_name=PROTOCOL_CHANGZHOU_XINSIWEI)
        status.xinsiwei_protocol = True
        status.voltage_60v = True
        status.voltage_48v = False
        status.xinsiwei_hall_count = 6800
        status.soc_percent = 60
        status.regen_charging = True
        status.current_a = -3
        status.xinsiwei_reserved_d0 = True
        return status

    @staticmethod
    def changzhou_xinsiwei_fault_scenario() -> StatusBits:
        status = StatusBits(protocol_name=PROTOCOL_CHANGZHOU_XINSIWEI)
        status.xinsiwei_protocol = True
        status.voltage_72v = True
        status.voltage_48v = False
        status.xinsiwei_hall_count = 0
        status.soc_fault = True
        status.throttle_fault = True
        status.controller_fault = True
        status.under_voltage = True
        status.xinsiwei_reserved_d0 = True
        status.xinsiwei_reserved_d1 = True
        return status

    @staticmethod
    def wuxi_yige_normal_running() -> StatusBits:
        status = StatusBits(protocol_name=PROTOCOL_WUXI_YIGE)
        status.voltage_48v = True
        status.hall_count = 3000
        status.soc_percent = 78
        status.lithium_soc_mode = True
        status.motor_running = True
        status.current_a = 10
        return status

    @staticmethod
    def wuxi_yige_energy_recovery() -> StatusBits:
        status = StatusBits(protocol_name=PROTOCOL_WUXI_YIGE)
        status.voltage_60v = True
        status.voltage_48v = False
        status.hall_count = 2500
        status.soc_percent = 66
        status.lithium_soc_mode = True
        status.regen_charging = True
        status.current_a = -2
        status.cloud_power_mode = True
        return status

    @staticmethod
    def wuxi_yige_fault_scenario() -> StatusBits:
        status = StatusBits(protocol_name=PROTOCOL_WUXI_YIGE)
        status.voltage_72v = True
        status.voltage_48v = False
        status.hall_count = 0
        status.walk_mode = True
        status.hall_fault = True
        status.controller_fault = True
        status.side_stand = True
        status.p_gear_protect = True
        return status

    @staticmethod
    def tailing_y34b_normal_running() -> StatusBits:
        status = StatusBits(protocol_name=PROTOCOL_TAILING_Y34B)
        status.voltage_48v = True
        status.hall_count = 3000
        status.soc_percent = 78
        status.lithium_soc_mode = True
        status.motor_running = True
        status.current_a = 10
        status.tailing_national_standard = True
        return status

    @staticmethod
    def tailing_y34b_energy_recovery() -> StatusBits:
        status = StatusBits(protocol_name=PROTOCOL_TAILING_Y34B)
        status.voltage_60v = True
        status.voltage_48v = False
        status.soc_percent = 66
        status.lithium_soc_mode = True
        status.regen_charging = True
        status.cloud_power_mode = True
        status.tailing_actual_speed_mode = True
        status.speed_kmh = 28.6
        status.current_a = -2
        status.tailing_national_standard = True
        return status

    @staticmethod
    def tailing_y34b_fault_scenario() -> StatusBits:
        status = StatusBits(protocol_name=PROTOCOL_TAILING_Y34B)
        status.voltage_72v = True
        status.voltage_48v = False
        status.hall_count = 0
        status.walk_mode = True
        status.hall_fault = True
        status.controller_fault = True
        status.under_voltage = True
        status.side_stand = True
        status.p_gear_protect = True
        status.tailing_display_sleep = True
        status.tailing_speed_15kmh_warning = True
        status.tailing_brake_fault = True
        return status

    @staticmethod
    def tailing_y34f_normal_running() -> StatusBits:
        status = StatusBits(protocol_name=PROTOCOL_TAILING_Y34F)
        status.voltage_48v = True
        status.hall_count = 3200
        status.soc_percent = 80
        status.lithium_soc_mode = True
        status.current_a = 11
        status.speed_mode = 2
        status.tailing_national_standard = True
        status.tailing_real_time_voltage_v = 54.6
        return status

    @staticmethod
    def tailing_y34f_energy_recovery() -> StatusBits:
        status = StatusBits(protocol_name=PROTOCOL_TAILING_Y34F)
        status.voltage_60v = True
        status.voltage_48v = False
        status.soc_percent = 64
        status.lithium_soc_mode = True
        status.regen_charging = True
        status.cloud_power_mode = True
        status.tailing_actual_speed_mode = True
        status.speed_kmh = 32.4
        status.current_a = -3
        status.speed_mode = 1
        status.tailing_national_standard = True
        status.tailing_tcs_indicator = True
        status.tailing_real_time_voltage_v = 61.2
        return status

    @staticmethod
    def tailing_y34f_fault_scenario() -> StatusBits:
        status = StatusBits(protocol_name=PROTOCOL_TAILING_Y34F)
        status.voltage_72v = True
        status.voltage_48v = False
        status.walk_mode = True
        status.hall_fault = True
        status.controller_fault = True
        status.under_voltage = True
        status.side_stand = True
        status.p_gear_protect = True
        status.brake = True
        status.tailing_tire_pressure_low = True
        status.tailing_tcs_indicator = True
        status.tailing_hdc_indicator = True
        status.tailing_dual_undervoltage = True
        status.tailing_seat_state = 0x01
        status.tailing_display_voltage_from_data = True
        status.tailing_battery_over_temp = True
        status.tailing_battery_over_current = True
        status.tailing_battery_over_voltage = True
        status.tailing_dual_soc = True
        status.tailing_display_sleep = True
        status.tailing_speed_15kmh_warning = True
        status.tailing_brake_fault = True
        status.tailing_real_time_voltage_v = 65.8
        return status

    @staticmethod
    def shenzhouxing_normal_running() -> StatusBits:
        status = StatusBits(protocol_name=PROTOCOL_SHENZHOUXING)
        status.voltage_48v = True
        status.hall_count = 3000
        status.soc_percent = 82
        status.lithium_soc_mode = True
        status.motor_running = True
        status.current_a = 10
        status.shenzhouxing_bluetooth = True
        status.shenzhouxing_time_display = True
        status.shenzhouxing_4g_signal_indicator = True
        status.shenzhouxing_signal_strength = 18
        status.shenzhouxing_time_hour = 14
        status.shenzhouxing_time_minute = 35
        return status

    @staticmethod
    def shenzhouxing_energy_recovery() -> StatusBits:
        status = StatusBits(protocol_name=PROTOCOL_SHENZHOUXING)
        status.voltage_60v = True
        status.voltage_48v = False
        status.hall_count = 2600
        status.soc_percent = 68
        status.lithium_soc_mode = True
        status.regen_charging = True
        status.current_a = -3
        status.speed_mode = 2
        status.shenzhouxing_tcs = True
        status.shenzhouxing_time_display = True
        status.shenzhouxing_4g_signal_indicator = True
        status.shenzhouxing_position_indicator = True
        status.shenzhouxing_signal_strength = 21
        status.shenzhouxing_time_hour = 9
        status.shenzhouxing_time_minute = 18
        return status

    @staticmethod
    def shenzhouxing_fault_scenario() -> StatusBits:
        status = StatusBits(protocol_name=PROTOCOL_SHENZHOUXING)
        status.voltage_72v = True
        status.voltage_48v = False
        status.hall_count = 0
        status.side_stand = True
        status.shenzhouxing_hdc = True
        status.p_gear_protect = True
        status.shenzhouxing_hhc = True
        status.shenzhouxing_tcs = True
        status.hall_fault = True
        status.controller_fault = True
        status.under_voltage = True
        status.shenzhouxing_brake_fault = True
        status.controller_protect = True
        status.anti_runaway = True
        status.stall_protect = True
        status.brake = True
        status.speed_limit = True
        status.shenzhouxing_signal_strength = 5
        status.shenzhouxing_time_hour = 23
        status.shenzhouxing_time_minute = 59
        status.shenzhouxing_push_assist = True
        status.shenzhouxing_p_blink = True
        return status

    @staticmethod
    def yadea_normal_running() -> StatusBits:
        status = StatusBits(protocol_name=PROTOCOL_YADEA)
        status.hall_count = 3200
        status.soc_percent = 80
        status.current_percentage = 55
        status.motor_running = True
        status.speed_mode = 3
        status.current_a = 12
        return status

    @staticmethod
    def yadea_energy_recovery() -> StatusBits:
        status = StatusBits(protocol_name=PROTOCOL_YADEA)
        status.hall_count = 2600
        status.soc_percent = 62
        status.current_percentage = 25
        status.regen_charging = True
        status.current_a = -2
        status.speed_mode = 2
        return status

    @staticmethod
    def yadea_fault_scenario() -> StatusBits:
        status = StatusBits(protocol_name=PROTOCOL_YADEA)
        status.hall_count = 0
        status.soc_percent = 18
        status.current_percentage = 0
        status.hall_fault = True
        status.controller_fault = True
        status.under_voltage = True
        status.side_stand = True
        status.p_gear_protect = True
        return status

    @staticmethod
    def youyibao_normal_running() -> StatusBits:
        status = StatusBits(protocol_name=PROTOCOL_YOUYIBAO)
        status.hall_count = 3200
        status.soc_percent = 80
        status.current_percentage = 55
        status.motor_running = True
        status.speed_mode = 3
        status.current_a = 12
        return status

    @staticmethod
    def youyibao_energy_recovery() -> StatusBits:
        status = StatusBits(protocol_name=PROTOCOL_YOUYIBAO)
        status.hall_count = 2600
        status.soc_percent = 62
        status.current_percentage = 25
        status.regen_charging = True
        status.current_a = -2
        status.speed_mode = 2
        return status

    @staticmethod
    def youyibao_fault_scenario() -> StatusBits:
        status = StatusBits(protocol_name=PROTOCOL_YOUYIBAO)
        status.hall_count = 0
        status.soc_percent = 18
        status.current_percentage = 0
        status.hall_fault = True
        status.controller_fault = True
        status.under_voltage = True
        status.side_stand = True
        status.p_gear_protect = True
        return status

    @staticmethod
    def jingxian_normal_running() -> StatusBits:
        status = StatusBits(protocol_name=PROTOCOL_JINGXIAN)
        status.hall_count = 3200
        status.voltage_percentage = 80
        status.current_percentage = 55
        status.motor_running = True
        status.speed_mode = 3
        status.current_a = 12
        return status

    @staticmethod
    def jingxian_energy_recovery() -> StatusBits:
        status = StatusBits(protocol_name=PROTOCOL_JINGXIAN)
        status.hall_count = 2600
        status.voltage_percentage = 62
        status.current_percentage = 25
        status.regen_charging = True
        status.current_a = -2
        status.speed_mode = 2
        return status

    @staticmethod
    def jingxian_fault_scenario() -> StatusBits:
        status = StatusBits(protocol_name=PROTOCOL_JINGXIAN)
        status.hall_count = 0
        status.voltage_percentage = 18
        status.current_percentage = 0
        status.walk_mode = True
        status.hall_fault = True
        status.controller_fault = True
        status.under_voltage = True
        status.speed_limit = True
        return status

    @staticmethod
    def dongwei_gtxh_normal_running() -> StatusBits:
        status = StatusBits(protocol_name=PROTOCOL_DONGWEI_GTXH)
        status.voltage_48v = True
        status.hall_count = 3000
        status.soc_percent = 80
        status.current_percentage = 55
        status.motor_running = True
        status.speed_mode = 3
        status.current_a = 10
        return status

    @staticmethod
    def dongwei_gtxh_energy_recovery() -> StatusBits:
        status = StatusBits(protocol_name=PROTOCOL_DONGWEI_GTXH)
        status.voltage_72v = True
        status.voltage_48v = False
        status.hall_count = 2400
        status.soc_percent = 65
        status.current_percentage = 30
        status.regen_charging = True
        status.current_a = -2
        status.speed_mode = 2
        return status

    @staticmethod
    def dongwei_gtxh_fault_scenario() -> StatusBits:
        status = StatusBits(protocol_name=PROTOCOL_DONGWEI_GTXH)
        status.voltage_80v = True
        status.voltage_48v = False
        status.hall_count = 0
        status.soc_percent = 20
        status.current_percentage = 0
        status.hall_fault = True
        status.controller_fault = True
        status.under_voltage = True
        status.side_stand = True
        status.p_gear_protect = True
        return status

    @staticmethod
    def xinchi_normal_running() -> StatusBits:
        status = StatusBits(protocol_name=PROTOCOL_XINCHI)
        status.xinchi_charge_mos = True
        status.xinchi_discharge_mos = True
        status.soc_percent = 80
        status.xinchi_cycle_count = 126
        status.xinchi_temperature_c = 28
        status.xinchi_total_voltage_v = 54.3
        status.xinchi_total_current_a = 18
        return status

    @staticmethod
    def xinchi_energy_recovery() -> StatusBits:
        status = StatusBits(protocol_name=PROTOCOL_XINCHI)
        status.xinchi_charge_mos = True
        status.xinchi_discharge_mos = False
        status.soc_percent = 62
        status.xinchi_cycle_count = 144
        status.xinchi_temperature_c = 32
        status.xinchi_total_voltage_v = 55.1
        status.xinchi_total_current_a = 8
        return status

    @staticmethod
    def xinchi_fault_scenario() -> StatusBits:
        status = StatusBits(protocol_name=PROTOCOL_XINCHI)
        status.xinchi_high_temp_fault = True
        status.xinchi_over_voltage_fault = True
        status.xinchi_under_voltage_fault = True
        status.xinchi_bms_fault = True
        status.soc_percent = 15
        status.xinchi_cycle_count = 318
        status.xinchi_temperature_c = 75
        status.xinchi_total_voltage_v = 42.0
        status.xinchi_total_current_a = 0
        return status

    @staticmethod
    def luyuan_bms_normal_running() -> StatusBits:
        status = StatusBits(protocol_name=PROTOCOL_LUYUAN_BMS)
        status.luyuan_charge_mos = False
        status.luyuan_discharge_mos = True
        status.luyuan_predischarge_mos = False
        status.luyuan_charge_enable = True
        status.luyuan_charger_connected = False
        status.soc_percent = 82
        status.luyuan_cycle_count = 126
        status.luyuan_temperature_c = 28
        status.luyuan_max_cell_voltage_mv = 4205
        status.luyuan_min_cell_voltage_mv = 4178
        status.luyuan_current_a = -18.25
        status.luyuan_total_voltage_v = 54
        status.luyuan_soh_percent = 98
        return status

    @staticmethod
    def luyuan_bms_energy_recovery() -> StatusBits:
        status = StatusBits(protocol_name=PROTOCOL_LUYUAN_BMS)
        status.luyuan_charge_mos = True
        status.luyuan_discharge_mos = False
        status.luyuan_predischarge_mos = False
        status.luyuan_charge_enable = True
        status.luyuan_charger_connected = True
        status.soc_percent = 64
        status.luyuan_cycle_count = 144
        status.luyuan_temperature_c = 31
        status.luyuan_max_cell_voltage_mv = 4156
        status.luyuan_min_cell_voltage_mv = 4128
        status.luyuan_current_a = 6.5
        status.luyuan_total_voltage_v = 55
        status.luyuan_soh_percent = 96
        return status

    @staticmethod
    def luyuan_bms_fault_scenario() -> StatusBits:
        status = StatusBits(protocol_name=PROTOCOL_LUYUAN_BMS)
        status.luyuan_charge_mos = False
        status.luyuan_discharge_mos = False
        status.luyuan_predischarge_mos = True
        status.luyuan_charge_enable = False
        status.luyuan_charger_connected = True
        status.soc_percent = 4
        status.luyuan_cycle_count = 318
        status.luyuan_temperature_c = -8
        status.luyuan_max_cell_voltage_mv = 4010
        status.luyuan_min_cell_voltage_mv = 3685
        status.luyuan_current_a = 0.0
        status.luyuan_total_voltage_v = 41
        status.luyuan_soh_percent = 68
        return status

    @staticmethod
    def lithium_bms_normal_running() -> StatusBits:
        status = StatusBits(protocol_name=PROTOCOL_LITHIUM_BMS)
        status.lithium_bms_alarm_enable = True
        status.soc_percent = 80
        status.lithium_bms_cycle_count = 126
        status.lithium_bms_max_temp_c = 28
        status.lithium_bms_min_temp_c = 22
        status.lithium_bms_total_voltage_v = 54
        status.lithium_bms_max_cell_voltage_v = 3.61
        status.lithium_bms_min_cell_voltage_v = 3.42
        return status

    @staticmethod
    def lithium_bms_energy_recovery() -> StatusBits:
        status = StatusBits(protocol_name=PROTOCOL_LITHIUM_BMS)
        status.lithium_bms_alarm_enable = True
        status.soc_percent = 62
        status.lithium_bms_cycle_count = 144
        status.lithium_bms_max_temp_c = 31
        status.lithium_bms_min_temp_c = 24
        status.lithium_bms_total_voltage_v = 55
        status.lithium_bms_max_cell_voltage_v = 3.68
        status.lithium_bms_min_cell_voltage_v = 3.50
        return status

    @staticmethod
    def lithium_bms_fault_scenario() -> StatusBits:
        status = StatusBits(protocol_name=PROTOCOL_LITHIUM_BMS)
        status.lithium_bms_alarm_enable = True
        status.lithium_bms_high_temp_alarm = True
        status.lithium_bms_low_temp_alarm = True
        status.lithium_bms_soh_low = True
        status.lithium_bms_mos_fault = True
        status.lithium_bms_short_circuit_fault = True
        status.soc_percent = 15
        status.lithium_bms_cycle_count = 318
        status.lithium_bms_max_temp_c = 78
        status.lithium_bms_min_temp_c = -8
        status.lithium_bms_total_voltage_v = 43
        status.lithium_bms_max_cell_voltage_v = 4.18
        status.lithium_bms_min_cell_voltage_v = 2.96
        return status

    @staticmethod
    def battery_single_wire_normal_running() -> StatusBits:
        status = StatusBits(protocol_name=PROTOCOL_BATTERY_SINGLE_WIRE)
        status.soc_percent = 80
        return status

    @staticmethod
    def battery_single_wire_energy_recovery() -> StatusBits:
        status = StatusBits(protocol_name=PROTOCOL_BATTERY_SINGLE_WIRE)
        status.soc_percent = 62
        return status

    @staticmethod
    def battery_single_wire_fault_scenario() -> StatusBits:
        status = StatusBits(protocol_name=PROTOCOL_BATTERY_SINGLE_WIRE)
        status.soc_percent = 15
        return status
