#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""lithium 协议配置页及状态绑定；不负责串口和升级。"""

from PyQt5.QtWidgets import (
    QWidget,
    QGridLayout,
    QLabel,
    QSpinBox,
    QDoubleSpinBox,
    QCheckBox,
)
from protocol.protocol_handler import (
    PROTOCOL_LITHIUM_BMS,
    PresetScenarios,
    StatusBits,
)


class LithiumBmsPages:
    """作为主窗口的界面组件，沿用现有控件名称和槽函数。"""

    def switch_to_lithium_bms_protocol(self):
        """切换到一线通锂电池 BMS 协议"""
        self.current_status = PresetScenarios.lithium_bms_normal_running()
        self.show_lithium_bms_status_config()
        self.normal_radio.setChecked(True)
        self.on_scenario_changed()

    def show_lithium_bms_status_config(self):
        """显示一线通锂电池 BMS 协议配置界面。"""
        self._clear_status_tabs()
        self.status_tabs.addTab(self.create_lithium_bms_status_flags_tab(), "故障状态")
        self.status_tabs.addTab(self.create_lithium_bms_battery_data_tab(), "电池数据")
        self._compact_status_tab_pages()
        self.connect_lithium_bms_status_signals()

    def create_lithium_bms_status_flags_tab(self) -> QWidget:
        """创建一线通锂电池 BMS 故障状态页。"""
        widget = QWidget()
        layout = QGridLayout(widget)

        self.lithium_bms_alarm_enable_cb = QCheckBox("带故障报警功能 (D7)")
        layout.addWidget(self.lithium_bms_alarm_enable_cb, 0, 0)
        self.lithium_bms_high_temp_alarm_cb = QCheckBox("高温报警 (D6)")
        layout.addWidget(self.lithium_bms_high_temp_alarm_cb, 0, 1)

        self.lithium_bms_low_temp_alarm_cb = QCheckBox("低温报警 (D5)")
        layout.addWidget(self.lithium_bms_low_temp_alarm_cb, 1, 0)
        self.lithium_bms_soh_low_cb = QCheckBox("SOH低于60% (D4)")
        layout.addWidget(self.lithium_bms_soh_low_cb, 1, 1)

        self.lithium_bms_mos_fault_cb = QCheckBox("MOS故障 (D3)")
        layout.addWidget(self.lithium_bms_mos_fault_cb, 2, 0)
        self.lithium_bms_short_circuit_fault_cb = QCheckBox("短路故障 (D2)")
        layout.addWidget(self.lithium_bms_short_circuit_fault_cb, 2, 1)

        self.lithium_bms_reserved_d1_cb = QCheckBox("预留位 (D1)")
        self.lithium_bms_reserved_d1_cb.setEnabled(False)
        layout.addWidget(self.lithium_bms_reserved_d1_cb, 3, 0)

        self.lithium_bms_reserved_d0_cb = QCheckBox("预留位 (D0)")
        self.lithium_bms_reserved_d0_cb.setEnabled(False)
        layout.addWidget(self.lithium_bms_reserved_d0_cb, 3, 1)

        return widget

    def create_lithium_bms_battery_data_tab(self) -> QWidget:
        """创建一线通锂电池 BMS 电池数据页。"""
        widget = QWidget()
        layout = QGridLayout(widget)

        layout.addWidget(QLabel("最高电芯电压 (V):"), 0, 0)
        self.lithium_bms_max_cell_voltage_spin = QDoubleSpinBox()
        self.lithium_bms_max_cell_voltage_spin.setRange(1.85, 4.40)
        self.lithium_bms_max_cell_voltage_spin.setDecimals(2)
        self.lithium_bms_max_cell_voltage_spin.setSingleStep(0.01)
        self.lithium_bms_max_cell_voltage_spin.setValue(3.60)
        layout.addWidget(self.lithium_bms_max_cell_voltage_spin, 0, 1)

        layout.addWidget(QLabel("SOC (%):"), 1, 0)
        self.lithium_bms_soc_spin = QSpinBox()
        self.lithium_bms_soc_spin.setRange(0, 100)
        self.lithium_bms_soc_spin.setValue(80)
        layout.addWidget(self.lithium_bms_soc_spin, 1, 1)

        layout.addWidget(QLabel("总压 (V):"), 2, 0)
        self.lithium_bms_total_voltage_spin = QSpinBox()
        self.lithium_bms_total_voltage_spin.setRange(0, 100)
        self.lithium_bms_total_voltage_spin.setValue(54)
        layout.addWidget(self.lithium_bms_total_voltage_spin, 2, 1)

        layout.addWidget(QLabel("最高电池温度 (℃):"), 3, 0)
        self.lithium_bms_max_temp_spin = QSpinBox()
        self.lithium_bms_max_temp_spin.setRange(-127, 127)
        self.lithium_bms_max_temp_spin.setValue(28)
        layout.addWidget(self.lithium_bms_max_temp_spin, 3, 1)

        layout.addWidget(QLabel("最低电池温度 (℃):"), 4, 0)
        self.lithium_bms_min_temp_spin = QSpinBox()
        self.lithium_bms_min_temp_spin.setRange(-127, 127)
        self.lithium_bms_min_temp_spin.setValue(22)
        layout.addWidget(self.lithium_bms_min_temp_spin, 4, 1)

        layout.addWidget(QLabel("循环次数:"), 5, 0)
        self.lithium_bms_cycle_count_spin = QSpinBox()
        self.lithium_bms_cycle_count_spin.setRange(0, 65535)
        layout.addWidget(self.lithium_bms_cycle_count_spin, 5, 1)

        layout.addWidget(QLabel("最低电芯电压 (V):"), 6, 0)
        self.lithium_bms_min_cell_voltage_spin = QDoubleSpinBox()
        self.lithium_bms_min_cell_voltage_spin.setRange(1.85, 4.40)
        self.lithium_bms_min_cell_voltage_spin.setDecimals(2)
        self.lithium_bms_min_cell_voltage_spin.setSingleStep(0.01)
        self.lithium_bms_min_cell_voltage_spin.setValue(3.40)
        layout.addWidget(self.lithium_bms_min_cell_voltage_spin, 6, 1)

        return widget

    def connect_lithium_bms_status_signals(self):
        """连接一线通锂电池 BMS 协议状态信号。"""
        self.lithium_bms_alarm_enable_cb.toggled.connect(self.update_current_frame_display)
        self.lithium_bms_high_temp_alarm_cb.toggled.connect(self.update_current_frame_display)
        self.lithium_bms_low_temp_alarm_cb.toggled.connect(self.update_current_frame_display)
        self.lithium_bms_soh_low_cb.toggled.connect(self.update_current_frame_display)
        self.lithium_bms_mos_fault_cb.toggled.connect(self.update_current_frame_display)
        self.lithium_bms_short_circuit_fault_cb.toggled.connect(self.update_current_frame_display)
        self.lithium_bms_max_cell_voltage_spin.valueChanged.connect(self.update_current_frame_display)
        self.lithium_bms_soc_spin.valueChanged.connect(self.update_current_frame_display)
        self.lithium_bms_total_voltage_spin.valueChanged.connect(self.update_current_frame_display)
        self.lithium_bms_max_temp_spin.valueChanged.connect(self.update_current_frame_display)
        self.lithium_bms_min_temp_spin.valueChanged.connect(self.update_current_frame_display)
        self.lithium_bms_cycle_count_spin.valueChanged.connect(self.update_current_frame_display)
        self.lithium_bms_min_cell_voltage_spin.valueChanged.connect(self.update_current_frame_display)

    def load_lithium_bms_preset_scenario(self, scenario_id):
        """加载一线通锂电池 BMS 协议预设场景。"""
        if scenario_id == 0:
            self.current_status = PresetScenarios.lithium_bms_normal_running()
        elif scenario_id == 1:
            self.current_status = PresetScenarios.lithium_bms_energy_recovery()
        elif scenario_id == 2:
            self.current_status = PresetScenarios.lithium_bms_fault_scenario()
        else:
            self.current_status = StatusBits(protocol_name=PROTOCOL_LITHIUM_BMS)

        self.update_lithium_bms_ui_from_status()

    def update_lithium_bms_ui_from_status(self):
        """根据一线通锂电池 BMS 协议状态更新 UI。"""
        if not hasattr(self, 'current_status') or not isinstance(self.current_status, StatusBits):
            return

        status = self.current_status

        if hasattr(self, 'lithium_bms_alarm_enable_cb'):
            self.lithium_bms_alarm_enable_cb.setChecked(
                getattr(status, 'lithium_bms_alarm_enable', False)
            )
        if hasattr(self, 'lithium_bms_high_temp_alarm_cb'):
            self.lithium_bms_high_temp_alarm_cb.setChecked(
                getattr(status, 'lithium_bms_high_temp_alarm', False)
            )
        if hasattr(self, 'lithium_bms_low_temp_alarm_cb'):
            self.lithium_bms_low_temp_alarm_cb.setChecked(
                getattr(status, 'lithium_bms_low_temp_alarm', False)
            )
        if hasattr(self, 'lithium_bms_soh_low_cb'):
            self.lithium_bms_soh_low_cb.setChecked(getattr(status, 'lithium_bms_soh_low', False))
        if hasattr(self, 'lithium_bms_mos_fault_cb'):
            self.lithium_bms_mos_fault_cb.setChecked(
                getattr(status, 'lithium_bms_mos_fault', False)
            )
        if hasattr(self, 'lithium_bms_short_circuit_fault_cb'):
            self.lithium_bms_short_circuit_fault_cb.setChecked(
                getattr(status, 'lithium_bms_short_circuit_fault', False)
            )

        if hasattr(self, 'lithium_bms_max_cell_voltage_spin'):
            self.lithium_bms_max_cell_voltage_spin.setValue(
                getattr(status, 'lithium_bms_max_cell_voltage_v', 3.60)
            )
        if hasattr(self, 'lithium_bms_soc_spin'):
            self.lithium_bms_soc_spin.setValue(getattr(status, 'soc_percent', 0))
        if hasattr(self, 'lithium_bms_total_voltage_spin'):
            self.lithium_bms_total_voltage_spin.setValue(
                int(round(getattr(status, 'lithium_bms_total_voltage_v', 48.0)))
            )
        if hasattr(self, 'lithium_bms_max_temp_spin'):
            self.lithium_bms_max_temp_spin.setValue(
                getattr(status, 'lithium_bms_max_temp_c', 25)
            )
        if hasattr(self, 'lithium_bms_min_temp_spin'):
            self.lithium_bms_min_temp_spin.setValue(
                getattr(status, 'lithium_bms_min_temp_c', 20)
            )
        if hasattr(self, 'lithium_bms_cycle_count_spin'):
            self.lithium_bms_cycle_count_spin.setValue(
                getattr(status, 'lithium_bms_cycle_count', 0)
            )
        if hasattr(self, 'lithium_bms_min_cell_voltage_spin'):
            self.lithium_bms_min_cell_voltage_spin.setValue(
                getattr(status, 'lithium_bms_min_cell_voltage_v', 3.40)
            )

    def get_lithium_bms_status_from_ui(self) -> StatusBits:
        """从 UI 获取一线通锂电池 BMS 协议配置。"""
        status = StatusBits()
        status.protocol_name = PROTOCOL_LITHIUM_BMS

        status.lithium_bms_alarm_enable = self.lithium_bms_alarm_enable_cb.isChecked()
        status.lithium_bms_high_temp_alarm = self.lithium_bms_high_temp_alarm_cb.isChecked()
        status.lithium_bms_low_temp_alarm = self.lithium_bms_low_temp_alarm_cb.isChecked()
        status.lithium_bms_soh_low = self.lithium_bms_soh_low_cb.isChecked()
        status.lithium_bms_mos_fault = self.lithium_bms_mos_fault_cb.isChecked()
        status.lithium_bms_short_circuit_fault = (
            self.lithium_bms_short_circuit_fault_cb.isChecked()
        )

        status.lithium_bms_max_cell_voltage_v = self.lithium_bms_max_cell_voltage_spin.value()
        status.soc_percent = self.lithium_bms_soc_spin.value()
        status.lithium_bms_total_voltage_v = self.lithium_bms_total_voltage_spin.value()
        status.lithium_bms_max_temp_c = self.lithium_bms_max_temp_spin.value()
        status.lithium_bms_min_temp_c = self.lithium_bms_min_temp_spin.value()
        status.lithium_bms_cycle_count = self.lithium_bms_cycle_count_spin.value()
        status.lithium_bms_min_cell_voltage_v = self.lithium_bms_min_cell_voltage_spin.value()

        return status
