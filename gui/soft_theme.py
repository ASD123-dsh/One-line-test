#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""经典浅灰与绿色配色，仅管理外观，不改变控件几何或协议、串口、升级状态。"""

from PyQt5.QtWidgets import QGroupBox

from app_paths import resource_path

PALETTE = {
    "caption_start": "#f0f0f0", "caption_end": "#f0f0f0", "caption_text": "#202020",
    "data_background": "#ffffff", "data_text": "#202020", "data_secondary": "#404040",
    "changed_row": "#fff2cc", "latest_row": "#e9f5e9", "error_row": "#fdeaea",
    "error_text": "#a12622", "warning_text": "#7c5900", "accent_blue": "#1267c5",
    "connected": "#4caf50", "disconnected": "#e53935", "grip": "#a0a0a0",
    "badge_ready": "#2e7d32", "badge_running": "#1267c5", "badge_error": "#c62828",
    "badge_muted": "#666666",
    "button_icon": "#ffffff", "button_icon_disabled": "#707070",
}


class PaletteCard(QGroupBox):
    """保留现有分组入口与几何；恢复 Qt 标题绘制，不再叠加深色标题条。"""


def set_visual_property(widget, name, value):
    """按角色刷新样式；属性未变时不重复重绘，避免干扰高频发送界面。"""
    if widget.property(name) == value:
        return
    widget.setProperty(name, value)
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)
    widget.update()


def set_badge_tone(widget, tone):
    """统一连接、只读与发送提示的状态色，保留原状态文本与行为。"""
    set_visual_property(widget, "badgeTone", tone)


