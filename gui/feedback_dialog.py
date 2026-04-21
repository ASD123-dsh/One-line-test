#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
反馈二维码弹窗
"""

import os
import sys

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QDialog, QFrame, QLabel, QVBoxLayout


def resource_path(*parts) -> str:
    """兼容源码运行和 PyInstaller 打包后的资源路径。"""
    if hasattr(sys, "_MEIPASS"):
        base_dir = sys._MEIPASS
    else:
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    return os.path.join(base_dir, *parts)


class FeedbackDialog(QDialog):
    """显示联系二维码的反馈弹窗。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("扫码反馈")
        self.setFixedSize(440, 520)
        self.setModal(True)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        qr_frame = QFrame()
        qr_frame.setObjectName("qrFrame")
        qr_layout = QVBoxLayout(qr_frame)
        qr_layout.setContentsMargins(14, 14, 14, 14)
        qr_layout.setSpacing(0)

        qr_label = QLabel()
        qr_label.setAlignment(Qt.AlignCenter)
        qr_label.setMinimumSize(380, 380)

        qr_path = resource_path("img", "联系我.jpg")
        qr_pixmap = QPixmap(qr_path)
        if qr_pixmap.isNull():
            qr_label.setText("未找到联系方式图片\nimg/联系我.jpg")
            qr_label.setStyleSheet(
                "color: #666666; font-size: 14px; background-color: white;"
            )
        else:
            qr_label.setPixmap(
                qr_pixmap.scaled(
                    380,
                    380,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation,
                )
            )

        tip_label = QLabel("请扫描二维码联系作者反馈问题")
        tip_label.setObjectName("tipLabel")
        tip_label.setAlignment(Qt.AlignCenter)
        tip_label.setWordWrap(True)

        qr_layout.addWidget(qr_label)
        layout.addWidget(qr_frame, 1)
        layout.addWidget(tip_label)

        self.setStyleSheet(
            """
            QDialog {
                background-color: #232831;
            }
            QFrame#qrFrame {
                background-color: white;
                border-radius: 4px;
            }
            QLabel#tipLabel {
                color: white;
                font-size: 15px;
                padding-bottom: 6px;
            }
            """
        )
