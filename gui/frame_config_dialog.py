#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
协议帧详细配置窗口
提供字节级和位级的协议帧编辑功能。
"""

from typing import List

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QCheckBox,
    QDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)


class ByteEditor(QFrame):
    """单个字节编辑器。"""

    valueChanged = pyqtSignal(int, int)

    def __init__(self, byte_index: int, byte_value: int = 0, description: str = ""):
        super().__init__()
        self.byte_index = byte_index
        self.init_ui(byte_value, description)

    def init_ui(self, byte_value: int, description: str):
        layout = QVBoxLayout()
        layout.setSpacing(5)

        title_label = QLabel(f"DATA{self.byte_index}")
        title_label.setFont(QFont("Arial", 10, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)

        if description:
            desc_label = QLabel(description)
            desc_label.setFont(QFont("Arial", 8))
            desc_label.setWordWrap(True)
            desc_label.setAlignment(Qt.AlignCenter)
            layout.addWidget(desc_label)

        hex_layout = QHBoxLayout()
        hex_layout.addWidget(QLabel("HEX:"))
        self.hex_edit = QLineEdit()
        self.hex_edit.setMaxLength(2)
        self.hex_edit.setFixedWidth(40)
        self.hex_edit.setText(f"{byte_value:02X}")
        self.hex_edit.textChanged.connect(self.on_hex_changed)
        hex_layout.addWidget(self.hex_edit)
        layout.addLayout(hex_layout)

        dec_layout = QHBoxLayout()
        dec_layout.addWidget(QLabel("DEC:"))
        self.dec_label = QLabel(str(byte_value))
        self.dec_label.setFixedWidth(40)
        self.dec_label.setAlignment(Qt.AlignCenter)
        dec_layout.addWidget(self.dec_label)
        layout.addLayout(dec_layout)

        bits_group = QGroupBox("位配置")
        bits_layout = QGridLayout()
        self.bit_checkboxes = []
        for i in range(8):
            bit_cb = QCheckBox(f"D{7 - i}")
            bit_cb.setChecked((byte_value >> (7 - i)) & 1)
            bit_cb.toggled.connect(self.on_bit_changed)
            bits_layout.addWidget(bit_cb, 0, i)
            self.bit_checkboxes.append(bit_cb)
        bits_group.setLayout(bits_layout)
        layout.addWidget(bits_group)

        self.setLayout(layout)
        self.setFrameStyle(QFrame.Box)
        self.setLineWidth(1)

    def on_hex_changed(self):
        """十六进制值变化时，同步十进制和位视图。"""
        try:
            hex_text = self.hex_edit.text().upper()
            if not hex_text:
                return

            value = int(hex_text, 16)
            if value > 255:
                value = 255
                self.hex_edit.setText("FF")

            self.dec_label.setText(str(value))
            for i, cb in enumerate(self.bit_checkboxes):
                cb.blockSignals(True)
                cb.setChecked((value >> (7 - i)) & 1)
                cb.blockSignals(False)

            self.valueChanged.emit(self.byte_index, value)
        except ValueError:
            pass

    def on_bit_changed(self):
        """位变化时，同步十六进制和十进制视图。"""
        value = 0
        for i, cb in enumerate(self.bit_checkboxes):
            if cb.isChecked():
                value |= 1 << (7 - i)

        self.hex_edit.blockSignals(True)
        self.hex_edit.setText(f"{value:02X}")
        self.hex_edit.blockSignals(False)
        self.dec_label.setText(str(value))
        self.valueChanged.emit(self.byte_index, value)

    def set_value(self, value: int):
        """设置字节值。"""
        value = max(0, min(255, value))
        self.hex_edit.blockSignals(True)
        self.hex_edit.setText(f"{value:02X}")
        self.hex_edit.blockSignals(False)
        self.dec_label.setText(str(value))

        for i, cb in enumerate(self.bit_checkboxes):
            cb.blockSignals(True)
            cb.setChecked((value >> (7 - i)) & 1)
            cb.blockSignals(False)

    def get_value(self) -> int:
        """获取当前字节值。"""
        try:
            return int(self.hex_edit.text(), 16)
        except ValueError:
            return 0


class FrameConfigDialog(QDialog):
    """协议帧详细配置窗口。"""

    frameChanged = pyqtSignal(list)

    def __init__(
        self,
        parent=None,
        initial_frame: List[int] = None,
        byte_descriptions: List[str] = None,
        dialog_title: str = None,
        checksum_mode: str = "xor",
    ):
        super().__init__(parent)
        frame_length = len(initial_frame) if initial_frame is not None else len(byte_descriptions or [])
        if frame_length <= 0:
            frame_length = 12

        self.frame_data = (initial_frame or ([0] * frame_length)).copy()
        self.byte_descriptions = byte_descriptions or self.default_byte_descriptions(frame_length)
        self.dialog_title = dialog_title or "协议帧详细配置"
        self.checksum_mode = checksum_mode
        self.byte_editors = []

        self.init_ui()
        self.update_frame_display()

    def default_byte_descriptions(self, frame_length: int = 12) -> List[str]:
        """默认字节描述。"""
        defaults = [
            "设备编码",
            "流水号",
            "Status1",
            "Status2",
            "Status3",
            "Status4",
            "Status5",
            "Status6",
            "Status7",
            "Status8",
            "Status9",
            "校验和(自动计算)",
        ]
        if frame_length <= len(defaults):
            return defaults[:frame_length]

        descriptions = defaults[:-1]
        while len(descriptions) < frame_length - 1:
            descriptions.append(f"DATA{len(descriptions)}")
        descriptions.append("校验和(自动计算)")
        return descriptions

    def calculate_checksum(self, payload: List[int]) -> int:
        """根据配置的校验模式计算校验值。"""
        if self.checksum_mode == "sum":
            return sum(payload) & 0xFF

        checksum = 0
        for value in payload:
            checksum ^= value
        return checksum & 0xFF

    def init_ui(self):
        self.setWindowTitle(self.dialog_title)
        self.setModal(True)
        self.resize(900, 800)

        layout = QVBoxLayout()
        tab_widget = QTabWidget()
        tab_widget.addTab(self.create_byte_editor_tab(), "字节编辑")
        tab_widget.addTab(self.create_preview_tab(), "帧预览")
        layout.addWidget(tab_widget)

        button_layout = QHBoxLayout()
        self.reset_btn = QPushButton("重置")
        self.reset_btn.clicked.connect(self.reset_frame)
        self.apply_btn = QPushButton("应用")
        self.apply_btn.clicked.connect(self.apply_changes)
        self.ok_btn = QPushButton("确定")
        self.ok_btn.clicked.connect(self.accept)
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self.reject)

        button_layout.addWidget(self.reset_btn)
        button_layout.addStretch()
        button_layout.addWidget(self.apply_btn)
        button_layout.addWidget(self.ok_btn)
        button_layout.addWidget(self.cancel_btn)
        layout.addLayout(button_layout)

        self.setLayout(layout)

    def create_byte_editor_tab(self) -> QWidget:
        """创建字节编辑页。"""
        widget = QWidget()
        layout = QVBoxLayout()

        scroll = QScrollArea()
        scroll_widget = QWidget()
        scroll_layout = QGridLayout()

        editor_count = len(self.frame_data)
        left_column_count = (editor_count + 1) // 2

        for i in range(editor_count):
            description = self.byte_descriptions[i] if i < len(self.byte_descriptions) else ""
            editor = ByteEditor(i, self.frame_data[i], description)
            editor.valueChanged.connect(self.on_byte_changed)
            self.byte_editors.append(editor)

            if i < left_column_count:
                row = i
                col = 0
            else:
                row = i - left_column_count
                col = 1
            scroll_layout.addWidget(editor, row, col)

        scroll_layout.setColumnStretch(0, 1)
        scroll_layout.setColumnStretch(1, 1)
        scroll_widget.setLayout(scroll_layout)
        scroll.setWidget(scroll_widget)
        scroll.setWidgetResizable(True)

        layout.addWidget(scroll)
        widget.setLayout(layout)
        return widget

    def create_preview_tab(self) -> QWidget:
        """创建帧预览页。"""
        widget = QWidget()
        layout = QVBoxLayout()

        frame_group = QGroupBox("完整帧数据")
        frame_layout = QVBoxLayout()
        self.frame_hex_label = QLabel()
        self.frame_hex_label.setFont(QFont("Courier", 10))
        self.frame_hex_label.setWordWrap(True)
        frame_layout.addWidget(self.frame_hex_label)

        self.frame_dec_label = QLabel()
        self.frame_dec_label.setFont(QFont("Courier", 10))
        self.frame_dec_label.setWordWrap(True)
        frame_layout.addWidget(self.frame_dec_label)
        frame_group.setLayout(frame_layout)
        layout.addWidget(frame_group)

        checksum_group = QGroupBox("校验信息")
        checksum_layout = QVBoxLayout()
        self.checksum_label = QLabel()
        self.checksum_label.setFont(QFont("Arial", 10))
        checksum_layout.addWidget(self.checksum_label)
        checksum_group.setLayout(checksum_layout)
        layout.addWidget(checksum_group)

        layout.addStretch()
        widget.setLayout(layout)
        return widget

    def on_byte_changed(self, byte_index: int, new_value: int):
        """字节值变化处理。"""
        self.frame_data[byte_index] = new_value

        checksum_index = len(self.frame_data) - 1
        if byte_index != checksum_index:
            checksum = self.calculate_checksum(self.frame_data[:checksum_index])
            self.frame_data[checksum_index] = checksum
            self.byte_editors[checksum_index].set_value(checksum)

        self.update_frame_display()
        self.frameChanged.emit(self.frame_data.copy())

    def update_frame_display(self):
        """更新帧显示。"""
        hex_str = " ".join(f"{b:02X}" for b in self.frame_data)
        self.frame_hex_label.setText(f"HEX: {hex_str}")

        dec_str = " ".join(f"{b:3d}" for b in self.frame_data)
        self.frame_dec_label.setText(f"DEC: {dec_str}")

        checksum_index = len(self.frame_data) - 1
        calculated_checksum = self.calculate_checksum(self.frame_data[:checksum_index])
        checksum_valid = calculated_checksum == self.frame_data[checksum_index]
        checksum_name = "累加和" if self.checksum_mode == "sum" else "异或校验"
        checksum_status = "正确" if checksum_valid else "错误"

        self.checksum_label.setText(
            f"校验方式: {checksum_name}\n"
            f"计算校验和: 0x{calculated_checksum:02X} ({calculated_checksum})\n"
            f"当前校验和: 0x{self.frame_data[checksum_index]:02X} ({self.frame_data[checksum_index]})\n"
            f"校验状态: {checksum_status}"
        )

    def reset_frame(self):
        """重置帧数据。"""
        self.frame_data = [0] * len(self.frame_data)
        for editor in self.byte_editors:
            editor.set_value(0)

        if self.frame_data:
            checksum_index = len(self.frame_data) - 1
            checksum = self.calculate_checksum(self.frame_data[:checksum_index])
            self.frame_data[checksum_index] = checksum
            self.byte_editors[checksum_index].set_value(checksum)

        self.update_frame_display()

    def apply_changes(self):
        """应用修改。"""
        self.frameChanged.emit(self.frame_data.copy())

    def set_frame_data(self, frame_data: List[int]):
        """设置帧数据。"""
        self.frame_data = frame_data.copy()
        for i, editor in enumerate(self.byte_editors):
            if i < len(frame_data):
                editor.set_value(frame_data[i])
        self.update_frame_display()

    def get_frame_data(self) -> List[int]:
        """获取当前帧数据。"""
        return self.frame_data.copy()