def soft_glass_stylesheet():
    """保留已有主题函数入口和全部尺寸规则，仅恢复经典浅灰、绿色与白底配色。"""
    check_path = resource_path("img", "ui", "check.svg").replace("\\", "/")
    radio_path = resource_path("img", "ui", "radio.svg").replace("\\", "/")
    down_path = resource_path("img", "ui", "chevron-down.svg").replace("\\", "/")
    up_path = resource_path("img", "ui", "chevron-up.svg").replace("\\", "/")
    return """
        QMainWindow
        {
            background: #f0f0f0;
            color: #202020;
        }
        QWidget#workspace, QWidget#controlPanel, QWidget#monitorPanel,
        QWidget#protocolPage, QWidget#framePreview, QWidget#historyEmptyState,
        QScrollArea#protocolPageScroll,
        QScrollArea#protocolPageScroll > QWidget > QWidget,
        QScrollArea#controlPanelScroll, QScrollArea#controlPanelScroll > QWidget
        {
            background: transparent;
        }
        QFrame#windowActionBar
        {
            background: #f0f0f0;
            border-bottom: 1px solid #d0d0d0;
        }
        QLabel#windowActionTitle
        {
            color: #202020;
            font-size: 11pt;
            font-weight: bold;
        }
        QLabel
        {
            color: #202020;
            background: transparent;
        }
        QLabel[muted="true"]
        {
            color: #707070;
        }
        QGroupBox
        {
            background: transparent;
            border: none;
            margin-top: 11px;
            padding-top: 10px;
            font-weight: bold;
            color: #202020;
        }
        QGroupBox[card="true"]
        {
            background: #f0f0f0;
            border: 1px solid #cccccc;
            border-radius: 7px;
            margin-top: 8px;
            padding-top: 10px;
        }
        QGroupBox::title
        {
            subcontrol-origin: margin;
            left: 13px;
            padding: 0 5px;
        }
        QGroupBox[card="true"]::title
        {
            color: #202020;
            background: #f0f0f0;
        }
        QPushButton, QToolButton#toolsButton
        {
            min-height: 18px;
            padding: 3px 12px;
            color: #ffffff;
            background: #4caf50;
            border: 1px solid #4caf50;
            border-radius: 5px;
        }
        QPushButton:hover, QToolButton#toolsButton:hover
        {
            background: #45a049;
            border-color: #45a049;
        }
        QPushButton:pressed, QToolButton#toolsButton:pressed
        {
            background: #388e3c;
        }
        QPushButton[visualRole="primary"]
        {
            color: #ffffff;
            background: #4caf50;
            border-color: #4caf50;
            font-weight: bold;
        }
        QPushButton[visualRole="primary"]:hover
        {
            background: #45a049;
        }
        QPushButton[visualRole="primary"]:pressed
        {
            background: #388e3c;
        }
        QPushButton:disabled, QPushButton[visualRole="primary"]:disabled
        {
            color: #707070;
            background: #cccccc;
            border-color: #cccccc;
        }
        QPushButton#connectButton
        {
            padding-top: 6px;
            padding-bottom: 6px;
            font-weight: bold;
        }
        QPushButton#connectButton[visualRole="primary"]
        {
            color: #ffffff;
            background: #4caf50;
            border-color: #4caf50;
        }
        QPushButton#connectButton[visualRole="secondary"]
        {
            color: #ffffff;
            background: #f44336;
            border-color: #f44336;
        }
        QPushButton#clearHistoryButton:enabled
        {
            color: #ffffff;
            background: #4caf50;
            border-color: #4caf50;
        }
        QToolButton#toolsButton
        {
            color: #202020;
            background: #fafafa;
            border-color: #bdbdbd;
        }
        QToolButton#toolsButton:hover
        {
            background: #e8e8e8;
            border-color: #a0a0a0;
        }
        QToolButton#toolsButton:pressed
        {
            background: #d8d8d8;
        }
        QToolButton#toolsButton::menu-indicator
        {
            image: none;
            width: 0;
        }
        QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox
        {
            color: #202020;
            background: #ffffff;
            border: 1px solid #bdbdbd;
            border-radius: 4px;
            padding: 3px 7px;
            min-height: 17px;
            selection-background-color: #cce4f7;
            selection-color: #202020;
        }
        QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus
        {
            border-color: #1267c5;
        }
        QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled
        {
            color: #808080;
            background: #eeeeee;
            border-color: #d0d0d0;
        }
        QComboBox::drop-down
        {
            width: 22px;
            border: none;
        }
        QComboBox
        {
            padding-right: 25px;
        }
        QComboBox::down-arrow
        {
            image: url("__DOWN_PATH__");
            width: 11px;
            height: 11px;
        }
        QSpinBox::up-button, QDoubleSpinBox::up-button
        {
            subcontrol-origin: border;
            subcontrol-position: top right;
            width: 19px;
            border: none;
            border-left: 1px solid #d0d0d0;
            border-top-right-radius: 4px;
            background: #eeeeee;
        }
        QSpinBox::down-button, QDoubleSpinBox::down-button
        {
            subcontrol-origin: border;
            subcontrol-position: bottom right;
            width: 19px;
            border: none;
            border-left: 1px solid #d0d0d0;
            border-bottom-right-radius: 4px;
            background: #eeeeee;
        }
        QSpinBox::up-arrow, QDoubleSpinBox::up-arrow
        {
            image: url("__UP_PATH__");
            width: 9px;
            height: 9px;
        }
        QSpinBox::down-arrow, QDoubleSpinBox::down-arrow
        {
            image: url("__DOWN_PATH__");
            width: 9px;
            height: 9px;
        }
        QCheckBox, QRadioButton
        {
            color: #202020;
            spacing: 7px;
            font-weight: normal;
        }
        QCheckBox:disabled, QRadioButton:disabled
        {
            color: #808080;
        }
        QCheckBox::indicator, QRadioButton::indicator
        {
            width: 14px;
            height: 14px;
            background: #ffffff;
            border: 1px solid #b0b0b0;
        }
        QCheckBox::indicator
        {
            border-radius: 3px;
        }
        QRadioButton::indicator
        {
            border-radius: 7px;
        }
        QCheckBox::indicator:checked
        {
            background: #1267c5;
            border-color: #1267c5;
            image: url("__CHECK_PATH__");
        }
        QRadioButton::indicator:checked
        {
            border-color: #1267c5;
            image: url("__RADIO_PATH__");
        }
        QCheckBox::indicator:checked:disabled
        {
            background: #a0a0a0;
            border-color: #a0a0a0;
        }
        QTabWidget::pane
        {
            border: none;
            background: transparent;
        }
        QTabBar::tab
        {
            color: #606060;
            background: transparent;
            border: none;
            border-bottom: 2px solid transparent;
            padding: 6px 9px;
            margin-right: 2px;
            font-weight: normal;
        }
        QTabBar::tab:selected
        {
            color: #1267c5;
            border-bottom-color: #1267c5;
            /* 保持同一字重，避免 Qt 5 高缩放下选中页签按旧字宽裁切首字。 */
            font-weight: normal;
        }
        QTabBar::tab:hover
        {
            background: #e4e4e4;
        }
        QScrollArea
        {
            border: none;
        }
        QScrollBar:vertical
        {
            width: 9px;
            background: transparent;
            margin: 0;
        }
        QScrollBar::handle:vertical
        {
            background: #b0b0b0;
            border-radius: 4px;
            min-height: 24px;
        }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical
        {
            height: 0;
        }
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical
        {
            background: transparent;
        }
        QSplitter::handle
        {
            background: transparent;
        }
        QSplitter::handle:hover
        {
            background: #d5d5d5;
        }
        QTextEdit, QTableView
        {
            color: #202020;
            background: #ffffff;
            border: 1px solid #cccccc;
            border-radius: 4px;
            selection-background-color: #cce4f7;
            selection-color: #202020;
            gridline-color: #e5e5e5;
        }
        QHeaderView::section
        {
            color: #202020;
            background: #eeeeee;
            border: none;
            border-bottom: 1px solid #d0d0d0;
            padding: 5px 8px;
            font-weight: bold;
        }
        QLineEdit#frameHex
        {
            color: #202020;
            background: #ffffff;
            padding: 8px;
            font-family: Consolas;
            font-size: 12pt;
        }
        QLabel[badgeTone]
        {
            padding: 5px 9px;
            border-radius: 5px;
            font-weight: normal;
        }
        QLabel[badgeTone="muted"]
        {
            color: #666666;
            background: #e8e8e8;
        }
        QLabel[badgeTone="ready"]
        {
            color: #2e7d32;
            background: #e8f5e9;
        }
        QLabel[badgeTone="running"]
        {
            color: #1267c5;
            background: #e7f0fa;
        }
        QLabel[badgeTone="warning"]
        {
            color: #8a5700;
            background: #fff3e0;
        }
        QLabel[badgeTone="error"]
        {
            color: #c62828;
            background: #ffebee;
        }
        QStatusBar
        {
            color: #202020;
            background: #f0f0f0;
            border-top: 1px solid #d0d0d0;
        }
        QStatusBar QLabel
        {
            color: #202020;
        }
        QStatusBar QLabel[muted="true"]
        {
            color: #707070;
        }
        QWidget#historyEmptyState QLabel[muted="true"]
        {
            color: #808080;
        }
        QTableView QScrollBar:vertical, QTextEdit QScrollBar:vertical
        {
            background: #ffffff;
        }
        QTableView QScrollBar::handle:vertical, QTextEdit QScrollBar::handle:vertical
        {
            background: #b0b0b0;
        }
        QLabel[sectionTitle="true"]
        {
            color: #202020;
            font-weight: bold;
        }
        QFrame#parameterSectionHeader
        {
            background: transparent;
            border-bottom: 1px solid #d5d5d5;
        }
        QLabel#changeSwatch
        {
            background: #fff2cc;
            border: 1px solid #e0c878;
            border-radius: 3px;
        }
        QStatusBar::item
        {
            border: none;
        }
        QMenu
        {
            color: #202020;
            background: #ffffff;
            border: 1px solid #bdbdbd;
            padding: 5px;
        }
        QMenu::item
        {
            padding: 7px 18px;
        }
        QMenu::item:selected
        {
            background: #cce4f7;
            border-radius: 3px;
        }
        QMenu::separator
        {
            height: 1px;
            background: #d0d0d0;
            margin: 4px;
        }
        QFrame#protocolSearchPopup
        {
            background: #ffffff;
            border: 1px solid #bdbdbd;
            border-radius: 6px;
        }
        QListWidget#protocolSearchList
        {
            color: #202020;
            background: #ffffff;
            border: none;
            outline: none;
        }
        QListWidget#protocolSearchList::item
        {
            padding: 7px;
        }
        QListWidget#protocolSearchList::item:selected
        {
            color: #202020;
            background: #cce4f7;
            border-radius: 3px;
        }
    """.replace("__CHECK_PATH__", check_path).replace("__RADIO_PATH__", radio_path).replace("__DOWN_PATH__", down_path).replace("__UP_PATH__", up_path)
