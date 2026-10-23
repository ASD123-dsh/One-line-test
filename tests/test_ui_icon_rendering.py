#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按钮图标对比度与页签圆角基线回归，仅使用离屏 Qt，不访问网络或串口。"""

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QPoint, QRect, QSize
from PyQt5.QtGui import QColor, QIcon, QPaintEvent
from PyQt5.QtWidgets import QApplication, QLabel, QStyleFactory, QTabWidget

from app_settings import SettingsStore
from gui.main_window import MainWindow
from gui.protocol_tabs import ProtocolTabs
from gui.soft_theme import PALETTE
from gui.ui_icons import button_icon, ui_icon
from serial_comm.serial_manager import SerialManager, SerialPortDetector

_APP = QApplication.instance() or QApplication([])
_BUTTON_SYMBOLS = ("refresh", "copy", "file", "trash")


def opaque_colors(icon, mode=QIcon.Normal):
    """只检查图标不透明笔画，避开透明背景和抗锯齿颜色舍入。"""
    image = icon.pixmap(QSize(36, 36), mode).toImage()
    return [image.pixelColor(x, y) for x in range(image.width()) for y in range(image.height())
            if image.pixelColor(x, y).alpha() == 255]


class ButtonIconTests(unittest.TestCase):
    """绿色按钮使用白色笔画，禁用状态仍可辨认，普通控件接口保持不变。"""

    def test_normal_active_selected_button_icons_are_white(self):
        """刷新、复制、配置和清空图标在启用、悬停及选中模式均为白色。"""
        for name in _BUTTON_SYMBOLS:
            for mode in (QIcon.Normal, QIcon.Active, QIcon.Selected):
                with self.subTest(name=name, mode=mode):
                    colors = opaque_colors(button_icon(name), mode)
                    self.assertGreater(len(colors), 8)
                    self.assertTrue(all(color == QColor(PALETTE["button_icon"]) for color in colors))

    def test_disabled_button_icons_use_explicit_gray(self):
        """禁用图标明确使用灰色，不让 Qt 把白色自动处理成难辨的浅灰。"""
        for name in _BUTTON_SYMBOLS:
            with self.subTest(name=name):
                colors = opaque_colors(button_icon(name), QIcon.Disabled)
                self.assertGreater(len(colors), 8)
                self.assertTrue(all(color == QColor(PALETTE["button_icon_disabled"]) for color in colors))

    def test_button_cache_size_and_legacy_dark_icon_are_preserved(self):
        """按钮缓存和双倍分辨率不变，新增白色角色不修改原深色图标。"""
        normal = ui_icon("copy")
        self.assertIs(button_icon("copy"), button_icon("copy"))
        self.assertIs(normal, ui_icon("copy"))
        self.assertEqual(button_icon("copy").availableSizes(), normal.availableSizes())
        self.assertTrue(all(color == QColor("#263c4b") for color in opaque_colors(normal)))


class IconWindowTests(unittest.TestCase):
    """真实主窗口的图标接入、圆角背景和原功能状态保持兼容。"""

    def setUp(self):
        """屏蔽端口扫描并使用内存配置，不读取客户授权或更新记录。"""
        for target, name, value in ((SerialPortDetector, "start_detection", None), (SerialManager, "scan_ports", []), (MainWindow, "refresh_recovery_notice", None)):
            stub = patch.object(target, name, return_value=value)
            stub.start()
            self.addCleanup(stub.stop)
        self.window = MainWindow(settings_store=SettingsStore())
        self.window.resize(1200, 800)
        self.window.show()
        _APP.processEvents()
        self.addCleanup(self.window.close)

    def assert_corner_background(self):
        """左右外角必须露出浅灰工作区，不能透出原生页签深色基线。"""
        _APP.processEvents()
        badge = self.window.parameter_mode_label
        origin = badge.mapTo(self.window, QPoint())
        pixels = self.window.grab().toImage()
        ratio = pixels.devicePixelRatio()
        for x in (0, badge.width() - 1):
            color = pixels.pixelColor(round((origin.x() + x) * ratio), round(origin.y() * ratio))
            self.assertEqual(color, QColor("#f0f0f0"))

    def test_four_button_icons_are_white_but_tools_icon_stays_dark(self):
        """只接入四个绿色按钮，浅色配置菜单的深色图标不被全局改白。"""
        self.window.frame_custom_radio.click()
        for button in (self.window.refresh_ports_btn, self.window.frame_config_btn, self.window.clear_history_btn, self.window.frame_preview.copy_button):
            with self.subTest(text=button.text()):
                colors = opaque_colors(button.icon())
                self.assertGreater(len(colors), 8)
                self.assertTrue(all(color == QColor("#ffffff") for color in colors))
        self.assertTrue(all(color == QColor("#263c4b") for color in opaque_colors(self.window.tools_btn.icon())))

    def test_all_three_parameter_modes_have_clean_rounded_corners(self):
        """预设预览、可编辑和原始帧编辑均无深色角落，标签文字保持原契约。"""
        for radio, text in ((self.window.normal_radio, "预设预览"), (self.window.custom_radio, "可编辑"), (self.window.frame_custom_radio, "原始帧编辑")):
            with self.subTest(text=text):
                radio.click()
                self.assertEqual(self.window.parameter_mode_label.text(), text)
                self.assert_corner_background()

    def test_available_windows_and_fusion_styles_have_no_corner_baseline(self):
        """在本机可用的 Windows 与 Fusion 样式下检查角落，不依赖单一皮肤。"""
        original = _APP.style().objectName()
        self.addCleanup(lambda: _APP.setStyle(original))
        self.window.frame_custom_radio.click()
        self.window.status_tabs.setCurrentIndex(3)
        for name in QStyleFactory.keys():
            if name.casefold() in ("windows", "windowsvista", "fusion"):
                with self.subTest(style=name):
                    _APP.setStyle(name)
                    self.assert_corner_background()

    def test_raw_frame_badge_stays_read_only_and_tab_browsing_keeps_configuration(self):
        """状态标签不变成新按钮，原始帧仍通过原帧配置入口编辑。"""
        self.window.frame_custom_radio.click()
        before = self.window.capture_configuration()
        self.assertIsInstance(self.window.parameter_mode_label, QLabel)
        self.assertTrue(self.window.frame_config_btn.isEnabled())
        for index in range(self.window.status_tabs.count()):
            self.window.status_tabs.setCurrentIndex(index)
            self.assertFalse(self.window.status_tabs.page_content(index).isEnabled())
        self.assertEqual(self.window.capture_configuration(), before)
        self.assertFalse(self.window.serial_manager.is_connected)
        self.assertFalse(self.window.serial_manager.is_cyclic_sending())


class ProtocolTabPaintTests(unittest.TestCase):
    """只取消文档模式多余基线；非文档模式保留 Qt 默认边框绘制。"""

    def test_native_paint_is_retained_outside_document_mode(self):
        """无边框文档模式不调用原生基线，切回普通模式仍委托原绘制入口。"""
        tabs = ProtocolTabs()
        self.addCleanup(tabs.close)
        event = QPaintEvent(QRect(0, 0, 100, 50))
        with patch.object(QTabWidget, "paintEvent") as native:
            tabs.paintEvent(event)
            native.assert_not_called()
            tabs.setDocumentMode(False)
            tabs.paintEvent(event)
            native.assert_called_once_with(event)


if __name__ == "__main__":
    unittest.main()
