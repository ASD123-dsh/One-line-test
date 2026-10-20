#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""xinri 协议配置页及状态绑定；不负责串口和升级。"""

from PyQt5.QtWidgets import (
    QWidget,
    QGridLayout,
    QCheckBox,
)
from protocol.protocol_handler import (
    PresetScenarios,
    StatusBits,
)


class XinriPages:
    """作为主窗口的界面组件，沿用现有控件名称和槽函数。"""

    def switch_to_xinri_protocol(self):
        """切换到新日协议"""
        # 初始化新日协议的状态结构
        self.current_status = PresetScenarios.xinri_normal_running()

        # 复用规格书字段化的通用 Status 页面，不再展示无编码映射的伪控件。
        self.show_xinri_status_config()

        # 重置为正常运行场景
        self.normal_radio.setChecked(True)
        self.on_scenario_changed()

    def show_xinri_status_config(self):
        """兼容旧入口，显示新日规格字段化的通用 Status 页面。"""

        self.show_ruilun_status_config()

    def create_xinri_vehicle_status_tab(self) -> QWidget:
        """创建新日协议车辆状态配置标签页"""
        widget = QWidget()
        layout = QGridLayout(widget)

        # 车辆状态位定义（基于新日协议规范）
        self.xinri_power_on_cb = QCheckBox("电源开启")
        layout.addWidget(self.xinri_power_on_cb, 0, 0)

        self.xinri_motor_running_cb = QCheckBox("电机运行")
        layout.addWidget(self.xinri_motor_running_cb, 0, 1)

        self.xinri_charging_cb = QCheckBox("充电状态")
        layout.addWidget(self.xinri_charging_cb, 1, 0)

        self.xinri_brake_cb = QCheckBox("刹车状态")
        layout.addWidget(self.xinri_brake_cb, 1, 1)

        self.xinri_cruise_cb = QCheckBox("巡航模式")
        layout.addWidget(self.xinri_cruise_cb, 2, 0)

        self.xinri_eco_mode_cb = QCheckBox("ECO模式")
        layout.addWidget(self.xinri_eco_mode_cb, 2, 1)

        self.xinri_sport_mode_cb = QCheckBox("运动模式")
        layout.addWidget(self.xinri_sport_mode_cb, 3, 0)

        self.xinri_reverse_cb = QCheckBox("倒车状态")
        layout.addWidget(self.xinri_reverse_cb, 3, 1)

        return widget

    def create_xinri_fault_status_tab(self) -> QWidget:
        """创建新日协议故障状态配置标签页"""
        widget = QWidget()
        layout = QGridLayout(widget)

        # 故障状态位定义
        self.xinri_motor_fault_cb = QCheckBox("电机故障")
        layout.addWidget(self.xinri_motor_fault_cb, 0, 0)

        self.xinri_controller_fault_cb = QCheckBox("控制器故障")
        layout.addWidget(self.xinri_controller_fault_cb, 0, 1)

        self.xinri_battery_fault_cb = QCheckBox("电池故障")
        layout.addWidget(self.xinri_battery_fault_cb, 1, 0)

        self.xinri_throttle_fault_cb = QCheckBox("转把故障")
        layout.addWidget(self.xinri_throttle_fault_cb, 1, 1)

        self.xinri_brake_fault_cb = QCheckBox("刹车故障")
        layout.addWidget(self.xinri_brake_fault_cb, 2, 0)

        self.xinri_hall_fault_cb = QCheckBox("霍尔故障")
        layout.addWidget(self.xinri_hall_fault_cb, 2, 1)

        self.xinri_over_temp_cb = QCheckBox("过温保护")
        layout.addWidget(self.xinri_over_temp_cb, 3, 0)

        self.xinri_under_voltage_cb = QCheckBox("欠压保护")
        layout.addWidget(self.xinri_under_voltage_cb, 3, 1)

        return widget

    def create_xinri_light_status_tab(self) -> QWidget:
        """创建新日协议灯光状态配置标签页"""
        widget = QWidget()
        layout = QGridLayout(widget)

        # 灯光状态位定义
        self.xinri_headlight_cb = QCheckBox("前大灯")
        layout.addWidget(self.xinri_headlight_cb, 0, 0)

        self.xinri_taillight_cb = QCheckBox("尾灯")
        layout.addWidget(self.xinri_taillight_cb, 0, 1)

        self.xinri_left_turn_cb = QCheckBox("左转向灯")
        layout.addWidget(self.xinri_left_turn_cb, 1, 0)

        self.xinri_right_turn_cb = QCheckBox("右转向灯")
        layout.addWidget(self.xinri_right_turn_cb, 1, 1)

        self.xinri_hazard_cb = QCheckBox("危险报警灯")
        layout.addWidget(self.xinri_hazard_cb, 2, 0)

        self.xinri_brake_light_cb = QCheckBox("刹车灯")
        layout.addWidget(self.xinri_brake_light_cb, 2, 1)

        self.xinri_high_beam_cb = QCheckBox("远光灯")
        layout.addWidget(self.xinri_high_beam_cb, 3, 0)

        self.xinri_low_beam_cb = QCheckBox("近光灯")
        layout.addWidget(self.xinri_low_beam_cb, 3, 1)

        return widget

    def create_xinri_gear_status_tab(self) -> QWidget:
        """创建新日协议档位状态配置标签页"""
        widget = QWidget()
        layout = QGridLayout(widget)

        # 档位状态位定义
        self.xinri_gear_p_cb = QCheckBox("P档（驻车）")
        layout.addWidget(self.xinri_gear_p_cb, 0, 0)

        self.xinri_gear_r_cb = QCheckBox("R档（倒车）")
        layout.addWidget(self.xinri_gear_r_cb, 0, 1)

        self.xinri_gear_n_cb = QCheckBox("N档（空档）")
        layout.addWidget(self.xinri_gear_n_cb, 1, 0)

        self.xinri_gear_d_cb = QCheckBox("D档（前进）")
        layout.addWidget(self.xinri_gear_d_cb, 1, 1)

        self.xinri_gear_1_cb = QCheckBox("1档")
        layout.addWidget(self.xinri_gear_1_cb, 2, 0)

        self.xinri_gear_2_cb = QCheckBox("2档")
        layout.addWidget(self.xinri_gear_2_cb, 2, 1)

        self.xinri_gear_3_cb = QCheckBox("3档")
        layout.addWidget(self.xinri_gear_3_cb, 3, 0)

        self.xinri_gear_boost_cb = QCheckBox("助力档")
        layout.addWidget(self.xinri_gear_boost_cb, 3, 1)

        return widget

    def create_xinri_battery_status_tab(self) -> QWidget:
        """创建新日协议电池状态配置标签页"""
        widget = QWidget()
        layout = QGridLayout(widget)

        # 电池状态位定义
        self.xinri_battery_normal_cb = QCheckBox("电池正常")
        layout.addWidget(self.xinri_battery_normal_cb, 0, 0)

        self.xinri_battery_low_cb = QCheckBox("电量低")
        layout.addWidget(self.xinri_battery_low_cb, 0, 1)

        self.xinri_battery_critical_cb = QCheckBox("电量极低")
        layout.addWidget(self.xinri_battery_critical_cb, 1, 0)

        self.xinri_battery_charging_cb = QCheckBox("充电中")
        layout.addWidget(self.xinri_battery_charging_cb, 1, 1)

        self.xinri_battery_full_cb = QCheckBox("充电完成")
        layout.addWidget(self.xinri_battery_full_cb, 2, 0)

        self.xinri_battery_temp_high_cb = QCheckBox("电池温度高")
        layout.addWidget(self.xinri_battery_temp_high_cb, 2, 1)

        self.xinri_battery_temp_low_cb = QCheckBox("电池温度低")
        layout.addWidget(self.xinri_battery_temp_low_cb, 3, 0)

        self.xinri_battery_error_cb = QCheckBox("电池通信错误")
        layout.addWidget(self.xinri_battery_error_cb, 3, 1)

        return widget

    def connect_xinri_status_signals(self):
        """兼容旧入口；通用页面在创建时已完成信号连接。"""

        return None

    def load_xinri_preset_scenario(self, scenario_id):
        """加载新日协议预设场景"""
        # 新日协议现在也使用StatusBits对象
        if scenario_id == 0:  # 正常运行
            self.current_status = PresetScenarios.xinri_normal_running()
        elif scenario_id == 1:  # 能量回收
            self.current_status = PresetScenarios.xinri_energy_recovery()
        elif scenario_id == 2:  # 故障场景
            self.current_status = PresetScenarios.xinri_fault_scenario()
        else:
            # 自定义场景，初始化为空StatusBits对象
            self.current_status = StatusBits()

        # 更新 UI 显示
        self.update_xinri_ui_from_status()

    def update_xinri_ui_from_status(self):
        """兼容旧入口，使用新日规格字段化的通用状态映射。"""

        self.update_ruilun_ui_from_status()

    def get_xinri_status_from_ui(self) -> StatusBits:
        """兼容旧入口，读取新日规格字段化的通用状态页面。"""

        return self.get_ruilun_status_from_ui()
