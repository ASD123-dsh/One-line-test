#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""锂神单线 BMS 配置页与状态绑定，不负责串口和单线波形生成。"""

from PyQt5.QtWidgets import QGridLayout, QLabel, QSpinBox, QWidget

from protocol.protocol_handler import PROTOCOL_LISHEN_BMS, PresetScenarios, StatusBits


class LishenBmsPages:
    """仅显示规格书定义的 SOC、总压和温度，保留位不提供编辑控件。"""

    def switch_to_lishen_bms_protocol(self):
        """切换到锂神协议并加载合法的正常预设。"""
        self.current_status = PresetScenarios.lishen_bms_normal_running()
        self.show_lishen_bms_status_config()
        self.normal_radio.setChecked(True)
        self.on_scenario_changed()

    def show_lishen_bms_status_config(self):
        """销毁旧配置页，再建立独立的锂神电池数据页。"""
        self._clear_status_tabs()
        self.status_tabs.addTab(self.create_lishen_bms_data_tab(), "电池数据")
        self._compact_status_tab_pages()
        for control in (
            self.lishen_soc_spin,
            self.lishen_total_voltage_spin,
            self.lishen_temperature_spin,
        ):
            control.valueChanged.connect(self.update_current_frame_display)

    def create_lishen_bms_data_tab(self) -> QWidget:
        """按字节实际量程建立整数输入，不借用其他 BMS 的比例或温度编码。"""
        widget = QWidget()
        widget.setProperty("formColumns", True)
        layout = QGridLayout(widget)

        # 对齐参考图：三列字段的名称置于输入框上方，量程和绑定保持原样。
        layout.addWidget(QLabel("SOC (%):"), 0, 0)
        self.lishen_soc_spin = QSpinBox()
        self.lishen_soc_spin.setRange(0, 100)
        self.lishen_soc_spin.setValue(self.current_status.soc_percent)
        layout.addWidget(self.lishen_soc_spin, 1, 0)

        layout.addWidget(QLabel("总电压 (V):"), 0, 1)
        self.lishen_total_voltage_spin = QSpinBox()
        self.lishen_total_voltage_spin.setRange(0, 255)
        self.lishen_total_voltage_spin.setValue(self.current_status.lishen_total_voltage_v)
        self.lishen_total_voltage_spin.setToolTip("1V/bit；0～255V 是字节编码量程，不代表电池额定范围")
        layout.addWidget(self.lishen_total_voltage_spin, 1, 1)

        layout.addWidget(QLabel("电池温度 (℃):"), 0, 2)
        self.lishen_temperature_spin = QSpinBox()
        self.lishen_temperature_spin.setRange(-128, 127)
        self.lishen_temperature_spin.setValue(self.current_status.lishen_temperature_c)
        self.lishen_temperature_spin.setToolTip("1℃/bit，有符号8位补码；例如 -10℃ = 0xF6")
        layout.addWidget(self.lishen_temperature_spin, 1, 2)
        for control in (self.lishen_soc_spin, self.lishen_total_voltage_spin, self.lishen_temperature_spin):
            control.setMinimumWidth(90)
        for column in range(3):
            layout.setColumnStretch(column, 1)

        self.lishen_protocol_note = QLabel(
            "Byte1 / Byte5 固定 00 · 累加校验\n"
            "规格建议 1000～2000ms；测试范围 10～5000ms。\n"
            "本协议无回收或故障标志，预设仅提供测试数据。"
        )
        self.lishen_protocol_note.setProperty("muted", True)
        self.lishen_protocol_note.setToolTip(
            "自动生成帧的 Byte1/Byte5 固定为 00；校验为前5字节累加和低8位。\n"
            "偏离规格建议周期仅供测试，单线时序仍由转码平台实现。\n"
            "本协议无回收/故障标志；对应预设仅改变三项测试数据。"
        )
        self.lishen_protocol_note.setWordWrap(True)
        layout.addWidget(self.lishen_protocol_note, 2, 0, 1, 3)
        return widget

    def load_lishen_bms_preset_scenario(self, scenario_id):
        """复用三类场景入口，但只改变锂神协议定义的数据字段。"""
        factories = (
            PresetScenarios.lishen_bms_normal_running,
            PresetScenarios.lishen_bms_energy_recovery,
            PresetScenarios.lishen_bms_fault_scenario,
        )
        if scenario_id in (0, 1, 2):
            self.current_status = factories[scenario_id]()
        else:
            self.current_status = StatusBits(protocol_name=PROTOCOL_LISHEN_BMS)
        self.update_lishen_bms_ui_from_status()

    def update_lishen_bms_ui_from_status(self):
        """恢复配置或场景中的三项数据，不自动连接或发送。"""
        if not isinstance(getattr(self, "current_status", None), StatusBits):
            return
        self.lishen_soc_spin.setValue(self.current_status.soc_percent)
        self.lishen_total_voltage_spin.setValue(self.current_status.lishen_total_voltage_v)
        self.lishen_temperature_spin.setValue(self.current_status.lishen_temperature_c)

    def get_lishen_bms_status_from_ui(self) -> StatusBits:
        """在界面线程读取当前数据，供实时预览和循环发送生成独立帧。"""
        return StatusBits(
            protocol_name=PROTOCOL_LISHEN_BMS,
            soc_percent=self.lishen_soc_spin.value(),
            lishen_total_voltage_v=self.lishen_total_voltage_spin.value(),
            lishen_temperature_c=self.lishen_temperature_spin.value(),
        )
