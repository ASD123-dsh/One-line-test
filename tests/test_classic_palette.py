#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""经典配色的可读性、无布局变化和纯显示语义回归，不访问网络或真实串口。"""

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QApplication, QGroupBox, QPushButton, QVBoxLayout

from app_settings import SettingsStore
from gui.frame_preview import FramePreview
from gui.main_window import MainWindow
from gui.send_history import HistoryTableModel
from gui.soft_theme import PALETTE, PaletteCard, soft_glass_stylesheet
from protocol.definitions import PROTOCOL_LISHEN_BMS
from serial_comm.serial_manager import SerialManager, SerialPortDetector

_APP = QApplication.instance() or QApplication([])


def contrast_ratio(foreground, background):
    """按相对亮度计算不透明颜色对比度，避免表格中的低对比文字。"""
    def luminance(value):
        """把 sRGB 通道线性化，不依赖屏幕或截图采样。"""
        color = QColor(value)
        channels = [channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4
                    for channel in (color.redF(), color.greenF(), color.blueF())]
        return sum(channel * weight for channel, weight in zip(channels, (0.2126, 0.7152, 0.0722)))
    first, second = sorted((luminance(foreground), luminance(background)))
    return (second + 0.05) / (first + 0.05)


class PaletteContrastTests(unittest.TestCase):
    """白底深色数据及异常文字在所有语义底色上均应清晰可辨。"""

    def test_palette_colors_are_valid_and_data_area_is_classic_white(self):
        """关键色集中维护，经典白色数据底和深色字节文本不再使用深蓝终端配色。"""
        self.assertTrue(all(QColor(value).isValid() for value in PALETTE.values()))
        self.assertEqual(QColor(PALETTE["data_background"]), QColor("#ffffff"))
        self.assertLess(QColor(PALETTE["data_text"]).lightness(), 80)
        self.assertEqual(PALETTE["connected"], "#4caf50")

    def test_normal_changed_latest_and_error_rows_keep_readable_contrast(self):
        """普通、变化和最新行不能因换色让字节或索引消失。"""
        pairs = [(foreground, background)
                 for foreground in ("data_text", "data_secondary")
                 for background in ("data_background", "changed_row", "latest_row")]
        pairs.extend((("error_text", "error_row"), ("warning_text", "data_background"), ("caption_text", "caption_start")))
        for foreground, background in pairs:
            with self.subTest(foreground=foreground, background=background):
                self.assertGreaterEqual(contrast_ratio(PALETTE[foreground], PALETTE[background]), 4.5)

    def test_change_latest_and_error_colors_remain_distinct(self):
        """变化、最新写入和失败保持三种语义，不用同一种颜色混淆结果。"""
        self.assertEqual(len({PALETTE[key] for key in ("changed_row", "latest_row", "error_row")}), 3)
        self.assertNotEqual(PALETTE["connected"], PALETTE["disconnected"])


