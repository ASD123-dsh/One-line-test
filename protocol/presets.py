#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""各协议标准场景预设，保持旧 PresetScenarios 导出入口。"""

from .definitions import (
    PROTOCOL_TAILING_Y34B,
    PROTOCOL_TAILING_Y34F,
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
    PROTOCOL_SXSY,
    PROTOCOL_WUXI_YIGE,
    PROTOCOL_XINCHI,
    PROTOCOL_XINRI,
    PROTOCOL_YADEA,
    PROTOCOL_YOUYIBAO,
)
from .models import StatusBits


class PresetScenarios:
    """预设场景。"""

    @staticmethod
    def normal_running() -> StatusBits:
        """创建本协议预设状态，保留原来的默认数据。"""
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
        """创建本协议预设状态，保留原来的默认数据。"""
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
        """创建本协议预设状态，保留原来的默认数据。"""
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
        """创建本协议预设状态，保留原来的默认数据。"""
        status = StatusBits(protocol_name=PROTOCOL_FZ_SIF)
        status.voltage_48v = True
        status.hall_count = 3200
        status.voltage_percentage = 80
        status.motor_running = True
        status.current_a = 12
        return status

    @staticmethod
    def fz_sif_energy_recovery() -> StatusBits:
        """创建本协议预设状态，保留原来的默认数据。"""
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
        """创建本协议预设状态，保留原来的默认数据。"""
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
        """创建本协议预设状态，保留原来的默认数据。"""
        status = StatusBits(protocol_name=PROTOCOL_XINRI)
        status.hall_count = 2800
        status.current_a = 8
        status.speed_mode = 2
        return status

    @staticmethod
    def xinri_energy_recovery() -> StatusBits:
        """创建本协议预设状态，保留原来的默认数据。"""
        status = StatusBits(protocol_name=PROTOCOL_XINRI)
        status.hall_count = 2200
        status.current_a = 4
        status.speed_mode = 1
        status.cruise = True
        return status

    @staticmethod
    def xinri_fault_scenario() -> StatusBits:
        """创建本协议预设状态，保留原来的默认数据。"""
        status = StatusBits(protocol_name=PROTOCOL_XINRI)
        status.hall_fault = True
        status.throttle_fault = True
        status.controller_fault = True
        status.brake = True
        status.low_voltage_alarm = True
        return status

    @staticmethod
    def hangzhou_anxian_normal_running() -> StatusBits:
        """创建本协议预设状态，保留原来的默认数据。"""
        status = StatusBits(protocol_name=PROTOCOL_HANGZHOU_ANXIAN)
        status.voltage_48v = True
        status.hall_count = 3000
        status.voltage_percentage = 75
        status.motor_running = True
        status.speed_mode = 2
        return status

    @staticmethod
    def hangzhou_anxian_energy_recovery() -> StatusBits:
        """创建本协议预设状态，保留原来的默认数据。"""
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
        """创建本协议预设状态，保留原来的默认数据。"""
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
    def sxsy_normal_running() -> StatusBits:
        """SXSY 正常运行预设。"""

        status = StatusBits(protocol_name=PROTOCOL_SXSY)
        status.sxsy_p_gear_state = 0x00
        status.sxsy_three_speed = True
        status.motor_running = True
        status.speed_mode = 2
        status.current_a = 12
        status.hall_count = 3000
        status.voltage_percentage = 80
        status.soc_percent = 80
        return status

    @staticmethod
    def sxsy_energy_recovery() -> StatusBits:
        """SXSY 能量回收预设。"""

        status = StatusBits(protocol_name=PROTOCOL_SXSY)
        status.sxsy_p_gear_state = 0x00
        status.sxsy_three_speed = True
        status.regen_charging = True
        status.speed_mode = 2
        status.current_a = -3
        status.hall_count = 2400
        status.voltage_percentage = 70
        status.soc_percent = 60
        return status

    @staticmethod
    def sxsy_fault_scenario() -> StatusBits:
        """SXSY 故障预设。"""

        status = StatusBits(protocol_name=PROTOCOL_SXSY)
        status.sxsy_p_gear_state = 0x0F
        status.hall_fault = True
        status.throttle_fault = True
        status.controller_fault = True
        status.under_voltage = True
        status.controller_protect = True
        status.current_a = 0
        status.hall_count = 0
        status.voltage_percentage = 20
        status.soc_percent = 20
        return status

    @staticmethod
    def changzhou_xinsiwei_normal_running() -> StatusBits:
        """创建本协议预设状态，保留原来的默认数据。"""
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
        """创建本协议预设状态，保留原来的默认数据。"""
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
        """创建本协议预设状态，保留原来的默认数据。"""
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
        """创建本协议预设状态，保留原来的默认数据。"""
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
        """创建本协议预设状态，保留原来的默认数据。"""
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
        """创建本协议预设状态，保留原来的默认数据。"""
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
        """创建本协议预设状态，保留原来的默认数据。"""
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
        """创建本协议预设状态，保留原来的默认数据。"""
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
        """创建本协议预设状态，保留原来的默认数据。"""
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
        """创建本协议预设状态，保留原来的默认数据。"""
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
        """创建本协议预设状态，保留原来的默认数据。"""
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
        """创建本协议预设状态，保留原来的默认数据。"""
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
        """创建本协议预设状态，保留原来的默认数据。"""
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
        """创建本协议预设状态，保留原来的默认数据。"""
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
        """创建本协议预设状态，保留原来的默认数据。"""
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
        """创建本协议预设状态，保留原来的默认数据。"""
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
        """创建本协议预设状态，保留原来的默认数据。"""
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
        """创建本协议预设状态，保留原来的默认数据。"""
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
        """创建本协议预设状态，保留原来的默认数据。"""
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
        """创建本协议预设状态，保留原来的默认数据。"""
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
        """创建本协议预设状态，保留原来的默认数据。"""
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
        """创建本协议预设状态，保留原来的默认数据。"""
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
        """创建本协议预设状态，保留原来的默认数据。"""
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
        """创建本协议预设状态，保留原来的默认数据。"""
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
        """创建本协议预设状态，保留原来的默认数据。"""
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
        """创建本协议预设状态，保留原来的默认数据。"""
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
        """创建本协议预设状态，保留原来的默认数据。"""
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
        """创建本协议预设状态，保留原来的默认数据。"""
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
        """创建本协议预设状态，保留原来的默认数据。"""
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
        """创建本协议预设状态，保留原来的默认数据。"""
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
        """创建本协议预设状态，保留原来的默认数据。"""
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
        """创建本协议预设状态，保留原来的默认数据。"""
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
        """创建本协议预设状态，保留原来的默认数据。"""
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
        """创建本协议预设状态，保留原来的默认数据。"""
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
        """创建本协议预设状态，保留原来的默认数据。"""
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
        """创建本协议预设状态，保留原来的默认数据。"""
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
        """创建本协议预设状态，保留原来的默认数据。"""
        status = StatusBits(protocol_name=PROTOCOL_BATTERY_SINGLE_WIRE)
        status.soc_percent = 80
        return status

    @staticmethod
    def battery_single_wire_energy_recovery() -> StatusBits:
        """创建本协议预设状态，保留原来的默认数据。"""
        status = StatusBits(protocol_name=PROTOCOL_BATTERY_SINGLE_WIRE)
        status.soc_percent = 62
        return status

    @staticmethod
    def battery_single_wire_fault_scenario() -> StatusBits:
        """创建本协议预设状态，保留原来的默认数据。"""
        status = StatusBits(protocol_name=PROTOCOL_BATTERY_SINGLE_WIRE)
        status.soc_percent = 15
        return status
