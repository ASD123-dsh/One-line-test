#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""luyuan 协议配置页及状态绑定；不负责串口和升级。"""

from PyQt5.QtWidgets import (
    QWidget,
    QGridLayout,
    QLabel,
    QSpinBox,
    QDoubleSpinBox,
    QCheckBox,
)
from protocol.protocol_handler import (
    PROTOCOL_LUYUAN_BMS,
    PresetScenarios,
    StatusBits,
)


class LuyuanBmsPages:
    """作为主窗口的界面组件，沿用现有控件名称和槽函数。"""

    def switch_to_luyuan_bms_protocol(self):
        """切换到绿源 BMS 一线通协议"""
        self.current_status = PresetScenarios.luyuan_bms_normal_running()
        self.show_luyuan_bms_status_config()
        self.normal_radio.setChecked(True)
        self.on_scenario_changed()

    def show_luyuan_bms_status_config(self):
        """显示绿源 BMS 一线通协议配置界面。"""
        self._clear_status_tabs()
        self.status_tabs.addTab(self.create_luyuan_bms_status_flags_tab(), "BMS状态")
        self.status_tabs.addTab(self.create_luyuan_bms_battery_data_tab(), "电池数据")
        self._compact_status_tab_pages()
        self.connect_luyuan_bms_status_signals()

    def create_luyuan_bms_status_flags_tab(self) -> QWidget:
        """创建绿源 BMS 状态页。"""
        widget = QWidget()
        layout = QGridLayout(widget)

        self.luyuan_charge_mos_cb = QCheckBox("充电MOS状态 (D7)")
        layout.addWidget(self.luyuan_charge_mos_cb, 0, 0)
        self.luyuan_discharge_mos_cb = QCheckBox("放电MOS状态 (D6)")
        layout.addWidget(self.luyuan_discharge_mos_cb, 0, 1)

        self.luyuan_predischarge_mos_cb = QCheckBox("预放电MOS (D5)")
        layout.addWidget(self.luyuan_predischarge_mos_cb, 1, 0)
        self.luyuan_charge_enable_cb = QCheckBox("充电允许 (D4)")
        layout.addWidget(self.luyuan_charge_enable_cb, 1, 1)

        self.luyuan_charger_connected_cb = QCheckBox("充电器连接状态 (D3)")
        layout.addWidget(self.luyuan_charger_connected_cb, 2, 0)

        self.luyuan_reserved_d2_cb = QCheckBox("Reserved (D2)")
        self.luyuan_reserved_d2_cb.setEnabled(False)
        layout.addWidget(self.luyuan_reserved_d2_cb, 2, 1)

        self.luyuan_reserved_d1_cb = QCheckBox("Reserved (D1)")
        self.luyuan_reserved_d1_cb.setEnabled(False)
        layout.addWidget(self.luyuan_reserved_d1_cb, 3, 0)

        self.luyuan_reserved_d0_cb = QCheckBox("Reserved (D0)")
        self.luyuan_reserved_d0_cb.setEnabled(False)
        layout.addWidget(self.luyuan_reserved_d0_cb, 3, 1)

        return widget

    def create_luyuan_bms_battery_data_tab(self) -> QWidget:
        """创建绿源 BMS 电池数据页。"""
        widget = QWidget()
        layout = QGridLayout(widget)

        layout.addWidget(QLabel("SOC (%):"), 0, 0)
        self.luyuan_soc_spin = QSpinBox()
        self.luyuan_soc_spin.setRange(0, 100)
        self.luyuan_soc_spin.setValue(80)
        layout.addWidget(self.luyuan_soc_spin, 0, 1)

        layout.addWidget(QLabel("循环次数:"), 1, 0)
        self.luyuan_cycle_count_spin = QSpinBox()
        self.luyuan_cycle_count_spin.setRange(0, 65535)
        layout.addWidget(self.luyuan_cycle_count_spin, 1, 1)

        layout.addWidget(QLabel("电池温度 (℃):"), 2, 0)
        self.luyuan_temperature_spin = QSpinBox()
        self.luyuan_temperature_spin.setRange(-40, 120)
        self.luyuan_temperature_spin.setValue(25)
        layout.addWidget(self.luyuan_temperature_spin, 2, 1)

        layout.addWidget(QLabel("最高电芯电压 (mV):"), 3, 0)
        self.luyuan_max_cell_voltage_spin = QSpinBox()
        self.luyuan_max_cell_voltage_spin.setRange(0, 65535)
        self.luyuan_max_cell_voltage_spin.setValue(4200)
        layout.addWidget(self.luyuan_max_cell_voltage_spin, 3, 1)

        layout.addWidget(QLabel("最低电芯电压 (mV):"), 4, 0)
        self.luyuan_min_cell_voltage_spin = QSpinBox()
        self.luyuan_min_cell_voltage_spin.setRange(0, 65535)
        self.luyuan_min_cell_voltage_spin.setValue(4100)
        layout.addWidget(self.luyuan_min_cell_voltage_spin, 4, 1)

        layout.addWidget(QLabel("电流 (A，充电为正/放电为负):"), 5, 0)
        self.luyuan_current_spin = QDoubleSpinBox()
        self.luyuan_current_spin.setRange(-327.67, 327.67)
        self.luyuan_current_spin.setDecimals(2)
        self.luyuan_current_spin.setSingleStep(0.01)
        self.luyuan_current_spin.setValue(-12.00)
        layout.addWidget(self.luyuan_current_spin, 5, 1)

        layout.addWidget(QLabel("总电压 (V):"), 6, 0)
        self.luyuan_total_voltage_spin = QSpinBox()
        self.luyuan_total_voltage_spin.setRange(0, 255)
        self.luyuan_total_voltage_spin.setValue(54)
        layout.addWidget(self.luyuan_total_voltage_spin, 6, 1)

        layout.addWidget(QLabel("健康度 SOH (%):"), 7, 0)
        self.luyuan_soh_spin = QSpinBox()
        self.luyuan_soh_spin.setRange(0, 100)
        self.luyuan_soh_spin.setValue(100)
        layout.addWidget(self.luyuan_soh_spin, 7, 1)

        return widget

    def connect_luyuan_bms_status_signals(self):
        """连接绿源 BMS 一线通协议状态信号。"""
        self.luyuan_charge_mos_cb.toggled.connect(self.update_current_frame_display)
        self.luyuan_discharge_mos_cb.toggled.connect(self.update_current_frame_display)
        self.luyuan_predischarge_mos_cb.toggled.connect(self.update_current_frame_display)
        self.luyuan_charge_enable_cb.toggled.connect(self.update_current_frame_display)
        self.luyuan_charger_connected_cb.toggled.connect(self.update_current_frame_display)
        self.luyuan_soc_spin.valueChanged.connect(self.update_current_frame_display)
        self.luyuan_cycle_count_spin.valueChanged.connect(self.update_current_frame_display)
        self.luyuan_temperature_spin.valueChanged.connect(self.update_current_frame_display)
        self.luyuan_max_cell_voltage_spin.valueChanged.connect(self.update_current_frame_display)
        self.luyuan_min_cell_voltage_spin.valueChanged.connect(self.update_current_frame_display)
        self.luyuan_current_spin.valueChanged.connect(self.update_current_frame_display)
        self.luyuan_total_voltage_spin.valueChanged.connect(self.update_current_frame_display)
        self.luyuan_soh_spin.valueChanged.connect(self.update_current_frame_display)

    def load_luyuan_bms_preset_scenario(self, scenario_id):
        """加载绿源 BMS 一线通协议预设场景。"""
        if scenario_id == 0:
            self.current_status = PresetScenarios.luyuan_bms_normal_running()
        elif scenario_id == 1:
            self.current_status = PresetScenarios.luyuan_bms_energy_recovery()
        elif scenario_id == 2:
            self.current_status = PresetScenarios.luyuan_bms_fault_scenario()
        else:
            self.current_status = StatusBits(protocol_name=PROTOCOL_LUYUAN_BMS)

        self.update_luyuan_bms_ui_from_status()

    def update_luyuan_bms_ui_from_status(self):
        """根据绿源 BMS 一线通协议状态更新 UI。"""
        if not hasattr(self, 'current_status') or not isinstance(self.current_status, StatusBits):
            return

        status = self.current_status

        if hasattr(self, 'luyuan_charge_mos_cb'):
            self.luyuan_charge_mos_cb.setChecked(getattr(status, 'luyuan_charge_mos', False))
        if hasattr(self, 'luyuan_discharge_mos_cb'):
            self.luyuan_discharge_mos_cb.setChecked(
                getattr(status, 'luyuan_discharge_mos', False)
            )
        if hasattr(self, 'luyuan_predischarge_mos_cb'):
            self.luyuan_predischarge_mos_cb.setChecked(
                getattr(status, 'luyuan_predischarge_mos', False)
            )
        if hasattr(self, 'luyuan_charge_enable_cb'):
            self.luyuan_charge_enable_cb.setChecked(
                getattr(status, 'luyuan_charge_enable', False)
            )
        if hasattr(self, 'luyuan_charger_connected_cb'):
            self.luyuan_charger_connected_cb.setChecked(
                getattr(status, 'luyuan_charger_connected', False)
            )

        if hasattr(self, 'luyuan_soc_spin'):
            self.luyuan_soc_spin.setValue(getattr(status, 'soc_percent', 0))
        if hasattr(self, 'luyuan_cycle_count_spin'):
            self.luyuan_cycle_count_spin.setValue(getattr(status, 'luyuan_cycle_count', 0))
        if hasattr(self, 'luyuan_temperature_spin'):
            self.luyuan_temperature_spin.setValue(getattr(status, 'luyuan_temperature_c', 25))
        if hasattr(self, 'luyuan_max_cell_voltage_spin'):
            self.luyuan_max_cell_voltage_spin.setValue(
                getattr(status, 'luyuan_max_cell_voltage_mv', 4200)
            )
        if hasattr(self, 'luyuan_min_cell_voltage_spin'):
            self.luyuan_min_cell_voltage_spin.setValue(
                getattr(status, 'luyuan_min_cell_voltage_mv', 4100)
            )
        if hasattr(self, 'luyuan_current_spin'):
            self.luyuan_current_spin.setValue(getattr(status, 'luyuan_current_a', 0.0))
        if hasattr(self, 'luyuan_total_voltage_spin'):
            self.luyuan_total_voltage_spin.setValue(
                getattr(status, 'luyuan_total_voltage_v', 48)
            )
        if hasattr(self, 'luyuan_soh_spin'):
            self.luyuan_soh_spin.setValue(getattr(status, 'luyuan_soh_percent', 100))

    def get_luyuan_bms_status_from_ui(self) -> StatusBits:
        """从 UI 获取绿源 BMS 一线通协议配置。"""
        status = StatusBits()
        status.protocol_name = PROTOCOL_LUYUAN_BMS

        status.luyuan_charge_mos = self.luyuan_charge_mos_cb.isChecked()
        status.luyuan_discharge_mos = self.luyuan_discharge_mos_cb.isChecked()
        status.luyuan_predischarge_mos = self.luyuan_predischarge_mos_cb.isChecked()
        status.luyuan_charge_enable = self.luyuan_charge_enable_cb.isChecked()
        status.luyuan_charger_connected = self.luyuan_charger_connected_cb.isChecked()

        status.soc_percent = self.luyuan_soc_spin.value()
        status.luyuan_cycle_count = self.luyuan_cycle_count_spin.value()
        status.luyuan_temperature_c = self.luyuan_temperature_spin.value()
        status.luyuan_max_cell_voltage_mv = self.luyuan_max_cell_voltage_spin.value()
        status.luyuan_min_cell_voltage_mv = self.luyuan_min_cell_voltage_spin.value()
        status.luyuan_current_a = self.luyuan_current_spin.value()
        status.luyuan_total_voltage_v = self.luyuan_total_voltage_spin.value()
        status.luyuan_soh_percent = self.luyuan_soh_spin.value()

        return status
