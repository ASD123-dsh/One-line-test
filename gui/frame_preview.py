#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""只读帧预览及复制组件，显示独立字节快照，不调用编码或发送接口。"""

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtWidgets import (
    QAbstractItemView, QApplication, QHeaderView, QHBoxLayout, QLabel, QLineEdit,
    QAction, QPushButton, QTabWidget, QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget,
)

from protocol.frame_utils import normalize_frame
from protocol.definitions import PROTOCOL_LISHEN_BMS
from gui.ui_icons import button_icon
from gui.soft_theme import PALETTE


class FramePreview(QWidget):
    """把预览与历史中的实际写入帧区分开，保留原始文本视图兼容原有调用。"""

    def __init__(self, parent=None):
        """建立轻量表格，不启动额外计时器或动画。"""
        super().__init__(parent)
        self.setObjectName("framePreview")
        self._last_protocol = None
        self._last_frame = None
        self._last_descriptions = ()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(7)
        controls = QHBoxLayout()
        self.byte_count = QLabel("-- 字节")
        controls.addWidget(self.byte_count)
        controls.addStretch()
        self.copy_button = QPushButton("复制整帧")
        self.copy_button.setIcon(button_icon("copy"))
        self.copy_button.setEnabled(False)
        self.copy_button.clicked.connect(self.copy_frame)
        controls.addWidget(self.copy_button)
        layout.addLayout(controls)

        self.hex_text = QLineEdit()
        self.hex_text.setObjectName("frameHex")
        self.hex_text.setReadOnly(True)
        self.hex_text.setPlaceholderText("当前无可用帧")
        self.hex_text.setFont(QFont("Consolas", 11))
        layout.addWidget(self.hex_text)

        self.views = QTabWidget()
        self.views.setDocumentMode(True)
        self.views.tabBar().hide()
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["字节", "十六进制", "十进制", "含义"])
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setShowGrid(True)
        self.table.setWordWrap(False)
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(24)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        header.resizeSection(0, 80)
        for column in (1, 2, 3):
            header.setSectionResizeMode(column, QHeaderView.Stretch)
        self.table.setMinimumHeight(110)
        self.views.addTab(self.table, "字节详情")
        # 兼容原 current_frame_text.toPlainText()，原格式仍由 ProtocolHandler 提供。
        self.legacy_text = QTextEdit()
        self.legacy_text.setReadOnly(True)
        self.legacy_text.setFont(QFont("Consolas", 9))
        self.views.addTab(self.legacy_text, "原始说明")
        layout.addWidget(self.views, 1)
        # 参考图不额外占用一行预览页签，原格式仍可从表格右键打开并返回。
        raw_action = QAction("查看原始说明", self.table)
        raw_action.triggered.connect(lambda: self.views.setCurrentIndex(1))
        self.table.addAction(raw_action)
        self.table.setContextMenuPolicy(Qt.ActionsContextMenu)
        back_action = QAction("返回字节表格", self.legacy_text)
        back_action.triggered.connect(lambda: self.views.setCurrentIndex(0))
        self.legacy_text.addAction(back_action)
        self.legacy_text.setContextMenuPolicy(Qt.ActionsContextMenu)
        self.table.setToolTip("右键可查看原始说明；复制整帧不会消耗协议流水号")

        legend = QHBoxLayout()
        legend.addStretch()
        self.change_swatch = QLabel()
        self.change_swatch.setObjectName("changeSwatch")
        self.change_swatch.setFixedSize(13, 13)
        legend.addWidget(self.change_swatch)
        self.change_hint = QLabel("本次变化")
        self.change_hint.setToolTip("浅色行表示与上次预览不同，不等于已写入硬件；实际写入见发送历史")
        legend.addWidget(self.change_hint)
        self.change_hint.hide()
        self.change_swatch.hide()
        layout.addLayout(legend)

    def _meaning(self, protocol, snapshot, row, description):
        """只把锂神已知字段显示为易读值，不参与编码或修改原始字节说明。"""
        if protocol != PROTOCOL_LISHEN_BMS or len(snapshot) != 6:
            return description
        temperature = snapshot[3] if snapshot[3] < 128 else snapshot[3] - 256
        return ("保留", f"SOC {snapshot[1]}%", f"总电压 {snapshot[2]}V", f"温度 {temperature}℃", "保留", "累加校验")[row]

    def set_frame(self, protocol, frame, descriptions):
        """显示经校验的独立快照，仅协议相同且值发生变化时更新单元格。"""
        try:
            snapshot = tuple(normalize_frame(frame))
        except ValueError as exc:
            self.show_error(str(exc))
            return False
        descriptions = tuple(descriptions)
        if (protocol, snapshot, descriptions) == (self._last_protocol, self._last_frame, self._last_descriptions):
            return False
        previous = self._last_frame if self._last_protocol == protocol else None
        same_length = previous is not None and len(previous) == len(snapshot)
        if self._last_protocol != protocol:
            self.table.setColumnHidden(3, protocol != PROTOCOL_LISHEN_BMS)
            self.table.horizontalHeader().resizeSection(0, 60 if protocol == PROTOCOL_LISHEN_BMS else 80)
            self.table.verticalHeader().setDefaultSectionSize(30 if protocol == PROTOCOL_LISHEN_BMS else 24)
        self.table.setUpdatesEnabled(False)
        try:
            if self.table.rowCount() != len(snapshot):
                self.table.setRowCount(len(snapshot))
            for row, value in enumerate(snapshot):
                description = descriptions[row] if row < len(descriptions) else ""
                values = (str(row), f"{value:02X}", str(value), self._meaning(protocol, snapshot, row, description))
                changed = same_length and previous[row] != value
                for column, text in enumerate(values):
                    item = self.table.item(row, column)
                    if item is None:
                        item = QTableWidgetItem()
                        item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                        self.table.setItem(row, column, item)
                    if item.text() != text:
                        item.setText(text)
                    item.setToolTip(f"DATA{row}: {value:02X} ({value})\n{description}")
                    item.setTextAlignment(Qt.AlignVCenter | Qt.AlignHCenter)
                    item.setBackground(QColor(PALETTE["changed_row"]) if changed else QColor(Qt.transparent))
                    item.setForeground(QColor(PALETTE["data_secondary"] if column in (0, 3) else PALETTE["data_text"]))
        finally:
            self.table.setUpdatesEnabled(True)
        self._last_protocol = protocol
        self._last_frame = snapshot
        self._last_descriptions = descriptions
        self.hex_text.setText(" ".join(f"{value:02X}" for value in snapshot))
        self.hex_text.setCursorPosition(0)
        self.byte_count.setText(f"{len(snapshot)} 字节")
        self.copy_button.setEnabled(True)
        changed = same_length and previous != snapshot
        self.change_hint.setText("本次变化")
        self.change_hint.setVisible(changed)
        self.change_swatch.setVisible(changed)
        return True

    def show_error(self, message):
        """无效预览时清除旧字节和复制入口，避免误把旧帧当作当前数据。"""
        self._last_protocol = None
        self._last_frame = None
        self._last_descriptions = ()
        self.table.setRowCount(0)
        self.hex_text.clear()
        self.byte_count.setText("-- 字节")
        self.copy_button.setEnabled(False)
        self.legacy_text.setPlainText(message)
        self.change_hint.setText(message)
        self.change_hint.show()
        self.change_swatch.hide()

    def copy_frame(self):
        """只复制已经展示的字节，不再次编码、不推进序号，也不触发串口写入。"""
        if self._last_frame is not None:
            QApplication.clipboard().setText(self.hex_text.text())
