#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""battery 协议配置页及状态绑定；不负责串口和升级。"""

from PyQt5.QtWidgets import (
    QWidget,
    QGridLayout,
    QLabel,
    QSpinBox,
)
from protocol.protocol_handler import (
    PROTOCOL_BATTERY_SINGLE_WIRE,
    PresetScenarios,
    StatusBits,
)


class BatterySingleWirePages:
    """作为主窗口的界面组件，沿用现有控件名称和槽函数。"""

    def switch_to_battery_single_wire_protocol(self):
        """切换到电池单线通讯协议"""
        self.current_status = PresetScenarios.battery_single_wire_normal_running()
        self.show_battery_single_wire_status_config()
        self.normal_radio.setChecked(True)
        self.on_scenario_changed()

    def show_battery_single_wire_status_config(self):
        """显示电池单线通讯协议配置界面。"""
        self._clear_status_tabs()
        self.status_tabs.addTab(self.create_battery_single_wire_data_tab(), "电池数据")
        self._compact_status_tab_pages()
        self.connect_battery_single_wire_status_signals()

    def create_battery_single_wire_data_tab(self) -> QWidget:
        """创建电池单线通讯协议数据页。"""
        widget = QWidget()
        layout = QGridLayout(widget)

        layout.addWidget(QLabel("电池剩余容量 SOC (%):"), 0, 0)
        self.battery_single_wire_soc_spin = QSpinBox()
        self.battery_single_wire_soc_spin.setRange(0, 100)
        self.battery_single_wire_soc_spin.setValue(80)
        layout.addWidget(self.battery_single_wire_soc_spin, 0, 1)

        return widget

    def connect_battery_single_wire_status_signals(self):
        """连接电池单线通讯协议控件信号。"""
        self.battery_single_wire_soc_spin.valueChanged.connect(self.update_current_frame_display)

    def load_battery_single_wire_preset_scenario(self, scenario_id):
        """加载电池单线通讯协议预设场景。"""
        if scenario_id == 0:
            self.current_status = PresetScenarios.battery_single_wire_normal_running()
        elif scenario_id == 1:
            self.current_status = PresetScenarios.battery_single_wire_energy_recovery()
        elif scenario_id == 2:
            self.current_status = PresetScenarios.battery_single_wire_fault_scenario()
        else:
            self.current_status = StatusBits(protocol_name=PROTOCOL_BATTERY_SINGLE_WIRE)

        self.update_battery_single_wire_ui_from_status()

    def update_battery_single_wire_ui_from_status(self):
        """根据电池单线通讯协议状态更新 UI。"""
        if not hasattr(self, 'current_status') or not isinstance(self.current_status, StatusBits):
            return

        if hasattr(self, 'battery_single_wire_soc_spin'):
            self.battery_single_wire_soc_spin.setValue(
                getattr(self.current_status, 'soc_percent', 0)
            )

    def get_battery_single_wire_status_from_ui(self) -> StatusBits:
        """从 UI 获取电池单线通讯协议配置。"""
        status = StatusBits()
        status.protocol_name = PROTOCOL_BATTERY_SINGLE_WIRE
        status.soc_percent = self.battery_single_wire_soc_spin.value()
        return status
