#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""协议下拉搜索只提交已注册项目，不因输入关键字切换协议或停止循环。"""

from PyQt5.QtCore import QEvent, QPoint, Qt
from PyQt5.QtWidgets import QApplication, QComboBox, QFrame, QLabel, QLineEdit, QListWidget, QListWidgetItem, QVBoxLayout, QWidget

from gui.protocol_search import normalize_search_text, protocol_search_keys


class ProtocolSelector(QComboBox):
    """保留普通 QComboBox 的设置和信号契约，将搜索输入隔离在下拉层。"""

    def __init__(self, parent=None):
        """延迟建立弹层，关闭或取消搜索不改变当前选择。"""
        super().__init__(parent)
        self._popup = None
        self._search = None
        self._results = None
        self._result_hint = None
        self._ime_composing = False
        self.setToolTip("点击下拉后可输入中文、全拼、首字母或型号搜索；选择结果后才切换协议")

    def _create_popup(self):
        """建立窗口自有的搜索弹层，不调用发送控制或协议生成函数。"""
        # 修复 Windows 输入法上下文与菜单式弹层抢占焦点的问题：使用可正常激活的工具浮层。
        # 不使用原生键盘钩子、grabKeyboard 或系统输入法开关，不拦截 Shift 等模式切换键。
        self._popup = QFrame(self, Qt.Tool | Qt.FramelessWindowHint)
        self._popup.setObjectName("protocolSearchPopup")
        self._popup.setFocusPolicy(Qt.StrongFocus)
        layout = QVBoxLayout(self._popup)
        layout.setContentsMargins(10, 10, 10, 8)
        layout.setSpacing(7)
        self._search = QLineEdit(self._popup)
        self._search.setPlaceholderText("中文 / 全拼 / 首字母 / 型号，如 rui、rl、Y34B")
        self._search.setClearButtonEnabled(True)
        self._search.setAttribute(Qt.WA_InputMethodEnabled, True)
        self._search.setInputMethodHints(Qt.ImhNone)
        self._popup.setFocusProxy(self._search)
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
        self._ime_composing = False
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
        QApplication.instance().installEventFilter(self)
        self._popup.show()
        self._popup.activateWindow()
        self._search.setFocus(Qt.OtherFocusReason)
        QApplication.inputMethod().update(Qt.ImEnabled | Qt.ImCursorRectangle)

    def hidePopup(self):
        """关闭自有弹层并重置原控件弹出状态，不自动选中搜索结果。"""
        if self._popup is not None:
            self._popup.hide()
        QApplication.instance().removeEventFilter(self)
        self._ime_composing = False
        super().hidePopup()

    def eventFilter(self, watched, event):
        """只管理搜索层的取消与普通导航，输入法事件和 Shift/Ctrl/Alt 等按键交还 Qt。"""
        if watched is self._popup and event.type() == QEvent.Hide:
            QApplication.instance().removeEventFilter(self)
            self._ime_composing = False
        if self._popup is None or not self._popup.isVisible():
            return False
        if watched is self._search and event.type() == QEvent.InputMethod:
            # 合成文本尚未确认时不能把候选确认/取消键当作协议选择操作。
            self._ime_composing = bool(event.preeditString())
            return False
        # QApplication 的过滤器还会收到布局和窗口对象，只有 QWidget 才能查询父子关系。
        is_widget = isinstance(watched, QWidget)
        inside_popup = is_widget and (watched is self._popup or self._popup.isAncestorOf(watched))
        if event.type() == QEvent.KeyPress and inside_popup and not self._ime_composing:
            if event.key() == Qt.Key_Escape and event.modifiers() == Qt.NoModifier:
                self.hidePopup()
                self.setFocus(Qt.OtherFocusReason)
                return True
            if watched is self._search and event.key() in (Qt.Key_Up, Qt.Key_Down) and event.modifiers() == Qt.NoModifier:
                self._move_result(-1 if event.key() == Qt.Key_Up else 1)
                return True
        if event.type() == QEvent.MouseButtonPress and not inside_popup:
            on_combo = is_widget and (watched is self or self.isAncestorOf(watched))
            self.hidePopup()
            # 再次点击同一箭头是收起，其他位置的鼠标事件继续执行原有动作。
            return bool(on_combo)
        if watched is self.window() and event.type() in (QEvent.Hide, QEvent.Close, QEvent.WindowStateChange):
            self.hidePopup()
        return False

    def _move_result(self, offset):
        """只在可见结果间移动高亮，输入期间不修改当前协议。"""
        visible = [self._results.item(row) for row in range(self._results.count())
                   if not self._results.item(row).isHidden()]
        if not visible:
            return
        current = self._results.currentItem()
        position = visible.index(current) if current in visible else (-1 if offset > 0 else len(visible))
        target = visible[max(0, min(len(visible) - 1, position + offset))]
        self._results.setCurrentItem(target)
        self._results.scrollToItem(target)

    def _filter_results(self, text):
        """按中文、型号或集中维护的拼音索引过滤，不构造伪协议选项。"""
        keyword = normalize_search_text(text)
        visible = []
        for row in range(self._results.count()):
            item = self._results.item(row)
            matched = any(keyword in key for key in protocol_search_keys(item.text()))
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
        if self._popup is None or not self._popup.isVisible() or self._ime_composing:
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
