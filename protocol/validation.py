#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""协议参数校验，与帧编码分开维护。"""

from typing import Tuple
from .definitions import (
    DEFAULT_PROTOCOL_DEFINITION,
    PROTOCOL_TAILING_Y34B,
    PROTOCOL_TAILING_Y34F,
    PROTOCOL_BATTERY_SINGLE_WIRE,
    PROTOCOL_CHANGZHOU_XINSIWEI,
    PROTOCOL_DEFINITIONS,
    PROTOCOL_DONGWEI_GTXH,
    PROTOCOL_FZ_SIF,
    PROTOCOL_JINGXIAN,
    PROTOCOL_LITHIUM_BMS,
    PROTOCOL_LUYUAN_BMS,
    PROTOCOL_SHENZHOUXING,
    PROTOCOL_SXSY,
    PROTOCOL_XINCHI,
    PROTOCOL_XINRI,
    PROTOCOL_YADEA,
)
from .constants import VOLTAGE_OPTIONS, SXSY_P_GEAR_STATES
from .models import StatusBits


class StatusValidation:
    """由兼容处理器提供共享状态，本模块不保存界面或串口对象。"""

    def validate_status_bits(self, status: StatusBits) -> Tuple[bool, str]:
        """校验状态字段是否合法。"""

        if not isinstance(status, StatusBits):
            return False, "协议状态必须是 StatusBits 对象"

        protocol_name = self.resolve_protocol_name(status)
        if isinstance(status.current_a, bool) or not isinstance(status.current_a, (int, float)):
            return False, "运行电流必须是数值"
        current_a = float(status.current_a)

        if protocol_name == PROTOCOL_SXSY:
            integer_fields = (
                ("速度模式", status.speed_mode),
                ("霍尔计数", status.hall_count),
                ("电压百分比", status.voltage_percentage),
                ("SOC", status.soc_percent),
            )
            for field_label, field_value in integer_fields:
                if isinstance(field_value, bool) or not isinstance(field_value, int):
                    return False, f"SXSY {field_label}必须是整数"

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

        if protocol_name == PROTOCOL_SXSY:
            if not (-127 <= current_a <= 127):
                return False, "SXSY 运行电流必须在 -127A 到 127A 范围内"
            if (
                isinstance(status.sxsy_p_gear_state, bool)
                or not isinstance(status.sxsy_p_gear_state, int)
                or status.sxsy_p_gear_state not in SXSY_P_GEAR_STATES
            ):
                return False, "SXSY P档状态必须是 0x00、0x0D、0x0E 或 0x0F"

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
