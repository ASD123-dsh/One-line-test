#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Standalone activation code generator window."""

import sys
from datetime import datetime, timedelta
from pathlib import Path

import rsa
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from licensing.activation import (  # noqa: E402
    DEFAULT_VALIDITY_UNIT,
    DEFAULT_VALIDITY_VALUE,
    DURATION_UNITS,
    build_validity_seconds,
    describe_validity_duration,
    generate_activation_code,
    get_current_device_code,
    normalize_device_code,
)

DEFAULT_PRIVATE_KEY_PATH = ROOT_DIR / "keys" / "activation_private.pem"
DEFAULT_OUTPUT_PATH = Path(__file__).resolve().parent / "activation_code.txt"
UNIT_ORDER = ["hours", "days", "weeks", "months", "years"]


def load_private_key(path: Path) -> rsa.PrivateKey:
    with path.open("rb") as file_obj:
        return rsa.PrivateKey.load_pkcs1(file_obj.read())


def save_activation_code_file(
    device_code: str,
    activation_code: str,
    validity_text: str,
    expires_at_text: str,
    output_path: Path = DEFAULT_OUTPUT_PATH,
) -> Path:
    output_path.write_text(
        "\n".join(
            [
                f"设备码: {device_code}",
                f"有效时长: {validity_text}",
                f"到期时间: {expires_at_text}",
                f"激活码: {activation_code}",
                f"生成时间: {datetime.now().isoformat(timespec='seconds')}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return output_path


class ActivationToolWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("激活码工具")
        self.resize(780, 460)
        self._build_ui()
        self.fill_current_device_code()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(14, 14, 14, 14)
        root_layout.setSpacing(12)

        tip_label = QLabel("输入客户设备码，设置有效时长，选择本地私钥文件，即可生成激活码。")
        tip_label.setWordWrap(True)
        root_layout.addWidget(tip_label)

        form_layout = QGridLayout()
        form_layout.setHorizontalSpacing(10)
        form_layout.setVerticalSpacing(10)

        form_layout.addWidget(QLabel("设备码"), 0, 0)
        self.device_code_edit = QLineEdit()
        self.device_code_edit.setPlaceholderText("粘贴客户发来的设备码")
        form_layout.addWidget(self.device_code_edit, 0, 1)

        self.fill_device_btn = QPushButton("读取本机")
        self.fill_device_btn.clicked.connect(self.fill_current_device_code)
        form_layout.addWidget(self.fill_device_btn, 0, 2)

        self.copy_device_btn = QPushButton("复制")
        self.copy_device_btn.clicked.connect(self.copy_device_code)
        form_layout.addWidget(self.copy_device_btn, 0, 3)

        form_layout.addWidget(QLabel("有效时长"), 1, 0)
        validity_row = QHBoxLayout()
        validity_row.setContentsMargins(0, 0, 0, 0)
        validity_row.setSpacing(8)
        self.validity_value_spin = QSpinBox()
        self.validity_value_spin.setRange(1, 99999)
        self.validity_value_spin.setValue(DEFAULT_VALIDITY_VALUE)
        validity_row.addWidget(self.validity_value_spin)

        self.validity_unit_combo = QComboBox()
        for unit in UNIT_ORDER:
            self.validity_unit_combo.addItem(DURATION_UNITS[unit][0], unit)
        self.validity_unit_combo.setCurrentIndex(UNIT_ORDER.index(DEFAULT_VALIDITY_UNIT))
        validity_row.addWidget(self.validity_unit_combo)
        validity_row.addStretch()
        form_layout.addLayout(validity_row, 1, 1)

        form_layout.addWidget(QLabel("私钥文件"), 2, 0)
        self.private_key_edit = QLineEdit(str(DEFAULT_PRIVATE_KEY_PATH))
        form_layout.addWidget(self.private_key_edit, 2, 1)

        self.browse_key_btn = QPushButton("浏览")
        self.browse_key_btn.clicked.connect(self.browse_private_key)
        form_layout.addWidget(self.browse_key_btn, 2, 2)

        self.generate_btn = QPushButton("生成激活码")
        self.generate_btn.clicked.connect(self.generate_code)
        form_layout.addWidget(self.generate_btn, 2, 3)

        root_layout.addLayout(form_layout)

        result_label = QLabel("激活码")
        root_layout.addWidget(result_label)

        self.result_edit = QLineEdit()
        self.result_edit.setReadOnly(True)
        self.result_edit.setPlaceholderText("生成结果会显示在这里")
        root_layout.addWidget(self.result_edit, 1)

        action_row = QHBoxLayout()
        self.copy_result_btn = QPushButton("复制激活码")
        self.copy_result_btn.clicked.connect(self.copy_result)
        action_row.addWidget(self.copy_result_btn)

        self.clear_btn = QPushButton("清空结果")
        self.clear_btn.clicked.connect(self.clear_result)
        action_row.addWidget(self.clear_btn)

        action_row.addStretch()
        root_layout.addLayout(action_row)

        self.status_label = QLabel("就绪")
        self.status_label.setStyleSheet("color: #666666;")
        root_layout.addWidget(self.status_label)

        self.setStyleSheet(
            """
            QMainWindow {
                background-color: #f6f7fb;
            }
            QLineEdit {
                background-color: white;
                border: 1px solid #cfd6e4;
                border-radius: 4px;
                padding: 6px 8px;
            }
            QPushButton {
                background-color: #4CAF50;
                border: none;
                color: white;
                padding: 7px 14px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3d8b40;
            }
            """
        )

    def fill_current_device_code(self):
        self.device_code_edit.setText(get_current_device_code())
        self.status_label.setText("已读取本机设备码")

    def copy_device_code(self):
        text = self.device_code_edit.text().strip()
        if not text:
            QMessageBox.warning(self, "提示", "没有可复制的设备码。")
            return
        QApplication.clipboard().setText(text)
        self.status_label.setText("设备码已复制")

    def browse_private_key(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择私钥文件",
            str(DEFAULT_PRIVATE_KEY_PATH.parent),
            "PEM 文件 (*.pem);;所有文件 (*)",
        )
        if path:
            self.private_key_edit.setText(path)

    def _current_validity(self):
        value = self.validity_value_spin.value()
        unit = self.validity_unit_combo.currentData()
        validity_seconds = build_validity_seconds(value, unit)
        validity_text = describe_validity_duration(value, unit)
        expires_at = datetime.now() + timedelta(seconds=validity_seconds)
        return validity_seconds, validity_text, expires_at

    def generate_code(self):
        device_code = normalize_device_code(self.device_code_edit.text())
        if not device_code:
            QMessageBox.warning(self, "提示", "请输入设备码。")
            return

        private_key_path = Path(self.private_key_edit.text().strip())
        if not private_key_path.exists():
            QMessageBox.warning(self, "提示", f"未找到私钥文件：{private_key_path}")
            return

        try:
            private_key = load_private_key(private_key_path)
            validity_seconds, validity_text, expires_at = self._current_validity()
            activation_code = generate_activation_code(
                device_code,
                private_key,
                validity_seconds=validity_seconds,
            )
        except Exception as exc:
            QMessageBox.critical(self, "生成失败", f"激活码生成失败：{exc}")
            return

        try:
            output_path = save_activation_code_file(
                device_code,
                activation_code,
                validity_text,
                expires_at.isoformat(timespec="seconds"),
            )
        except OSError as exc:
            QMessageBox.critical(self, "保存失败", f"激活码已生成，但写入 TXT 失败：{exc}")
            self.status_label.setText("激活码已生成，但保存失败")
            return

        self.result_edit.setText(activation_code)
        self.status_label.setText(f"激活码已保存到 {output_path}")

    def copy_result(self):
        text = self.result_edit.text().strip()
        if not text:
            QMessageBox.warning(self, "提示", "没有可复制的激活码。")
            return
        QApplication.clipboard().setText(text)
        self.status_label.setText("激活码已复制")

    def clear_result(self):
        self.result_edit.clear()
        self.status_label.setText("已清空结果")


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("激活码工具")
    app.setOrganizationName("AD仪表")
    window = ActivationToolWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
