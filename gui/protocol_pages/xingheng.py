#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""星恒智能BMS专属参数页；沿用原发送按钮，不包含加密或自动混合调度。"""

from dataclasses import replace

from PyQt5.QtWidgets import QComboBox, QDoubleSpinBox, QGridLayout, QLabel, QSpinBox, QWidget

from protocol.definitions import PROTOCOL_XINGHENG_BMS
from protocol.models import StatusBits
from protocol.presets import PresetScenarios
from protocol.xingheng import (
    XINGHENG_COMMON_FIELDS, XINGHENG_PUBLIC, XINGHENG_PUBLIC_FIELDS,
    XINGHENG_RAW_FIELDS, XINGHENG_REALTIME, XINGHENG_REALTIME_FIELDS,
    XINGHENG_VERSION_FIELD, xingheng_frame_length,
)


class XinghengBmsPages:
    """仅在当前协议构建控件，类型变化停发，物理量变化供后续循环动态读取。"""

    def switch_to_xingheng_bms_protocol(self):
        """默认选择客户实际使用的3A格式，保持切换协议时的原停止逻辑。"""
        self.current_status = PresetScenarios.xingheng_bms_normal_running()
        self.show_xingheng_bms_status_config()
        self.normal_radio.setChecked(True)
        self.on_scenario_changed()

    def show_xingheng_bms_status_config(self):
        """按报文类型建立独立滚动参数页，不修改主窗口布局和其他协议控件。"""
        self._xingheng_loading = True
        try:
            self._clear_status_tabs()
            self.xingheng_controls = {}
            common = self._create_xingheng_form(XINGHENG_COMMON_FIELDS, with_message_type=True)
            self.status_tabs.addTab(common, "电池数据")
            if self.current_status.xingheng_message_id == XINGHENG_PUBLIC:
                self.status_tabs.addTab(self._create_xingheng_form(XINGHENG_PUBLIC_FIELDS + (XINGHENG_VERSION_FIELD,)), "电池信息")
            else:
                self.status_tabs.addTab(self._create_xingheng_form(XINGHENG_REALTIME_FIELDS), "实时扩展")
                self.status_tabs.addTab(self._create_xingheng_form((XINGHENG_VERSION_FIELD,) + XINGHENG_RAW_FIELDS), "原始字段")
            self._compact_status_tab_pages()
        finally:
            self._xingheng_loading = False

    def _create_xingheng_form(self, specs, with_message_type=False):
        """共享字段定义驱动三列表单，按实际精度输入，原始字节以十六进制显示。"""
        widget = QWidget()
        widget.setProperty("formColumns", True)
        layout = QGridLayout(widget)
        row_offset = 0
        if with_message_type:
            layout.addWidget(QLabel("报文类型"), 0, 0)
            self.xingheng_message_combo = QComboBox()
            self.xingheng_message_combo.addItem("0x3A 实时信息 · 未加密 · 31字节", XINGHENG_REALTIME)
            self.xingheng_message_combo.addItem("0x01 公有报文 · 20字节", XINGHENG_PUBLIC)
            self.xingheng_message_combo.setCurrentIndex(self.xingheng_message_combo.findData(self.current_status.xingheng_message_id))
            self.xingheng_message_combo.currentIndexChanged.connect(self.on_xingheng_message_changed)
            layout.addWidget(self.xingheng_message_combo, 0, 1, 1, 2)
            row_offset = 1
        for index, spec in enumerate(specs):
            row, column = row_offset + (index // 3) * 2, index % 3
            layout.addWidget(QLabel(spec.label), row, column)
            control = QSpinBox() if spec.step == 1 else QDoubleSpinBox()
            if isinstance(control, QDoubleSpinBox):
                control.setDecimals(1)
            if spec.hexadecimal:
                control.setDisplayIntegerBase(16)
                control.setPrefix("0x")
            control.setRange(spec.minimum, spec.maximum)
            control.setSingleStep(spec.step)
            control.setValue(getattr(self.current_status, "xingheng_" + spec.name))
            control.setObjectName("xingheng_" + spec.name)
            control.setMinimumWidth(90)
            hints = {
                "work_state": "0：放电；1：充电；2：回馈",
                "response_device": "0：不需要；1：充电器；2：ECU；3：TBOX；写入D5～D7",
                "charge_state": "0：保留；1：满充停止；2：非法充电；3：保护；4：正在充电",
                "fault_code": "按表A.4原始故障码；含0x14/0x15报警及0x22～0x29预警，不按十进制25截断",
                "current_a": "0.1A/bit，偏移-500A；0A编码为88 13，不使用符号原码",
                "charge_current_a": "8位、0.1A/bit；FA表示25A，FF无效；250A无法编码",
                "regen_current_a": "8位、0.1A/bit；FF无效，不将超范围数据取模",
                "bms_status_raw": "文档标注需解码；只透传原始字节，不提供已解密状态解释",
                "key_raw": "保持手填原始值，不生成随机数或加密结果",
                "result0_raw": "客户截图原始值2F；更改数据不会重新生成该字节",
                "result1_raw": "客户截图原始值9E；不保证新数据通过接收端验密",
                "version": "默认沿用客户截图13；主、次版本均不能为F",
            }
            control.setToolTip(hints.get(spec.name, f"{spec.minimum}～{spec.maximum}；步进{spec.step}；FF/FFFF等无效值请使用全部自定义帧测试"))
            control.valueChanged.connect(self.on_xingheng_value_changed)
            self.xingheng_controls[spec.name] = control
            layout.addWidget(control, row + 1, column)
        if with_message_type:
            note = QLabel("未实现加密 · UART测试；转码驱动暂未适配")
            note.setProperty("muted", True)
            note.setWordWrap(True)
            note.setToolTip("公有和31字节实时帧可单次/循环测试；不模拟上拉接入、启动3帧、互认或60秒混合调度。单线时序须由后续转码固件实现；原始保护字段不随数据变化重算。")
            self.xingheng_protocol_note = note
            layout.addWidget(note, row_offset + ((len(specs) + 2) // 3) * 2, 0, 1, 3)
        for column in range(3):
            layout.setColumnStretch(column, 1)
        return widget

    def get_xingheng_status_from_ui(self):
        """仅在界面线程读取本协议控件，隐藏格式的参数保留原值。"""
        values = {"xingheng_" + name: control.value() for name, control in self.xingheng_controls.items()}
        values["xingheng_message_id"] = self.xingheng_message_combo.currentData()
        return replace(self.current_status, protocol_name=PROTOCOL_XINGHENG_BMS, **values)

    def on_xingheng_value_changed(self, *_):
        """同步当前状态后再预览，确保转入原始帧模式也使用最后修改的数据。"""
        if self.current_protocol != PROTOCOL_XINGHENG_BMS or self._xingheng_loading:
            return
        self.current_status = self.get_xingheng_status_from_ui()
        self.update_current_frame_display()

    def on_xingheng_message_changed(self, *_):
        """20/31字节格式切换先停止旧循环，不向原长度回调提交另一种帧。"""
        if self.current_protocol != PROTOCOL_XINGHENG_BMS or self._xingheng_loading:
            return
        self.current_status = self.get_xingheng_status_from_ui()
        if self.serial_manager.is_cyclic_sending():
            self.serial_manager.stop_cyclic_send()
            self._reset_send_action_buttons()
            self.send_status.setText("就绪")
        self.custom_frame_data = None
        self.show_xingheng_bms_status_config()
        self._refresh_parameter_mode()
        self.update_current_frame_display()

    def update_xingheng_bms_ui_from_status(self):
        """恢复配置时抑制回调，不自动连接或发送，不将导入值覆盖为默认值。"""
        if not isinstance(getattr(self, "current_status", None), StatusBits):
            return
        if self.xingheng_message_combo.currentData() != self.current_status.xingheng_message_id:
            self.show_xingheng_bms_status_config()
            return
        self._xingheng_loading = True
        try:
            for name, control in self.xingheng_controls.items():
                control.setValue(getattr(self.current_status, "xingheng_" + name))
        finally:
            self._xingheng_loading = False

    def load_xingheng_bms_preset_scenario(self, scenario_id):
        """复用三个场景入口并保留已选类型，不引入自动报文调度。"""
        message_id = self.current_status.xingheng_message_id
        factories = (PresetScenarios.xingheng_bms_normal_running,
                     PresetScenarios.xingheng_bms_energy_recovery,
                     PresetScenarios.xingheng_bms_fault_scenario)
        self.current_status = factories[scenario_id]() if scenario_id in (0, 1, 2) else StatusBits(protocol_name=PROTOCOL_XINGHENG_BMS)
        self.current_status.xingheng_message_id = message_id
        self.update_xingheng_bms_ui_from_status()

    def xingheng_selected_packet_frames(self, frames):
        """按当前格式取包组，配置可保留两种长度，但不混在同一循环发送。"""
        length = xingheng_frame_length(self.current_status.xingheng_message_id)
        return [frame.copy() for frame in (frames or []) if len(frame) == length]

    def store_xingheng_packet_frames(self, frames):
        """编辑一种类型的包组不删除另一类型已保存的测试帧。"""
        length = xingheng_frame_length(self.current_status.xingheng_message_id)
        others = [frame.copy() for frame in self.packet_sequence_frames.get(PROTOCOL_XINGHENG_BMS, []) if len(frame) != length]
        self.packet_sequence_frames[PROTOCOL_XINGHENG_BMS] = others + [frame.copy() for frame in frames]
