#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""common_bindings 协议配置页及状态绑定；不负责串口和升级。"""

from protocol.protocol_handler import (
    PROTOCOL_DONGWEI_GTXH,
    PROTOCOL_FZ_SIF,
    PROTOCOL_HANGZHOU_ANXIAN,
    PROTOCOL_JINGXIAN,
    PROTOCOL_SHENZHOUXING,
    PROTOCOL_SXSY,
    PROTOCOL_TAILING_Y34B,
    PROTOCOL_TAILING_Y34F,
    PROTOCOL_WUXI_YIGE,
    PROTOCOL_XINRI,
    PROTOCOL_YADEA,
    PROTOCOL_YOUYIBAO,
    StatusBits,
)


class CommonProtocolBindings:
    """作为主窗口的界面组件，沿用现有控件名称和槽函数。"""

    def show_ruilun_status_config(self):
        """显示瑞轮协议Status配置界面"""
        for attr_name in (
            "tailing_display_voltage_from_data_cb",
            "tailing_battery_over_temp_cb",
            "tailing_battery_over_current_cb",
            "tailing_battery_over_voltage_cb",
            "tailing_dual_soc_cb",
            "tailing_display_sleep_cb",
            "tailing_speed_15_warning_cb",
            "tailing_brake_fault_cb",
            "tailing_real_time_voltage_spin",
            "shenzhouxing_real_time_voltage_spin",
            "shenzhouxing_signal_strength_spin",
            "shenzhouxing_time_hour_spin",
            "shenzhouxing_time_minute_spin",
            "shenzhouxing_push_assist_cb",
            "shenzhouxing_p_blink_cb",
        ):
            if hasattr(self, attr_name):
                delattr(self, attr_name)

        # 清除现有标签页
        self._clear_status_tabs()

        # 添加瑞轮协议的标签页
        status1_tab = self.create_ruilun_status1_tab()
        self.status_tabs.addTab(status1_tab, "Status1")

        status2_tab = self.create_ruilun_status2_tab()
        self.status_tabs.addTab(status2_tab, "Status2")

        status3_tab = self.create_ruilun_status3_tab()
        self.status_tabs.addTab(status3_tab, "Status3")

        status4_tab = self.create_ruilun_status4_tab()
        self.status_tabs.addTab(status4_tab, "Status4")

        status5_9_tab = self.create_ruilun_status5_9_tab()
        self.status_tabs.addTab(status5_9_tab, "Status5-9")
        if self.current_protocol in {PROTOCOL_TAILING_Y34B, PROTOCOL_TAILING_Y34F}:
            self.status_tabs.addTab(self.create_tailing_extended_status_tab(), "扩展状态")
        elif self.current_protocol == PROTOCOL_SHENZHOUXING:
            self.status_tabs.addTab(self.create_shenzhouxing_extended_status_tab(), "扩展状态")
        self._compact_status_tab_pages()

        # 重新连接信号
        self.connect_status_signals()

    def update_ruilun_ui_from_status(self):
        """根据瑞轮协议状态更新UI显示（杭州安显协议复用此逻辑）"""
        if not hasattr(self, 'current_status') or not isinstance(self.current_status, StatusBits):
            return

        status = self.current_status

        if self.current_protocol == PROTOCOL_XINRI:
            self.distance_mode_cb.setChecked(getattr(status, "p_gear_protect", False))
            self.speed_alarm_cb.setChecked(getattr(status, "low_voltage_alarm", False))
            self.p_gear_protect_cb.setChecked(False)
            self.tcs_status_cb.setChecked(False)
        elif self.current_protocol == PROTOCOL_HANGZHOU_ANXIAN:
            self.distance_mode_cb.setChecked(False)
            self.speed_alarm_cb.setChecked(getattr(status, "protocol_speed_limit", False))
            self.p_gear_protect_cb.setChecked(getattr(status, "p_gear_protect", False))
            self.tcs_status_cb.setChecked(False)
        elif self.current_protocol == PROTOCOL_SXSY:
            state_code = getattr(status, "sxsy_p_gear_state", 0x00)
            state_button = self.sxsy_p_gear_group.button(state_code)
            if state_button is None:
                state_button = self.sxsy_p_gear_group.button(0x00)
            state_button.setChecked(True)
        elif self.current_protocol == PROTOCOL_FZ_SIF:
            self.distance_mode_cb.setChecked(getattr(status, "side_stand", False))
            self.speed_alarm_cb.setChecked(getattr(status, "protocol_speed_limit", False))
            self.p_gear_protect_cb.setChecked(getattr(status, "p_gear_protect", False))
            self.tcs_status_cb.setChecked(False)
        elif self.current_protocol == PROTOCOL_DONGWEI_GTXH:
            self.distance_mode_cb.setChecked(False)
            self.speed_alarm_cb.setChecked(False)
            self.p_gear_protect_cb.setChecked(getattr(status, "p_gear_protect", False))
            self.tcs_status_cb.setChecked(False)
        elif self.current_protocol in {PROTOCOL_WUXI_YIGE, PROTOCOL_JINGXIAN}:
            self.distance_mode_cb.setChecked(getattr(status, "side_stand", False))
            self.speed_alarm_cb.setChecked(False)
            self.p_gear_protect_cb.setChecked(getattr(status, "p_gear_protect", False))
            self.tcs_status_cb.setChecked(False)
        elif self.current_protocol in {PROTOCOL_TAILING_Y34B, PROTOCOL_TAILING_Y34F}:
            self.distance_mode_cb.setChecked(getattr(status, "side_stand", False))
            self.speed_alarm_cb.setChecked(False)
            self.p_gear_protect_cb.setChecked(getattr(status, "p_gear_protect", False))
            self.tcs_status_cb.setChecked(getattr(status, "tailing_national_standard", False))
        elif self.current_protocol == PROTOCOL_SHENZHOUXING:
            self.distance_mode_cb.setChecked(getattr(status, "side_stand", False))
            self.speed_alarm_cb.setChecked(getattr(status, "shenzhouxing_hdc", False))
            self.p_gear_protect_cb.setChecked(getattr(status, "p_gear_protect", False))
            self.tcs_status_cb.setChecked(getattr(status, "shenzhouxing_hhc", False))
        elif self.current_protocol == PROTOCOL_YADEA:
            self.distance_mode_cb.setChecked(getattr(status, "side_stand", False))
            self.speed_alarm_cb.setChecked(False)
            self.p_gear_protect_cb.setChecked(getattr(status, "p_gear_protect", False))
            self.tcs_status_cb.setChecked(False)
        elif self.current_protocol == PROTOCOL_YOUYIBAO:
            self.distance_mode_cb.setChecked(getattr(status, "p_gear_protect", False))
            self.speed_alarm_cb.setChecked(getattr(status, "side_stand", False))
            self.p_gear_protect_cb.setChecked(False)
            self.tcs_status_cb.setChecked(False)
        else:
            self.distance_mode_cb.setChecked(getattr(status, "distance_mode", False))
            self.speed_alarm_cb.setChecked(getattr(status, "speed_alarm", False))
            self.p_gear_protect_cb.setChecked(getattr(status, "p_gear_protect", False))
            self.tcs_status_cb.setChecked(getattr(status, "tcs_status", False))

        self.status2_d7_cb.setChecked(getattr(status, "walk_mode", False))
        self.hall_fault_cb.setChecked(getattr(status, "hall_fault", False))
        self.throttle_fault_cb.setChecked(getattr(status, "throttle_fault", False))
        self.controller_fault_cb.setChecked(getattr(status, "controller_fault", False))
        self.under_voltage_cb.setChecked(getattr(status, "under_voltage", False))
        self.cruise_cb.setChecked(getattr(status, "cruise", False))
        if self.current_protocol == PROTOCOL_TAILING_Y34F:
            self.assist_cb.setChecked(getattr(status, "tailing_tire_pressure_low", False))
            self.motor_phase_loss_cb.setChecked(False)
        else:
            self.assist_cb.setChecked(getattr(status, "assist", False))
            self.motor_phase_loss_cb.setChecked(getattr(status, "motor_phase_loss", False))
        if self.current_protocol == PROTOCOL_SHENZHOUXING:
            self.status2_d7_cb.setChecked(getattr(status, "shenzhouxing_tcs", False))

        if self.current_protocol == PROTOCOL_SXSY:
            self.gear_four_cb.setChecked(
                getattr(status, "sxsy_three_speed", False)
            )
        else:
            self.gear_four_cb.setChecked(getattr(status, "gear_four", False))
        if self.current_protocol == PROTOCOL_TAILING_Y34F:
            self.motor_running_cb.setChecked(getattr(status, "tailing_tcs_indicator", False))
        else:
            self.motor_running_cb.setChecked(getattr(status, "motor_running", False))
        if self.current_protocol == PROTOCOL_SHENZHOUXING:
            self.brake_cb.setChecked(getattr(status, "shenzhouxing_brake_fault", False))
        else:
            self.brake_cb.setChecked(getattr(status, "brake", False))
        if self.current_protocol == PROTOCOL_TAILING_Y34F:
            self.controller_protect_cb.setChecked(getattr(status, "tailing_hdc_indicator", False))
        else:
            self.controller_protect_cb.setChecked(getattr(status, "controller_protect", False))
        self.regen_charging_cb.setChecked(getattr(status, "regen_charging", False))
        self.anti_runaway_cb.setChecked(
            False if self.current_protocol == PROTOCOL_TAILING_Y34F else getattr(status, "anti_runaway", False)
        )
        self.speed_mode_spin.setValue(getattr(status, "speed_mode", 0))

        if self.current_protocol in {
            PROTOCOL_WUXI_YIGE,
            PROTOCOL_TAILING_Y34B,
            PROTOCOL_TAILING_Y34F,
            PROTOCOL_FZ_SIF,
        }:
            self.current_70_flag_cb.setChecked(getattr(status, "cloud_power_mode", False))
        elif self.current_protocol == PROTOCOL_SHENZHOUXING:
            self.current_70_flag_cb.setChecked(getattr(status, "shenzhouxing_bluetooth", False))
        else:
            self.current_70_flag_cb.setChecked(getattr(status, "current_70_flag", False))
        if self.current_protocol == PROTOCOL_DONGWEI_GTXH:
            self.one_key_enable_cb.setChecked(getattr(status, "side_stand", False))
        elif self.current_protocol in {PROTOCOL_TAILING_Y34B, PROTOCOL_TAILING_Y34F}:
            self.one_key_enable_cb.setChecked(getattr(status, "tailing_actual_speed_mode", False))
        elif self.current_protocol == PROTOCOL_SHENZHOUXING:
            self.one_key_enable_cb.setChecked(getattr(status, "shenzhouxing_time_display", False))
        else:
            self.one_key_enable_cb.setChecked(getattr(status, "one_key_enable", False))
        if self.current_protocol == PROTOCOL_TAILING_Y34F:
            self.ekk_enable_cb.setChecked(getattr(status, "tailing_dual_undervoltage", False))
        elif self.current_protocol == PROTOCOL_SHENZHOUXING:
            self.ekk_enable_cb.setChecked(getattr(status, "shenzhouxing_4g_signal_indicator", False))
        else:
            self.ekk_enable_cb.setChecked(getattr(status, "ekk_enable", False))
        if self.current_protocol == PROTOCOL_SHENZHOUXING:
            self.over_current_cb.setChecked(getattr(status, "shenzhouxing_position_indicator", False))
        else:
            self.over_current_cb.setChecked(getattr(status, "over_current", False))
        self.stall_protect_cb.setChecked(getattr(status, "stall_protect", False))
        self.reverse_cb.setChecked(getattr(status, "reverse", False))
        if self.current_protocol == PROTOCOL_TAILING_Y34F:
            seat_state = getattr(status, "tailing_seat_state", 0)
            self.electronic_brake_cb.setChecked(bool(seat_state & 0x02))
            self.speed_limit_cb.setChecked(bool(seat_state & 0x01))
        elif self.current_protocol == PROTOCOL_SHENZHOUXING:
            self.electronic_brake_cb.setChecked(getattr(status, "brake", False))
            self.speed_limit_cb.setChecked(getattr(status, "speed_limit", False))
        else:
            self.electronic_brake_cb.setChecked(getattr(status, "electronic_brake", False))
            self.speed_limit_cb.setChecked(
                False if self.current_protocol == PROTOCOL_TAILING_Y34B else getattr(status, "speed_limit", False)
            )

        self.current_spin.setValue(getattr(status, "current_a", 0))
        self.hall_count_spin.setValue(getattr(status, "hall_count", 0))
        self.speed_spin.setValue(getattr(status, "speed_kmh", 0.0))
        if getattr(self, "soc_spin", None) is not None:
            if self.current_protocol in {
                PROTOCOL_HANGZHOU_ANXIAN,
                PROTOCOL_FZ_SIF,
                PROTOCOL_JINGXIAN,
                PROTOCOL_SXSY,
            }:
                self.soc_spin.setValue(getattr(status, "voltage_percentage", 0))
            else:
                self.soc_spin.setValue(getattr(status, "soc_percent", 0))
        if getattr(self, "sxsy_soc_spin", None) is not None:
            self.sxsy_soc_spin.setValue(getattr(status, "soc_percent", 0))

        if getattr(self, "lithium_soc_mode_cb", None) is not None:
            self.lithium_soc_mode_cb.setChecked(getattr(status, "lithium_soc_mode", True))
        if getattr(self, "soc_fault_cb", None) is not None:
            self.soc_fault_cb.setChecked(getattr(status, "soc_fault", False))
        if getattr(self, "current_percent_spin", None) is not None:
            self.current_percent_spin.setValue(getattr(status, "current_percentage", 0))

        if getattr(self, "voltage_group", None) is not None:
            voltage_map = [
                status.voltage_36v,
                status.voltage_48v,
                status.voltage_60v,
                status.voltage_64v,
                status.voltage_72v,
                status.voltage_80v,
                status.voltage_84v,
                status.voltage_96v,
            ]
            checked_index = next((index for index, checked in enumerate(voltage_map) if checked), None)
            if checked_index is not None:
                button = self.voltage_group.button(checked_index)
                if button is not None:
                    button.setChecked(True)
            elif self.current_protocol == PROTOCOL_DONGWEI_GTXH and hasattr(self, "voltage_default_rb"):
                self.voltage_default_rb.setChecked(True)
        if getattr(self, "tailing_display_voltage_from_data_cb", None) is not None:
            self.tailing_display_voltage_from_data_cb.setChecked(
                getattr(status, "tailing_display_voltage_from_data", False)
            )
        if getattr(self, "tailing_battery_over_temp_cb", None) is not None:
            self.tailing_battery_over_temp_cb.setChecked(getattr(status, "tailing_battery_over_temp", False))
        if getattr(self, "tailing_battery_over_current_cb", None) is not None:
            self.tailing_battery_over_current_cb.setChecked(
                getattr(status, "tailing_battery_over_current", False)
            )
        if getattr(self, "tailing_battery_over_voltage_cb", None) is not None:
            self.tailing_battery_over_voltage_cb.setChecked(
                getattr(status, "tailing_battery_over_voltage", False)
            )
        if getattr(self, "tailing_dual_soc_cb", None) is not None:
            self.tailing_dual_soc_cb.setChecked(getattr(status, "tailing_dual_soc", False))
        if getattr(self, "tailing_display_sleep_cb", None) is not None:
            self.tailing_display_sleep_cb.setChecked(getattr(status, "tailing_display_sleep", False))
        if getattr(self, "tailing_speed_15_warning_cb", None) is not None:
            self.tailing_speed_15_warning_cb.setChecked(
                getattr(status, "tailing_speed_15kmh_warning", False)
            )
        if getattr(self, "tailing_brake_fault_cb", None) is not None:
            self.tailing_brake_fault_cb.setChecked(getattr(status, "tailing_brake_fault", False))
        if getattr(self, "tailing_real_time_voltage_spin", None) is not None:
            self.tailing_real_time_voltage_spin.setValue(
                getattr(status, "tailing_real_time_voltage_v", 48.0)
            )
        if getattr(self, "shenzhouxing_real_time_voltage_spin", None) is not None:
            self.shenzhouxing_real_time_voltage_spin.setValue(
                getattr(status, "shenzhouxing_real_time_voltage_v", 48)
            )
        if getattr(self, "shenzhouxing_signal_strength_spin", None) is not None:
            self.shenzhouxing_signal_strength_spin.setValue(
                getattr(status, "shenzhouxing_signal_strength", 0)
            )
        if getattr(self, "shenzhouxing_time_hour_spin", None) is not None:
            self.shenzhouxing_time_hour_spin.setValue(getattr(status, "shenzhouxing_time_hour", 0))
        if getattr(self, "shenzhouxing_time_minute_spin", None) is not None:
            self.shenzhouxing_time_minute_spin.setValue(getattr(status, "shenzhouxing_time_minute", 0))
        if getattr(self, "shenzhouxing_push_assist_cb", None) is not None:
            self.shenzhouxing_push_assist_cb.setChecked(getattr(status, "shenzhouxing_push_assist", False))
        if getattr(self, "shenzhouxing_p_blink_cb", None) is not None:
            self.shenzhouxing_p_blink_cb.setChecked(getattr(status, "shenzhouxing_p_blink", False))

    def get_ruilun_status_from_ui(self) -> StatusBits:
        """从UI获取瑞伦协议的Status位配置"""
        status = StatusBits()
        status.protocol_name = self.current_protocol

        # Status1
        if self.current_protocol == PROTOCOL_XINRI:
            status.p_gear_protect = self.distance_mode_cb.isChecked()
            status.low_voltage_alarm = self.speed_alarm_cb.isChecked()
        elif self.current_protocol == PROTOCOL_HANGZHOU_ANXIAN:
            status.protocol_speed_limit = self.speed_alarm_cb.isChecked()
            status.p_gear_protect = self.p_gear_protect_cb.isChecked()
        elif self.current_protocol == PROTOCOL_SXSY:
            state_code = self.sxsy_p_gear_group.checkedId()
            status.sxsy_p_gear_state = state_code if state_code >= 0 else 0x00
        elif self.current_protocol == PROTOCOL_FZ_SIF:
            status.side_stand = self.distance_mode_cb.isChecked()
            status.protocol_speed_limit = self.speed_alarm_cb.isChecked()
            status.p_gear_protect = self.p_gear_protect_cb.isChecked()
        elif self.current_protocol == PROTOCOL_YOUYIBAO:
            status.p_gear_protect = self.distance_mode_cb.isChecked()
            status.side_stand = self.speed_alarm_cb.isChecked()
        elif self.current_protocol == PROTOCOL_DONGWEI_GTXH:
            status.p_gear_protect = self.p_gear_protect_cb.isChecked()
        elif self.current_protocol in {PROTOCOL_TAILING_Y34B, PROTOCOL_TAILING_Y34F}:
            status.side_stand = self.distance_mode_cb.isChecked()
            status.p_gear_protect = self.p_gear_protect_cb.isChecked()
            status.tailing_national_standard = self.tcs_status_cb.isChecked()
        elif self.current_protocol == PROTOCOL_SHENZHOUXING:
            status.side_stand = self.distance_mode_cb.isChecked()
            status.shenzhouxing_hdc = self.speed_alarm_cb.isChecked()
            status.p_gear_protect = self.p_gear_protect_cb.isChecked()
            status.shenzhouxing_hhc = self.tcs_status_cb.isChecked()
        elif self.current_protocol in {PROTOCOL_WUXI_YIGE, PROTOCOL_YADEA, PROTOCOL_JINGXIAN}:
            status.side_stand = self.distance_mode_cb.isChecked()
            status.p_gear_protect = self.p_gear_protect_cb.isChecked()
        else:
            status.distance_mode = self.distance_mode_cb.isChecked()
            status.speed_alarm = self.speed_alarm_cb.isChecked()
            status.p_gear_protect = self.p_gear_protect_cb.isChecked()
            status.tcs_status = self.tcs_status_cb.isChecked()

        # Status2
        if self.current_protocol == PROTOCOL_SHENZHOUXING:
            status.shenzhouxing_tcs = self.status2_d7_cb.isChecked()
        else:
            status.walk_mode = self.status2_d7_cb.isChecked()
        status.hall_fault = self.hall_fault_cb.isChecked()
        status.throttle_fault = self.throttle_fault_cb.isChecked()
        status.controller_fault = self.controller_fault_cb.isChecked()
        status.under_voltage = self.under_voltage_cb.isChecked()
        status.cruise = self.cruise_cb.isChecked()
        if self.current_protocol == PROTOCOL_TAILING_Y34F:
            status.tailing_tire_pressure_low = self.assist_cb.isChecked()
        else:
            status.assist = self.assist_cb.isChecked()
            status.motor_phase_loss = self.motor_phase_loss_cb.isChecked()

        # Status3
        if self.current_protocol == PROTOCOL_SXSY:
            status.sxsy_three_speed = self.gear_four_cb.isChecked()
        else:
            status.gear_four = self.gear_four_cb.isChecked()
        if self.current_protocol == PROTOCOL_TAILING_Y34F:
            status.tailing_tcs_indicator = self.motor_running_cb.isChecked()
        else:
            status.motor_running = self.motor_running_cb.isChecked()
        if self.current_protocol == PROTOCOL_SHENZHOUXING:
            status.shenzhouxing_brake_fault = self.brake_cb.isChecked()
        else:
            status.brake = self.brake_cb.isChecked()
        if self.current_protocol == PROTOCOL_TAILING_Y34F:
            status.tailing_hdc_indicator = self.controller_protect_cb.isChecked()
        else:
            status.controller_protect = self.controller_protect_cb.isChecked()
        status.regen_charging = self.regen_charging_cb.isChecked()
        if self.current_protocol != PROTOCOL_TAILING_Y34F:
            status.anti_runaway = self.anti_runaway_cb.isChecked()
        status.speed_mode = self.speed_mode_spin.value()

        # Status4
        if self.current_protocol in {
            PROTOCOL_WUXI_YIGE,
            PROTOCOL_TAILING_Y34B,
            PROTOCOL_TAILING_Y34F,
            PROTOCOL_FZ_SIF,
        }:
            status.cloud_power_mode = self.current_70_flag_cb.isChecked()
        elif self.current_protocol == PROTOCOL_SHENZHOUXING:
            status.shenzhouxing_bluetooth = self.current_70_flag_cb.isChecked()
        else:
            status.current_70_flag = self.current_70_flag_cb.isChecked()
        if self.current_protocol == PROTOCOL_DONGWEI_GTXH:
            status.side_stand = self.one_key_enable_cb.isChecked()
        elif self.current_protocol in {PROTOCOL_TAILING_Y34B, PROTOCOL_TAILING_Y34F}:
            status.tailing_actual_speed_mode = self.one_key_enable_cb.isChecked()
        elif self.current_protocol == PROTOCOL_SHENZHOUXING:
            status.shenzhouxing_time_display = self.one_key_enable_cb.isChecked()
        else:
            status.one_key_enable = self.one_key_enable_cb.isChecked()
        if self.current_protocol == PROTOCOL_TAILING_Y34F:
            status.tailing_dual_undervoltage = self.ekk_enable_cb.isChecked()
        elif self.current_protocol == PROTOCOL_SHENZHOUXING:
            status.shenzhouxing_4g_signal_indicator = self.ekk_enable_cb.isChecked()
        else:
            status.ekk_enable = self.ekk_enable_cb.isChecked()
        if self.current_protocol == PROTOCOL_SHENZHOUXING:
            status.shenzhouxing_position_indicator = self.over_current_cb.isChecked()
        else:
            status.over_current = self.over_current_cb.isChecked()
        status.stall_protect = self.stall_protect_cb.isChecked()
        status.reverse = self.reverse_cb.isChecked()
        if self.current_protocol == PROTOCOL_TAILING_Y34F:
            status.tailing_seat_state = (
                (0x02 if self.electronic_brake_cb.isChecked() else 0x00)
                | (0x01 if self.speed_limit_cb.isChecked() else 0x00)
            )
        elif self.current_protocol == PROTOCOL_SHENZHOUXING:
            status.brake = self.electronic_brake_cb.isChecked()
            status.speed_limit = self.speed_limit_cb.isChecked()
        else:
            status.electronic_brake = self.electronic_brake_cb.isChecked()
            if self.current_protocol != PROTOCOL_TAILING_Y34B:
                status.speed_limit = self.speed_limit_cb.isChecked()

        # Status5-9
        status.current_a = self.current_spin.value()
        status.hall_count = self.hall_count_spin.value()
        status.speed_kmh = self.speed_spin.value()
        if getattr(self, "soc_spin", None) is not None:
            if self.current_protocol in {
                PROTOCOL_HANGZHOU_ANXIAN,
                PROTOCOL_FZ_SIF,
                PROTOCOL_JINGXIAN,
                PROTOCOL_SXSY,
            }:
                status.voltage_percentage = self.soc_spin.value()
            else:
                status.soc_percent = self.soc_spin.value()
        if getattr(self, "sxsy_soc_spin", None) is not None:
            status.soc_percent = self.sxsy_soc_spin.value()
        if getattr(self, "lithium_soc_mode_cb", None) is not None:
            status.lithium_soc_mode = self.lithium_soc_mode_cb.isChecked()
        if getattr(self, "soc_fault_cb", None) is not None:
            status.soc_fault = self.soc_fault_cb.isChecked()
        if getattr(self, "current_percent_spin", None) is not None:
            status.current_percentage = self.current_percent_spin.value()

        # 系统电压
        if getattr(self, "voltage_group", None) is not None:
            voltage_id = self.voltage_group.checkedId()
            if self.current_protocol == PROTOCOL_DONGWEI_GTXH and voltage_id == 8:
                status.voltage_36v = False
                status.voltage_48v = False
                status.voltage_60v = False
                status.voltage_64v = False
                status.voltage_72v = False
                status.voltage_80v = False
                status.voltage_84v = False
                status.voltage_96v = False
            else:
                status.voltage_36v = (voltage_id == 0)
                status.voltage_48v = (voltage_id == 1)
                status.voltage_60v = (voltage_id == 2)
                status.voltage_64v = (voltage_id == 3)
                status.voltage_72v = (voltage_id == 4)
                status.voltage_80v = (voltage_id == 5)
                status.voltage_84v = (voltage_id == 6)
                status.voltage_96v = (voltage_id == 7)
        else:
            status.voltage_36v = False
            status.voltage_48v = False
            status.voltage_60v = False
            status.voltage_64v = False
            status.voltage_72v = False
            status.voltage_80v = False
            status.voltage_84v = False
            status.voltage_96v = False
        if getattr(self, "tailing_display_voltage_from_data_cb", None) is not None:
            status.tailing_display_voltage_from_data = (
                self.tailing_display_voltage_from_data_cb.isChecked()
            )
        if getattr(self, "tailing_battery_over_temp_cb", None) is not None:
            status.tailing_battery_over_temp = self.tailing_battery_over_temp_cb.isChecked()
        if getattr(self, "tailing_battery_over_current_cb", None) is not None:
            status.tailing_battery_over_current = (
                self.tailing_battery_over_current_cb.isChecked()
            )
        if getattr(self, "tailing_battery_over_voltage_cb", None) is not None:
            status.tailing_battery_over_voltage = (
                self.tailing_battery_over_voltage_cb.isChecked()
            )
        if getattr(self, "tailing_dual_soc_cb", None) is not None:
            status.tailing_dual_soc = self.tailing_dual_soc_cb.isChecked()
        if getattr(self, "tailing_display_sleep_cb", None) is not None:
            status.tailing_display_sleep = self.tailing_display_sleep_cb.isChecked()
        if getattr(self, "tailing_speed_15_warning_cb", None) is not None:
            status.tailing_speed_15kmh_warning = self.tailing_speed_15_warning_cb.isChecked()
        if getattr(self, "tailing_brake_fault_cb", None) is not None:
            status.tailing_brake_fault = self.tailing_brake_fault_cb.isChecked()
        if getattr(self, "tailing_real_time_voltage_spin", None) is not None:
            status.tailing_real_time_voltage_v = self.tailing_real_time_voltage_spin.value()
        if getattr(self, "shenzhouxing_real_time_voltage_spin", None) is not None:
            status.shenzhouxing_real_time_voltage_v = self.shenzhouxing_real_time_voltage_spin.value()
        if getattr(self, "shenzhouxing_signal_strength_spin", None) is not None:
            status.shenzhouxing_signal_strength = self.shenzhouxing_signal_strength_spin.value()
        if getattr(self, "shenzhouxing_time_hour_spin", None) is not None:
            status.shenzhouxing_time_hour = self.shenzhouxing_time_hour_spin.value()
        if getattr(self, "shenzhouxing_time_minute_spin", None) is not None:
            status.shenzhouxing_time_minute = self.shenzhouxing_time_minute_spin.value()
        if getattr(self, "shenzhouxing_push_assist_cb", None) is not None:
            status.shenzhouxing_push_assist = self.shenzhouxing_push_assist_cb.isChecked()
        if getattr(self, "shenzhouxing_p_blink_cb", None) is not None:
            status.shenzhouxing_p_blink = self.shenzhouxing_p_blink_cb.isChecked()

        return status
