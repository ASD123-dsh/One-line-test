#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""xinchi 协议配置页及状态绑定；不负责串口和升级。"""

from PyQt5.QtWidgets import (
    QWidget,
    QGridLayout,
    QLabel,
    QSpinBox,
    QDoubleSpinBox,
    QCheckBox,
)
from protocol.protocol_handler import (
    PROTOCOL_XINCHI,
    PresetScenarios,
    StatusBits,
)


class XinchiPages:
    """作为主窗口的界面组件，沿用现有控件名称和槽函数。"""

    def switch_to_xinchi_protocol(self):
        """切换到芯驰 BMS 协议"""
        self.current_status = PresetScenarios.xinchi_normal_running()
        self.show_xinchi_status_config()
        self.normal_radio.setChecked(True)
        self.on_scenario_changed()

    def show_xinchi_status_config(self):
        """显示芯驰 BMS 协议配置界面。"""
        self._clear_status_tabs()
        self.status_tabs.addTab(self.create_xinchi_status_flags_tab(), "BMS状态")
        self.status_tabs.addTab(self.create_xinchi_battery_data_tab(), "电池数据")
        self._compact_status_tab_pages()
        self.connect_xinchi_status_signals()

    def create_xinchi_status_flags_tab(self) -> QWidget:
        """创建芯驰 BMS 状态页。"""
        widget = QWidget()
        layout = QGridLayout(widget)

        self.xinchi_charge_mos_cb = QCheckBox("充电MOS状态 (D7)")
        layout.addWidget(self.xinchi_charge_mos_cb, 0, 0)
        self.xinchi_discharge_mos_cb = QCheckBox("放电MOS状态 (D6)")
        layout.addWidget(self.xinchi_discharge_mos_cb, 0, 1)

        self.xinchi_high_temp_fault_cb = QCheckBox("高温故障 (D5)")
        layout.addWidget(self.xinchi_high_temp_fault_cb, 1, 0)
        self.xinchi_low_temp_fault_cb = QCheckBox("低温故障 (D4)")
        layout.addWidget(self.xinchi_low_temp_fault_cb, 1, 1)

        self.xinchi_over_voltage_fault_cb = QCheckBox("过压故障 (D3)")
        layout.addWidget(self.xinchi_over_voltage_fault_cb, 2, 0)
        self.xinchi_under_voltage_fault_cb = QCheckBox("欠压故障 (D2)")
        layout.addWidget(self.xinchi_under_voltage_fault_cb, 2, 1)

        self.xinchi_reserved_d1_cb = QCheckBox("Reserved (D1)")
        self.xinchi_reserved_d1_cb.setEnabled(False)
        layout.addWidget(self.xinchi_reserved_d1_cb, 3, 0)

        self.xinchi_bms_fault_cb = QCheckBox("BMS故障 (D0)")
        layout.addWidget(self.xinchi_bms_fault_cb, 3, 1)

        return widget

    def create_xinchi_battery_data_tab(self) -> QWidget:
        """创建芯驰电池数据页。"""
        widget = QWidget()
        layout = QGridLayout(widget)

        layout.addWidget(QLabel("SOC (%):"), 0, 0)
        self.xinchi_soc_spin = QSpinBox()
        self.xinchi_soc_spin.setRange(0, 100)
        self.xinchi_soc_spin.setValue(80)
        layout.addWidget(self.xinchi_soc_spin, 0, 1)

        layout.addWidget(QLabel("循环次数:"), 1, 0)
        self.xinchi_cycle_count_spin = QSpinBox()
        self.xinchi_cycle_count_spin.setRange(0, 65535)
        layout.addWidget(self.xinchi_cycle_count_spin, 1, 1)

        layout.addWidget(QLabel("电池温度 (℃):"), 2, 0)
        self.xinchi_temperature_spin = QSpinBox()
        self.xinchi_temperature_spin.setRange(-40, 120)
        self.xinchi_temperature_spin.setValue(25)
        layout.addWidget(self.xinchi_temperature_spin, 2, 1)

        layout.addWidget(QLabel("总电压 (V):"), 3, 0)
        self.xinchi_total_voltage_spin = QDoubleSpinBox()
        self.xinchi_total_voltage_spin.setRange(0.0, 6553.5)
        self.xinchi_total_voltage_spin.setDecimals(1)
        self.xinchi_total_voltage_spin.setSingleStep(0.1)
        self.xinchi_total_voltage_spin.setValue(48.0)
        layout.addWidget(self.xinchi_total_voltage_spin, 3, 1)

        layout.addWidget(QLabel("总电流 (A):"), 4, 0)
        self.xinchi_total_current_spin = QSpinBox()
        self.xinchi_total_current_spin.setRange(0, 255)
        self.xinchi_total_current_spin.setValue(0)
        layout.addWidget(self.xinchi_total_current_spin, 4, 1)

        return widget

    def connect_xinchi_status_signals(self):
        """连接芯驰 BMS 协议状态信号。"""
        self.xinchi_charge_mos_cb.toggled.connect(self.update_current_frame_display)
        self.xinchi_discharge_mos_cb.toggled.connect(self.update_current_frame_display)
        self.xinchi_high_temp_fault_cb.toggled.connect(self.update_current_frame_display)
        self.xinchi_low_temp_fault_cb.toggled.connect(self.update_current_frame_display)
        self.xinchi_over_voltage_fault_cb.toggled.connect(self.update_current_frame_display)
        self.xinchi_under_voltage_fault_cb.toggled.connect(self.update_current_frame_display)
        self.xinchi_bms_fault_cb.toggled.connect(self.update_current_frame_display)
        self.xinchi_soc_spin.valueChanged.connect(self.update_current_frame_display)
        self.xinchi_cycle_count_spin.valueChanged.connect(self.update_current_frame_display)
        self.xinchi_temperature_spin.valueChanged.connect(self.update_current_frame_display)
        self.xinchi_total_voltage_spin.valueChanged.connect(self.update_current_frame_display)
        self.xinchi_total_current_spin.valueChanged.connect(self.update_current_frame_display)

    def load_xinchi_preset_scenario(self, scenario_id):
        """加载芯驰 BMS 协议预设场景。"""
        if scenario_id == 0:
            self.current_status = PresetScenarios.xinchi_normal_running()
        elif scenario_id == 1:
            self.current_status = PresetScenarios.xinchi_energy_recovery()
        elif scenario_id == 2:
            self.current_status = PresetScenarios.xinchi_fault_scenario()
        else:
            self.current_status = StatusBits(protocol_name=PROTOCOL_XINCHI)

        self.update_xinchi_ui_from_status()

    def update_xinchi_ui_from_status(self):
        """根据芯驰 BMS 协议状态更新 UI。"""
        if not hasattr(self, 'current_status') or not isinstance(self.current_status, StatusBits):
            return

        status = self.current_status

        if hasattr(self, 'xinchi_charge_mos_cb'):
            self.xinchi_charge_mos_cb.setChecked(getattr(status, 'xinchi_charge_mos', False))
        if hasattr(self, 'xinchi_discharge_mos_cb'):
            self.xinchi_discharge_mos_cb.setChecked(getattr(status, 'xinchi_discharge_mos', False))
        if hasattr(self, 'xinchi_high_temp_fault_cb'):
            self.xinchi_high_temp_fault_cb.setChecked(getattr(status, 'xinchi_high_temp_fault', False))
        if hasattr(self, 'xinchi_low_temp_fault_cb'):
            self.xinchi_low_temp_fault_cb.setChecked(getattr(status, 'xinchi_low_temp_fault', False))
        if hasattr(self, 'xinchi_over_voltage_fault_cb'):
            self.xinchi_over_voltage_fault_cb.setChecked(getattr(status, 'xinchi_over_voltage_fault', False))
        if hasattr(self, 'xinchi_under_voltage_fault_cb'):
            self.xinchi_under_voltage_fault_cb.setChecked(getattr(status, 'xinchi_under_voltage_fault', False))
        if hasattr(self, 'xinchi_bms_fault_cb'):
            self.xinchi_bms_fault_cb.setChecked(getattr(status, 'xinchi_bms_fault', False))

        if hasattr(self, 'xinchi_soc_spin'):
            self.xinchi_soc_spin.setValue(getattr(status, 'soc_percent', 0))
        if hasattr(self, 'xinchi_cycle_count_spin'):
            self.xinchi_cycle_count_spin.setValue(getattr(status, 'xinchi_cycle_count', 0))
        if hasattr(self, 'xinchi_temperature_spin'):
            self.xinchi_temperature_spin.setValue(getattr(status, 'xinchi_temperature_c', 25))
        if hasattr(self, 'xinchi_total_voltage_spin'):
            self.xinchi_total_voltage_spin.setValue(getattr(status, 'xinchi_total_voltage_v', 48.0))
        if hasattr(self, 'xinchi_total_current_spin'):
            self.xinchi_total_current_spin.setValue(getattr(status, 'xinchi_total_current_a', 0))

    def get_xinchi_status_from_ui(self) -> StatusBits:
        """从 UI 获取芯驰 BMS 协议配置。"""
        status = StatusBits()
        status.protocol_name = PROTOCOL_XINCHI

        status.xinchi_charge_mos = self.xinchi_charge_mos_cb.isChecked()
        status.xinchi_discharge_mos = self.xinchi_discharge_mos_cb.isChecked()
        status.xinchi_high_temp_fault = self.xinchi_high_temp_fault_cb.isChecked()
        status.xinchi_low_temp_fault = self.xinchi_low_temp_fault_cb.isChecked()
        status.xinchi_over_voltage_fault = self.xinchi_over_voltage_fault_cb.isChecked()
        status.xinchi_under_voltage_fault = self.xinchi_under_voltage_fault_cb.isChecked()
        status.xinchi_bms_fault = self.xinchi_bms_fault_cb.isChecked()

        status.soc_percent = self.xinchi_soc_spin.value()
        status.xinchi_cycle_count = self.xinchi_cycle_count_spin.value()
        status.xinchi_temperature_c = self.xinchi_temperature_spin.value()
        status.xinchi_total_voltage_v = self.xinchi_total_voltage_spin.value()
        status.xinchi_total_current_a = self.xinchi_total_current_spin.value()

        return status
