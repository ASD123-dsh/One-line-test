#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Packet sequence editor for cyclic multi-frame sending."""

from typing import Callable, List, Optional

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from gui.frame_config_dialog import FrameConfigDialog


class PacketSequenceDialog(QDialog):
    def __init__(
        self,
        parent=None,
        initial_frames: Optional[List[List[int]]] = None,
        byte_descriptions: Optional[List[str]] = None,
        dialog_title: str = "包组配置",
        checksum_mode: str = "xor",
        default_frame_provider: Optional[Callable[[], List[int]]] = None,
    ):
        super().__init__(parent)
        self.byte_descriptions = byte_descriptions or []
        self.dialog_title = dialog_title
        self.checksum_mode = checksum_mode
        self.default_frame_provider = default_frame_provider
        self.frame_length = len(self.byte_descriptions) or 12
        self.frames: List[List[int]] = [
            frame.copy() for frame in (initial_frames or []) if frame is not None
        ]

        if not self.frames:
            self.frames.append(self._make_default_frame())

        self.frame_config_dialog = None
        self.init_ui()
        self.refresh_list()
        self.update_preview()

    def init_ui(self):
        self.setWindowTitle(self.dialog_title)
        self.resize(980, 620)

        root_layout = QVBoxLayout(self)
        root_layout.addWidget(QLabel("可维护多组数据包，并按列表顺序循环发送。"))

        splitter = QSplitter(Qt.Horizontal)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        self.frame_list = QListWidget()
        self.frame_list.currentRowChanged.connect(lambda *_: self.update_preview())
        self.frame_list.itemDoubleClicked.connect(lambda *_: self.edit_selected_frame())
        left_layout.addWidget(self.frame_list)

        button_row = QHBoxLayout()
        self.add_current_btn = QPushButton("新增当前帧")
        self.add_current_btn.clicked.connect(self.add_current_frame)
        button_row.addWidget(self.add_current_btn)

        self.add_blank_btn = QPushButton("新增空白帧")
        self.add_blank_btn.clicked.connect(self.add_blank_frame)
        button_row.addWidget(self.add_blank_btn)
        left_layout.addLayout(button_row)

        action_row = QHBoxLayout()
        self.edit_btn = QPushButton("编辑")
        self.edit_btn.clicked.connect(self.edit_selected_frame)
        action_row.addWidget(self.edit_btn)

        self.copy_btn = QPushButton("复制")
        self.copy_btn.clicked.connect(self.copy_selected_frame)
        action_row.addWidget(self.copy_btn)
        left_layout.addLayout(action_row)

        move_row = QHBoxLayout()
        self.up_btn = QPushButton("上移")
        self.up_btn.clicked.connect(self.move_selected_up)
        move_row.addWidget(self.up_btn)

        self.down_btn = QPushButton("下移")
        self.down_btn.clicked.connect(self.move_selected_down)
        move_row.addWidget(self.down_btn)

        self.delete_btn = QPushButton("删除")
        self.delete_btn.clicked.connect(self.delete_selected_frame)
        move_row.addWidget(self.delete_btn)
        left_layout.addLayout(move_row)

        splitter.addWidget(left_panel)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        self.summary_label = QLabel()
        self.summary_label.setFont(QFont("Consolas", 10))
        right_layout.addWidget(self.summary_label)

        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setFont(QFont("Consolas", 9))
        right_layout.addWidget(self.preview_text)

        splitter.addWidget(right_panel)
        splitter.setSizes([420, 560])
        root_layout.addWidget(splitter, 1)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self._on_accept)
        button_box.rejected.connect(self.reject)
        root_layout.addWidget(button_box)

    def _make_default_frame(self) -> List[int]:
        if self.default_frame_provider is not None:
            try:
                frame_data = self.default_frame_provider()
                if frame_data:
                    return frame_data.copy()
            except Exception:
                pass
        return [0] * self.frame_length

    def _frame_text(self, index: int, frame: List[int]) -> str:
        return f"包{index + 1:02d}  {len(frame)}字节  {' '.join(f'{b:02X}' for b in frame)}"

    def refresh_list(self):
        current_row = self.frame_list.currentRow()
        self.frame_list.clear()
        for index, frame in enumerate(self.frames):
            self.frame_list.addItem(QListWidgetItem(self._frame_text(index, frame)))
        if self.frames:
            self.frame_list.setCurrentRow(min(max(current_row, 0), len(self.frames) - 1))
        self._update_controls()

    def _update_controls(self):
        has_selection = self.frame_list.currentRow() >= 0
        can_move_up = has_selection and self.frame_list.currentRow() > 0
        can_move_down = has_selection and self.frame_list.currentRow() < len(self.frames) - 1
        self.edit_btn.setEnabled(has_selection)
        self.copy_btn.setEnabled(has_selection)
        self.delete_btn.setEnabled(has_selection)
        self.up_btn.setEnabled(can_move_up)
        self.down_btn.setEnabled(can_move_down)
        self.summary_label.setText(f"当前共 {len(self.frames)} 组数据包")

    def update_preview(self):
        self._update_controls()
        row = self.frame_list.currentRow()
        if row < 0 or row >= len(self.frames):
            self.preview_text.setPlainText("请选择一组数据包")
            return

        frame = self.frames[row]
        hex_str = " ".join(f"{b:02X}" for b in frame)
        dec_str = " ".join(f"{b:3d}" for b in frame)
        self.preview_text.setPlainText(
            f"包序号: {row + 1}\n"
            f"HEX: {hex_str}\n"
            f"DEC: {dec_str}"
        )

    def _open_editor(self, frame: List[int], title: str) -> Optional[List[int]]:
        dialog = FrameConfigDialog(
            self,
            frame,
            byte_descriptions=self.byte_descriptions,
            dialog_title=title,
            checksum_mode=self.checksum_mode,
        )
        self.frame_config_dialog = dialog
        if dialog.exec_() == QDialog.Accepted:
            return dialog.get_frame_data()
        return None

    def add_current_frame(self):
        frame = self._make_default_frame()
        edited = self._open_editor(frame, f"{self.dialog_title} - 新增数据包")
        if edited is None:
            return
        self.frames.append(edited)
        self.refresh_list()
        self.frame_list.setCurrentRow(len(self.frames) - 1)

    def add_blank_frame(self):
        edited = self._open_editor([0] * self.frame_length, f"{self.dialog_title} - 新增空白包")
        if edited is None:
            return
        self.frames.append(edited)
        self.refresh_list()
        self.frame_list.setCurrentRow(len(self.frames) - 1)

    def edit_selected_frame(self):
        row = self.frame_list.currentRow()
        if row < 0 or row >= len(self.frames):
            return

        edited = self._open_editor(self.frames[row], f"{self.dialog_title} - 编辑数据包 {row + 1}")
        if edited is None:
            return
        self.frames[row] = edited
        self.refresh_list()
        self.frame_list.setCurrentRow(row)

    def copy_selected_frame(self):
        row = self.frame_list.currentRow()
        if row < 0 or row >= len(self.frames):
            return
        self.frames.insert(row + 1, self.frames[row].copy())
        self.refresh_list()
        self.frame_list.setCurrentRow(row + 1)

    def move_selected_up(self):
        row = self.frame_list.currentRow()
        if row <= 0:
            return
        self.frames[row - 1], self.frames[row] = self.frames[row], self.frames[row - 1]
        self.refresh_list()
        self.frame_list.setCurrentRow(row - 1)

    def move_selected_down(self):
        row = self.frame_list.currentRow()
        if row < 0 or row >= len(self.frames) - 1:
            return
        self.frames[row + 1], self.frames[row] = self.frames[row], self.frames[row + 1]
        self.refresh_list()
        self.frame_list.setCurrentRow(row + 1)

    def delete_selected_frame(self):
        row = self.frame_list.currentRow()
        if row < 0 or row >= len(self.frames):
            return
        if len(self.frames) == 1:
            QMessageBox.warning(self, "提示", "至少保留一组数据包")
            return
        del self.frames[row]
        self.refresh_list()
        self.frame_list.setCurrentRow(min(row, len(self.frames) - 1))

    def _on_accept(self):
        if not self.frames:
            QMessageBox.warning(self, "提示", "请至少配置一组数据包")
            return
        self.accept()

    def get_frames(self) -> List[List[int]]:
        return [frame.copy() for frame in self.frames]
