#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Packet sequence editor for cyclic multi-frame sending."""

import json
import os
from datetime import datetime
from typing import Callable, List, Optional

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QFileDialog,
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
from protocol.frame_utils import normalize_frame, validate_frame_length

PACKET_SEQUENCE_FILE_MAGIC = "sifexe.packet_sequence"
PACKET_SEQUENCE_FILE_VERSION = 1


def _normalize_frame(frame, expected_length: Optional[int] = None) -> List[int]:
    """兼容旧调用入口，统一使用公共帧校验器。"""

    return normalize_frame(
        frame,
        expected_length=expected_length,
        label="数据帧",
    )


def build_packet_sequence_payload(
    frames,
    frame_length: int,
    dialog_title: str = "",
    checksum_mode: str = "xor",
    byte_descriptions: Optional[List[str]] = None,
):
    frame_length = validate_frame_length(frame_length)
    if not isinstance(frames, (list, tuple)):
        raise ValueError("数据包组必须是帧列表")
    normalized_frames = [
        _normalize_frame(frame, expected_length=frame_length)
        for frame in frames
    ]
    if not normalized_frames:
        raise ValueError("至少需要一组数据包")

    return {
        "format": PACKET_SEQUENCE_FILE_MAGIC,
        "version": PACKET_SEQUENCE_FILE_VERSION,
        "dialog_title": dialog_title,
        "checksum_mode": checksum_mode,
        "frame_length": frame_length,
        "byte_descriptions": byte_descriptions or [],
        "frame_count": len(normalized_frames),
        "frames": normalized_frames,
    }


def load_packet_sequence_payload(payload, expected_frame_length: int) -> List[List[int]]:
    expected_frame_length = validate_frame_length(expected_frame_length, "当前协议帧长度")

    if isinstance(payload, dict):
        file_format = payload.get("format")
        if file_format not in (None, PACKET_SEQUENCE_FILE_MAGIC):
            raise ValueError("不支持的包组文件格式")

        file_version = payload.get("version")
        if file_version is not None and (
            isinstance(file_version, bool)
            or not isinstance(file_version, int)
            or file_version != PACKET_SEQUENCE_FILE_VERSION
        ):
            raise ValueError(f"不支持的包组文件版本：{file_version}")
        if file_format == PACKET_SEQUENCE_FILE_MAGIC and file_version is None:
            raise ValueError("包组文件中缺少 version 字段")

        file_length = payload.get("frame_length")
        if file_length is not None:
            validate_frame_length(file_length, "文件帧长度")
            if file_length != expected_frame_length:
                raise ValueError(
                    f"文件帧长度为 {file_length} 字节，"
                    f"当前协议需要 {expected_frame_length} 字节"
                )

        frames = payload.get("frames")
        if frames is None:
            raise ValueError("文件中缺少 frames 字段")
        if not isinstance(frames, (list, tuple)):
            raise ValueError("文件中的 frames 字段必须是帧列表")

        frame_count = payload.get("frame_count")
        if frame_count is not None:
            if (
                isinstance(frame_count, bool)
                or not isinstance(frame_count, int)
                or frame_count < 0
            ):
                raise ValueError("文件中的 frame_count 必须是非负整数")
            if frame_count != len(frames):
                raise ValueError("文件中的 frame_count 与实际帧数量不一致")
    elif isinstance(payload, list):
        frames = payload
    else:
        raise ValueError("包组文件内容格式错误")

    normalized_frames = [
        _normalize_frame(frame, expected_length=expected_frame_length)
        for frame in frames
    ]
    if not normalized_frames:
        raise ValueError("包组文件中没有可用数据包")

    return normalized_frames


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
            _normalize_frame(frame, expected_length=self.frame_length)
            for frame in (initial_frames or [])
            if frame is not None
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

        file_row = QHBoxLayout()
        self.export_btn = QPushButton("导出包组")
        self.export_btn.clicked.connect(self.export_frames_to_file)
        file_row.addWidget(self.export_btn)

        self.import_btn = QPushButton("导入包组")
        self.import_btn.clicked.connect(self.import_frames_from_file)
        file_row.addWidget(self.import_btn)
        left_layout.addLayout(file_row)

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
            frame_data = self.default_frame_provider()
            if frame_data is None:
                raise ValueError("当前协议未能生成默认数据帧")
            return _normalize_frame(
                frame_data,
                expected_length=self.frame_length,
            )
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
        try:
            frame = self._make_default_frame()
        except ValueError as exc:
            QMessageBox.critical(self, "帧生成失败", str(exc))
            return
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

    def _default_export_filename(self) -> str:
        safe_title = "".join(
            ch if ch.isalnum() or ch in ("-", "_") else "_"
            for ch in self.dialog_title
        ).strip("_")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{safe_title or 'packet_sequence'}_{timestamp}.json"

    def export_frames_to_file(self):
        path, _ = QFileDialog.getSaveFileName(
            self,
            "导出包组文件",
            self._default_export_filename(),
            "包组文件 (*.json);;所有文件 (*)",
        )
        if not path:
            return

        if not os.path.splitext(path)[1]:
            path += ".json"

        try:
            payload = build_packet_sequence_payload(
                self.frames,
                frame_length=self.frame_length,
                dialog_title=self.dialog_title,
                checksum_mode=self.checksum_mode,
                byte_descriptions=self.byte_descriptions,
            )
            with open(path, "w", encoding="utf-8") as file_obj:
                json.dump(payload, file_obj, ensure_ascii=False, indent=2)
        except (OSError, ValueError) as exc:
            QMessageBox.critical(self, "导出失败", f"包组导出失败：{exc}")
            return

        QMessageBox.information(self, "导出成功", f"已导出到：{path}")

    def import_frames_from_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "导入包组文件",
            "",
            "包组文件 (*.json);;所有文件 (*)",
        )
        if not path:
            return

        try:
            with open(path, "r", encoding="utf-8-sig") as file_obj:
                payload = json.load(file_obj)
            imported_frames = load_packet_sequence_payload(payload, self.frame_length)
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
            QMessageBox.critical(self, "导入失败", f"包组导入失败：{exc}")
            return

        reply = QMessageBox.question(
            self,
            "确认导入",
            f"将使用文件中的 {len(imported_frames)} 组数据包替换当前包组，是否继续？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        self.frames = [frame.copy() for frame in imported_frames]
        self.refresh_list()
        self.frame_list.setCurrentRow(0)
        QMessageBox.information(self, "导入成功", f"已从文件导入 {len(self.frames)} 组数据包")

    def _on_accept(self):
        if not self.frames:
            QMessageBox.warning(self, "提示", "请至少配置一组数据包")
            return
        self.accept()

    def get_frames(self) -> List[List[int]]:
        return [frame.copy() for frame in self.frames]
