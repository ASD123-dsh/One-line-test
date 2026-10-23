#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""协议下拉搜索只提交已注册项目，不因输入关键字切换协议或停止循环。"""

from PyQt5.QtCore import QPoint, Qt
from PyQt5.QtWidgets import QApplication, QComboBox, QFrame, QLabel, QLineEdit, QListWidget, QListWidgetItem, QVBoxLayout


class ProtocolSelector(QComboBox):
    """保留普通 QComboBox 的设置和信号契约，将搜索输入隔离在下拉层。"""

    def __init__(self, parent=None):
        """延迟建立弹层，关闭或取消搜索不改变当前选择。"""
        super().__init__(parent)
        self._popup = None
        self._search = None
        self._results = None
        self._result_hint = None
        self.setToolTip("点击下拉后可输入协议名称搜索；选择结果后才切换协议")

    def _create_popup(self):
        """建立窗口自有的搜索弹层，不调用发送控制或协议生成函数。"""
        self._popup = QFrame(self, Qt.Popup)
        self._popup.setObjectName("protocolSearchPopup")
        layout = QVBoxLayout(self._popup)
        layout.setContentsMargins(10, 10, 10, 8)
        layout.setSpacing(7)
        self._search = QLineEdit(self._popup)
        self._search.setPlaceholderText("输入协议名称搜索…")
        self._search.setClearButtonEnabled(True)
        layout.addWidget(self._search)
        self._results = QListWidget(self._popup)
        self._results.setObjectName("protocolSearchList")
        self._results.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        layout.addWidget(self._results, 1)
        self._result_hint = QLabel(self._popup)
        self._result_hint.setProperty("muted", True)
        layout.addWidget(self._result_hint)
        self._search.textChanged.connect(self._filter_results)
        self._search.returnPressed.connect(self._commit_selection)
        self._results.itemClicked.connect(self._commit_selection)
        self._results.itemActivated.connect(self._commit_selection)

    def showPopup(self):
        """只列出当前下拉框的合法项，输入过程不发送 currentTextChanged。"""
        if self._popup is None:
            self._create_popup()
        self._results.clear()
        for index in range(self.count()):
            item = QListWidgetItem(self.itemText(index))
            item.setData(Qt.UserRole, index)
            self._results.addItem(item)
        self._search.clear()
        self._filter_results("")
        if self.currentIndex() >= 0:
            self._results.setCurrentRow(self.currentIndex())
        screen = QApplication.desktop().availableGeometry(self)
        width = min(max(self.width(), 340), screen.width() - 16)
        height = min(340, screen.height() - 24)
        origin = self.mapToGlobal(QPoint(0, self.height()))
        x = min(max(origin.x(), screen.left() + 8), screen.right() - width - 8)
        y = origin.y()
        if y + height > screen.bottom() - 8:
            y = max(screen.top() + 8, self.mapToGlobal(QPoint(0, 0)).y() - height)
        self._popup.setGeometry(x, y, width, height)
        self._popup.show()
        self._search.setFocus(Qt.PopupFocusReason)

    def hidePopup(self):
        """关闭自有弹层并重置原控件弹出状态，不自动选中搜索结果。"""
        if self._popup is not None:
            self._popup.hide()
        super().hidePopup()

    def _filter_results(self, text):
        """按名称包含关系过滤，未找到结果时不构造伪协议选项。"""
        keyword = text.strip().casefold()
        visible = []
        for row in range(self._results.count()):
            item = self._results.item(row)
            matched = keyword in item.text().casefold()
            item.setHidden(not matched)
            if matched:
                visible.append(item)
        current = self._results.currentItem()
        if visible and (current is None or current.isHidden()):
            self._results.setCurrentItem(visible[0])
        if not visible:
            self._results.setCurrentRow(-1)
        self._result_hint.setText(f"找到 {len(visible)} 种协议" if visible else "未找到匹配协议")

    def _commit_selection(self, item=None):
        """仅接受当前可见且仍对应原项目的结果，避免输入文字触发错误协议回退。"""
        if self._popup is None or not self._popup.isVisible():
            return
        item = item if isinstance(item, QListWidgetItem) else self._results.currentItem()
        if item is None or item.isHidden():
            return
        index = item.data(Qt.UserRole)
        if not isinstance(index, int) or not 0 <= index < self.count() or self.itemText(index) != item.text():
            return
        self.setCurrentIndex(index)
        self.hidePopup()
        self.setFocus(Qt.PopupFocusReason)
