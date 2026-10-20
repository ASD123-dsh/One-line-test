#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""xinsiwei 协议配置页及状态绑定；不负责串口和升级。"""

from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QGroupBox,
    QLabel,
    QSpinBox,
    QCheckBox,
    QRadioButton,
    QButtonGroup,
    QScrollArea,
)
from PyQt5.QtCore import Qt
from protocol.protocol_handler import (
    PROTOCOL_CHANGZHOU_XINSIWEI,
    PresetScenarios,
    StatusBits,
)


class XinsiweiPages:
    """作为主窗口的界面组件，沿用现有控件名称和槽函数。"""

    def switch_to_changzhou_xinsiwei_protocol(self):
        """切换到常州新思维协议"""
        # 初始化常州新思维协议的状态结构
        self.current_status = PresetScenarios.changzhou_xinsiwei_normal_running()

        # 显示常州新思维协议的Status配置界面
        self.show_changzhou_xinsiwei_status_config()

        # 重置为正常运行场景
        self.normal_radio.setChecked(True)
        self.on_scenario_changed()

    def show_changzhou_xinsiwei_status_config(self):
        """显示常州新思维协议Status配置界面"""
        # 清除现有标签页
        self._clear_status_tabs()

        # 添加常州新思维协议的标签页
        status1_tab = self.create_xinsiwei_status1_tab()
        self.status_tabs.addTab(status1_tab, "Status1")

        status2_tab = self.create_xinsiwei_status2_tab()
        self.status_tabs.addTab(status2_tab, "Status2")

        status3_tab = self.create_xinsiwei_status3_tab()
        self.status_tabs.addTab(status3_tab, "Status3")

        status4_tab = self.create_xinsiwei_status4_tab()
        self.status_tabs.addTab(status4_tab, "Status4")

        status5_9_tab = self.create_xinsiwei_status5_9_tab()
        self.status_tabs.addTab(status5_9_tab, "Status5-9")

        # 重新连接信号
        self._compact_status_tab_pages()
        self.connect_changzhou_xinsiwei_status_signals()

    def create_xinsiwei_status1_tab(self) -> QWidget:
        """创建常州新思维协议Status1配置标签页"""
        widget = QWidget()
        layout = QGridLayout(widget)

        # Status1位定义（根据常州新思维协议文档）
        self.xinsiwei_reserved_d3_cb = QCheckBox("保留位 D3")
        layout.addWidget(self.xinsiwei_reserved_d3_cb, 0, 0)

        self.xinsiwei_reserved_d2_cb = QCheckBox("保留位 D2")
        layout.addWidget(self.xinsiwei_reserved_d2_cb, 0, 1)

        self.xinsiwei_reserved_d1_cb = QCheckBox("保留位 D1")
        layout.addWidget(self.xinsiwei_reserved_d1_cb, 1, 0)

        self.xinsiwei_reserved_d0_cb = QCheckBox("保留位 D0")
        layout.addWidget(self.xinsiwei_reserved_d0_cb, 1, 1)

        return widget

    def create_xinsiwei_status2_tab(self) -> QWidget:
        """创建常州新思维协议Status2配置标签页"""
        widget = QWidget()
        layout = QGridLayout(widget)
        layout.setSpacing(8)  # 减少间距
        layout.setContentsMargins(10, 10, 10, 10)  # 减少边距

        # Status2位定义（复用瑞轮协议的Status2定义）
        self.hall_fault_cb = QCheckBox("霍尔故障 (D6)")
        layout.addWidget(self.hall_fault_cb, 0, 0)

        self.throttle_fault_cb = QCheckBox("转把故障 (D5)")
        layout.addWidget(self.throttle_fault_cb, 0, 1)

        self.controller_fault_cb = QCheckBox("控制器故障 (D4)")
        layout.addWidget(self.controller_fault_cb, 1, 0)

        self.under_voltage_cb = QCheckBox("欠压保护 (D3)")
        layout.addWidget(self.under_voltage_cb, 1, 1)

        self.cruise_cb = QCheckBox("巡航 (D2)")
        layout.addWidget(self.cruise_cb, 2, 0)

        self.assist_cb = QCheckBox("助力 (D1)")
        layout.addWidget(self.assist_cb, 2, 1)

        self.motor_phase_loss_cb = QCheckBox("电机缺相 (D0)")
        layout.addWidget(self.motor_phase_loss_cb, 3, 0)

        # 添加垂直弹簧，将控件推向顶部
        layout.setRowStretch(4, 1)

        return widget

    def create_xinsiwei_status3_tab(self) -> QWidget:
        """创建常州新思维协议Status3配置标签页"""
        widget = QWidget()
        layout = QGridLayout(widget)
        layout.setSpacing(8)  # 减少间距
        layout.setContentsMargins(10, 10, 10, 10)  # 减少边距

        # Status3位定义（复用瑞轮协议的Status3定义）
        self.gear_four_cb = QCheckBox("四档指示 (D7)")
        layout.addWidget(self.gear_four_cb, 0, 0)

        self.motor_running_cb = QCheckBox("电机运行状态 (D6) - 1=运行/0=停止")
        layout.addWidget(self.motor_running_cb, 0, 1)

        self.brake_cb = QCheckBox("刹车 (D5)")
        layout.addWidget(self.brake_cb, 1, 0)

        self.controller_protect_cb = QCheckBox("控制器保护 (D4)")
        layout.addWidget(self.controller_protect_cb, 1, 1)

        self.regen_charging_cb = QCheckBox("滑行充电 (D3) - 1=能量回收")
        layout.addWidget(self.regen_charging_cb, 2, 0)

        self.anti_runaway_cb = QCheckBox("防飞车保护 (D2)")
        layout.addWidget(self.anti_runaway_cb, 2, 1)

        # 三速模式
        layout.addWidget(QLabel("三速模式 (D1~D0):"), 3, 0)
        self.speed_mode_spin = QSpinBox()
        self.speed_mode_spin.setRange(0, 3)
        layout.addWidget(self.speed_mode_spin, 3, 1)

        # 添加垂直弹簧，将控件推向顶部
        layout.setRowStretch(4, 1)

        return widget

    def create_xinsiwei_status4_tab(self) -> QWidget:
        """创建常州新思维协议Status4配置标签页"""
        widget = QWidget()
        layout = QGridLayout(widget)
        layout.setSpacing(8)  # 减少间距
        layout.setContentsMargins(10, 10, 10, 10)  # 减少边距

        self.current_70_flag_cb = QCheckBox("备用 (D7)")
        self.current_70_flag_cb.setEnabled(False)
        layout.addWidget(self.current_70_flag_cb, 0, 0)

        self.one_key_enable_cb = QCheckBox("一键通启用 (D6)")
        layout.addWidget(self.one_key_enable_cb, 0, 1)

        self.ekk_enable_cb = QCheckBox("EKK启用 (D5)")
        layout.addWidget(self.ekk_enable_cb, 1, 0)

        self.over_current_cb = QCheckBox("过流保护 (D4)")
        layout.addWidget(self.over_current_cb, 1, 1)

        self.stall_protect_cb = QCheckBox("堵转保护 (D3)")
        layout.addWidget(self.stall_protect_cb, 2, 0)

        self.reverse_cb = QCheckBox("倒车 (D2)")
        layout.addWidget(self.reverse_cb, 2, 1)

        self.electronic_brake_cb = QCheckBox("电子刹车 (D1)")
        layout.addWidget(self.electronic_brake_cb, 3, 0)

        self.speed_limit_cb = QCheckBox("限速 (D0) - 1=限速/0=解除")
        layout.addWidget(self.speed_limit_cb, 3, 1)

        # 添加垂直弹簧，将控件推向顶部
        layout.setRowStretch(4, 1)

        return widget

    def create_xinsiwei_status5_9_tab(self) -> QWidget:
        """创建常州新思维协议Status5-9配置标签页"""
        widget = QWidget()
        main_layout = QVBoxLayout(widget)
        main_layout.setSpacing(8)  # 减少间距
        main_layout.setContentsMargins(10, 10, 10, 10)  # 减少边距

        # 创建滚动区域以防内容过多
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        scroll_widget = QWidget()
        layout = QGridLayout(scroll_widget)
        layout.setSpacing(6)  # 更紧凑的间距
        layout.setContentsMargins(5, 5, 5, 5)  # 更小的边距

        # Status5 - 运行电流
        layout.addWidget(QLabel("运行电流 (A):"), 0, 0)
        self.current_spin = QSpinBox()
        self.current_spin.setRange(-128, 127)
        self.current_spin.setValue(0)
        layout.addWidget(self.current_spin, 0, 1)

        # Status6~7 - 霍尔计数速度（常州新思维协议特有）
        layout.addWidget(QLabel("霍尔计数速度:"), 1, 0)
        self.xinsiwei_hall_count_spin = QSpinBox()
        self.xinsiwei_hall_count_spin.setRange(0, 65535)
        self.xinsiwei_hall_count_spin.setValue(0)
        layout.addWidget(self.xinsiwei_hall_count_spin, 1, 1)

        # Status8 - 电池SOC
        layout.addWidget(QLabel("电池SOC (%):"), 2, 0)
        soc_layout = QHBoxLayout()
        self.soc_spin = QSpinBox()
        self.soc_spin.setRange(0, 100)
        self.soc_spin.setValue(50)
        soc_layout.addWidget(self.soc_spin)

        self.soc_fault_cb = QCheckBox("SOC故障")
        self.soc_fault_cb.toggled.connect(self.on_soc_fault_toggled)
        soc_layout.addWidget(self.soc_fault_cb)
        soc_widget = QWidget()
        soc_widget.setLayout(soc_layout)
        layout.addWidget(soc_widget, 2, 1)

        # Status9 - 系统电压 - 使用更紧凑的布局
        voltage_group = QGroupBox("系统电压")
        voltage_layout = QGridLayout(voltage_group)
        voltage_layout.setSpacing(4)  # 更紧凑的间距
        voltage_layout.setContentsMargins(8, 8, 8, 8)  # 更小的边距

        self.voltage_group = QButtonGroup()

        self.voltage_24v_rb = QRadioButton("24V")
        self.voltage_group.addButton(self.voltage_24v_rb, 0)
        voltage_layout.addWidget(self.voltage_24v_rb, 0, 0)

        self.voltage_36v_rb = QRadioButton("36V")
        self.voltage_group.addButton(self.voltage_36v_rb, 1)
        voltage_layout.addWidget(self.voltage_36v_rb, 0, 1)

        self.voltage_48v_rb = QRadioButton("48V")
        self.voltage_48v_rb.setChecked(True)  # 默认选中48V
        self.voltage_group.addButton(self.voltage_48v_rb, 2)
        voltage_layout.addWidget(self.voltage_48v_rb, 0, 2)

        self.voltage_60v_rb = QRadioButton("60V")
        self.voltage_group.addButton(self.voltage_60v_rb, 3)
        voltage_layout.addWidget(self.voltage_60v_rb, 1, 0)

        self.voltage_72v_rb = QRadioButton("72V")
        self.voltage_group.addButton(self.voltage_72v_rb, 4)
        voltage_layout.addWidget(self.voltage_72v_rb, 1, 1)

        layout.addWidget(voltage_group, 3, 0, 1, 2)

        # 常州新思维协议特有字段
        layout.addWidget(QLabel("协议标识:"), 4, 0)
        self.protocol_id_spin = QSpinBox()
        self.protocol_id_spin.setRange(0, 15)
        self.protocol_id_spin.setValue(1)  # 默认协议标识为1
        layout.addWidget(self.protocol_id_spin, 4, 1)

        layout.addWidget(QLabel("序列号 (0-4095):"), 5, 0)
        self.sequence_num_spin = QSpinBox()
        self.sequence_num_spin.setRange(0, 4095)
        self.sequence_num_spin.setValue(0)
        layout.addWidget(self.sequence_num_spin, 5, 1)

        # 设置滚动区域
        scroll_area.setWidget(scroll_widget)
        main_layout.addWidget(scroll_area)

        return widget

    def connect_changzhou_xinsiwei_status_signals(self):
        """连接常州新思维协议状态信号"""
        # Status1 - 预留位D0-D3
        if hasattr(self, 'xinsiwei_reserved_d0_cb'):
            self.xinsiwei_reserved_d0_cb.toggled.connect(self.update_current_frame_display)
        if hasattr(self, 'xinsiwei_reserved_d1_cb'):
            self.xinsiwei_reserved_d1_cb.toggled.connect(self.update_current_frame_display)
        if hasattr(self, 'xinsiwei_reserved_d2_cb'):
            self.xinsiwei_reserved_d2_cb.toggled.connect(self.update_current_frame_display)
        if hasattr(self, 'xinsiwei_reserved_d3_cb'):
            self.xinsiwei_reserved_d3_cb.toggled.connect(self.update_current_frame_display)

        # Status2 - 故障状态（复用瑞轮协议控件）
        if hasattr(self, 'hall_fault_cb'):
            self.hall_fault_cb.toggled.connect(self.update_current_frame_display)
        if hasattr(self, 'throttle_fault_cb'):
            self.throttle_fault_cb.toggled.connect(self.update_current_frame_display)
        if hasattr(self, 'controller_fault_cb'):
            self.controller_fault_cb.toggled.connect(self.update_current_frame_display)
        if hasattr(self, 'under_voltage_cb'):
            self.under_voltage_cb.toggled.connect(self.update_current_frame_display)
        if hasattr(self, 'cruise_cb'):
            self.cruise_cb.toggled.connect(self.update_current_frame_display)
        if hasattr(self, 'assist_cb'):
            self.assist_cb.toggled.connect(self.update_current_frame_display)
        if hasattr(self, 'motor_phase_loss_cb'):
            self.motor_phase_loss_cb.toggled.connect(self.update_current_frame_display)

        # Status3 - 运行状态（复用瑞轮协议控件）
        if hasattr(self, 'gear_four_cb'):
            self.gear_four_cb.toggled.connect(self.update_current_frame_display)
        if hasattr(self, 'motor_running_cb'):
            self.motor_running_cb.toggled.connect(self.update_current_frame_display)
        if hasattr(self, 'brake_cb'):
            self.brake_cb.toggled.connect(self.update_current_frame_display)
        if hasattr(self, 'controller_protect_cb'):
            self.controller_protect_cb.toggled.connect(self.update_current_frame_display)
        if hasattr(self, 'regen_charging_cb'):
            self.regen_charging_cb.toggled.connect(self.update_current_frame_display)
        if hasattr(self, 'anti_runaway_cb'):
            self.anti_runaway_cb.toggled.connect(self.update_current_frame_display)
        if hasattr(self, 'speed_mode_spin'):
            self.speed_mode_spin.valueChanged.connect(self.update_current_frame_display)

        # Status4 - 保护状态（复用瑞轮协议控件）
        if hasattr(self, 'current_70_flag_cb'):
            self.current_70_flag_cb.toggled.connect(self.update_current_frame_display)
        if hasattr(self, 'one_key_enable_cb'):
            self.one_key_enable_cb.toggled.connect(self.update_current_frame_display)
        if hasattr(self, 'ekk_enable_cb'):
            self.ekk_enable_cb.toggled.connect(self.update_current_frame_display)
        if hasattr(self, 'over_current_cb'):
            self.over_current_cb.toggled.connect(self.update_current_frame_display)
        if hasattr(self, 'stall_protect_cb'):
            self.stall_protect_cb.toggled.connect(self.update_current_frame_display)
        if hasattr(self, 'reverse_cb'):
            self.reverse_cb.toggled.connect(self.update_current_frame_display)
        if hasattr(self, 'electronic_brake_cb'):
            self.electronic_brake_cb.toggled.connect(self.update_current_frame_display)
        if hasattr(self, 'speed_limit_cb'):
            self.speed_limit_cb.toggled.connect(self.update_current_frame_display)

        # Status5-9 - 新思维特有控件
        if hasattr(self, 'current_spin'):
            self.current_spin.valueChanged.connect(self.update_current_frame_display)
        if hasattr(self, 'xinsiwei_hall_count_spin'):
            self.xinsiwei_hall_count_spin.valueChanged.connect(self.update_current_frame_display)
        if hasattr(self, 'soc_spin'):
            self.soc_spin.valueChanged.connect(self.update_current_frame_display)
        if hasattr(self, 'soc_fault_cb'):
            self.soc_fault_cb.toggled.connect(self.update_current_frame_display)
        if hasattr(self, 'voltage_group'):
            self.voltage_group.buttonClicked.connect(self.update_current_frame_display)
        if hasattr(self, 'shenzhouxing_real_time_voltage_spin'):
            self.shenzhouxing_real_time_voltage_spin.valueChanged.connect(self.update_current_frame_display)
        if hasattr(self, 'shenzhouxing_signal_strength_spin'):
            self.shenzhouxing_signal_strength_spin.valueChanged.connect(self.update_current_frame_display)
        if hasattr(self, 'shenzhouxing_time_hour_spin'):
            self.shenzhouxing_time_hour_spin.valueChanged.connect(self.update_current_frame_display)
        if hasattr(self, 'shenzhouxing_time_minute_spin'):
            self.shenzhouxing_time_minute_spin.valueChanged.connect(self.update_current_frame_display)
        if hasattr(self, 'shenzhouxing_push_assist_cb'):
            self.shenzhouxing_push_assist_cb.toggled.connect(self.update_current_frame_display)
        if hasattr(self, 'shenzhouxing_p_blink_cb'):
            self.shenzhouxing_p_blink_cb.toggled.connect(self.update_current_frame_display)

    def load_changzhou_xinsiwei_preset_scenario(self, scenario_id):
        """加载常州新思维协议预设场景"""
        if scenario_id == 0:  # 正常运行
            self.current_status = PresetScenarios.changzhou_xinsiwei_normal_running()
        elif scenario_id == 1:  # 能量回收
            self.current_status = PresetScenarios.changzhou_xinsiwei_energy_recovery()
        elif scenario_id == 2:  # 故障场景
            self.current_status = PresetScenarios.changzhou_xinsiwei_fault_scenario()
        else:
            # 自定义场景，初始化为空StatusBits对象
            self.current_status = StatusBits()

        # 更新UI显示
        self.update_changzhou_xinsiwei_ui_from_status()

    def update_changzhou_xinsiwei_ui_from_status(self):
        """根据常州新思维协议状态更新UI显示"""
        if not hasattr(self, 'current_status') or not isinstance(self.current_status, StatusBits):
            return

        status = self.current_status

        # 更新Status1 - 预留位D0-D3
        if hasattr(self, 'xinsiwei_reserved_d0_cb'):
            self.xinsiwei_reserved_d0_cb.setChecked(getattr(status, 'xinsiwei_reserved_d0', False))
        if hasattr(self, 'xinsiwei_reserved_d1_cb'):
            self.xinsiwei_reserved_d1_cb.setChecked(getattr(status, 'xinsiwei_reserved_d1', False))
        if hasattr(self, 'xinsiwei_reserved_d2_cb'):
            self.xinsiwei_reserved_d2_cb.setChecked(getattr(status, 'xinsiwei_reserved_d2', False))
        if hasattr(self, 'xinsiwei_reserved_d3_cb'):
            self.xinsiwei_reserved_d3_cb.setChecked(getattr(status, 'xinsiwei_reserved_d3', False))

        # 更新Status2
        if hasattr(self, 'hall_fault_cb'):
            self.hall_fault_cb.setChecked(getattr(status, 'hall_fault', False))
        if hasattr(self, 'throttle_fault_cb'):
            self.throttle_fault_cb.setChecked(getattr(status, 'throttle_fault', False))
        if hasattr(self, 'controller_fault_cb'):
            self.controller_fault_cb.setChecked(getattr(status, 'controller_fault', False))
        if hasattr(self, 'under_voltage_cb'):
            self.under_voltage_cb.setChecked(getattr(status, 'under_voltage', False))
        if hasattr(self, 'cruise_cb'):
            self.cruise_cb.setChecked(getattr(status, 'cruise', False))
        if hasattr(self, 'assist_cb'):
            self.assist_cb.setChecked(getattr(status, 'assist', False))
        if hasattr(self, 'motor_phase_loss_cb'):
            self.motor_phase_loss_cb.setChecked(getattr(status, 'motor_phase_loss', False))

        # 更新Status3
        if hasattr(self, 'gear_four_cb'):
            self.gear_four_cb.setChecked(getattr(status, 'gear_four', False))
        if hasattr(self, 'motor_running_cb'):
            self.motor_running_cb.setChecked(getattr(status, 'motor_running', False))
        if hasattr(self, 'brake_cb'):
            self.brake_cb.setChecked(getattr(status, 'brake', False))
        if hasattr(self, 'controller_protect_cb'):
            self.controller_protect_cb.setChecked(getattr(status, 'controller_protect', False))
        if hasattr(self, 'regen_charging_cb'):
            self.regen_charging_cb.setChecked(getattr(status, 'regen_charging', False))
        if hasattr(self, 'anti_runaway_cb'):
            self.anti_runaway_cb.setChecked(getattr(status, 'anti_runaway', False))
        if hasattr(self, 'speed_mode_spin'):
            self.speed_mode_spin.setValue(getattr(status, 'speed_mode', 0))

        # 更新Status4
        if hasattr(self, 'one_key_enable_cb'):
            self.one_key_enable_cb.setChecked(getattr(status, 'one_key_enable', False))
        if hasattr(self, 'ekk_enable_cb'):
            self.ekk_enable_cb.setChecked(getattr(status, 'ekk_enable', False))
        if hasattr(self, 'over_current_cb'):
            self.over_current_cb.setChecked(getattr(status, 'over_current', False))
        if hasattr(self, 'stall_protect_cb'):
            self.stall_protect_cb.setChecked(getattr(status, 'stall_protect', False))
        if hasattr(self, 'reverse_cb'):
            self.reverse_cb.setChecked(getattr(status, 'reverse', False))
        if hasattr(self, 'electronic_brake_cb'):
            self.electronic_brake_cb.setChecked(getattr(status, 'electronic_brake', False))
        if hasattr(self, 'speed_limit_cb'):
            self.speed_limit_cb.setChecked(getattr(status, 'speed_limit', False))

        # 更新Status5-9
        if hasattr(self, 'current_spin'):
            self.current_spin.setValue(getattr(status, 'current_a', 0))
        if hasattr(self, 'xinsiwei_hall_count_spin'):
            self.xinsiwei_hall_count_spin.setValue(getattr(status, 'xinsiwei_hall_count', 0))
        if hasattr(self, 'soc_spin'):
            self.soc_spin.setValue(getattr(status, 'soc_percent', 0))
        if hasattr(self, 'soc_fault_cb'):
            self.soc_fault_cb.setChecked(getattr(status, 'soc_fault', False))

        voltage_map = [
            status.voltage_24v,
            status.voltage_36v,
            status.voltage_48v,
            status.voltage_60v,
            status.voltage_72v,
        ]
        checked_index = next((index for index, checked in enumerate(voltage_map) if checked), None)
        if checked_index is not None and hasattr(self, 'voltage_group'):
            button = self.voltage_group.button(checked_index)
            if button is not None:
                button.setChecked(True)

    def get_changzhou_xinsiwei_status_from_ui(self) -> StatusBits:
        """从UI获取常州新思维协议的Status位配置"""
        status = StatusBits()
        status.protocol_name = PROTOCOL_CHANGZHOU_XINSIWEI

        # Status1 - 预留位D0-D3
        if hasattr(self, 'xinsiwei_reserved_d0_cb'):
            status.xinsiwei_reserved_d0 = self.xinsiwei_reserved_d0_cb.isChecked()
        if hasattr(self, 'xinsiwei_reserved_d1_cb'):
            status.xinsiwei_reserved_d1 = self.xinsiwei_reserved_d1_cb.isChecked()
        if hasattr(self, 'xinsiwei_reserved_d2_cb'):
            status.xinsiwei_reserved_d2 = self.xinsiwei_reserved_d2_cb.isChecked()
        if hasattr(self, 'xinsiwei_reserved_d3_cb'):
            status.xinsiwei_reserved_d3 = self.xinsiwei_reserved_d3_cb.isChecked()

        # Status2 - 故障状态（使用实际创建的控件名称）
        if hasattr(self, 'hall_fault_cb'):
            status.hall_fault = self.hall_fault_cb.isChecked()
        if hasattr(self, 'motor_phase_loss_cb'):
            status.motor_phase_loss = self.motor_phase_loss_cb.isChecked()
        if hasattr(self, 'controller_fault_cb'):
            status.controller_fault = self.controller_fault_cb.isChecked()
        if hasattr(self, 'throttle_fault_cb'):
            status.throttle_fault = self.throttle_fault_cb.isChecked()
        if hasattr(self, 'under_voltage_cb'):
            status.under_voltage = self.under_voltage_cb.isChecked()
        if hasattr(self, 'cruise_cb'):
            status.cruise = self.cruise_cb.isChecked()
        if hasattr(self, 'assist_cb'):
            status.assist = self.assist_cb.isChecked()

        # Status3 - 运行状态（使用实际创建的控件名称）
        if hasattr(self, 'gear_four_cb'):
            status.gear_four = self.gear_four_cb.isChecked()
        if hasattr(self, 'motor_running_cb'):
            status.motor_running = self.motor_running_cb.isChecked()
        if hasattr(self, 'brake_cb'):
            status.brake = self.brake_cb.isChecked()
        if hasattr(self, 'controller_protect_cb'):
            status.controller_protect = self.controller_protect_cb.isChecked()
        if hasattr(self, 'regen_charging_cb'):
            status.regen_charging = self.regen_charging_cb.isChecked()
        if hasattr(self, 'anti_runaway_cb'):
            status.anti_runaway = self.anti_runaway_cb.isChecked()
        if hasattr(self, 'speed_mode_spin'):
            status.speed_mode = self.speed_mode_spin.value()

        # Status4 - 保护状态（使用实际创建的控件名称）
        if hasattr(self, 'current_70_flag_cb'):
            status.current_70_flag = self.current_70_flag_cb.isChecked()
        if hasattr(self, 'one_key_enable_cb'):
            status.one_key_enable = self.one_key_enable_cb.isChecked()
        if hasattr(self, 'ekk_enable_cb'):
            status.ekk_enable = self.ekk_enable_cb.isChecked()
        if hasattr(self, 'over_current_cb'):
            status.over_current = self.over_current_cb.isChecked()
        if hasattr(self, 'stall_protect_cb'):
            status.stall_protect = self.stall_protect_cb.isChecked()
        if hasattr(self, 'reverse_cb'):
            status.reverse = self.reverse_cb.isChecked()
        if hasattr(self, 'electronic_brake_cb'):
            status.electronic_brake = self.electronic_brake_cb.isChecked()
        if hasattr(self, 'speed_limit_cb'):
            status.speed_limit = self.speed_limit_cb.isChecked()

        # Status5-9 - 新思维特有控件（使用实际创建的控件名称）
        if hasattr(self, 'current_spin'):
            status.current_a = self.current_spin.value()
        if hasattr(self, 'xinsiwei_hall_count_spin'):
            status.xinsiwei_hall_count = self.xinsiwei_hall_count_spin.value()
        if hasattr(self, 'soc_spin'):
            status.soc_percent = self.soc_spin.value()
        if hasattr(self, 'soc_fault_cb'):
            status.soc_fault = self.soc_fault_cb.isChecked()

        # 系统电压选择（使用实际创建的控件名称）
        if hasattr(self, 'voltage_24v_rb') and self.voltage_24v_rb.isChecked():
            status.voltage_24v = True
            status.voltage_36v = False
            status.voltage_48v = False
            status.voltage_60v = False
            status.voltage_72v = False
        elif hasattr(self, 'voltage_36v_rb') and self.voltage_36v_rb.isChecked():
            status.voltage_24v = False
            status.voltage_36v = True
            status.voltage_48v = False
            status.voltage_60v = False
            status.voltage_72v = False
        elif hasattr(self, 'voltage_48v_rb') and self.voltage_48v_rb.isChecked():
            status.voltage_24v = False
            status.voltage_36v = False
            status.voltage_48v = True
            status.voltage_60v = False
            status.voltage_72v = False
        elif hasattr(self, 'voltage_60v_rb') and self.voltage_60v_rb.isChecked():
            status.voltage_24v = False
            status.voltage_36v = False
            status.voltage_48v = False
            status.voltage_60v = True
            status.voltage_72v = False
        elif hasattr(self, 'voltage_72v_rb') and self.voltage_72v_rb.isChecked():
            status.voltage_24v = False
            status.voltage_36v = False
            status.voltage_48v = False
            status.voltage_60v = False
            status.voltage_72v = True
        else:
            # 默认48V
            status.voltage_24v = False
            status.voltage_36v = False
            status.voltage_48v = True
            status.voltage_60v = False
            status.voltage_72v = False

        # 新思维特有字段
        # 设置协议标识，确保协议路由正确识别
        status.xinsiwei_protocol = True

        # 协议标识符和流水号（使用实际创建的控件名称）
        if hasattr(self, 'protocol_id_spin'):
            status.protocol_identifier = self.protocol_id_spin.value()
        if hasattr(self, 'sequence_num_spin'):
            status.sequence_number = self.sequence_num_spin.value()

        # 序号由自动递增功能管理，这里不需要从UI获取
        # if hasattr(self, 'xinsiwei_sequence_spinbox'):
        #     status.xinsiwei_sequence = self.xinsiwei_sequence_spinbox.value()

        return status