class PaletteCardTests(unittest.TestCase):
    """恢复 Qt 默认标题绘制，不通过新行、高度或内边距更改界面结构。"""

    def make_card(self, card_type):
        """建立与原 QGroupBox 相同的子布局供逐项度量。"""
        card = card_type("串口配置")
        card.setProperty("card", True)
        layout = QVBoxLayout(card)
        button = QPushButton("连接")
        layout.addWidget(button)
        card.setStyleSheet(soft_glass_stylesheet())
        card.resize(360, 160)
        card.show()
        _APP.processEvents()
        self.addCleanup(card.close)
        return card, button

    def test_card_size_hints_and_child_geometry_match_original_group(self):
        """经典标题绘制不改变原分组的尺寸提示、内容矩形或按钮位置。"""
        original, old_button = self.make_card(QGroupBox)
        colored, new_button = self.make_card(PaletteCard)
        self.assertEqual(colored.sizeHint(), original.sizeHint())
        self.assertEqual(colored.minimumSizeHint(), original.minimumSizeHint())
        self.assertEqual(colored.contentsRect(), original.contentsRect())
        self.assertEqual(new_button.geometry(), old_button.geometry())

    def test_header_and_body_are_classic_gray_without_dark_strip(self):
        """标题及内容均为经典浅灰，不再覆盖深色标题条或遮挡下方控件。"""
        card, button = self.make_card(PaletteCard)
        before = button.geometry()
        pixels = card.grab().toImage()
        header = pixels.pixelColor(card.width() - 16, 10)
        body = pixels.pixelColor(card.width() - 16, card.height() - 16)
        self.assertEqual(header, QColor("#f0f0f0"))
        self.assertEqual(body, QColor("#f0f0f0"))
        self.assertEqual(button.geometry(), before)

    def test_buttons_restore_green_and_disabled_gray_without_resizing(self):
        """按钮恢复经典绿和禁用灰，主按钮的尺寸不因状态或颜色变化。"""
        _, button = self.make_card(PaletteCard)
        original = button.geometry()
        self.assertEqual(button.grab().toImage().pixelColor(8, button.height() // 2), QColor("#4caf50"))
        button.setProperty("visualRole", "primary")
        button.setEnabled(False)
        _APP.processEvents()
        self.assertEqual(button.grab().toImage().pixelColor(8, button.height() // 2), QColor("#cccccc"))
        self.assertEqual(button.geometry(), original)


class DataPaletteTests(unittest.TestCase):
    """数据层保持不变，只替换 Qt 显示角色与只读表格颜色。"""

    def test_preview_color_roles_do_not_change_raw_bytes_or_descriptions(self):
        """所有列恢复深色文字，原说明和 F6 不被显示颜色改写。"""
        preview = FramePreview()
        self.addCleanup(preview.close)
        frame = [0, 50, 48, 246, 0, 88]
        preview.set_frame(PROTOCOL_LISHEN_BMS, frame, ["", "", "", "温度补码", "", "SUM"])
        self.assertEqual(preview.table.item(3, 1).foreground().color(), QColor(PALETTE["data_text"]))
        self.assertEqual(preview.table.item(3, 0).foreground().color(), QColor(PALETTE["data_secondary"]))
        self.assertEqual(preview.table.item(3, 1).text(), "F6")
        self.assertEqual(preview.table.item(3, 2).text(), "246")
        self.assertIn("温度补码", preview.table.item(3, 3).toolTip())
        self.assertEqual(frame, [0, 50, 48, 246, 0, 88])

    def test_changed_row_still_copies_exact_snapshot(self):
        """浅黄高亮不影响复制，也不会把颜色信息写进实际帧。"""
        preview = FramePreview()
        self.addCleanup(preview.close)
        preview.set_frame(PROTOCOL_LISHEN_BMS, [0, 50, 48, 25, 0, 123], [])
        preview.set_frame(PROTOCOL_LISHEN_BMS, [0, 50, 48, 246, 0, 88], [])
        self.assertEqual(preview.table.item(3, 1).background().color(), QColor(PALETTE["changed_row"]))
        preview.copy_frame()
        self.assertEqual(_APP.clipboard().text(), "00 32 30 F6 00 58")

    def test_history_color_roles_distinguish_time_frame_error_and_hint(self):
        """深色时间和帧、红色失败和棕色提示保留原日志分类。"""
        model = HistoryTableModel()
        model.append_lines(["[10:00:00.000] 发送成功: 00 32", "[10:00:01.000] 发送失败: 断开", "[时序提示] 缓冲"])
        for row, column, color in ((0, 0, "data_secondary"), (0, 2, "data_text"), (1, 2, "error_text"), (2, 2, "warning_text")):
            with self.subTest(row=row, column=column):
                self.assertEqual(model.data(model.index(row, column), Qt.ForegroundRole), QColor(PALETTE[color]))
        self.assertEqual(model.data(model.index(0, 2)), "00 32")
        self.assertEqual(model.data(model.index(1, 1)), "发送失败")

    def test_main_keeps_six_original_cards_and_no_automatic_sending(self):
        """换色仍是原六个区域，不新增页签、改变发送间隔或自动连接。"""
        with patch.object(SerialPortDetector, "start_detection"), patch.object(SerialManager, "scan_ports", return_value=[]):
            window = MainWindow(settings_store=SettingsStore())
            self.addCleanup(window.close)
            self.assertEqual(len([card for card in window.findChildren(PaletteCard) if card.property("card")]), 6)
            self.assertEqual(window.status_tabs.count(), 5)
            self.assertEqual(window.interval_spin.value(), 500)
            self.assertEqual(window.clear_history_btn.objectName(), "clearHistoryButton")
            self.assertFalse(window.serial_manager.is_connected)
            self.assertFalse(window.serial_manager.is_cyclic_sending())


if __name__ == "__main__":
    unittest.main()
