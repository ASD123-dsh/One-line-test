#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""本机AI连接申请和设置窗口；授权仅对本次会话有效，不保存或自动恢复。"""

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QDialog, QFormLayout, QHBoxLayout, QLabel, QMessageBox, QPushButton, QVBoxLayout


class AiConnectionRequestDialog(QDialog):
    """非阻塞人工确认，不在HTTP处理过程中运行嵌套事件循环或自动同意。"""

    def __init__(self, controller, request_id, parent=None):
        """默认拒绝，不信任客户端自报账号，不让任意申请改动串口或协议。"""
        super().__init__(parent)
        self.controller = controller
        self.request_id = request_id
        self._resolved = False
        self.setWindowTitle("本机 AI 请求连接")
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setMinimumWidth(440)
        self.setModal(False)
        layout = QVBoxLayout(self)
        title = QLabel("允许本机 AI 连接一线通工具吗？")
        layout.addWidget(title)
        note = QLabel("允许控制后，AI可选择协议、修改参数、连接串口并发送测试数据。\n请确认接线和被测设备安全。")
        note.setWordWrap(True)
        layout.addWidget(note)
        scope = QLabel("仅本次有效，断开或关闭工具后失效；不会自动连接串口或开始发送。")
        scope.setWordWrap(True)
        layout.addWidget(scope)
        buttons = QHBoxLayout()
        self.allow_button = QPushButton("本次允许控制")
        self.read_only_button = QPushButton("仅允许只读")
        self.reject_button = QPushButton("拒绝")
        for button in (self.allow_button, self.read_only_button):
            button.setAutoDefault(False)
        self.reject_button.setDefault(True)
        self.allow_button.clicked.connect(lambda: self._choose("control"))
        self.read_only_button.clicked.connect(lambda: self._choose("read_only"))
        self.reject_button.clicked.connect(self.reject)
        for button in (self.allow_button, self.read_only_button, self.reject_button):
            buttons.addWidget(button)
        layout.addLayout(buttons)
        self.finished.connect(self._on_finished)

    def _choose(self, access):
        """只在用户点击时批准，申请过期或手动循环繁忙时不能偷偷授予控制。"""
        self._resolved = True
        try:
            accepted = self.controller.resolve_connection(self.request_id, access)
        except ValueError as exc:
            self._resolved = False
            QMessageBox.warning(self, "无法允许本次连接", str(exc))
            return
        if accepted:
            self.accept()
        else:
            self.reject()

    def _on_finished(self, result):
        """关闭、Esc或默认按钮均等同拒绝，不把关闭弹窗当作同意。"""
        if not self._resolved:
            self._resolved = True
            self.controller.resolve_connection(self.request_id, "reject")

    def dismiss(self):
        """申请失效或工具退出时关闭提示，不误处理另一份新申请。"""
        if self._resolved:
            return
        self._resolved = True
        self.reject()


class AiControlDialog(QDialog):
    """非模态显示开关、临时权限和停止入口，不改变主界面布局。"""

    def __init__(self, controller, parent=None):
        """仅创建设置窗口，默认不启动服务或授予操作权。"""
        super().__init__(parent)
        self.controller = controller
        self.setWindowTitle("AI 本机接口")
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setMinimumWidth(440)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.state_label = QLabel()
        self.endpoint_label = QLabel()
        self.endpoint_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        form.addRow("状态", self.state_label)
        form.addRow("本机地址", self.endpoint_label)
        layout.addLayout(form)
        note = QLabel("AI可主动申请连接，由你确认是否允许；本次授权不设固定时限，关闭工具后失效。")
        note.setWordWrap(True)
        layout.addWidget(note)
        row = QHBoxLayout()
        self.enable_button = QPushButton()
        self.enable_button.clicked.connect(self.toggle_service)
        self.grant_button = QPushButton("允许本次控制")
        self.grant_button.clicked.connect(self.grant)
        self.revoke_button = QPushButton("断开AI并撤销本次授权")
        self.revoke_button.clicked.connect(self.revoke)
        row.addWidget(self.enable_button)
        row.addWidget(self.grant_button)
        layout.addLayout(row)
        layout.addWidget(self.revoke_button)
        detail = QLabel("单次自动循环最多60秒；连接失联10秒后停止后续发送。已进入驱动的帧需等待完成。")
        detail.setWordWrap(True)
        layout.addWidget(detail)
        self.timer = QTimer(self)
        self.timer.setInterval(500)
        self.timer.timeout.connect(self.refresh)
        self.timer.start()
        self.refresh()

    def refresh(self):
        """显示申请、只读及本次控制状态，不显示、复制或记录令牌。"""
        enabled = self.controller.server is not None
        state = self.controller.connection_state()
        label = "等待确认" if state["state"] == "pending" else "本次允许控制" if self.controller._write_allowed else "只读" if self.controller._approved else "等待连接申请"
        self.state_label.setText(label if enabled else "已关闭")
        self.endpoint_label.setText(self.controller.server.endpoint if enabled else "—")
        self.enable_button.setText("关闭接口" if enabled else "接收连接申请")
        self.grant_button.setEnabled(enabled)
        self.revoke_button.setEnabled(enabled)

    def toggle_service(self):
        """开关仅由界面发起，写入权限不随开启或配置记忆自动恢复。"""
        try:
            if self.controller.server is None:
                self.controller.listen_for_requests()
            else:
                self.controller.shutdown()
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "AI接口未开启", str(exc))
        self.refresh()

    def grant(self):
        """明确提示会真实发帧，拒绝确认时不赋予AI控制权。"""
        answer = QMessageBox.question(self, "允许本机AI操作", "允许本机AI在本次连接中选择协议、连接串口并实际发送测试数据？\n请先确认接线和被测设备安全。授权不设分钟数，断开或关闭工具后失效。", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if answer != QMessageBox.Yes:
            return
        try:
            self.controller.grant_writes()
        except ValueError as exc:
            QMessageBox.warning(self, "无法授权", str(exc))
        self.refresh()

    def revoke(self):
        """界面停止始终可用，不等待AI或HTTP请求先结束。"""
        self.controller.close_connection()
        self.refresh()
