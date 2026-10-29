#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""协议参数页使用各自的滚动容器，预设可浏览但不能手动改变数据。"""

from PyQt5.QtCore import QSize, Qt
from PyQt5.QtWidgets import QFrame, QHBoxLayout, QLabel, QScrollArea, QTabWidget, QVBoxLayout, QWidget


class ProtocolTabs(QTabWidget):
    """复用原 addTab 入口，不让大数据页撑高只有少量选项的其他页。"""

    def __init__(self, parent=None):
        """创建独立页滚动视图，默认处于预设只读模式。"""
        super().__init__(parent)
        self._editable = False
        self.setDocumentMode(True)
        self.tabBar().setDrawBase(False)

    def paintEvent(self, event):
        """修复原生页签基线透过圆角标签形成黑角；文档模式仅保留已有页签样式。"""
        # 文档模式的 Qt 原生基线会延伸至角落标签背后；取消叠绘，不改变页签和布局。
        if not self.documentMode():
            super().paintEvent(event)

    def addTab(self, widget, label):
        """自动包裹原有协议控件，避免每个协议都重写滚动和只读逻辑。"""
        if isinstance(widget, QScrollArea):
            scroll = widget
        else:
            scroll = QScrollArea()
            wrapper = QWidget()
            wrapper.setObjectName("protocolPage")
            body = QVBoxLayout(wrapper)
            body.setContentsMargins(0, 0, 0, 0)
            body.setSpacing(2)
            # 修复切换协议时的闪窗：创建时就归属参数页，避免显示后才入布局形成临时顶层窗口。
            heading = QFrame(wrapper)
            heading.setObjectName("parameterSectionHeader")
            row = QHBoxLayout(heading)
            row.setContentsMargins(4, 6, 4, 6)
            title = QLabel()
            title.setProperty("sectionTitle", True)
            row.addWidget(title)
            hint = QLabel()
            hint.setProperty("muted", True)
            hint.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            row.addWidget(hint, 1)
            heading.setVisible(label.startswith("Status"))
            body.addWidget(heading)
            body.addWidget(widget, 1)
            scroll.setWidget(wrapper)
            scroll._protocol_content = widget
            scroll._section_title = title
            scroll._section_hint = hint
        scroll.setObjectName("protocolPageScroll")
        scroll.setWidgetResizable(True)
        content = getattr(scroll, "_protocol_content", scroll.widget())
        if content is not None:
            content.setObjectName("protocolPage")
            content.setEnabled(self._editable)
        return super().addTab(scroll, label)

    def page_content(self, index):
        """为原布局压缩及测试返回实际协议页，不把包装层当成业务控件。"""
        page = self.widget(index)
        return getattr(page, "_protocol_content", page.widget()) if isinstance(page, QScrollArea) else page

    def set_page_context(self, title, hint):
        """把当前参数页说明放到页签下方，不改变参数值或编辑状态。"""
        page = self.currentWidget()
        if hasattr(page, "_section_title"):
            page._section_title.setText(title)
            page._section_hint.setText(hint)
            page._section_hint.setToolTip(hint)

    def set_editable(self, editable):
        """只禁用参数内容，保留页签和滚动条供用户查看预设全部字段。"""
        self._editable = bool(editable)
        for index in range(self.count()):
            page = self.page_content(index)
            if page is not None:
                page.setEnabled(self._editable)

    def sizeHint(self):
        """参数区域优先使用可分配高度，不跟随最长页面扩大整个主窗口。"""
        return QSize(480, 130)

    def minimumSizeHint(self):
        """窄窗口保留页签及基本内容，更多参数通过当前页滚动查看。"""
        return QSize(260, 130)
