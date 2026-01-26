#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
协议帧详细配置窗口

提供字节级和位级的协议帧数据编辑功能
支持手动修改每个字节的每一位数据
"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox,
    QLabel, QSpinBox, QCheckBox, QPushButton, QScrollArea,
    QWidget, QFrame, QLineEdit, QMessageBox, QTabWidget
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont, QPalette, QColor
from typing import List, Dict


class ByteEditor(QFrame):
    """单个字节编辑器"""
    
    valueChanged = pyqtSignal(int, int)  # (byte_index, new_value)
    
    def __init__(self, byte_index: int, byte_value: int = 0, description: str = ""):
        super().__init__()
        self.byte_index = byte_index
        self.init_ui(byte_value, description)
        
    def init_ui(self, byte_value: int, description: str):
        layout = QVBoxLayout()
        layout.setSpacing(5)
        
        # 字节标题
        title_label = QLabel(f"DATA{self.byte_index}")
        title_label.setFont(QFont("Arial", 10, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        
        # 描述
        if description:
            desc_label = QLabel(description)
            desc_label.setFont(QFont("Arial", 8))
            desc_label.setWordWrap(True)
            desc_label.setAlignment(Qt.AlignCenter)
            layout.addWidget(desc_label)
        
        # 十六进制值输入
        hex_layout = QHBoxLayout()
        hex_label = QLabel("HEX:")
        self.hex_edit = QLineEdit()
        self.hex_edit.setMaxLength(2)
        self.hex_edit.setFixedWidth(40)
        self.hex_edit.setText(f"{byte_value:02X}")
        self.hex_edit.textChanged.connect(self.on_hex_changed)
        hex_layout.addWidget(hex_label)
        hex_layout.addWidget(self.hex_edit)
        layout.addLayout(hex_layout)
        
        # 十进制值显示
        dec_layout = QHBoxLayout()
        dec_label = QLabel("DEC:")
        self.dec_label = QLabel(str(byte_value))
        self.dec_label.setFixedWidth(40)
        self.dec_label.setAlignment(Qt.AlignCenter)
        dec_layout.addWidget(dec_label)
        dec_layout.addWidget(self.dec_label)
        layout.addLayout(dec_layout)
        
        # 位编辑器
        bits_group = QGroupBox("位配置")
        bits_layout = QGridLayout()
        
        self.bit_checkboxes = []
        for i in range(8):
            bit_cb = QCheckBox(f"D{7-i}")
            bit_cb.setChecked((byte_value >> (7-i)) & 1)
            bit_cb.toggled.connect(self.on_bit_changed)
            bits_layout.addWidget(bit_cb, 0, i)
            self.bit_checkboxes.append(bit_cb)
        
        bits_group.setLayout(bits_layout)
        layout.addWidget(bits_group)
        
        self.setLayout(layout)
        
        # 设置样式
        self.setFrameStyle(QFrame.Box)
        self.setLineWidth(1)
        
    def on_hex_changed(self):
        """十六进制值改变时更新其他显示"""
        try:
            hex_text = self.hex_edit.text().upper()
            if len(hex_text) == 0:
                return
            
            value = int(hex_text, 16)
            if value > 255:
                value = 255
                self.hex_edit.setText("FF")
            
            # 更新十进制显示
            self.dec_label.setText(str(value))
            
            # 更新位显示
            for i, cb in enumerate(self.bit_checkboxes):
                cb.blockSignals(True)
                cb.setChecked((value >> (7-i)) & 1)
                cb.blockSignals(False)
            
            # 发送信号
            self.valueChanged.emit(self.byte_index, value)
            
        except ValueError:
            pass
    
    def on_bit_changed(self):
        """位值改变时更新其他显示"""
        value = 0
        for i, cb in enumerate(self.bit_checkboxes):
            if cb.isChecked():
                value |= (1 << (7-i))
        
        # 更新十六进制和十进制显示
        self.hex_edit.blockSignals(True)
        self.hex_edit.setText(f"{value:02X}")
        self.hex_edit.blockSignals(False)
        
        self.dec_label.setText(str(value))
        
        # 发送信号
        self.valueChanged.emit(self.byte_index, value)
    
    def set_value(self, value: int):
        """设置字节值"""
        value = max(0, min(255, value))
        
        # 更新所有显示
        self.hex_edit.blockSignals(True)
        self.hex_edit.setText(f"{value:02X}")
        self.hex_edit.blockSignals(False)
        
        self.dec_label.setText(str(value))
        
        for i, cb in enumerate(self.bit_checkboxes):
            cb.blockSignals(True)
            cb.setChecked((value >> (7-i)) & 1)
            cb.blockSignals(False)
    
    def get_value(self) -> int:
        """获取当前字节值"""
        try:
            return int(self.hex_edit.text(), 16)
        except ValueError:
            return 0


class FrameConfigDialog(QDialog):
    """协议帧详细配置窗口"""
    
    frameChanged = pyqtSignal(list)  # 帧数据改变信号
    
    def __init__(self, parent=None, initial_frame: List[int] = None):
        super().__init__(parent)
        self.frame_data = initial_frame or [0] * 12
        self.byte_editors = []
        self.init_ui()
        self.update_frame_display()
        
    def init_ui(self):
        self.setWindowTitle("协议帧详细配置")
        self.setModal(True)
        # 调整窗口大小以适合两列显示：宽度适合两列，高度适合6行内容
        self.resize(900, 800)
        
        layout = QVBoxLayout()
        
        # 创建标签页
        tab_widget = QTabWidget()
        
        # 字节编辑标签页
        byte_tab = self.create_byte_editor_tab()
        tab_widget.addTab(byte_tab, "字节编辑")
        
        # 帧预览标签页
        preview_tab = self.create_preview_tab()
        tab_widget.addTab(preview_tab, "帧预览")
        
        layout.addWidget(tab_widget)
        
        # 按钮区域
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
        """创建字节编辑标签页"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # 创建滚动区域
        scroll = QScrollArea()
        scroll_widget = QWidget()
        scroll_layout = QGridLayout()
        
        # 字节描述
        byte_descriptions = [
            "设备编码 (固定0x08)",
            "流水号低8位 (固定0x61)",
            "流水号高4位 + Status1",
            "Status2 + 加密码",
            "Status3 + 加密码",
            "Status4 + 加密码",
            "Status5 (不加密)",
            "Status6 + 加密码",
            "Status7 + 加密码",
            "Status8 + 加密码",
            "Status9 + 加密码",
            "校验和 (自动计算)"
        ]
        
        # 创建字节编辑器 - 改为2x6布局（左右两列，每列6个）
        for i in range(12):
            editor = ByteEditor(i, self.frame_data[i], byte_descriptions[i])
            editor.valueChanged.connect(self.on_byte_changed)
            self.byte_editors.append(editor)
            
            # 左右两列布局：左列0-5，右列6-11
            if i < 6:
                # 左列
                row = i
                col = 0
            else:
                # 右列
                row = i - 6
                col = 1
            
            scroll_layout.addWidget(editor, row, col)
        
        # 设置列的拉伸比例，使两列等宽
        scroll_layout.setColumnStretch(0, 1)
        scroll_layout.setColumnStretch(1, 1)
        
        scroll_widget.setLayout(scroll_layout)
        scroll.setWidget(scroll_widget)
        scroll.setWidgetResizable(True)
        
        layout.addWidget(scroll)
        widget.setLayout(layout)
        return widget
    
    def create_preview_tab(self) -> QWidget:
        """创建帧预览标签页"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # 帧数据显示
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
        
        # 校验信息
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
        """字节值改变处理"""
        self.frame_data[byte_index] = new_value
        
        # 如果不是校验和字节，自动重新计算校验和
        if byte_index != 11:
            checksum = 0
            for i in range(11):
                checksum ^= self.frame_data[i]
            self.frame_data[11] = checksum
            self.byte_editors[11].set_value(checksum)
        
        self.update_frame_display()
        self.frameChanged.emit(self.frame_data.copy())
    
    def update_frame_display(self):
        """更新帧显示"""
        # 十六进制显示
        hex_str = " ".join([f"{b:02X}" for b in self.frame_data])
        self.frame_hex_label.setText(f"HEX: {hex_str}")
        
        # 十进制显示
        dec_str = " ".join([f"{b:3d}" for b in self.frame_data])
        self.frame_dec_label.setText(f"DEC: {dec_str}")
        
        # 校验和信息
        calculated_checksum = 0
        for i in range(11):
            calculated_checksum ^= self.frame_data[i]
        
        checksum_valid = calculated_checksum == self.frame_data[11]
        checksum_status = "✓ 正确" if checksum_valid else "✗ 错误"
        
        self.checksum_label.setText(
            f"计算校验和: 0x{calculated_checksum:02X} ({calculated_checksum})\n"
            f"当前校验和: 0x{self.frame_data[11]:02X} ({self.frame_data[11]})\n"
            f"校验状态: {checksum_status}"
        )
    
    def reset_frame(self):
        """重置帧数据"""
        self.frame_data = [0] * 12
        for i, editor in enumerate(self.byte_editors):
            editor.set_value(0)
        self.update_frame_display()
    
    def apply_changes(self):
        """应用更改"""
        self.frameChanged.emit(self.frame_data.copy())
    
    def set_frame_data(self, frame_data: List[int]):
        """设置帧数据"""
        self.frame_data = frame_data.copy()
        for i, editor in enumerate(self.byte_editors):
            if i < len(frame_data):
                editor.set_value(frame_data[i])
        self.update_frame_display()
    
    def get_frame_data(self) -> List[int]:
        """获取当前帧数据"""
        return self.frame_data.copy()