#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
一线通协议处理模块

负责不同厂商协议的帧生成、校验和基础场景预设。
"""

from dataclasses import dataclass
from typing import Dict, List, Tuple

PROTOCOL_RUILUN = "瑞轮协议"
PROTOCOL_XINRI = "新日协议"
PROTOCOL_HANGZHOU_ANXIAN = "杭州安显协议"
PROTOCOL_CHANGZHOU_XINSIWEI = "常州新思维协议"
PROTOCOL_WUXI_YIGE = "无锡一格Y67协议"
PROTOCOL_YADEA = "雅迪协议"
PROTOCOL_DONGWEI_GTXH = "东威GTXH协议"
PROTOCOL_XINCHI = "芯驰BMS协议"
PROTOCOL_LITHIUM_BMS = "一线通--锂电池BMS"

SUPPORTED_PROTOCOLS = [
    PROTOCOL_RUILUN,
    PROTOCOL_XINRI,
    PROTOCOL_HANGZHOU_ANXIAN,
    PROTOCOL_CHANGZHOU_XINSIWEI,
    PROTOCOL_WUXI_YIGE,
    PROTOCOL_YADEA,
    PROTOCOL_DONGWEI_GTXH,
    PROTOCOL_XINCHI,
    PROTOCOL_LITHIUM_BMS,
]

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


@dataclass
class ProtocolConfig:
    """协议基础配置。"""

    tosc_us: int = 100
    baud_rate: int = 9600
    send_interval_ms: int = 1000


@dataclass
class StatusBits:
    """统一的协议状态模型。"""

    protocol_name: str = PROTOCOL_RUILUN

    # Status1
    distance_mode: bool = False
    speed_alarm: bool = False
    p_gear_protect: bool = False
    tcs_status: bool = False
    protocol_speed_limit: bool = False
    side_stand: bool = False
    low_voltage_alarm: bool = False

    # Status2
    walk_mode: bool = False
    hall_fault: bool = False
    throttle_fault: bool = False
    controller_fault: bool = False
    under_voltage: bool = False
    cruise: bool = False
    assist: bool = False
    motor_phase_loss: bool = False

    # Status3
    gear_four: bool = False
    motor_running: bool = False
    brake: bool = False
    controller_protect: bool = False
    regen_charging: bool = False
    anti_runaway: bool = False
    speed_mode: int = 0

    # Status4
    current_70_flag: bool = False
    one_key_enable: bool = False
    ekk_enable: bool = False
    over_current: bool = False
    stall_protect: bool = False
    reverse: bool = False
    electronic_brake: bool = False
    speed_limit: bool = False
    cloud_power_mode: bool = False

    # 运行数据
    current_a: int = 0
    hall_count: int = 0
    speed_kmh: float = 0.0  # 兼容旧 UI 的兜底输入

    # 百分比类数据
    soc_percent: int = 50
    soc_fault: bool = False
    lithium_soc_mode: bool = True
    voltage_percentage: int = 0
    current_percentage: int = 0

    # 协议切换电压
    voltage_24v: bool = False
    voltage_36v: bool = False
    voltage_48v: bool = True
    voltage_60v: bool = False
    voltage_64v: bool = False
    voltage_72v: bool = False
    voltage_80v: bool = False
    voltage_84v: bool = False
    voltage_96v: bool = False

    # 常州新思维
    xinsiwei_reserved_d3: bool = False
    xinsiwei_reserved_d2: bool = False
    xinsiwei_reserved_d1: bool = False
    xinsiwei_reserved_d0: bool = False
    xinsiwei_protocol: bool = False
    xinsiwei_sequence: int = 0
    xinsiwei_hall_count: int = 0

    # 兼容旧代码中残留的字段
    backup_power: bool = False
    protocol_identifier: int = 0
    sequence_number: int = 0

    # 芯驰 BMS-SIF
    xinchi_charge_mos: bool = False
    xinchi_discharge_mos: bool = False
    xinchi_high_temp_fault: bool = False
    xinchi_low_temp_fault: bool = False
    xinchi_over_voltage_fault: bool = False
    xinchi_under_voltage_fault: bool = False
    xinchi_bms_fault: bool = False
    xinchi_cycle_count: int = 0
    xinchi_temperature_c: int = 25
    xinchi_total_voltage_v: float = 48.0
    xinchi_total_current_a: int = 0

    # 一线通锂电池 BMS
    lithium_bms_alarm_enable: bool = False
    lithium_bms_high_temp_alarm: bool = False
    lithium_bms_low_temp_alarm: bool = False
    lithium_bms_soh_low: bool = False
    lithium_bms_mos_fault: bool = False
    lithium_bms_short_circuit_fault: bool = False
    lithium_bms_cycle_count: int = 0
    lithium_bms_max_temp_c: int = 25
    lithium_bms_min_temp_c: int = 20
    lithium_bms_total_voltage_v: float = 48.0
    lithium_bms_max_cell_voltage_v: float = 3.60
    lithium_bms_min_cell_voltage_v: float = 3.40


class ProtocolHandler:
    """多协议帧生成器。"""

    def __init__(self):
        self.config = ProtocolConfig()
        self.status = StatusBits()
        self._xinsiwei_sequence_counter = 1
        self._hangzhou_sequence_counter = 1

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

        return 10 if protocol_name == PROTOCOL_XINCHI else 12

    def get_protocol_checksum_mode(self, protocol_name: str) -> str:
        """获取协议校验模式。"""

        return "sum" if protocol_name == PROTOCOL_XINCHI else "xor"

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

    def validate_status_bits(self, status: StatusBits) -> Tuple[bool, str]:
        """校验状态字段是否合法。"""

        protocol_name = self.resolve_protocol_name(status)
        speed_mode_max = (
            7 if protocol_name in {PROTOCOL_XINRI, PROTOCOL_YADEA, PROTOCOL_DONGWEI_GTXH} else 3
        )
        if not (0 <= status.speed_mode <= speed_mode_max):
            return False, f"当前协议的速度模式必须在 0-{speed_mode_max} 范围内"

        if not (-128 <= status.current_a <= 127):
            return False, "运行电流必须在 -128A 到 127A 范围内"

        if not (0 <= status.hall_count <= 65535):
            return False, "霍尔计数必须在 0-65535 范围内"

        if not (0 <= status.xinsiwei_hall_count <= 65535):
            return False, "常州新思维霍尔计数必须在 0-65535 范围内"

        if not (0 <= status.speed_kmh <= 6553.5):
            return False, "兼容速度输入必须在 0-6553.5 范围内"

        if not status.soc_fault and not (0 <= status.soc_percent <= 100):
            return False, "百分比输入必须在 0-100 范围内"

        if not (0 <= status.voltage_percentage <= 100):
            return False, "电压百分比必须在 0-100 范围内"

        if not (0 <= status.current_percentage <= 100):
            return False, "电流百分比必须在 0-100 范围内"

        voltage_mask_count = sum(
            1 for field_name, _ in VOLTAGE_OPTIONS if getattr(status, field_name, False)
        )
        if voltage_mask_count > 1:
            return False, "协议切换电压最多只能勾选一个电压位"

        if protocol_name == PROTOCOL_DONGWEI_GTXH:
            unsupported_voltage_fields = ("voltage_36v", "voltage_64v", "voltage_84v")
            if any(getattr(status, field_name, False) for field_name in unsupported_voltage_fields):
                return False, "东威协议的电压状态仅支持默认/48V/60V/72V/80V/96V"

        if protocol_name == PROTOCOL_CHANGZHOU_XINSIWEI and not (
            0 <= status.xinsiwei_sequence <= 4095
        ):
            return False, "常州新思维序号必须在 0-4095 范围内"

        if protocol_name == PROTOCOL_XINCHI:
            if not (0 <= status.xinchi_cycle_count <= 65535):
                return False, "芯驰循环次数必须在 0-65535 范围内"
            if not (-40 <= status.xinchi_temperature_c <= 120):
                return False, "芯驰电池温度必须在 -40℃ 到 120℃ 范围内"
            if not (0 <= status.xinchi_total_voltage_v <= 6553.5):
                return False, "芯驰总电压必须在 0.0V 到 6553.5V 范围内"
            if not (0 <= status.xinchi_total_current_a <= 255):
                return False, "芯驰总电流必须在 0A 到 255A 范围内"

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

    def generate_xinsiwei_frame_for_preview(self, status: StatusBits) -> Tuple[bool, List[int], str]:
        """生成常州新思维预览帧，不递增序号。"""

        preview_status = self._copy_status(status)
        preview_status.protocol_name = PROTOCOL_CHANGZHOU_XINSIWEI
        preview_status.xinsiwei_protocol = True
        preview_status.xinsiwei_sequence = self.get_current_xinsiwei_sequence()
        return self.generate_xinsiwei_frame(preview_status)

    def generate_frame(self, status: StatusBits) -> Tuple[bool, List[int], str]:
        """根据协议生成发送帧。"""

        protocol_name = self.resolve_protocol_name(status)
        if protocol_name == PROTOCOL_CHANGZHOU_XINSIWEI:
            return self.generate_xinsiwei_frame_with_auto_sequence(status)
        if protocol_name == PROTOCOL_HANGZHOU_ANXIAN:
            return self._generate_hangzhou_frame(status, preview=False)
        if protocol_name == PROTOCOL_XINRI:
            return self._generate_xinri_frame(status)
        if protocol_name == PROTOCOL_WUXI_YIGE:
            return self._generate_wuxi_yige_frame(status)
        if protocol_name == PROTOCOL_YADEA:
            return self._generate_yadea_frame(status)
        if protocol_name == PROTOCOL_DONGWEI_GTXH:
            return self._generate_dongwei_gtxh_frame(status)
        if protocol_name == PROTOCOL_XINCHI:
            return self._generate_xinchi_frame(status)
        if protocol_name == PROTOCOL_LITHIUM_BMS:
            return self._generate_lithium_bms_frame(status)
        return self._generate_ruilun_frame(status)

    def generate_frame_for_preview(self, status: StatusBits) -> Tuple[bool, List[int], str]:
        """根据协议生成预览帧。"""

        protocol_name = self.resolve_protocol_name(status)
        if protocol_name == PROTOCOL_CHANGZHOU_XINSIWEI:
            return self.generate_xinsiwei_frame_for_preview(status)
        if protocol_name == PROTOCOL_HANGZHOU_ANXIAN:
            return self._generate_hangzhou_frame(status, preview=True)
        if protocol_name == PROTOCOL_XINRI:
            return self._generate_xinri_frame(status)
        if protocol_name == PROTOCOL_WUXI_YIGE:
            return self._generate_wuxi_yige_frame(status)
        if protocol_name == PROTOCOL_YADEA:
            return self._generate_yadea_frame(status)
        if protocol_name == PROTOCOL_DONGWEI_GTXH:
            return self._generate_dongwei_gtxh_frame(status)
        if protocol_name == PROTOCOL_XINCHI:
            return self._generate_xinchi_frame(status)
        if protocol_name == PROTOCOL_LITHIUM_BMS:
            return self._generate_lithium_bms_frame(status)
        return self._generate_ruilun_frame(status)

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
        frame[9] = 0xEE if status.soc_fault else (status.soc_percent & 0xFF)
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

    def _encode_yadea_status1(self, status: StatusBits) -> int:
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
        if protocol_name in {PROTOCOL_YADEA, PROTOCOL_DONGWEI_GTXH}:
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
        if protocol_name == PROTOCOL_WUXI_YIGE:
            if status.cloud_power_mode:
                value |= 0x80
        elif protocol_name in {PROTOCOL_RUILUN, PROTOCOL_DONGWEI_GTXH}:
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

    def _encode_ruilun_soc(self, status: StatusBits) -> int:
        if status.soc_fault:
            return 0xEE
        if status.lithium_soc_mode:
            return 0x80 | (status.soc_percent & 0x7F)
        return 0x00

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

    def _encode_signed_current(self, current_a: int) -> int:
        return current_a & 0xFF

    def _encode_xinri_current(self, current_a: int) -> int:
        raw_value = round(abs(current_a) * 5)
        return max(0, min(255, raw_value))

    def _encode_dongwei_current(self, current_a: int) -> int:
        scaled_value = round(current_a * 5)
        scaled_value = max(-128, min(127, scaled_value))
        return scaled_value & 0xFF

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

    def _encode_lithium_bms_temperature(self, temp_c: int) -> int:
        magnitude = min(127, abs(int(temp_c)))
        if temp_c < 0:
            return 0x80 | magnitude
        return magnitude & 0x7F

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
