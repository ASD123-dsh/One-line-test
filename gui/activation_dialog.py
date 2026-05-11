#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Offline activation dialog shown before entering the main window."""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
)

from gui.feedback_dialog import FeedbackDialog
from licensing.activation import ActivationService


class ActivationDialog(QDialog):
    def __init__(self, activation_service: ActivationService, parent=None):
        super().__init__(parent)
        self.activation_service = activation_service
        self.device_code = self.activation_service.get_device_code()
        self.setWindowTitle("软件激活")
        self.setModal(True)
        self.resize(620, 360)
        self._init_ui()

    def _init_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(16, 16, 16, 16)
        root_layout.setSpacing(12)

        header_row = QHBoxLayout()
        header_row.addStretch()
        help_btn = QToolButton()
        help_btn.setText("?")
        help_btn.setToolTip("查看二维码")
        help_btn.setFixedSize(28, 28)
        help_btn.clicked.connect(self.show_qr_help_dialog)
        header_row.addWidget(help_btn)
        root_layout.addLayout(header_row)

        intro_label = QLabel("当前版本需要激活后使用，请将下方设备码发送给作者获取激活码。")
        intro_label.setWordWrap(True)
        root_layout.addWidget(intro_label)

        device_frame = QFrame()
        device_frame.setObjectName("deviceFrame")
        device_layout = QVBoxLayout(device_frame)
        device_layout.setContentsMargins(12, 12, 12, 12)
        device_layout.setSpacing(8)

        device_title = QLabel("设备码")
        device_title.setObjectName("sectionTitle")
        device_layout.addWidget(device_title)

        device_row = QHBoxLayout()
        self.device_code_edit = QLineEdit(self.device_code)
        self.device_code_edit.setReadOnly(True)
        self.device_code_edit.setAlignment(Qt.AlignCenter)
        device_row.addWidget(self.device_code_edit, 1)

        copy_btn = QPushButton("复制设备码")
        copy_btn.clicked.connect(self.copy_device_code)
        device_row.addWidget(copy_btn)
        device_layout.addLayout(device_row)
        root_layout.addWidget(device_frame)

        code_title = QLabel("激活码")
        code_title.setObjectName("sectionTitle")
        root_layout.addWidget(code_title)

        self.activation_code_edit = QTextEdit()
        self.activation_code_edit.setPlaceholderText("请粘贴作者生成的激活码")
        self.activation_code_edit.setAcceptRichText(False)
        self.activation_code_edit.setFixedHeight(110)
        root_layout.addWidget(self.activation_code_edit)

        tip_label = QLabel("激活码支持多行粘贴，程序会自动忽略空格和换行。")
        tip_label.setObjectName("tipLabel")
        tip_label.setWordWrap(True)
        root_layout.addWidget(tip_label)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #666666;")
        root_layout.addWidget(self.status_label)

        button_box = QDialogButtonBox()
        self.activate_btn = button_box.addButton("激活并进入", QDialogButtonBox.AcceptRole)
        self.exit_btn = button_box.addButton("退出", QDialogButtonBox.RejectRole)
        self.activate_btn.clicked.connect(self.try_activate)
        self.exit_btn.clicked.connect(self.reject)
        root_layout.addWidget(button_box)

        self.setStyleSheet(
            """
            QDialog {
                background-color: #f6f7f9;
            }
            QFrame#deviceFrame {
                background-color: white;
                border: 1px solid #d8dde6;
                border-radius: 6px;
            }
            QLabel#sectionTitle {
                font-size: 13px;
                font-weight: bold;
                color: #333333;
            }
            QLabel#tipLabel {
                color: #666666;
            }
            QToolButton {
                background-color: transparent;
                border: 1px solid #cfd6e4;
                border-radius: 14px;
                color: #666666;
                font-weight: bold;
            }
            """
        )

    def show_qr_help_dialog(self):
        dialog = FeedbackDialog(
            self,
            remaining_validity_text="未激活",
            footer_text="扫描二维码联系作者获取激活码",
        )
        dialog.exec_()

    def copy_device_code(self):
        from PyQt5.QtWidgets import QApplication

        QApplication.clipboard().setText(self.device_code)
        QMessageBox.information(self, "已复制", "设备码已复制到剪贴板。")

    def try_activate(self):
        activation_code = self.activation_code_edit.toPlainText().strip()
        if not activation_code:
            QMessageBox.warning(self, "提示", "请先输入激活码。")
            return

        success, message = self.activation_service.activate(activation_code)
        if not success:
            QMessageBox.critical(self, "激活失败", message)
            return

        self.status_label.setText("激活成功，正在进入主程序...")
        self.accept()
