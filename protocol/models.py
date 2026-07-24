#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
协议数据模型。

保存协议处理器与界面之间共享的配置和状态结构。
"""

from dataclasses import dataclass

from .definitions import PROTOCOL_RUILUN


@dataclass
class ProtocolConfig:
    """协议基础配置。"""

    tosc_us: int = 100
    baud_rate: int = 9600
    send_interval_ms: int = 500


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

    # 台铃 Y34 扩展状态
    tailing_national_standard: bool = False
    tailing_actual_speed_mode: bool = False
    tailing_tire_pressure_low: bool = False
    tailing_tcs_indicator: bool = False
    tailing_hdc_indicator: bool = False
    tailing_dual_undervoltage: bool = False
    tailing_seat_state: int = 0
    tailing_dual_soc: bool = False
    tailing_display_sleep: bool = False
    tailing_speed_15kmh_warning: bool = False
    tailing_brake_fault: bool = False
    tailing_display_voltage_from_data: bool = False
    tailing_battery_over_temp: bool = False
    tailing_battery_over_current: bool = False
    tailing_battery_over_voltage: bool = False
    tailing_real_time_voltage_v: float = 48.0

    # 神州行扩展状态
    shenzhouxing_hdc: bool = False
    shenzhouxing_hhc: bool = False
    shenzhouxing_tcs: bool = False
    shenzhouxing_brake_fault: bool = False
    shenzhouxing_bluetooth: bool = False
    shenzhouxing_time_display: bool = False
    shenzhouxing_4g_signal_indicator: bool = False
    shenzhouxing_position_indicator: bool = False
    shenzhouxing_real_time_voltage_v: int = 48
    shenzhouxing_signal_strength: int = 0
    shenzhouxing_time_hour: int = 0
    shenzhouxing_time_minute: int = 0
    shenzhouxing_push_assist: bool = False
    shenzhouxing_p_blink: bool = False

    # 运行数据
    current_a: float = 0
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

    # 绿源 BMS 一线通
    luyuan_charge_mos: bool = False
    luyuan_discharge_mos: bool = False
    luyuan_predischarge_mos: bool = False
    luyuan_charge_enable: bool = False
    luyuan_charger_connected: bool = False
    luyuan_cycle_count: int = 0
    luyuan_temperature_c: int = 25
    luyuan_max_cell_voltage_mv: int = 4200
    luyuan_min_cell_voltage_mv: int = 4100
    luyuan_current_a: float = -12.0
    luyuan_total_voltage_v: int = 54
    luyuan_soh_percent: int = 100

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
