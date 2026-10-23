#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""发送历史的有界表格视图，只接收已有日志批次，不编码或发送帧。"""

import re

from PyQt5.QtCore import QAbstractTableModel, QModelIndex, Qt
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtWidgets import QAbstractItemView, QHeaderView, QLabel, QTableView, QVBoxLayout, QWidget

from gui.ui_icons import ui_icon
from gui.soft_theme import PALETTE

_HISTORY_LINE = re.compile(r"^\[([^\]]+)\] 发送(成功|失败): (.*)$", re.DOTALL)


class HistoryTableModel(QAbstractTableModel):
    """按批次增删有界行，避免逐帧建立整张 QTableWidget。"""

    def __init__(self, limit=10000, parent=None):
        """历史上限与原只读文本一致，不引入无界队列。"""
        super().__init__(parent)
        self.limit = max(1, int(limit))
        self._rows = []

    def rowCount(self, parent=QModelIndex()):
        """平面模型只返回最外层记录数量。"""
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent=QModelIndex()):
        """固定时间、结果和已写入帧三列，不由协议数量决定。"""
        return 0 if parent.isValid() else 3

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        """保持列名简短；错误行的第三列显示原错误消息。"""
        if orientation == Qt.Horizontal and role == Qt.DisplayRole and 0 <= section < 3:
            return ("时间", "结果", "已写入帧")[section]
        return None

    def data(self, index, role=Qt.DisplayRole):
        """仅按可视单元格取值，不在绘制时遍历或生成协议数据。"""
        if not index.isValid() or not 0 <= index.row() < len(self._rows) or not 0 <= index.column() < 3:
            return None
        row = self._rows[index.row()]
        if role in (Qt.DisplayRole, Qt.ToolTipRole):
            return row[index.column()]
        if role == Qt.TextAlignmentRole:
            return int(Qt.AlignVCenter | Qt.AlignLeft)
        if role == Qt.BackgroundRole:
            if row[1] == "发送失败":
                return QColor(PALETTE["error_row"])
            if index.row() == len(self._rows) - 1:
                return QColor(PALETTE["latest_row"])
        if role == Qt.ForegroundRole:
            if row[1] == "发送失败":
                return QColor(PALETTE["error_text"])
            if row[1] == "提示":
                return QColor(PALETTE["warning_text"])
            return QColor(PALETTE["data_text"] if index.column() == 2 else PALETTE["data_secondary"])
        if role == Qt.FontRole and index.column() == 2:
            return QFont("Consolas", 9)
        return None

    def append_lines(self, lines):
        """只解析原日志格式；提示和错误保留原文，不伪造写入结果。"""
        rows = []
        for line in lines:
            line = str(line)
            match = _HISTORY_LINE.fullmatch(line)
            if match:
                timestamp, result, detail = match.groups()
                rows.append((timestamp, "已写入" if result == "成功" else "发送失败", detail))
            else:
                rows.append(("—", "提示", str(line)))
        rows = rows[-self.limit:]
        if not rows:
            return
        discard = max(0, len(self._rows) + len(rows) - self.limit)
        if discard:
            self.beginRemoveRows(QModelIndex(), 0, discard - 1)
            del self._rows[:discard]
            self.endRemoveRows()
        old_last = len(self._rows) - 1
        self.beginInsertRows(QModelIndex(), len(self._rows), len(self._rows) + len(rows) - 1)
        self._rows.extend(rows)
        self.endInsertRows()
        if old_last >= 0:
            self.dataChanged.emit(self.index(old_last, 0), self.index(old_last, 2), [Qt.BackgroundRole])

    def clear(self):
        """清空当前模型，不影响任何串口或发送状态。"""
        if self._rows:
            self.beginResetModel()
            self._rows.clear()
            self.endResetModel()


class SendHistoryView(QTableView):
    """空态与分列历史共用一张表，复用主窗口原有 100ms 批量刷新。"""

    def __init__(self, limit=10000, parent=None):
        """设置只读、按行选择和可水平滚动，不压缩或截去实际帧内容。"""
        super().__init__(parent)
        self.setObjectName("sendHistoryTable")
        self.history_model = HistoryTableModel(limit, self)
        self.setModel(self.history_model)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setWordWrap(False)
        self.setShowGrid(True)
        self.verticalHeader().hide()
        self.verticalHeader().setDefaultSectionSize(28)
        self.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self.horizontalHeader().resizeSection(0, 110)
        self.horizontalHeader().setSectionResizeMode(1, QHeaderView.Fixed)
        self.horizontalHeader().resizeSection(1, 70)
        self.horizontalHeader().setSectionResizeMode(2, QHeaderView.Interactive)
        self.horizontalHeader().resizeSection(2, 270)
        self.horizontalHeader().setStretchLastSection(True)
        self.horizontalHeader().setMinimumSectionSize(60)
        self.setMinimumHeight(85)
        self.empty_state = QWidget(self.viewport())
        self.empty_state.setObjectName("historyEmptyState")
        self.empty_state.setAttribute(Qt.WA_TransparentForMouseEvents)
        layout = QVBoxLayout(self.empty_state)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(9)
        layout.addStretch()
        self.empty_icon = QLabel()
        self.empty_icon.setPixmap(ui_icon("empty", "#b6c7d1", 36).pixmap(36, 36))
        self.empty_icon.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.empty_icon)
        label = QLabel("暂无发送记录")
        label.setProperty("muted", True)
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)
        layout.addStretch()
        self._refresh_empty_state()

    def _refresh_empty_state(self):
        """空态位于表头下方，出现记录后立即隐藏，不遮盖实际发送内容。"""
        self.empty_state.setGeometry(self.viewport().rect())
        # 修复低高度窗口的空态图标挤出视口问题，优先保留“暂无发送记录”文字。
        self.empty_icon.setVisible(self.viewport().height() >= 72)
        self.empty_state.setVisible(self.history_model.rowCount() == 0)

    def resizeEvent(self, event):
        """跟随实际视口布局空态，保留原表格滚动行为。"""
        super().resizeEvent(event)
        if hasattr(self, "empty_state"):
            self._refresh_empty_state()

    def append_lines(self, lines, auto_scroll=True):
        """一次提交一批已有日志，仅在用户启用自动滚动时移动视口。"""
        self.history_model.append_lines(lines)
        self._refresh_empty_state()
        if auto_scroll:
            self.scrollToBottom()

    def clear(self):
        """与原清空按钮同步恢复空态，不清理用户磁盘日志。"""
        self.history_model.clear()
        self._refresh_empty_state()
