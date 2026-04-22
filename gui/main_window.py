#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
主窗口GUI界面

实现串口配置、场景选择、Status位配置、发送控制、数据监控等功能区域
"""

import sys
import json
import os
from datetime import datetime
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QGroupBox, QLabel, QComboBox, QPushButton, QSpinBox, QDoubleSpinBox,
    QCheckBox, QRadioButton, QButtonGroup, QTextEdit, QLineEdit,
    QMessageBox, QSplitter, QFrame, QScrollArea, QTabWidget,
    QProgressBar, QStatusBar, QDialog, QToolButton
)
from PyQt5.QtCore import Qt, QTimer, pyqtSlot
from PyQt5.QtGui import QFont, QIcon, QPalette, QColor

from protocol.protocol_handler import (
    PROTOCOL_CHANGZHOU_XINSIWEI,
    PROTOCOL_DONGWEI_GTXH,
    PROTOCOL_HANGZHOU_ANXIAN,
    PROTOCOL_RUILUN,
    PROTOCOL_WUXI_YIGE,
    PROTOCOL_XINCHI,
    PROTOCOL_XINRI,
    PROTOCOL_YADEA,
    ProtocolHandler,
    StatusBits,
    PresetScenarios,
)
from gui.feedback_dialog import FeedbackDialog
from serial_comm.serial_manager import SerialManager, SerialPortDetector
from gui.frame_config_dialog import FrameConfigDialog

class MainWindow(QMainWindow):
    """主窗口"""
    
    def __init__(self):
        super().__init__()
        self.protocol_handler = ProtocolHandler()
        self.serial_manager = SerialManager()
        self.port_detector = SerialPortDetector()
        
        # 当前状态
        self.current_status = StatusBits()
        self.current_protocol = PROTOCOL_RUILUN  # 默认协议
        self.custom_scenarios = {}  # 自定义场景存储
        self.custom_frame_data = None  # 全部自定义模式的帧数据
        self.frame_config_dialog = None  # 帧配置窗口
        self._previous_scenario_id = 0  # 初始场景ID（正常运行）
        
        # 性能优化相关
        self.pending_history_updates = []  # 待更新的历史记录缓冲
        self.history_update_timer = QTimer()
        self.history_update_timer.timeout.connect(self._flush_history_updates)
        self.history_update_timer.setSingleShot(False)
        self.history_update_timer.start(100)  # 每100ms批量更新一次历史记录
        
        self.init_ui()
        self.connect_signals()
        self.load_settings()
        
        # 启动串口检测
        self.port_detector.start_detection()
    
    def init_ui(self):
        """初始化用户界面"""
        self.setWindowTitle("AD仪表一线通协议测试工具 V1.56")
        self.setGeometry(100, 100, 1200, 800)
        
        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 创建主布局
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        title_bar = self.create_window_action_bar()
        main_layout.addWidget(title_bar)

        content_widget = QWidget()
        content_layout = QHBoxLayout(content_widget)
        content_layout.setContentsMargins(10, 10, 10, 10)
        content_layout.setSpacing(10)
        
        # 创建分割器
        splitter = QSplitter(Qt.Horizontal)
        splitter = QSplitter(Qt.Horizontal)
        content_layout.addWidget(splitter)
        main_layout.addWidget(content_widget, 1)
        
        # 左侧控制面板
        left_panel = self.create_control_panel()
        splitter.addWidget(left_panel)
        
        # 右侧监控面板
        right_panel = self.create_monitor_panel()
        splitter.addWidget(right_panel)
        
        # 设置分割比例
        splitter.setSizes([600, 600])
        
        # 创建状态栏
        self.create_status_bar()
        
        # 设置样式
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f0f0f0;
            }
            QFrame#windowActionBar {
                background-color: #f8f8f8;
                border-bottom: 1px solid #d9d9d9;
            }
            QLabel#windowActionTitle {
                color: #4d4d4d;
                font-size: 12px;
                font-weight: bold;
                padding-left: 4px;
            }
            QGroupBox {
                font-weight: bold;
                border: 2px solid #cccccc;
                border-radius: 5px;
                margin-top: 1ex;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
            QPushButton {
                background-color: #4CAF50;
                border: none;
                color: white;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3d8b40;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
            QToolButton#feedbackButton {
                background-color: transparent;
                border: none;
                color: #4d4d4d;
                font-size: 18px;
                font-weight: bold;
                padding: 0;
            }
            QToolButton#feedbackButton:hover {
                background-color: #e9eef5;
                color: #1d5fa7;
            }
            QToolButton#feedbackButton:pressed {
                background-color: #d8e5f5;
            }
        """)
    
    def create_window_action_bar(self) -> QFrame:
        """创建右上角反馈操作栏。"""
        bar = QFrame()
        bar.setObjectName("windowActionBar")
        bar.setFixedHeight(34)

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(10, 0, 0, 0)
        layout.setSpacing(0)

        title_label = QLabel("AD仪表一线通协议测试工具")
        title_label.setObjectName("windowActionTitle")
        layout.addWidget(title_label)
        layout.addStretch()

        self.feedback_btn = QToolButton()
        self.feedback_btn.setObjectName("feedbackButton")
        self.feedback_btn.setText("?")
        self.feedback_btn.setToolTip("扫码反馈")
        self.feedback_btn.setCursor(Qt.PointingHandCursor)
        self.feedback_btn.setFixedSize(42, 34)
        self.feedback_btn.clicked.connect(self.show_feedback_dialog)
        layout.addWidget(self.feedback_btn)

        return bar

    def show_feedback_dialog(self):
        """显示作者联系二维码。"""
        dialog = FeedbackDialog(self)
        dialog.exec_()

    def create_control_panel(self) -> QWidget:
        """创建左侧控制面板"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # 串口配置区
        serial_group = self.create_serial_config_group()
        layout.addWidget(serial_group)
        
        # 场景选择区
        scenario_group = self.create_scenario_group()
        layout.addWidget(scenario_group)
        
        # Status位配置区
        status_group = self.create_status_config_group()
        layout.addWidget(status_group)
        
        # 发送控制区
        send_group = self.create_send_control_group()
        layout.addWidget(send_group)
        
        layout.addStretch()
        return panel
    
    def create_serial_config_group(self) -> QGroupBox:
        """创建串口配置组"""
        group = QGroupBox("串口配置")
        layout = QGridLayout(group)
        
        # 串口选择
        layout.addWidget(QLabel("串口:"), 0, 0)
        self.port_combo = QComboBox()
        self.port_combo.setMinimumWidth(200)
        layout.addWidget(self.port_combo, 0, 1)
        
        self.refresh_ports_btn = QPushButton("刷新")
        self.refresh_ports_btn.clicked.connect(self.refresh_ports)
        layout.addWidget(self.refresh_ports_btn, 0, 2)
        
        # 波特率
        layout.addWidget(QLabel("波特率:"), 1, 0)
        self.baud_combo = QComboBox()
        self.baud_combo.addItems(["9600", "19200", "38400", "57600", "115200"])
        self.baud_combo.setCurrentText("9600")
        layout.addWidget(self.baud_combo, 1, 1)
        
        # Tosc值
        layout.addWidget(QLabel("Tosc (μs):"), 2, 0)
        self.tosc_spin = QSpinBox()
        self.tosc_spin.setRange(32, 320)
        self.tosc_spin.setValue(100)
        self.tosc_spin.valueChanged.connect(self.on_tosc_changed)
        layout.addWidget(self.tosc_spin, 2, 1)
        
        # 连接按钮
        self.connect_btn = QPushButton("连接")
        self.connect_btn.clicked.connect(self.toggle_connection)
        layout.addWidget(self.connect_btn, 3, 0, 1, 3)
        
        # 连接状态指示
        self.connection_status = QLabel("未连接")
        self.connection_status.setStyleSheet("color: red; font-weight: bold;")
        layout.addWidget(self.connection_status, 4, 0, 1, 3)
        
        return group

    def _compact_status_tab_pages(self):
        """统一收紧 Status 页签内部布局，避免选项间空白过大。"""
        for index in range(self.status_tabs.count()):
            self._compact_status_layout_tree(self.status_tabs.widget(index), is_root=True)

    def _last_used_grid_row(self, layout: QGridLayout) -> int:
        """返回当前网格布局中实际使用到的最后一行。"""
        last_row = -1
        for index in range(layout.count()):
            row, _, row_span, _ = layout.getItemPosition(index)
            last_row = max(last_row, row + row_span - 1)
        return last_row

    def _compact_status_layout_tree(self, widget_or_layout, is_root=False):
        """递归压缩 Status 页签布局的间距和拉伸。"""
        if widget_or_layout is None:
            return

        if isinstance(widget_or_layout, QWidget):
            layout = widget_or_layout.layout()
            if layout is None:
                return
        else:
            layout = widget_or_layout

        if isinstance(layout, QGridLayout):
            if is_root:
                layout.setContentsMargins(10, 10, 10, 8)
                layout.setHorizontalSpacing(18)
                layout.setVerticalSpacing(8)
            else:
                layout.setContentsMargins(8, 8, 8, 6)
                layout.setHorizontalSpacing(12)
                layout.setVerticalSpacing(6)

            layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)
            last_row = self._last_used_grid_row(layout)
            if last_row >= 0:
                layout.setRowStretch(last_row + 1, 1)
        elif isinstance(layout, QVBoxLayout):
            if is_root:
                layout.setContentsMargins(10, 8, 10, 8)
            layout.setSpacing(8)
            layout.setAlignment(Qt.AlignTop)
        elif isinstance(layout, QHBoxLayout):
            if is_root:
                layout.setContentsMargins(8, 6, 8, 6)
            layout.setSpacing(8)

        for index in range(layout.count()):
            item = layout.itemAt(index)

            child_layout = item.layout()
            if child_layout is not None:
                self._compact_status_layout_tree(child_layout)

            child_widget = item.widget()
            if child_widget is None:
                continue

            if isinstance(child_widget, QScrollArea):
                scroll_widget = child_widget.widget()
                if scroll_widget is not None:
                    self._compact_status_layout_tree(scroll_widget, is_root=True)
                continue

            if child_widget.layout() is not None:
                self._compact_status_layout_tree(child_widget, is_root=True)
    
    def create_scenario_group(self) -> QGroupBox:
        """创建协议和场景选择组"""
        group = QGroupBox("协议和测试场景")
        layout = QVBoxLayout(group)
        
        # 协议选择
        protocol_layout = QHBoxLayout()
        protocol_layout.addWidget(QLabel("协议列表:"))
        self.protocol_combo = QComboBox()
        self.protocol_combo.addItems(
            [
                PROTOCOL_RUILUN,
                PROTOCOL_XINRI,
                PROTOCOL_HANGZHOU_ANXIAN,
                PROTOCOL_CHANGZHOU_XINSIWEI,
                PROTOCOL_WUXI_YIGE,
                PROTOCOL_YADEA,
                PROTOCOL_DONGWEI_GTXH,
                PROTOCOL_XINCHI,
            ]
        )
        self.protocol_combo.setCurrentText(PROTOCOL_RUILUN)
        self.protocol_combo.currentTextChanged.connect(self.on_protocol_changed)
        protocol_layout.addWidget(self.protocol_combo)
        layout.addLayout(protocol_layout)
        
        # 预设场景
        preset_layout = QHBoxLayout()
        self.scenario_group = QButtonGroup()
        
        self.normal_radio = QRadioButton("正常运行")
        self.normal_radio.setChecked(True)
        self.scenario_group.addButton(self.normal_radio, 0)
        preset_layout.addWidget(self.normal_radio)
        
        self.recovery_radio = QRadioButton("能量回收")
        self.scenario_group.addButton(self.recovery_radio, 1)
        preset_layout.addWidget(self.recovery_radio)
        
        self.fault_radio = QRadioButton("故障场景")
        self.scenario_group.addButton(self.fault_radio, 2)
        preset_layout.addWidget(self.fault_radio)
        
        self.custom_radio = QRadioButton("数据自定义")
        self.scenario_group.addButton(self.custom_radio, 3)
        preset_layout.addWidget(self.custom_radio)
        
        self.frame_custom_radio = QRadioButton("全部自定义")
        self.scenario_group.addButton(self.frame_custom_radio, 4)
        preset_layout.addWidget(self.frame_custom_radio)
        
        layout.addLayout(preset_layout)
        
        # 自定义模式管理
        custom_layout = QHBoxLayout()
        
        # 全部自定义配置按钮
        self.frame_config_btn = QPushButton("帧配置")
        self.frame_config_btn.setEnabled(False)
        self.frame_config_btn.clicked.connect(self.open_frame_config)
        custom_layout.addWidget(self.frame_config_btn)
        
        layout.addLayout(custom_layout)
        
        # 连接信号
        self.scenario_group.buttonClicked.connect(self.on_scenario_changed)
        
        return group
    
    def create_status_config_group(self) -> QGroupBox:
        """创建Status位配置组"""
        group = QGroupBox("Status位配置")
        
        # 创建滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMaximumHeight(300)
        
        # 创建配置面板
        config_widget = QWidget()
        layout = QVBoxLayout(config_widget)
        
        # 创建标签页
        self.status_tabs = QTabWidget()
        
        # 默认显示瑞轮协议的Status配置
        self.show_ruilun_status_config()
        
        layout.addWidget(self.status_tabs)
        
        scroll.setWidget(config_widget)
        
        # 设置组布局
        group_layout = QVBoxLayout(group)
        group_layout.addWidget(scroll)
        
        # 默认禁用（选择预设场景时）
        self.status_tabs.setEnabled(False)
        
        return group
    
    def create_ruilun_status1_tab(self) -> QWidget:
        """创建瑞轮协议Status1配置标签页"""
        widget = QWidget()
        layout = QGridLayout(widget)
        
        protocol = self.current_protocol
        if protocol == PROTOCOL_HANGZHOU_ANXIAN:
            labels = [
                ("备用 (D3)", False),
                ("协议限速 (D2)", True),
                ("P档 (D1)", True),
                ("备用 (D0)", False),
            ]
        elif protocol == PROTOCOL_DONGWEI_GTXH:
            labels = [
                ("电压状态位 D2 (由下方电压状态控制)", False),
                ("电压状态位 D1 (由下方电压状态控制)", False),
                ("P驻车 (D3)", True),
                ("电压状态位 D0 (由下方电压状态控制)", False),
            ]
        elif protocol == PROTOCOL_WUXI_YIGE:
            labels = [
                ("侧撑指示 (D3)", True),
                ("备用 (D2)", False),
                ("驻车指示(P档) (D1)", True),
                ("备用 (D0)", False),
            ]
        elif protocol == PROTOCOL_YADEA:
            labels = [
                ("单撑断电检测 (D3)", True),
                ("备用 (D2)", False),
                ("启动保护 (D1)", True),
                ("备用 (D0)", False),
            ]
        else:
            labels = [
                ("运动里程模式 (D3)", True),
                ("超速提示音 (D2)", True),
                ("P档启动保护 (D1)", True),
                ("TCS状态 (D0) - 1=亮/0=灭", True),
            ]

        self.distance_mode_cb = QCheckBox(labels[0][0])
        self.distance_mode_cb.setEnabled(labels[0][1])
        layout.addWidget(self.distance_mode_cb, 0, 0)
        
        self.speed_alarm_cb = QCheckBox(labels[1][0])
        self.speed_alarm_cb.setEnabled(labels[1][1])
        layout.addWidget(self.speed_alarm_cb, 0, 1)
        
        self.p_gear_protect_cb = QCheckBox(labels[2][0])
        self.p_gear_protect_cb.setEnabled(labels[2][1])
        layout.addWidget(self.p_gear_protect_cb, 1, 0)
        
        self.tcs_status_cb = QCheckBox(labels[3][0])
        self.tcs_status_cb.setEnabled(labels[3][1])
        layout.addWidget(self.tcs_status_cb, 1, 1)
        
        return widget
    
    def create_ruilun_status2_tab(self) -> QWidget:
        """创建瑞轮协议Status2配置标签页"""
        widget = QWidget()
        layout = QGridLayout(widget)
        
        status2_d7_text = "6KM推行/推车标志 (D7)" if self.current_protocol == PROTOCOL_WUXI_YIGE else "备用 (D7)"
        status2_d7_enabled = self.current_protocol == PROTOCOL_WUXI_YIGE
        self.status2_d7_cb = QCheckBox(status2_d7_text)
        self.status2_d7_cb.setEnabled(status2_d7_enabled)
        layout.addWidget(self.status2_d7_cb, 0, 0)

        self.hall_fault_cb = QCheckBox("霍尔故障 (D6)")
        layout.addWidget(self.hall_fault_cb, 0, 1)
        
        self.throttle_fault_cb = QCheckBox("转把故障 (D5)")
        layout.addWidget(self.throttle_fault_cb, 1, 0)
        
        self.controller_fault_cb = QCheckBox("控制器故障 (D4)")
        layout.addWidget(self.controller_fault_cb, 1, 1)
        
        self.under_voltage_cb = QCheckBox("欠压保护 (D3)")
        layout.addWidget(self.under_voltage_cb, 2, 0)
        
        self.cruise_cb = QCheckBox("巡航 (D2)")
        layout.addWidget(self.cruise_cb, 2, 1)
        
        self.assist_cb = QCheckBox("助力 (D1)")
        layout.addWidget(self.assist_cb, 3, 0)
        
        self.motor_phase_loss_cb = QCheckBox("电机缺相 (D0)")
        layout.addWidget(self.motor_phase_loss_cb, 3, 1)
        
        return widget
    
    def create_ruilun_status3_tab(self) -> QWidget:
        """创建瑞轮协议Status3配置标签页"""
        widget = QWidget()
        layout = QGridLayout(widget)
        
        d7_text = (
            "速度模式高位 (D7)"
            if self.current_protocol in {PROTOCOL_YADEA, PROTOCOL_DONGWEI_GTXH}
            else "四档指示 (D7)"
        )
        speed_mode_label = (
            "档位模式 (D7+D1~D0):"
            if self.current_protocol == PROTOCOL_DONGWEI_GTXH
            else "速度模式 (D7+D1~D0):"
            if self.current_protocol == PROTOCOL_YADEA
            else "三速模式 (D1~D0):"
        )

        self.gear_four_cb = QCheckBox(d7_text)
        layout.addWidget(self.gear_four_cb, 0, 0)
        
        self.motor_running_cb = QCheckBox("电机运行状态 (D6) - 1=运行/0=停止")
        layout.addWidget(self.motor_running_cb, 0, 1)
        
        self.brake_cb = QCheckBox("刹车 (D5)")
        layout.addWidget(self.brake_cb, 1, 0)
        
        self.controller_protect_cb = QCheckBox("控制器保护 (D4)")
        layout.addWidget(self.controller_protect_cb, 1, 1)
        
        self.regen_charging_cb = QCheckBox("滑行充电 (D3) - 1=能量回收")
        layout.addWidget(self.regen_charging_cb, 2, 0)
        
        self.anti_runaway_cb = QCheckBox("防飞车保护 (D2)")
        layout.addWidget(self.anti_runaway_cb, 2, 1)
        
        layout.addWidget(QLabel(speed_mode_label), 3, 0)
        self.speed_mode_spin = QSpinBox()
        self.speed_mode_spin.setRange(
            0, 7 if self.current_protocol in {PROTOCOL_YADEA, PROTOCOL_DONGWEI_GTXH} else 3
        )
        layout.addWidget(self.speed_mode_spin, 3, 1)
        
        return widget
    
    def create_ruilun_status4_tab(self) -> QWidget:
        """创建瑞轮协议Status4配置标签页"""
        widget = QWidget()
        layout = QGridLayout(widget)
        
        if self.current_protocol == PROTOCOL_WUXI_YIGE:
            d7_text = "云动力模式(速度提升) (D7)"
            d7_enabled = True
        elif self.current_protocol in {PROTOCOL_RUILUN, PROTOCOL_DONGWEI_GTXH}:
            d7_text = "70%电流标志 (D7)"
            d7_enabled = True
        else:
            d7_text = "备用 (D7)"
            d7_enabled = False

        self.current_70_flag_cb = QCheckBox(d7_text)
        self.current_70_flag_cb.setEnabled(d7_enabled)
        layout.addWidget(self.current_70_flag_cb, 0, 0)
        
        d6_text = "侧撑检测/单撑 (D6)" if self.current_protocol == PROTOCOL_DONGWEI_GTXH else "一键通启用 (D6)"
        self.one_key_enable_cb = QCheckBox(d6_text)
        layout.addWidget(self.one_key_enable_cb, 0, 1)
        
        self.ekk_enable_cb = QCheckBox("EKK启用 (D5)")
        layout.addWidget(self.ekk_enable_cb, 1, 0)
        
        self.over_current_cb = QCheckBox("过流保护 (D4)")
        layout.addWidget(self.over_current_cb, 1, 1)
        
        self.stall_protect_cb = QCheckBox("堵转保护 (D3)")
        layout.addWidget(self.stall_protect_cb, 2, 0)
        
        self.reverse_cb = QCheckBox("倒车 (D2)")
        layout.addWidget(self.reverse_cb, 2, 1)
        
        self.electronic_brake_cb = QCheckBox("电子刹车 (D1)")
        layout.addWidget(self.electronic_brake_cb, 3, 0)
        
        self.speed_limit_cb = QCheckBox("限速 (D0) - 1=限速/0=解除")
        layout.addWidget(self.speed_limit_cb, 3, 1)
        
        return widget
    
    def create_ruilun_status5_9_tab(self) -> QWidget:
        """创建瑞轮协议Status5-9配置标签页"""
        widget = QWidget()
        layout = QGridLayout(widget)
        protocol = self.current_protocol

        for attr_name in (
            "soc_fault_cb",
            "current_percent_spin",
            "voltage_group",
            "voltage_default_rb",
            "voltage_36v_rb",
            "voltage_48v_rb",
            "voltage_60v_rb",
            "voltage_64v_rb",
            "voltage_72v_rb",
            "voltage_80v_rb",
            "voltage_84v_rb",
            "voltage_96v_rb",
        ):
            if hasattr(self, attr_name):
                delattr(self, attr_name)
        
        # Status5 - 运行电流
        current_label = (
            "运行电流 (A，发送按 0.2A/LSB 编码):"
            if protocol == PROTOCOL_DONGWEI_GTXH
            else "运行电流 (A):"
        )
        layout.addWidget(QLabel(current_label), 0, 0)
        self.current_spin = QSpinBox()
        self.current_spin.setRange(-128, 127)
        self.current_spin.setValue(0)
        layout.addWidget(self.current_spin, 0, 1)
        
        # Status6~7 - 霍尔计数
        layout.addWidget(QLabel("霍尔计数 (0.5s 三霍尔总数):"), 1, 0)
        self.hall_count_spin = QSpinBox()
        self.hall_count_spin.setRange(0, 65535)
        self.hall_count_spin.setValue(0)
        layout.addWidget(self.hall_count_spin, 1, 1)

        # 兼容旧 UI 的速度兜底值
        layout.addWidget(QLabel("兼容速度输入 (km/h，可留 0):"), 2, 0)
        self.speed_spin = QDoubleSpinBox()
        self.speed_spin.setRange(0.0, 6553.5)
        self.speed_spin.setDecimals(1)
        self.speed_spin.setSingleStep(0.1)
        self.speed_spin.setValue(0.0)
        layout.addWidget(self.speed_spin, 2, 1)
        
        if protocol == PROTOCOL_HANGZHOU_ANXIAN:
            status8_text = "电压百分比 (Status8):"
        elif protocol == PROTOCOL_YADEA:
            status8_text = "电量百分比 (Status8):"
        elif protocol == PROTOCOL_DONGWEI_GTXH:
            status8_text = "电压/电量百分比 (Status8):"
        else:
            status8_text = "电池SOC (%):"

        self.status8_label = QLabel(status8_text)
        layout.addWidget(self.status8_label, 3, 0)
        status8_layout = QHBoxLayout()
        self.soc_spin = QSpinBox()
        self.soc_spin.setRange(0, 100)
        self.soc_spin.setValue(50)
        status8_layout.addWidget(self.soc_spin)

        if protocol in {PROTOCOL_RUILUN, PROTOCOL_WUXI_YIGE}:
            self.lithium_soc_mode_cb = QCheckBox(
                "锂电SOC模式" if protocol == PROTOCOL_RUILUN else "透传锂电SOC(D7=1)"
            )
            self.lithium_soc_mode_cb.setChecked(True)
            status8_layout.addWidget(self.lithium_soc_mode_cb)
        else:
            self.lithium_soc_mode_cb = None

        if protocol == PROTOCOL_RUILUN:
            self.soc_fault_cb = QCheckBox("SOC故障")
            self.soc_fault_cb.toggled.connect(self.on_soc_fault_toggled)
            status8_layout.addWidget(self.soc_fault_cb)

        layout.addLayout(status8_layout, 3, 1)

        row_index = 4
        if protocol in {PROTOCOL_YADEA, PROTOCOL_DONGWEI_GTXH}:
            layout.addWidget(QLabel("电流百分比 (Status9):"), row_index, 0)
            self.current_percent_spin = QSpinBox()
            self.current_percent_spin.setRange(0, 100)
            self.current_percent_spin.setValue(50)
            layout.addWidget(self.current_percent_spin, row_index, 1)
            row_index += 1

        if protocol == PROTOCOL_YADEA:
            return widget

        # Status9 - 系统电压
        voltage_group_title = (
            "电压状态 (DATA2 D2~D0，仅支持默认/48V/60V/72V/80V/96V)"
            if protocol == PROTOCOL_DONGWEI_GTXH
            else "系统电压 (仅选一个，可全不选)"
        )
        voltage_group = QGroupBox(voltage_group_title)
        voltage_layout = QGridLayout(voltage_group)
        self.voltage_group = QButtonGroup()

        if protocol == PROTOCOL_DONGWEI_GTXH:
            self.voltage_default_rb = QRadioButton("仪表默认")
            self.voltage_group.addButton(self.voltage_default_rb, 8)
            voltage_layout.addWidget(self.voltage_default_rb, 0, 0)

        self.voltage_36v_rb = QRadioButton("36V")
        self.voltage_group.addButton(self.voltage_36v_rb, 0)
        voltage_layout.addWidget(self.voltage_36v_rb, 0 if protocol != PROTOCOL_DONGWEI_GTXH else 1, 0)

        self.voltage_48v_rb = QRadioButton("48V")
        self.voltage_48v_rb.setChecked(protocol != PROTOCOL_DONGWEI_GTXH)
        self.voltage_group.addButton(self.voltage_48v_rb, 1)
        voltage_layout.addWidget(self.voltage_48v_rb, 0 if protocol != PROTOCOL_DONGWEI_GTXH else 1, 1)

        self.voltage_60v_rb = QRadioButton("60V")
        self.voltage_group.addButton(self.voltage_60v_rb, 2)
        voltage_layout.addWidget(self.voltage_60v_rb, 0 if protocol != PROTOCOL_DONGWEI_GTXH else 1, 2)

        self.voltage_64v_rb = QRadioButton("64V")
        self.voltage_group.addButton(self.voltage_64v_rb, 3)
        voltage_layout.addWidget(self.voltage_64v_rb, 0 if protocol != PROTOCOL_DONGWEI_GTXH else 1, 3)

        self.voltage_72v_rb = QRadioButton("72V")
        self.voltage_group.addButton(self.voltage_72v_rb, 4)
        voltage_layout.addWidget(self.voltage_72v_rb, 1 if protocol != PROTOCOL_DONGWEI_GTXH else 2, 0)

        self.voltage_80v_rb = QRadioButton("80V")
        self.voltage_group.addButton(self.voltage_80v_rb, 5)
        voltage_layout.addWidget(self.voltage_80v_rb, 1 if protocol != PROTOCOL_DONGWEI_GTXH else 2, 1)

        self.voltage_84v_rb = QRadioButton("84V")
        self.voltage_group.addButton(self.voltage_84v_rb, 6)
        voltage_layout.addWidget(self.voltage_84v_rb, 1 if protocol != PROTOCOL_DONGWEI_GTXH else 2, 2)

        self.voltage_96v_rb = QRadioButton("96V")
        self.voltage_group.addButton(self.voltage_96v_rb, 7)
        voltage_layout.addWidget(self.voltage_96v_rb, 1 if protocol != PROTOCOL_DONGWEI_GTXH else 2, 3)

        if protocol == PROTOCOL_DONGWEI_GTXH:
            self.voltage_default_rb.setChecked(True)
            self.voltage_36v_rb.setEnabled(False)
            self.voltage_64v_rb.setEnabled(False)
            self.voltage_84v_rb.setEnabled(False)

        layout.addWidget(voltage_group, row_index, 0, 1, 2)
        
        return widget
    
    def create_send_control_group(self) -> QGroupBox:
        """创建发送控制组"""
        group = QGroupBox("发送控制")
        layout = QGridLayout(group)
        
        # 发送间隔
        layout.addWidget(QLabel("发送间隔 (ms):"), 0, 0)
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(500, 5000)
        self.interval_spin.setValue(1000)
        layout.addWidget(self.interval_spin, 0, 1)
        
        # 发送按钮
        self.single_send_btn = QPushButton("单次发送")
        self.single_send_btn.clicked.connect(self.send_single_frame)
        self.single_send_btn.setEnabled(False)
        layout.addWidget(self.single_send_btn, 1, 0)
        
        self.cyclic_send_btn = QPushButton("循环发送")
        self.cyclic_send_btn.clicked.connect(self.toggle_cyclic_send)
        self.cyclic_send_btn.setEnabled(False)
        layout.addWidget(self.cyclic_send_btn, 1, 1)
        
        # 发送状态
        self.send_status = QLabel("就绪")
        self.send_status.setStyleSheet("color: blue; font-weight: bold;")
        layout.addWidget(self.send_status, 2, 0, 1, 2)
        
        return group
    
    def create_monitor_panel(self) -> QWidget:
        """创建右侧监控面板"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # 数据监控组
        monitor_group = QGroupBox("数据监控")
        monitor_layout = QVBoxLayout(monitor_group)
        
        # 当前帧数据显示
        current_frame_group = QGroupBox("当前帧数据")
        current_frame_layout = QVBoxLayout(current_frame_group)
        
        self.current_frame_text = QTextEdit()
        self.current_frame_text.setMaximumHeight(200)
        self.current_frame_text.setFont(QFont("Consolas", 9))
        current_frame_layout.addWidget(self.current_frame_text)
        
        monitor_layout.addWidget(current_frame_group)
        
        # 发送历史记录
        history_group = QGroupBox("发送历史")
        history_layout = QVBoxLayout(history_group)
        
        # 控制按钮
        history_controls = QHBoxLayout()
        self.clear_history_btn = QPushButton("清空记录")
        self.clear_history_btn.clicked.connect(self.clear_send_history)
        history_controls.addWidget(self.clear_history_btn)
        
        self.auto_scroll_cb = QCheckBox("自动滚动")
        self.auto_scroll_cb.setChecked(True)
        history_controls.addWidget(self.auto_scroll_cb)
        
        history_controls.addStretch()
        history_layout.addLayout(history_controls)
        
        # 历史记录文本
        self.history_text = QTextEdit()
        self.history_text.setFont(QFont("Consolas", 8))
        history_layout.addWidget(self.history_text)
        
        monitor_layout.addWidget(history_group)
        
        layout.addWidget(monitor_group)
        
        return panel
    
    def create_status_bar(self):
        """创建状态栏"""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        # 添加状态信息
        self.status_bar.showMessage("就绪")
        
        # 添加版本信息
        version_label = QLabel("协议版本: V1.56")
        self.status_bar.addPermanentWidget(version_label)
    
    def connect_signals(self):
        """连接信号和槽"""
        # 串口管理器信号
        self.serial_manager.port_connected.connect(self.on_port_connected)
        self.serial_manager.port_disconnected.connect(self.on_port_disconnected)
        self.serial_manager.data_sent.connect(self.on_data_sent)
        self.serial_manager.send_error.connect(self.on_send_error)
        self.serial_manager.connection_error.connect(self.on_connection_error)
        
        # 串口检测器信号
        self.port_detector.ports_changed.connect(self.on_ports_changed)
        
        # Status位控件信号连接 - 实时更新当前帧数据
        self._compact_status_tab_pages()
        self.connect_status_signals()
    
    def connect_status_signals(self):
        """连接Status位控件信号，实现实时更新当前帧数据"""
        # Status1控件
        self.distance_mode_cb.toggled.connect(self.update_current_frame_display)
        self.speed_alarm_cb.toggled.connect(self.update_current_frame_display)
        self.p_gear_protect_cb.toggled.connect(self.update_current_frame_display)
        self.tcs_status_cb.toggled.connect(self.update_current_frame_display)
        
        # Status2控件
        self.status2_d7_cb.toggled.connect(self.update_current_frame_display)
        self.hall_fault_cb.toggled.connect(self.update_current_frame_display)
        self.throttle_fault_cb.toggled.connect(self.update_current_frame_display)
        self.controller_fault_cb.toggled.connect(self.update_current_frame_display)
        self.under_voltage_cb.toggled.connect(self.update_current_frame_display)
        self.cruise_cb.toggled.connect(self.update_current_frame_display)
        self.assist_cb.toggled.connect(self.update_current_frame_display)
        self.motor_phase_loss_cb.toggled.connect(self.update_current_frame_display)
        
        # Status3控件
        self.gear_four_cb.toggled.connect(self.update_current_frame_display)
        self.motor_running_cb.toggled.connect(self.update_current_frame_display)
        self.brake_cb.toggled.connect(self.update_current_frame_display)
        self.controller_protect_cb.toggled.connect(self.update_current_frame_display)
        self.regen_charging_cb.toggled.connect(self.update_current_frame_display)
        self.anti_runaway_cb.toggled.connect(self.update_current_frame_display)
        self.speed_mode_spin.valueChanged.connect(self.update_current_frame_display)
        
        # Status4控件
        self.current_70_flag_cb.toggled.connect(self.update_current_frame_display)
        self.one_key_enable_cb.toggled.connect(self.update_current_frame_display)
        self.ekk_enable_cb.toggled.connect(self.update_current_frame_display)
        self.over_current_cb.toggled.connect(self.update_current_frame_display)
        self.stall_protect_cb.toggled.connect(self.update_current_frame_display)
        self.reverse_cb.toggled.connect(self.update_current_frame_display)
        self.electronic_brake_cb.toggled.connect(self.update_current_frame_display)
        self.speed_limit_cb.toggled.connect(self.update_current_frame_display)
        
        # Status5-9控件
        self.current_spin.valueChanged.connect(self.update_current_frame_display)
        self.hall_count_spin.valueChanged.connect(self.update_current_frame_display)
        self.speed_spin.valueChanged.connect(self.update_current_frame_display)
        self.soc_spin.valueChanged.connect(self.update_current_frame_display)
        if getattr(self, "lithium_soc_mode_cb", None) is not None:
            self.lithium_soc_mode_cb.toggled.connect(self.update_current_frame_display)
        if getattr(self, "soc_fault_cb", None) is not None:
            self.soc_fault_cb.toggled.connect(self.update_current_frame_display)
        if getattr(self, "current_percent_spin", None) is not None:
            self.current_percent_spin.valueChanged.connect(self.update_current_frame_display)
        if getattr(self, "voltage_group", None) is not None:
            self.voltage_group.buttonClicked.connect(self.update_current_frame_display)
    
    def load_settings(self):
        """加载设置"""
        # 刷新串口列表
        self.refresh_ports()
        
        # 更新当前帧显示
        self.update_current_frame_display()
    
    # 槽函数实现
    @pyqtSlot()
    def refresh_ports(self):
        """刷新串口列表"""
        self.port_combo.clear()
        ports = self.serial_manager.scan_ports()
        for port in ports:
            self.port_combo.addItem(str(port), port.port)
    
    @pyqtSlot(list)
    def on_ports_changed(self, ports):
        """串口列表变化处理"""
        current_port = self.port_combo.currentData()
        self.port_combo.clear()
        
        current_index = -1
        for i, port in enumerate(ports):
            self.port_combo.addItem(str(port), port.port)
            if port.port == current_port:
                current_index = i
        
        if current_index >= 0:
            self.port_combo.setCurrentIndex(current_index)
    
    @pyqtSlot()
    def toggle_connection(self):
        """切换串口连接状态"""
        if self.serial_manager.is_connected:
            # 断开连接
            self.serial_manager.disconnect_port()
        else:
            # 连接串口
            port_name = self.port_combo.currentData()
            if not port_name:
                QMessageBox.warning(self, "警告", "请选择串口")
                return
            
            baud_rate = int(self.baud_combo.currentText())
            success, error_msg = self.serial_manager.connect_port(port_name, baud_rate)
            
            if not success:
                QMessageBox.critical(self, "连接失败", error_msg)
    
    def _flush_history_updates(self):
        """批量刷新历史记录更新"""
        if not self.pending_history_updates:
            return
        
        # 批量添加所有待更新的记录
        for history_line in self.pending_history_updates:
            self.history_text.append(history_line)
        
        # 清空缓冲区
        self.pending_history_updates.clear()
        
        # 自动滚动到底部
        if self.auto_scroll_cb.isChecked():
            cursor = self.history_text.textCursor()
            cursor.movePosition(cursor.End)
            self.history_text.setTextCursor(cursor)

    @pyqtSlot(str)
    def on_port_connected(self, port_name):
        """串口连接成功"""
        self.connection_status.setText(f"已连接: {port_name}")
        self.connection_status.setStyleSheet("color: green; font-weight: bold;")
        self.connect_btn.setText("断开")
        
        # 启用发送按钮
        self.single_send_btn.setEnabled(True)
        self.cyclic_send_btn.setEnabled(True)
        
        self.status_bar.showMessage(f"串口 {port_name} 连接成功")
    
    @pyqtSlot(str)
    def on_port_disconnected(self, port_name):
        """串口断开连接"""
        self.connection_status.setText("未连接")
        self.connection_status.setStyleSheet("color: red; font-weight: bold;")
        self.connect_btn.setText("连接")
        
        # 禁用发送按钮
        self.single_send_btn.setEnabled(False)
        self.cyclic_send_btn.setEnabled(False)
        self.cyclic_send_btn.setText("循环发送")
        
        self.send_status.setText("就绪")
        self.send_status.setStyleSheet("color: blue; font-weight: bold;")
        
        self.status_bar.showMessage(f"串口 {port_name} 已断开")
    
    @pyqtSlot(int)
    def on_tosc_changed(self, value):
        """Tosc值变化"""
        self.serial_manager.set_tosc_value(value)
    
    @pyqtSlot(str)
    def on_protocol_changed(self, protocol_name):
        """协议切换处理"""
        self.current_protocol = protocol_name
        
        # 根据协议类型切换Status配置界面
        if protocol_name == PROTOCOL_RUILUN:
            self.switch_to_ruilun_protocol()
        elif protocol_name == PROTOCOL_XINRI:
            self.switch_to_xinri_protocol()
        elif protocol_name == PROTOCOL_HANGZHOU_ANXIAN:
            self.switch_to_hangzhou_anxian_protocol()
        elif protocol_name == PROTOCOL_CHANGZHOU_XINSIWEI:
            self.switch_to_changzhou_xinsiwei_protocol()
        elif protocol_name == PROTOCOL_WUXI_YIGE:
            self.switch_to_wuxi_yige_protocol()
        elif protocol_name == PROTOCOL_YADEA:
            self.switch_to_yadea_protocol()
        elif protocol_name == PROTOCOL_DONGWEI_GTXH:
            self.switch_to_dongwei_gtxh_protocol()
        elif protocol_name == PROTOCOL_XINCHI:
            self.switch_to_xinchi_protocol()
        
        # 更新当前帧显示
        self.update_current_frame_display()
    
    def switch_to_ruilun_protocol(self):
        """切换到瑞轮协议"""
        # 初始化瑞轮协议的状态结构
        self.current_status = PresetScenarios.normal_running()
        
        # 显示瑞轮协议的Status配置界面
        self.show_ruilun_status_config()
        
        # 重置为正常运行场景
        self.normal_radio.setChecked(True)
        self.on_scenario_changed()
    
    def switch_to_xinri_protocol(self):
        """切换到新日协议"""
        # 初始化新日协议的状态结构
        self.current_status = PresetScenarios.xinri_normal_running()
        
        # 显示新日协议的Status配置界面
        self.show_xinri_status_config()
        
        # 重置为正常运行场景
        self.normal_radio.setChecked(True)
        self.on_scenario_changed()
    
    def switch_to_hangzhou_anxian_protocol(self):
        """切换到杭州安显协议"""
        # 初始化杭州安显协议的状态结构
        self.current_status = PresetScenarios.hangzhou_anxian_normal_running()
        
        # 显示杭州安显协议的Status配置界面
        self.show_hangzhou_anxian_status_config()
        
        # 重置为正常运行场景
        self.normal_radio.setChecked(True)
        self.on_scenario_changed()
    
    def switch_to_changzhou_xinsiwei_protocol(self):
        """切换到常州新思维协议"""
        # 初始化常州新思维协议的状态结构
        self.current_status = PresetScenarios.changzhou_xinsiwei_normal_running()
        
        # 显示常州新思维协议的Status配置界面
        self.show_changzhou_xinsiwei_status_config()
        
        # 重置为正常运行场景
        self.normal_radio.setChecked(True)
        self.on_scenario_changed()

    def switch_to_wuxi_yige_protocol(self):
        """切换到无锡一格 Y67 协议"""
        self.current_status = PresetScenarios.wuxi_yige_normal_running()
        self.show_ruilun_status_config()
        self.normal_radio.setChecked(True)
        self.on_scenario_changed()

    def switch_to_yadea_protocol(self):
        """切换到雅迪协议"""
        self.current_status = PresetScenarios.yadea_normal_running()
        self.show_ruilun_status_config()
        self.normal_radio.setChecked(True)
        self.on_scenario_changed()

    def switch_to_dongwei_gtxh_protocol(self):
        """切换到东威 GTXH 协议"""
        self.current_status = PresetScenarios.dongwei_gtxh_normal_running()
        self.show_ruilun_status_config()
        self.normal_radio.setChecked(True)
        self.on_scenario_changed()

    def switch_to_xinchi_protocol(self):
        """切换到芯驰 BMS 协议"""
        self.current_status = PresetScenarios.xinchi_normal_running()
        self.show_xinchi_status_config()
        self.normal_radio.setChecked(True)
        self.on_scenario_changed()

    def show_ruilun_status_config(self):
        """显示瑞轮协议Status配置界面"""
        # 清除现有标签页
        self.status_tabs.clear()
        
        # 添加瑞轮协议的标签页
        status1_tab = self.create_ruilun_status1_tab()
        self.status_tabs.addTab(status1_tab, "Status1")
        
        status2_tab = self.create_ruilun_status2_tab()
        self.status_tabs.addTab(status2_tab, "Status2")
        
        status3_tab = self.create_ruilun_status3_tab()
        self.status_tabs.addTab(status3_tab, "Status3")
        
        status4_tab = self.create_ruilun_status4_tab()
        self.status_tabs.addTab(status4_tab, "Status4")
        
        status5_9_tab = self.create_ruilun_status5_9_tab()
        self.status_tabs.addTab(status5_9_tab, "Status5-9")
        self._compact_status_tab_pages()
        
        # 重新连接信号
        self.connect_status_signals()

    def show_changzhou_xinsiwei_status_config(self):
        """显示常州新思维协议Status配置界面"""
        # 清除现有标签页
        self.status_tabs.clear()
        
        # 添加常州新思维协议的标签页
        status1_tab = self.create_xinsiwei_status1_tab()
        self.status_tabs.addTab(status1_tab, "Status1")
        
        status2_tab = self.create_xinsiwei_status2_tab()
        self.status_tabs.addTab(status2_tab, "Status2")
        
        status3_tab = self.create_xinsiwei_status3_tab()
        self.status_tabs.addTab(status3_tab, "Status3")
        
        status4_tab = self.create_xinsiwei_status4_tab()
        self.status_tabs.addTab(status4_tab, "Status4")
        
        status5_9_tab = self.create_xinsiwei_status5_9_tab()
        self.status_tabs.addTab(status5_9_tab, "Status5-9")
        
        # 重新连接信号
        self._compact_status_tab_pages()
        self.connect_changzhou_xinsiwei_status_signals()

    def show_xinri_status_config(self):
        """显示新日协议Status配置界面"""
        # 清除现有标签页
        self.status_tabs.clear()
        
        # 添加新日协议的标签页
        self.status_tabs.addTab(self.create_xinri_vehicle_status_tab(), "车辆状态")
        self.status_tabs.addTab(self.create_xinri_fault_status_tab(), "故障状态")
        self.status_tabs.addTab(self.create_xinri_light_status_tab(), "灯光状态")
        self.status_tabs.addTab(self.create_xinri_gear_status_tab(), "档位状态")
        self.status_tabs.addTab(self.create_xinri_battery_status_tab(), "电池状态")
        
        # 重新连接信号
        self._compact_status_tab_pages()
        self.connect_xinri_status_signals()

    def show_xinchi_status_config(self):
        """显示芯驰 BMS 协议配置界面。"""
        self.status_tabs.clear()
        self.status_tabs.addTab(self.create_xinchi_status_flags_tab(), "BMS状态")
        self.status_tabs.addTab(self.create_xinchi_battery_data_tab(), "电池数据")
        self._compact_status_tab_pages()
        self.connect_xinchi_status_signals()

    def create_xinchi_status_flags_tab(self) -> QWidget:
        """创建芯驰 BMS 状态页。"""
        widget = QWidget()
        layout = QGridLayout(widget)

        self.xinchi_charge_mos_cb = QCheckBox("充电MOS状态 (D7)")
        layout.addWidget(self.xinchi_charge_mos_cb, 0, 0)
        self.xinchi_discharge_mos_cb = QCheckBox("放电MOS状态 (D6)")
        layout.addWidget(self.xinchi_discharge_mos_cb, 0, 1)

        self.xinchi_high_temp_fault_cb = QCheckBox("高温故障 (D5)")
        layout.addWidget(self.xinchi_high_temp_fault_cb, 1, 0)
        self.xinchi_low_temp_fault_cb = QCheckBox("低温故障 (D4)")
        layout.addWidget(self.xinchi_low_temp_fault_cb, 1, 1)

        self.xinchi_over_voltage_fault_cb = QCheckBox("过压故障 (D3)")
        layout.addWidget(self.xinchi_over_voltage_fault_cb, 2, 0)
        self.xinchi_under_voltage_fault_cb = QCheckBox("欠压故障 (D2)")
        layout.addWidget(self.xinchi_under_voltage_fault_cb, 2, 1)

        self.xinchi_reserved_d1_cb = QCheckBox("Reserved (D1)")
        self.xinchi_reserved_d1_cb.setEnabled(False)
        layout.addWidget(self.xinchi_reserved_d1_cb, 3, 0)

        self.xinchi_bms_fault_cb = QCheckBox("BMS故障 (D0)")
        layout.addWidget(self.xinchi_bms_fault_cb, 3, 1)

        return widget

    def create_xinchi_battery_data_tab(self) -> QWidget:
        """创建芯驰电池数据页。"""
        widget = QWidget()
        layout = QGridLayout(widget)

        layout.addWidget(QLabel("SOC (%):"), 0, 0)
        self.xinchi_soc_spin = QSpinBox()
        self.xinchi_soc_spin.setRange(0, 100)
        self.xinchi_soc_spin.setValue(80)
        layout.addWidget(self.xinchi_soc_spin, 0, 1)

        layout.addWidget(QLabel("循环次数:"), 1, 0)
        self.xinchi_cycle_count_spin = QSpinBox()
        self.xinchi_cycle_count_spin.setRange(0, 65535)
        layout.addWidget(self.xinchi_cycle_count_spin, 1, 1)

        layout.addWidget(QLabel("电池温度 (℃):"), 2, 0)
        self.xinchi_temperature_spin = QSpinBox()
        self.xinchi_temperature_spin.setRange(-40, 120)
        self.xinchi_temperature_spin.setValue(25)
        layout.addWidget(self.xinchi_temperature_spin, 2, 1)

        layout.addWidget(QLabel("总电压 (V):"), 3, 0)
        self.xinchi_total_voltage_spin = QDoubleSpinBox()
        self.xinchi_total_voltage_spin.setRange(0.0, 6553.5)
        self.xinchi_total_voltage_spin.setDecimals(1)
        self.xinchi_total_voltage_spin.setSingleStep(0.1)
        self.xinchi_total_voltage_spin.setValue(48.0)
        layout.addWidget(self.xinchi_total_voltage_spin, 3, 1)

        layout.addWidget(QLabel("总电流 (A):"), 4, 0)
        self.xinchi_total_current_spin = QSpinBox()
        self.xinchi_total_current_spin.setRange(0, 255)
        self.xinchi_total_current_spin.setValue(0)
        layout.addWidget(self.xinchi_total_current_spin, 4, 1)

        return widget
    
    def create_xinsiwei_status1_tab(self) -> QWidget:
        """创建常州新思维协议Status1配置标签页"""
        widget = QWidget()
        layout = QGridLayout(widget)
        
        # Status1位定义（根据常州新思维协议文档）
        self.xinsiwei_reserved_d3_cb = QCheckBox("保留位 D3")
        layout.addWidget(self.xinsiwei_reserved_d3_cb, 0, 0)
        
        self.xinsiwei_reserved_d2_cb = QCheckBox("保留位 D2")
        layout.addWidget(self.xinsiwei_reserved_d2_cb, 0, 1)
        
        self.xinsiwei_reserved_d1_cb = QCheckBox("保留位 D1")
        layout.addWidget(self.xinsiwei_reserved_d1_cb, 1, 0)
        
        self.xinsiwei_reserved_d0_cb = QCheckBox("保留位 D0")
        layout.addWidget(self.xinsiwei_reserved_d0_cb, 1, 1)
        
        return widget

    def create_xinsiwei_status2_tab(self) -> QWidget:
        """创建常州新思维协议Status2配置标签页"""
        widget = QWidget()
        layout = QGridLayout(widget)
        layout.setSpacing(8)  # 减少间距
        layout.setContentsMargins(10, 10, 10, 10)  # 减少边距
        
        # Status2位定义（复用瑞轮协议的Status2定义）
        self.hall_fault_cb = QCheckBox("霍尔故障 (D6)")
        layout.addWidget(self.hall_fault_cb, 0, 0)
        
        self.throttle_fault_cb = QCheckBox("转把故障 (D5)")
        layout.addWidget(self.throttle_fault_cb, 0, 1)
        
        self.controller_fault_cb = QCheckBox("控制器故障 (D4)")
        layout.addWidget(self.controller_fault_cb, 1, 0)
        
        self.under_voltage_cb = QCheckBox("欠压保护 (D3)")
        layout.addWidget(self.under_voltage_cb, 1, 1)
        
        self.cruise_cb = QCheckBox("巡航 (D2)")
        layout.addWidget(self.cruise_cb, 2, 0)
        
        self.assist_cb = QCheckBox("助力 (D1)")
        layout.addWidget(self.assist_cb, 2, 1)
        
        self.motor_phase_loss_cb = QCheckBox("电机缺相 (D0)")
        layout.addWidget(self.motor_phase_loss_cb, 3, 0)
        
        # 添加垂直弹簧，将控件推向顶部
        layout.setRowStretch(4, 1)
        
        return widget

    def create_xinsiwei_status3_tab(self) -> QWidget:
        """创建常州新思维协议Status3配置标签页"""
        widget = QWidget()
        layout = QGridLayout(widget)
        layout.setSpacing(8)  # 减少间距
        layout.setContentsMargins(10, 10, 10, 10)  # 减少边距
        
        # Status3位定义（复用瑞轮协议的Status3定义）
        self.gear_four_cb = QCheckBox("四档指示 (D7)")
        layout.addWidget(self.gear_four_cb, 0, 0)
        
        self.motor_running_cb = QCheckBox("电机运行状态 (D6) - 1=运行/0=停止")
        layout.addWidget(self.motor_running_cb, 0, 1)
        
        self.brake_cb = QCheckBox("刹车 (D5)")
        layout.addWidget(self.brake_cb, 1, 0)
        
        self.controller_protect_cb = QCheckBox("控制器保护 (D4)")
        layout.addWidget(self.controller_protect_cb, 1, 1)
        
        self.regen_charging_cb = QCheckBox("滑行充电 (D3) - 1=能量回收")
        layout.addWidget(self.regen_charging_cb, 2, 0)
        
        self.anti_runaway_cb = QCheckBox("防飞车保护 (D2)")
        layout.addWidget(self.anti_runaway_cb, 2, 1)
        
        # 三速模式
        layout.addWidget(QLabel("三速模式 (D1~D0):"), 3, 0)
        self.speed_mode_spin = QSpinBox()
        self.speed_mode_spin.setRange(0, 3)
        layout.addWidget(self.speed_mode_spin, 3, 1)
        
        # 添加垂直弹簧，将控件推向顶部
        layout.setRowStretch(4, 1)
        
        return widget

    def create_xinsiwei_status4_tab(self) -> QWidget:
        """创建常州新思维协议Status4配置标签页"""
        widget = QWidget()
        layout = QGridLayout(widget)
        layout.setSpacing(8)  # 减少间距
        layout.setContentsMargins(10, 10, 10, 10)  # 减少边距
        
        self.current_70_flag_cb = QCheckBox("备用 (D7)")
        self.current_70_flag_cb.setEnabled(False)
        layout.addWidget(self.current_70_flag_cb, 0, 0)
        
        self.one_key_enable_cb = QCheckBox("一键通启用 (D6)")
        layout.addWidget(self.one_key_enable_cb, 0, 1)
        
        self.ekk_enable_cb = QCheckBox("EKK启用 (D5)")
        layout.addWidget(self.ekk_enable_cb, 1, 0)
        
        self.over_current_cb = QCheckBox("过流保护 (D4)")
        layout.addWidget(self.over_current_cb, 1, 1)
        
        self.stall_protect_cb = QCheckBox("堵转保护 (D3)")
        layout.addWidget(self.stall_protect_cb, 2, 0)
        
        self.reverse_cb = QCheckBox("倒车 (D2)")
        layout.addWidget(self.reverse_cb, 2, 1)
        
        self.electronic_brake_cb = QCheckBox("电子刹车 (D1)")
        layout.addWidget(self.electronic_brake_cb, 3, 0)
        
        self.speed_limit_cb = QCheckBox("限速 (D0) - 1=限速/0=解除")
        layout.addWidget(self.speed_limit_cb, 3, 1)
        
        # 添加垂直弹簧，将控件推向顶部
        layout.setRowStretch(4, 1)
        
        return widget

    def create_xinsiwei_status5_9_tab(self) -> QWidget:
        """创建常州新思维协议Status5-9配置标签页"""
        widget = QWidget()
        main_layout = QVBoxLayout(widget)
        main_layout.setSpacing(8)  # 减少间距
        main_layout.setContentsMargins(10, 10, 10, 10)  # 减少边距
        
        # 创建滚动区域以防内容过多
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        scroll_widget = QWidget()
        layout = QGridLayout(scroll_widget)
        layout.setSpacing(6)  # 更紧凑的间距
        layout.setContentsMargins(5, 5, 5, 5)  # 更小的边距
        
        # Status5 - 运行电流
        layout.addWidget(QLabel("运行电流 (A):"), 0, 0)
        self.current_spin = QSpinBox()
        self.current_spin.setRange(-128, 127)
        self.current_spin.setValue(0)
        layout.addWidget(self.current_spin, 0, 1)
        
        # Status6~7 - 霍尔计数速度（常州新思维协议特有）
        layout.addWidget(QLabel("霍尔计数速度:"), 1, 0)
        self.xinsiwei_hall_count_spin = QSpinBox()
        self.xinsiwei_hall_count_spin.setRange(0, 65535)
        self.xinsiwei_hall_count_spin.setValue(0)
        layout.addWidget(self.xinsiwei_hall_count_spin, 1, 1)
        
        # Status8 - 电池SOC
        layout.addWidget(QLabel("电池SOC (%):"), 2, 0)
        soc_layout = QHBoxLayout()
        self.soc_spin = QSpinBox()
        self.soc_spin.setRange(0, 100)
        self.soc_spin.setValue(50)
        soc_layout.addWidget(self.soc_spin)
        
        self.soc_fault_cb = QCheckBox("SOC故障")
        self.soc_fault_cb.toggled.connect(self.on_soc_fault_toggled)
        soc_layout.addWidget(self.soc_fault_cb)
        soc_widget = QWidget()
        soc_widget.setLayout(soc_layout)
        layout.addWidget(soc_widget, 2, 1)
        
        # Status9 - 系统电压 - 使用更紧凑的布局
        voltage_group = QGroupBox("系统电压")
        voltage_layout = QGridLayout(voltage_group)
        voltage_layout.setSpacing(4)  # 更紧凑的间距
        voltage_layout.setContentsMargins(8, 8, 8, 8)  # 更小的边距
        
        self.voltage_group = QButtonGroup()
        
        self.voltage_24v_rb = QRadioButton("24V")
        self.voltage_group.addButton(self.voltage_24v_rb, 0)
        voltage_layout.addWidget(self.voltage_24v_rb, 0, 0)
        
        self.voltage_36v_rb = QRadioButton("36V")
        self.voltage_group.addButton(self.voltage_36v_rb, 1)
        voltage_layout.addWidget(self.voltage_36v_rb, 0, 1)
        
        self.voltage_48v_rb = QRadioButton("48V")
        self.voltage_48v_rb.setChecked(True)  # 默认选中48V
        self.voltage_group.addButton(self.voltage_48v_rb, 2)
        voltage_layout.addWidget(self.voltage_48v_rb, 0, 2)
        
        self.voltage_60v_rb = QRadioButton("60V")
        self.voltage_group.addButton(self.voltage_60v_rb, 3)
        voltage_layout.addWidget(self.voltage_60v_rb, 1, 0)
        
        self.voltage_72v_rb = QRadioButton("72V")
        self.voltage_group.addButton(self.voltage_72v_rb, 4)
        voltage_layout.addWidget(self.voltage_72v_rb, 1, 1)
        
        layout.addWidget(voltage_group, 3, 0, 1, 2)
        
        # 常州新思维协议特有字段
        layout.addWidget(QLabel("协议标识:"), 4, 0)
        self.protocol_id_spin = QSpinBox()
        self.protocol_id_spin.setRange(0, 15)
        self.protocol_id_spin.setValue(1)  # 默认协议标识为1
        layout.addWidget(self.protocol_id_spin, 4, 1)
        
        layout.addWidget(QLabel("序列号 (0-4095):"), 5, 0)
        self.sequence_num_spin = QSpinBox()
        self.sequence_num_spin.setRange(0, 4095)
        self.sequence_num_spin.setValue(0)
        layout.addWidget(self.sequence_num_spin, 5, 1)
        
        # 设置滚动区域
        scroll_area.setWidget(scroll_widget)
        main_layout.addWidget(scroll_area)
        
        return widget

    def create_xinri_vehicle_status_tab(self) -> QWidget:
        """创建新日协议车辆状态配置标签页"""
        widget = QWidget()
        layout = QGridLayout(widget)
        
        # 车辆状态位定义（基于新日协议规范）
        self.xinri_power_on_cb = QCheckBox("电源开启")
        layout.addWidget(self.xinri_power_on_cb, 0, 0)
        
        self.xinri_motor_running_cb = QCheckBox("电机运行")
        layout.addWidget(self.xinri_motor_running_cb, 0, 1)
        
        self.xinri_charging_cb = QCheckBox("充电状态")
        layout.addWidget(self.xinri_charging_cb, 1, 0)
        
        self.xinri_brake_cb = QCheckBox("刹车状态")
        layout.addWidget(self.xinri_brake_cb, 1, 1)
        
        self.xinri_cruise_cb = QCheckBox("巡航模式")
        layout.addWidget(self.xinri_cruise_cb, 2, 0)
        
        self.xinri_eco_mode_cb = QCheckBox("ECO模式")
        layout.addWidget(self.xinri_eco_mode_cb, 2, 1)
        
        self.xinri_sport_mode_cb = QCheckBox("运动模式")
        layout.addWidget(self.xinri_sport_mode_cb, 3, 0)
        
        self.xinri_reverse_cb = QCheckBox("倒车状态")
        layout.addWidget(self.xinri_reverse_cb, 3, 1)
        
        return widget
    
    def create_xinri_fault_status_tab(self) -> QWidget:
        """创建新日协议故障状态配置标签页"""
        widget = QWidget()
        layout = QGridLayout(widget)
        
        # 故障状态位定义
        self.xinri_motor_fault_cb = QCheckBox("电机故障")
        layout.addWidget(self.xinri_motor_fault_cb, 0, 0)
        
        self.xinri_controller_fault_cb = QCheckBox("控制器故障")
        layout.addWidget(self.xinri_controller_fault_cb, 0, 1)
        
        self.xinri_battery_fault_cb = QCheckBox("电池故障")
        layout.addWidget(self.xinri_battery_fault_cb, 1, 0)
        
        self.xinri_throttle_fault_cb = QCheckBox("转把故障")
        layout.addWidget(self.xinri_throttle_fault_cb, 1, 1)
        
        self.xinri_brake_fault_cb = QCheckBox("刹车故障")
        layout.addWidget(self.xinri_brake_fault_cb, 2, 0)
        
        self.xinri_hall_fault_cb = QCheckBox("霍尔故障")
        layout.addWidget(self.xinri_hall_fault_cb, 2, 1)
        
        self.xinri_over_temp_cb = QCheckBox("过温保护")
        layout.addWidget(self.xinri_over_temp_cb, 3, 0)
        
        self.xinri_under_voltage_cb = QCheckBox("欠压保护")
        layout.addWidget(self.xinri_under_voltage_cb, 3, 1)
        
        return widget
    
    def create_xinri_light_status_tab(self) -> QWidget:
        """创建新日协议灯光状态配置标签页"""
        widget = QWidget()
        layout = QGridLayout(widget)
        
        # 灯光状态位定义
        self.xinri_headlight_cb = QCheckBox("前大灯")
        layout.addWidget(self.xinri_headlight_cb, 0, 0)
        
        self.xinri_taillight_cb = QCheckBox("尾灯")
        layout.addWidget(self.xinri_taillight_cb, 0, 1)
        
        self.xinri_left_turn_cb = QCheckBox("左转向灯")
        layout.addWidget(self.xinri_left_turn_cb, 1, 0)
        
        self.xinri_right_turn_cb = QCheckBox("右转向灯")
        layout.addWidget(self.xinri_right_turn_cb, 1, 1)
        
        self.xinri_hazard_cb = QCheckBox("危险报警灯")
        layout.addWidget(self.xinri_hazard_cb, 2, 0)
        
        self.xinri_brake_light_cb = QCheckBox("刹车灯")
        layout.addWidget(self.xinri_brake_light_cb, 2, 1)
        
        self.xinri_high_beam_cb = QCheckBox("远光灯")
        layout.addWidget(self.xinri_high_beam_cb, 3, 0)
        
        self.xinri_low_beam_cb = QCheckBox("近光灯")
        layout.addWidget(self.xinri_low_beam_cb, 3, 1)
        
        return widget
    
    def create_xinri_gear_status_tab(self) -> QWidget:
        """创建新日协议档位状态配置标签页"""
        widget = QWidget()
        layout = QGridLayout(widget)
        
        # 档位状态位定义
        self.xinri_gear_p_cb = QCheckBox("P档（驻车）")
        layout.addWidget(self.xinri_gear_p_cb, 0, 0)
        
        self.xinri_gear_r_cb = QCheckBox("R档（倒车）")
        layout.addWidget(self.xinri_gear_r_cb, 0, 1)
        
        self.xinri_gear_n_cb = QCheckBox("N档（空档）")
        layout.addWidget(self.xinri_gear_n_cb, 1, 0)
        
        self.xinri_gear_d_cb = QCheckBox("D档（前进）")
        layout.addWidget(self.xinri_gear_d_cb, 1, 1)
        
        self.xinri_gear_1_cb = QCheckBox("1档")
        layout.addWidget(self.xinri_gear_1_cb, 2, 0)
        
        self.xinri_gear_2_cb = QCheckBox("2档")
        layout.addWidget(self.xinri_gear_2_cb, 2, 1)
        
        self.xinri_gear_3_cb = QCheckBox("3档")
        layout.addWidget(self.xinri_gear_3_cb, 3, 0)
        
        self.xinri_gear_boost_cb = QCheckBox("助力档")
        layout.addWidget(self.xinri_gear_boost_cb, 3, 1)
        
        return widget
    
    def create_xinri_battery_status_tab(self) -> QWidget:
        """创建新日协议电池状态配置标签页"""
        widget = QWidget()
        layout = QGridLayout(widget)
        
        # 电池状态位定义
        self.xinri_battery_normal_cb = QCheckBox("电池正常")
        layout.addWidget(self.xinri_battery_normal_cb, 0, 0)
        
        self.xinri_battery_low_cb = QCheckBox("电量低")
        layout.addWidget(self.xinri_battery_low_cb, 0, 1)
        
        self.xinri_battery_critical_cb = QCheckBox("电量极低")
        layout.addWidget(self.xinri_battery_critical_cb, 1, 0)
        
        self.xinri_battery_charging_cb = QCheckBox("充电中")
        layout.addWidget(self.xinri_battery_charging_cb, 1, 1)
        
        self.xinri_battery_full_cb = QCheckBox("充电完成")
        layout.addWidget(self.xinri_battery_full_cb, 2, 0)
        
        self.xinri_battery_temp_high_cb = QCheckBox("电池温度高")
        layout.addWidget(self.xinri_battery_temp_high_cb, 2, 1)
        
        self.xinri_battery_temp_low_cb = QCheckBox("电池温度低")
        layout.addWidget(self.xinri_battery_temp_low_cb, 3, 0)
        
        self.xinri_battery_error_cb = QCheckBox("电池通信错误")
        layout.addWidget(self.xinri_battery_error_cb, 3, 1)
        
        return widget
    
    def connect_xinri_status_signals(self):
        """连接新日协议状态信号"""
        # 车辆状态控件
        self.xinri_power_on_cb.toggled.connect(self.update_current_frame_display)
        self.xinri_motor_running_cb.toggled.connect(self.update_current_frame_display)
        self.xinri_charging_cb.toggled.connect(self.update_current_frame_display)
        self.xinri_brake_cb.toggled.connect(self.update_current_frame_display)
        self.xinri_cruise_cb.toggled.connect(self.update_current_frame_display)
        self.xinri_eco_mode_cb.toggled.connect(self.update_current_frame_display)
        self.xinri_sport_mode_cb.toggled.connect(self.update_current_frame_display)
        self.xinri_reverse_cb.toggled.connect(self.update_current_frame_display)
        
        # 故障状态控件
        self.xinri_motor_fault_cb.toggled.connect(self.update_current_frame_display)
        self.xinri_controller_fault_cb.toggled.connect(self.update_current_frame_display)
        self.xinri_battery_fault_cb.toggled.connect(self.update_current_frame_display)
        self.xinri_throttle_fault_cb.toggled.connect(self.update_current_frame_display)
        self.xinri_brake_fault_cb.toggled.connect(self.update_current_frame_display)
        self.xinri_hall_fault_cb.toggled.connect(self.update_current_frame_display)
        self.xinri_over_temp_cb.toggled.connect(self.update_current_frame_display)
        self.xinri_under_voltage_cb.toggled.connect(self.update_current_frame_display)
        
        # 灯光状态控件
        self.xinri_headlight_cb.toggled.connect(self.update_current_frame_display)
        self.xinri_taillight_cb.toggled.connect(self.update_current_frame_display)
        self.xinri_left_turn_cb.toggled.connect(self.update_current_frame_display)
        self.xinri_right_turn_cb.toggled.connect(self.update_current_frame_display)
        self.xinri_hazard_cb.toggled.connect(self.update_current_frame_display)
        self.xinri_brake_light_cb.toggled.connect(self.update_current_frame_display)
        self.xinri_high_beam_cb.toggled.connect(self.update_current_frame_display)
        self.xinri_low_beam_cb.toggled.connect(self.update_current_frame_display)
        
        # 档位状态控件
        self.xinri_gear_p_cb.toggled.connect(self.update_current_frame_display)
        self.xinri_gear_r_cb.toggled.connect(self.update_current_frame_display)
        self.xinri_gear_n_cb.toggled.connect(self.update_current_frame_display)
        self.xinri_gear_d_cb.toggled.connect(self.update_current_frame_display)
        self.xinri_gear_1_cb.toggled.connect(self.update_current_frame_display)
        self.xinri_gear_2_cb.toggled.connect(self.update_current_frame_display)
        self.xinri_gear_3_cb.toggled.connect(self.update_current_frame_display)
        self.xinri_gear_boost_cb.toggled.connect(self.update_current_frame_display)
        
        # 电池状态控件
        self.xinri_battery_normal_cb.toggled.connect(self.update_current_frame_display)
        self.xinri_battery_low_cb.toggled.connect(self.update_current_frame_display)
        self.xinri_battery_critical_cb.toggled.connect(self.update_current_frame_display)
        self.xinri_battery_charging_cb.toggled.connect(self.update_current_frame_display)
        self.xinri_battery_full_cb.toggled.connect(self.update_current_frame_display)
        self.xinri_battery_temp_high_cb.toggled.connect(self.update_current_frame_display)
        self.xinri_battery_temp_low_cb.toggled.connect(self.update_current_frame_display)
        self.xinri_battery_error_cb.toggled.connect(self.update_current_frame_display)

    def connect_xinchi_status_signals(self):
        """连接芯驰 BMS 协议状态信号。"""
        self.xinchi_charge_mos_cb.toggled.connect(self.update_current_frame_display)
        self.xinchi_discharge_mos_cb.toggled.connect(self.update_current_frame_display)
        self.xinchi_high_temp_fault_cb.toggled.connect(self.update_current_frame_display)
        self.xinchi_low_temp_fault_cb.toggled.connect(self.update_current_frame_display)
        self.xinchi_over_voltage_fault_cb.toggled.connect(self.update_current_frame_display)
        self.xinchi_under_voltage_fault_cb.toggled.connect(self.update_current_frame_display)
        self.xinchi_bms_fault_cb.toggled.connect(self.update_current_frame_display)
        self.xinchi_soc_spin.valueChanged.connect(self.update_current_frame_display)
        self.xinchi_cycle_count_spin.valueChanged.connect(self.update_current_frame_display)
        self.xinchi_temperature_spin.valueChanged.connect(self.update_current_frame_display)
        self.xinchi_total_voltage_spin.valueChanged.connect(self.update_current_frame_display)
        self.xinchi_total_current_spin.valueChanged.connect(self.update_current_frame_display)
    
    def connect_changzhou_xinsiwei_status_signals(self):
        """连接常州新思维协议状态信号"""
        # Status1 - 预留位D0-D3
        if hasattr(self, 'xinsiwei_reserved_d0_cb'):
            self.xinsiwei_reserved_d0_cb.toggled.connect(self.update_current_frame_display)
        if hasattr(self, 'xinsiwei_reserved_d1_cb'):
            self.xinsiwei_reserved_d1_cb.toggled.connect(self.update_current_frame_display)
        if hasattr(self, 'xinsiwei_reserved_d2_cb'):
            self.xinsiwei_reserved_d2_cb.toggled.connect(self.update_current_frame_display)
        if hasattr(self, 'xinsiwei_reserved_d3_cb'):
            self.xinsiwei_reserved_d3_cb.toggled.connect(self.update_current_frame_display)
        
        # Status2 - 故障状态（复用瑞轮协议控件）
        if hasattr(self, 'hall_fault_cb'):
            self.hall_fault_cb.toggled.connect(self.update_current_frame_display)
        if hasattr(self, 'throttle_fault_cb'):
            self.throttle_fault_cb.toggled.connect(self.update_current_frame_display)
        if hasattr(self, 'controller_fault_cb'):
            self.controller_fault_cb.toggled.connect(self.update_current_frame_display)
        if hasattr(self, 'under_voltage_cb'):
            self.under_voltage_cb.toggled.connect(self.update_current_frame_display)
        if hasattr(self, 'cruise_cb'):
            self.cruise_cb.toggled.connect(self.update_current_frame_display)
        if hasattr(self, 'assist_cb'):
            self.assist_cb.toggled.connect(self.update_current_frame_display)
        if hasattr(self, 'motor_phase_loss_cb'):
            self.motor_phase_loss_cb.toggled.connect(self.update_current_frame_display)
        
        # Status3 - 运行状态（复用瑞轮协议控件）
        if hasattr(self, 'gear_four_cb'):
            self.gear_four_cb.toggled.connect(self.update_current_frame_display)
        if hasattr(self, 'motor_running_cb'):
            self.motor_running_cb.toggled.connect(self.update_current_frame_display)
        if hasattr(self, 'brake_cb'):
            self.brake_cb.toggled.connect(self.update_current_frame_display)
        if hasattr(self, 'controller_protect_cb'):
            self.controller_protect_cb.toggled.connect(self.update_current_frame_display)
        if hasattr(self, 'regen_charging_cb'):
            self.regen_charging_cb.toggled.connect(self.update_current_frame_display)
        if hasattr(self, 'anti_runaway_cb'):
            self.anti_runaway_cb.toggled.connect(self.update_current_frame_display)
        if hasattr(self, 'speed_mode_spin'):
            self.speed_mode_spin.valueChanged.connect(self.update_current_frame_display)
        
        # Status4 - 保护状态（复用瑞轮协议控件）
        if hasattr(self, 'current_70_flag_cb'):
            self.current_70_flag_cb.toggled.connect(self.update_current_frame_display)
        if hasattr(self, 'one_key_enable_cb'):
            self.one_key_enable_cb.toggled.connect(self.update_current_frame_display)
        if hasattr(self, 'ekk_enable_cb'):
            self.ekk_enable_cb.toggled.connect(self.update_current_frame_display)
        if hasattr(self, 'over_current_cb'):
            self.over_current_cb.toggled.connect(self.update_current_frame_display)
        if hasattr(self, 'stall_protect_cb'):
            self.stall_protect_cb.toggled.connect(self.update_current_frame_display)
        if hasattr(self, 'reverse_cb'):
            self.reverse_cb.toggled.connect(self.update_current_frame_display)
        if hasattr(self, 'electronic_brake_cb'):
            self.electronic_brake_cb.toggled.connect(self.update_current_frame_display)
        if hasattr(self, 'speed_limit_cb'):
            self.speed_limit_cb.toggled.connect(self.update_current_frame_display)
        
        # Status5-9 - 新思维特有控件
        if hasattr(self, 'current_spin'):
            self.current_spin.valueChanged.connect(self.update_current_frame_display)
        if hasattr(self, 'xinsiwei_hall_count_spin'):
            self.xinsiwei_hall_count_spin.valueChanged.connect(self.update_current_frame_display)
        if hasattr(self, 'soc_spin'):
            self.soc_spin.valueChanged.connect(self.update_current_frame_display)
        if hasattr(self, 'soc_fault_cb'):
            self.soc_fault_cb.toggled.connect(self.update_current_frame_display)
        if hasattr(self, 'voltage_group'):
            self.voltage_group.buttonClicked.connect(self.update_current_frame_display)
    
    def show_hangzhou_anxian_status_config(self):
        """显示杭州安显协议Status配置界面"""
        # 清除现有标签页
        self.status_tabs.clear()
        
        # 添加杭州安显协议的标签页（复用瑞轮协议的界面结构）
        status1_tab = self.create_ruilun_status1_tab()
        self.status_tabs.addTab(status1_tab, "Status1")
        
        status2_tab = self.create_ruilun_status2_tab()
        self.status_tabs.addTab(status2_tab, "Status2")
        
        status3_tab = self.create_ruilun_status3_tab()
        self.status_tabs.addTab(status3_tab, "Status3")
        
        status4_tab = self.create_ruilun_status4_tab()
        self.status_tabs.addTab(status4_tab, "Status4")
        
        status5_9_tab = self.create_ruilun_status5_9_tab()
        self.status_tabs.addTab(status5_9_tab, "Status5-9")
        
        # 重新连接信号
        self.connect_status_signals()
    
    @pyqtSlot()
    def on_scenario_changed(self):
        """场景选择变化"""
        scenario_id = self.scenario_group.checkedId()
        previous_scenario = getattr(self, '_previous_scenario_id', None)
        
        if scenario_id == 3:  # 数据自定义场景
            self.status_tabs.setEnabled(True)
            self.frame_config_btn.setEnabled(False)
        elif scenario_id == 4:  # 全部自定义场景
            self.status_tabs.setEnabled(False)
            self.frame_config_btn.setEnabled(True)
            
            # 如果是从数据自定义场景切换过来，使用当前UI中的Status配置生成帧数据
            if previous_scenario == 3:  # 从数据自定义切换过来
                current_status = self.get_current_status_from_ui()
                success, frame_data, _ = self.generate_protocol_frame(current_status)
                if success:
                    self.custom_frame_data = frame_data
                else:
                    # 如果生成失败，保持原有的自定义帧数据不变
                    pass
        else:
            self.status_tabs.setEnabled(False)
            self.frame_config_btn.setEnabled(False)
            
            # 根据当前协议加载预设场景
            if self.current_protocol == PROTOCOL_RUILUN:
                self.load_ruilun_preset_scenario(scenario_id)
            elif self.current_protocol == PROTOCOL_XINRI:
                self.load_xinri_preset_scenario(scenario_id)
            elif self.current_protocol == PROTOCOL_HANGZHOU_ANXIAN:
                self.load_hangzhou_anxian_preset_scenario(scenario_id)
            elif self.current_protocol == PROTOCOL_CHANGZHOU_XINSIWEI:
                self.load_changzhou_xinsiwei_preset_scenario(scenario_id)
            elif self.current_protocol == PROTOCOL_WUXI_YIGE:
                self.load_wuxi_yige_preset_scenario(scenario_id)
            elif self.current_protocol == PROTOCOL_YADEA:
                self.load_yadea_preset_scenario(scenario_id)
            elif self.current_protocol == PROTOCOL_DONGWEI_GTXH:
                self.load_dongwei_gtxh_preset_scenario(scenario_id)
            elif self.current_protocol == PROTOCOL_XINCHI:
                self.load_xinchi_preset_scenario(scenario_id)
        
        # 记录当前场景ID，用于下次切换时判断
        self._previous_scenario_id = scenario_id
        self.update_current_frame_display()
    
    def load_ruilun_preset_scenario(self, scenario_id):
        """加载瑞轮协议预设场景"""
        if scenario_id == 0:  # 正常运行
            self.current_status = PresetScenarios.normal_running()
        elif scenario_id == 1:  # 能量回收
            self.current_status = PresetScenarios.energy_recovery()
        elif scenario_id == 2:  # 故障场景
            self.current_status = PresetScenarios.fault_scenario()
        
        # 更新UI显示
        self.update_ruilun_ui_from_status()
    
    def load_xinri_preset_scenario(self, scenario_id):
        """加载新日协议预设场景"""
        # 新日协议现在也使用StatusBits对象
        if scenario_id == 0:  # 正常运行
            self.current_status = PresetScenarios.xinri_normal_running()
        elif scenario_id == 1:  # 能量回收
            self.current_status = PresetScenarios.xinri_energy_recovery()
        elif scenario_id == 2:  # 故障场景
            self.current_status = PresetScenarios.xinri_fault_scenario()
        else:
            # 自定义场景，初始化为空StatusBits对象
            self.current_status = StatusBits()
        
        # 更新UI显示
        self.update_xinri_ui_from_status()
    
    def load_hangzhou_anxian_preset_scenario(self, scenario_id):
        """加载杭州安显协议预设场景"""
        if scenario_id == 0:  # 正常运行
            self.current_status = PresetScenarios.hangzhou_anxian_normal_running()
        elif scenario_id == 1:  # 能量回收
            self.current_status = PresetScenarios.hangzhou_anxian_energy_recovery()
        elif scenario_id == 2:  # 故障场景
            self.current_status = PresetScenarios.hangzhou_anxian_fault_scenario()
        else:
            # 自定义场景，初始化为空StatusBits对象
            self.current_status = StatusBits()
        
        # 更新UI显示（复用瑞轮协议的UI更新逻辑）
        self.update_ruilun_ui_from_status()

    def load_wuxi_yige_preset_scenario(self, scenario_id):
        """加载无锡一格 Y67 协议预设场景"""
        if scenario_id == 0:
            self.current_status = PresetScenarios.wuxi_yige_normal_running()
        elif scenario_id == 1:
            self.current_status = PresetScenarios.wuxi_yige_energy_recovery()
        elif scenario_id == 2:
            self.current_status = PresetScenarios.wuxi_yige_fault_scenario()
        else:
            self.current_status = StatusBits(protocol_name=PROTOCOL_WUXI_YIGE)

        self.update_ruilun_ui_from_status()

    def load_yadea_preset_scenario(self, scenario_id):
        """加载雅迪协议预设场景"""
        if scenario_id == 0:
            self.current_status = PresetScenarios.yadea_normal_running()
        elif scenario_id == 1:
            self.current_status = PresetScenarios.yadea_energy_recovery()
        elif scenario_id == 2:
            self.current_status = PresetScenarios.yadea_fault_scenario()
        else:
            self.current_status = StatusBits(protocol_name=PROTOCOL_YADEA)

        self.update_ruilun_ui_from_status()

    def load_dongwei_gtxh_preset_scenario(self, scenario_id):
        """加载东威 GTXH 协议预设场景"""
        if scenario_id == 0:
            self.current_status = PresetScenarios.dongwei_gtxh_normal_running()
        elif scenario_id == 1:
            self.current_status = PresetScenarios.dongwei_gtxh_energy_recovery()
        elif scenario_id == 2:
            self.current_status = PresetScenarios.dongwei_gtxh_fault_scenario()
        else:
            self.current_status = StatusBits(protocol_name=PROTOCOL_DONGWEI_GTXH)

        self.update_ruilun_ui_from_status()

    def load_xinchi_preset_scenario(self, scenario_id):
        """加载芯驰 BMS 协议预设场景。"""
        if scenario_id == 0:
            self.current_status = PresetScenarios.xinchi_normal_running()
        elif scenario_id == 1:
            self.current_status = PresetScenarios.xinchi_energy_recovery()
        elif scenario_id == 2:
            self.current_status = PresetScenarios.xinchi_fault_scenario()
        else:
            self.current_status = StatusBits(protocol_name=PROTOCOL_XINCHI)

        self.update_xinchi_ui_from_status()
    
    def load_changzhou_xinsiwei_preset_scenario(self, scenario_id):
        """加载常州新思维协议预设场景"""
        if scenario_id == 0:  # 正常运行
            self.current_status = PresetScenarios.changzhou_xinsiwei_normal_running()
        elif scenario_id == 1:  # 能量回收
            self.current_status = PresetScenarios.changzhou_xinsiwei_energy_recovery()
        elif scenario_id == 2:  # 故障场景
            self.current_status = PresetScenarios.changzhou_xinsiwei_fault_scenario()
        else:
            # 自定义场景，初始化为空StatusBits对象
            self.current_status = StatusBits()
        
        # 更新UI显示
        self.update_changzhou_xinsiwei_ui_from_status()
    
    def update_changzhou_xinsiwei_ui_from_status(self):
        """根据常州新思维协议状态更新UI显示"""
        if not hasattr(self, 'current_status') or not isinstance(self.current_status, StatusBits):
            return
        
        status = self.current_status
        
        # 更新Status1 - 预留位D0-D3
        if hasattr(self, 'xinsiwei_reserved_d0_cb'):
            self.xinsiwei_reserved_d0_cb.setChecked(getattr(status, 'xinsiwei_reserved_d0', False))
        if hasattr(self, 'xinsiwei_reserved_d1_cb'):
            self.xinsiwei_reserved_d1_cb.setChecked(getattr(status, 'xinsiwei_reserved_d1', False))
        if hasattr(self, 'xinsiwei_reserved_d2_cb'):
            self.xinsiwei_reserved_d2_cb.setChecked(getattr(status, 'xinsiwei_reserved_d2', False))
        if hasattr(self, 'xinsiwei_reserved_d3_cb'):
            self.xinsiwei_reserved_d3_cb.setChecked(getattr(status, 'xinsiwei_reserved_d3', False))
        
        # 更新Status2
        if hasattr(self, 'hall_fault_cb'):
            self.hall_fault_cb.setChecked(getattr(status, 'hall_fault', False))
        if hasattr(self, 'throttle_fault_cb'):
            self.throttle_fault_cb.setChecked(getattr(status, 'throttle_fault', False))
        if hasattr(self, 'controller_fault_cb'):
            self.controller_fault_cb.setChecked(getattr(status, 'controller_fault', False))
        if hasattr(self, 'under_voltage_cb'):
            self.under_voltage_cb.setChecked(getattr(status, 'under_voltage', False))
        if hasattr(self, 'cruise_cb'):
            self.cruise_cb.setChecked(getattr(status, 'cruise', False))
        if hasattr(self, 'assist_cb'):
            self.assist_cb.setChecked(getattr(status, 'assist', False))
        if hasattr(self, 'motor_phase_loss_cb'):
            self.motor_phase_loss_cb.setChecked(getattr(status, 'motor_phase_loss', False))

        # 更新Status3
        if hasattr(self, 'gear_four_cb'):
            self.gear_four_cb.setChecked(getattr(status, 'gear_four', False))
        if hasattr(self, 'motor_running_cb'):
            self.motor_running_cb.setChecked(getattr(status, 'motor_running', False))
        if hasattr(self, 'brake_cb'):
            self.brake_cb.setChecked(getattr(status, 'brake', False))
        if hasattr(self, 'controller_protect_cb'):
            self.controller_protect_cb.setChecked(getattr(status, 'controller_protect', False))
        if hasattr(self, 'regen_charging_cb'):
            self.regen_charging_cb.setChecked(getattr(status, 'regen_charging', False))
        if hasattr(self, 'anti_runaway_cb'):
            self.anti_runaway_cb.setChecked(getattr(status, 'anti_runaway', False))
        if hasattr(self, 'speed_mode_spin'):
            self.speed_mode_spin.setValue(getattr(status, 'speed_mode', 0))

        # 更新Status4
        if hasattr(self, 'one_key_enable_cb'):
            self.one_key_enable_cb.setChecked(getattr(status, 'one_key_enable', False))
        if hasattr(self, 'ekk_enable_cb'):
            self.ekk_enable_cb.setChecked(getattr(status, 'ekk_enable', False))
        if hasattr(self, 'over_current_cb'):
            self.over_current_cb.setChecked(getattr(status, 'over_current', False))
        if hasattr(self, 'stall_protect_cb'):
            self.stall_protect_cb.setChecked(getattr(status, 'stall_protect', False))
        if hasattr(self, 'reverse_cb'):
            self.reverse_cb.setChecked(getattr(status, 'reverse', False))
        if hasattr(self, 'electronic_brake_cb'):
            self.electronic_brake_cb.setChecked(getattr(status, 'electronic_brake', False))
        if hasattr(self, 'speed_limit_cb'):
            self.speed_limit_cb.setChecked(getattr(status, 'speed_limit', False))

        # 更新Status5-9
        if hasattr(self, 'current_spin'):
            self.current_spin.setValue(getattr(status, 'current_a', 0))
        if hasattr(self, 'xinsiwei_hall_count_spin'):
            self.xinsiwei_hall_count_spin.setValue(getattr(status, 'xinsiwei_hall_count', 0))
        if hasattr(self, 'soc_spin'):
            self.soc_spin.setValue(getattr(status, 'soc_percent', 0))
        if hasattr(self, 'soc_fault_cb'):
            self.soc_fault_cb.setChecked(getattr(status, 'soc_fault', False))

        voltage_map = [
            status.voltage_24v,
            status.voltage_36v,
            status.voltage_48v,
            status.voltage_60v,
            status.voltage_72v,
        ]
        checked_index = next((index for index, checked in enumerate(voltage_map) if checked), None)
        if checked_index is not None and hasattr(self, 'voltage_group'):
            button = self.voltage_group.button(checked_index)
            if button is not None:
                button.setChecked(True)
    
    def update_ruilun_ui_from_status(self):
        """根据瑞轮协议状态更新UI显示（杭州安显协议复用此逻辑）"""
        if not hasattr(self, 'current_status') or not isinstance(self.current_status, StatusBits):
            return
        
        status = self.current_status

        if self.current_protocol == PROTOCOL_HANGZHOU_ANXIAN:
            self.distance_mode_cb.setChecked(False)
            self.speed_alarm_cb.setChecked(getattr(status, "protocol_speed_limit", False))
            self.p_gear_protect_cb.setChecked(getattr(status, "p_gear_protect", False))
            self.tcs_status_cb.setChecked(False)
        elif self.current_protocol == PROTOCOL_DONGWEI_GTXH:
            self.distance_mode_cb.setChecked(False)
            self.speed_alarm_cb.setChecked(False)
            self.p_gear_protect_cb.setChecked(getattr(status, "p_gear_protect", False))
            self.tcs_status_cb.setChecked(False)
        elif self.current_protocol == PROTOCOL_WUXI_YIGE:
            self.distance_mode_cb.setChecked(getattr(status, "side_stand", False))
            self.speed_alarm_cb.setChecked(False)
            self.p_gear_protect_cb.setChecked(getattr(status, "p_gear_protect", False))
            self.tcs_status_cb.setChecked(False)
        elif self.current_protocol == PROTOCOL_YADEA:
            self.distance_mode_cb.setChecked(getattr(status, "side_stand", False))
            self.speed_alarm_cb.setChecked(False)
            self.p_gear_protect_cb.setChecked(getattr(status, "p_gear_protect", False))
            self.tcs_status_cb.setChecked(False)
        else:
            self.distance_mode_cb.setChecked(getattr(status, "distance_mode", False))
            self.speed_alarm_cb.setChecked(getattr(status, "speed_alarm", False))
            self.p_gear_protect_cb.setChecked(getattr(status, "p_gear_protect", False))
            self.tcs_status_cb.setChecked(getattr(status, "tcs_status", False))

        self.status2_d7_cb.setChecked(getattr(status, "walk_mode", False))
        self.hall_fault_cb.setChecked(getattr(status, "hall_fault", False))
        self.throttle_fault_cb.setChecked(getattr(status, "throttle_fault", False))
        self.controller_fault_cb.setChecked(getattr(status, "controller_fault", False))
        self.under_voltage_cb.setChecked(getattr(status, "under_voltage", False))
        self.cruise_cb.setChecked(getattr(status, "cruise", False))
        self.assist_cb.setChecked(getattr(status, "assist", False))
        self.motor_phase_loss_cb.setChecked(getattr(status, "motor_phase_loss", False))

        self.gear_four_cb.setChecked(getattr(status, "gear_four", False))
        self.motor_running_cb.setChecked(getattr(status, "motor_running", False))
        self.brake_cb.setChecked(getattr(status, "brake", False))
        self.controller_protect_cb.setChecked(getattr(status, "controller_protect", False))
        self.regen_charging_cb.setChecked(getattr(status, "regen_charging", False))
        self.anti_runaway_cb.setChecked(getattr(status, "anti_runaway", False))
        self.speed_mode_spin.setValue(getattr(status, "speed_mode", 0))

        if self.current_protocol == PROTOCOL_WUXI_YIGE:
            self.current_70_flag_cb.setChecked(getattr(status, "cloud_power_mode", False))
        else:
            self.current_70_flag_cb.setChecked(getattr(status, "current_70_flag", False))
        if self.current_protocol == PROTOCOL_DONGWEI_GTXH:
            self.one_key_enable_cb.setChecked(getattr(status, "side_stand", False))
        else:
            self.one_key_enable_cb.setChecked(getattr(status, "one_key_enable", False))
        self.ekk_enable_cb.setChecked(getattr(status, "ekk_enable", False))
        self.over_current_cb.setChecked(getattr(status, "over_current", False))
        self.stall_protect_cb.setChecked(getattr(status, "stall_protect", False))
        self.reverse_cb.setChecked(getattr(status, "reverse", False))
        self.electronic_brake_cb.setChecked(getattr(status, "electronic_brake", False))
        self.speed_limit_cb.setChecked(getattr(status, "speed_limit", False))

        self.current_spin.setValue(getattr(status, "current_a", 0))
        self.hall_count_spin.setValue(getattr(status, "hall_count", 0))
        self.speed_spin.setValue(getattr(status, "speed_kmh", 0.0))
        if self.current_protocol == PROTOCOL_HANGZHOU_ANXIAN:
            self.soc_spin.setValue(getattr(status, "voltage_percentage", 0))
        else:
            self.soc_spin.setValue(getattr(status, "soc_percent", 0))

        if getattr(self, "lithium_soc_mode_cb", None) is not None:
            self.lithium_soc_mode_cb.setChecked(getattr(status, "lithium_soc_mode", True))
        if getattr(self, "soc_fault_cb", None) is not None:
            self.soc_fault_cb.setChecked(getattr(status, "soc_fault", False))
        if getattr(self, "current_percent_spin", None) is not None:
            self.current_percent_spin.setValue(getattr(status, "current_percentage", 0))

        if getattr(self, "voltage_group", None) is not None:
            voltage_map = [
                status.voltage_36v,
                status.voltage_48v,
                status.voltage_60v,
                status.voltage_64v,
                status.voltage_72v,
                status.voltage_80v,
                status.voltage_84v,
                status.voltage_96v,
            ]
            checked_index = next((index for index, checked in enumerate(voltage_map) if checked), None)
            if checked_index is not None:
                button = self.voltage_group.button(checked_index)
                if button is not None:
                    button.setChecked(True)
            elif self.current_protocol == PROTOCOL_DONGWEI_GTXH and hasattr(self, "voltage_default_rb"):
                self.voltage_default_rb.setChecked(True)
    
    def update_xinri_ui_from_status(self):
        """根据新日协议状态更新UI显示"""
        if not hasattr(self, 'current_status') or not isinstance(self.current_status, StatusBits):
            return
        
        status = self.current_status
        
        # 更新车辆状态 - 映射到StatusBits对应的属性
        if hasattr(self, 'xinri_power_on_cb'):
            self.xinri_power_on_cb.setChecked(getattr(status, 'power_on', False))
        if hasattr(self, 'xinri_motor_running_cb'):
            self.xinri_motor_running_cb.setChecked(getattr(status, 'motor_running', False))
        if hasattr(self, 'xinri_charging_cb'):
            self.xinri_charging_cb.setChecked(getattr(status, 'regen_charging', False))
        if hasattr(self, 'xinri_brake_cb'):
            self.xinri_brake_cb.setChecked(getattr(status, 'brake', False))
        if hasattr(self, 'xinri_cruise_cb'):
            self.xinri_cruise_cb.setChecked(getattr(status, 'cruise', False))
        if hasattr(self, 'xinri_eco_mode_cb'):
            self.xinri_eco_mode_cb.setChecked(getattr(status, 'eco_mode', False))
        if hasattr(self, 'xinri_sport_mode_cb'):
            self.xinri_sport_mode_cb.setChecked(getattr(status, 'sport_mode', False))
        if hasattr(self, 'xinri_reverse_cb'):
            self.xinri_reverse_cb.setChecked(getattr(status, 'reverse', False))
        
        # 更新故障状态
        if hasattr(self, 'xinri_motor_fault_cb'):
            self.xinri_motor_fault_cb.setChecked(getattr(status, 'motor_fault', False))
        if hasattr(self, 'xinri_controller_fault_cb'):
            self.xinri_controller_fault_cb.setChecked(getattr(status, 'controller_fault', False))
        if hasattr(self, 'xinri_battery_fault_cb'):
            self.xinri_battery_fault_cb.setChecked(getattr(status, 'battery_fault', False))
        if hasattr(self, 'xinri_throttle_fault_cb'):
            self.xinri_throttle_fault_cb.setChecked(getattr(status, 'throttle_fault', False))
        if hasattr(self, 'xinri_brake_fault_cb'):
            self.xinri_brake_fault_cb.setChecked(getattr(status, 'brake_fault', False))
        if hasattr(self, 'xinri_hall_fault_cb'):
            self.xinri_hall_fault_cb.setChecked(getattr(status, 'hall_fault', False))
        if hasattr(self, 'xinri_over_temp_cb'):
            self.xinri_over_temp_cb.setChecked(getattr(status, 'over_temp', False))
        if hasattr(self, 'xinri_under_voltage_cb'):
            self.xinri_under_voltage_cb.setChecked(getattr(status, 'under_voltage', False))
        
        # 更新灯光状态
        if hasattr(self, 'xinri_headlight_cb'):
            self.xinri_headlight_cb.setChecked(getattr(status, 'headlight', False))
        if hasattr(self, 'xinri_taillight_cb'):
            self.xinri_taillight_cb.setChecked(getattr(status, 'taillight', False))
        if hasattr(self, 'xinri_left_turn_cb'):
            self.xinri_left_turn_cb.setChecked(getattr(status, 'left_turn', False))
        if hasattr(self, 'xinri_right_turn_cb'):
            self.xinri_right_turn_cb.setChecked(getattr(status, 'right_turn', False))
        if hasattr(self, 'xinri_hazard_cb'):
            self.xinri_hazard_cb.setChecked(getattr(status, 'hazard', False))
        if hasattr(self, 'xinri_brake_light_cb'):
            self.xinri_brake_light_cb.setChecked(getattr(status, 'brake_light', False))
        if hasattr(self, 'xinri_high_beam_cb'):
            self.xinri_high_beam_cb.setChecked(getattr(status, 'high_beam', False))
        if hasattr(self, 'xinri_low_beam_cb'):
            self.xinri_low_beam_cb.setChecked(getattr(status, 'low_beam', False))
        
        # 更新档位状态
        if hasattr(self, 'xinri_gear_p_cb'):
            self.xinri_gear_p_cb.setChecked(getattr(status, 'p_gear_protect', False))
        if hasattr(self, 'xinri_gear_r_cb'):
            self.xinri_gear_r_cb.setChecked(getattr(status, 'reverse', False))
        if hasattr(self, 'xinri_gear_n_cb'):
            self.xinri_gear_n_cb.setChecked(getattr(status, 'neutral', False))
        if hasattr(self, 'xinri_gear_d_cb'):
            self.xinri_gear_d_cb.setChecked(getattr(status, 'drive', False))
        if hasattr(self, 'xinri_gear_1_cb'):
            self.xinri_gear_1_cb.setChecked(getattr(status, 'gear_1', False))
        if hasattr(self, 'xinri_gear_2_cb'):
            self.xinri_gear_2_cb.setChecked(getattr(status, 'gear_2', False))
        if hasattr(self, 'xinri_gear_3_cb'):
            self.xinri_gear_3_cb.setChecked(getattr(status, 'gear_3', False))
        if hasattr(self, 'xinri_gear_boost_cb'):
            self.xinri_gear_boost_cb.setChecked(getattr(status, 'boost_mode', False))
        
        # 更新电池状态
        if hasattr(self, 'xinri_battery_normal_cb'):
            self.xinri_battery_normal_cb.setChecked(getattr(status, 'battery_normal', False))
        if hasattr(self, 'xinri_battery_low_cb'):
            self.xinri_battery_low_cb.setChecked(getattr(status, 'battery_low', False))
        if hasattr(self, 'xinri_battery_critical_cb'):
            self.xinri_battery_critical_cb.setChecked(getattr(status, 'battery_critical', False))
        if hasattr(self, 'xinri_battery_charging_cb'):
            self.xinri_battery_charging_cb.setChecked(getattr(status, 'regen_charging', False))
        if hasattr(self, 'xinri_battery_full_cb'):
            self.xinri_battery_full_cb.setChecked(getattr(status, 'battery_full', False))
        if hasattr(self, 'xinri_battery_temp_high_cb'):
            self.xinri_battery_temp_high_cb.setChecked(getattr(status, 'battery_temp_high', False))
        if hasattr(self, 'xinri_battery_temp_low_cb'):
            self.xinri_battery_temp_low_cb.setChecked(getattr(status, 'battery_temp_low', False))
        if hasattr(self, 'xinri_battery_error_cb'):
            self.xinri_battery_error_cb.setChecked(getattr(status, 'battery_error', False))

    def update_xinchi_ui_from_status(self):
        """根据芯驰 BMS 协议状态更新 UI。"""
        if not hasattr(self, 'current_status') or not isinstance(self.current_status, StatusBits):
            return

        status = self.current_status

        if hasattr(self, 'xinchi_charge_mos_cb'):
            self.xinchi_charge_mos_cb.setChecked(getattr(status, 'xinchi_charge_mos', False))
        if hasattr(self, 'xinchi_discharge_mos_cb'):
            self.xinchi_discharge_mos_cb.setChecked(getattr(status, 'xinchi_discharge_mos', False))
        if hasattr(self, 'xinchi_high_temp_fault_cb'):
            self.xinchi_high_temp_fault_cb.setChecked(getattr(status, 'xinchi_high_temp_fault', False))
        if hasattr(self, 'xinchi_low_temp_fault_cb'):
            self.xinchi_low_temp_fault_cb.setChecked(getattr(status, 'xinchi_low_temp_fault', False))
        if hasattr(self, 'xinchi_over_voltage_fault_cb'):
            self.xinchi_over_voltage_fault_cb.setChecked(getattr(status, 'xinchi_over_voltage_fault', False))
        if hasattr(self, 'xinchi_under_voltage_fault_cb'):
            self.xinchi_under_voltage_fault_cb.setChecked(getattr(status, 'xinchi_under_voltage_fault', False))
        if hasattr(self, 'xinchi_bms_fault_cb'):
            self.xinchi_bms_fault_cb.setChecked(getattr(status, 'xinchi_bms_fault', False))

        if hasattr(self, 'xinchi_soc_spin'):
            self.xinchi_soc_spin.setValue(getattr(status, 'soc_percent', 0))
        if hasattr(self, 'xinchi_cycle_count_spin'):
            self.xinchi_cycle_count_spin.setValue(getattr(status, 'xinchi_cycle_count', 0))
        if hasattr(self, 'xinchi_temperature_spin'):
            self.xinchi_temperature_spin.setValue(getattr(status, 'xinchi_temperature_c', 25))
        if hasattr(self, 'xinchi_total_voltage_spin'):
            self.xinchi_total_voltage_spin.setValue(getattr(status, 'xinchi_total_voltage_v', 48.0))
        if hasattr(self, 'xinchi_total_current_spin'):
            self.xinchi_total_current_spin.setValue(getattr(status, 'xinchi_total_current_a', 0))
    
    @pyqtSlot(bool)
    def on_soc_fault_toggled(self, checked):
        """SOC故障状态切换"""
        self.soc_spin.setEnabled(not checked)
    
    def get_current_status_from_ui(self) -> StatusBits:
        """从UI获取当前Status位配置，统一返回StatusBits对象"""
        if self.current_protocol == PROTOCOL_XINRI:
            return self.get_xinri_status_from_ui()
        elif self.current_protocol == PROTOCOL_CHANGZHOU_XINSIWEI:
            return self.get_changzhou_xinsiwei_status_from_ui()
        elif self.current_protocol == PROTOCOL_XINCHI:
            return self.get_xinchi_status_from_ui()
        else:
            return self.get_ruilun_status_from_ui()
    
    def get_ruilun_status_from_ui(self) -> StatusBits:
        """从UI获取瑞伦协议的Status位配置"""
        status = StatusBits()
        status.protocol_name = self.current_protocol
        
        # Status1
        if self.current_protocol == PROTOCOL_HANGZHOU_ANXIAN:
            status.protocol_speed_limit = self.speed_alarm_cb.isChecked()
            status.p_gear_protect = self.p_gear_protect_cb.isChecked()
        elif self.current_protocol == PROTOCOL_DONGWEI_GTXH:
            status.p_gear_protect = self.p_gear_protect_cb.isChecked()
        elif self.current_protocol in {PROTOCOL_WUXI_YIGE, PROTOCOL_YADEA}:
            status.side_stand = self.distance_mode_cb.isChecked()
            status.p_gear_protect = self.p_gear_protect_cb.isChecked()
        else:
            status.distance_mode = self.distance_mode_cb.isChecked()
            status.speed_alarm = self.speed_alarm_cb.isChecked()
            status.p_gear_protect = self.p_gear_protect_cb.isChecked()
            status.tcs_status = self.tcs_status_cb.isChecked()
        
        # Status2
        status.walk_mode = self.status2_d7_cb.isChecked()
        status.hall_fault = self.hall_fault_cb.isChecked()
        status.throttle_fault = self.throttle_fault_cb.isChecked()
        status.controller_fault = self.controller_fault_cb.isChecked()
        status.under_voltage = self.under_voltage_cb.isChecked()
        status.cruise = self.cruise_cb.isChecked()
        status.assist = self.assist_cb.isChecked()
        status.motor_phase_loss = self.motor_phase_loss_cb.isChecked()
        
        # Status3
        status.gear_four = self.gear_four_cb.isChecked()
        status.motor_running = self.motor_running_cb.isChecked()
        status.brake = self.brake_cb.isChecked()
        status.controller_protect = self.controller_protect_cb.isChecked()
        status.regen_charging = self.regen_charging_cb.isChecked()
        status.anti_runaway = self.anti_runaway_cb.isChecked()
        status.speed_mode = self.speed_mode_spin.value()
        
        # Status4
        if self.current_protocol == PROTOCOL_WUXI_YIGE:
            status.cloud_power_mode = self.current_70_flag_cb.isChecked()
        else:
            status.current_70_flag = self.current_70_flag_cb.isChecked()
        if self.current_protocol == PROTOCOL_DONGWEI_GTXH:
            status.side_stand = self.one_key_enable_cb.isChecked()
        else:
            status.one_key_enable = self.one_key_enable_cb.isChecked()
        status.ekk_enable = self.ekk_enable_cb.isChecked()
        status.over_current = self.over_current_cb.isChecked()
        status.stall_protect = self.stall_protect_cb.isChecked()
        status.reverse = self.reverse_cb.isChecked()
        status.electronic_brake = self.electronic_brake_cb.isChecked()
        status.speed_limit = self.speed_limit_cb.isChecked()
        
        # Status5-9
        status.current_a = self.current_spin.value()
        status.hall_count = self.hall_count_spin.value()
        status.speed_kmh = self.speed_spin.value()
        if self.current_protocol == PROTOCOL_HANGZHOU_ANXIAN:
            status.voltage_percentage = self.soc_spin.value()
        else:
            status.soc_percent = self.soc_spin.value()
        if getattr(self, "lithium_soc_mode_cb", None) is not None:
            status.lithium_soc_mode = self.lithium_soc_mode_cb.isChecked()
        if getattr(self, "soc_fault_cb", None) is not None:
            status.soc_fault = self.soc_fault_cb.isChecked()
        if getattr(self, "current_percent_spin", None) is not None:
            status.current_percentage = self.current_percent_spin.value()
        
        # 系统电压
        if getattr(self, "voltage_group", None) is not None:
            voltage_id = self.voltage_group.checkedId()
            if self.current_protocol == PROTOCOL_DONGWEI_GTXH and voltage_id == 8:
                status.voltage_36v = False
                status.voltage_48v = False
                status.voltage_60v = False
                status.voltage_64v = False
                status.voltage_72v = False
                status.voltage_80v = False
                status.voltage_84v = False
                status.voltage_96v = False
            else:
                status.voltage_36v = (voltage_id == 0)
                status.voltage_48v = (voltage_id == 1)
                status.voltage_60v = (voltage_id == 2)
                status.voltage_64v = (voltage_id == 3)
                status.voltage_72v = (voltage_id == 4)
                status.voltage_80v = (voltage_id == 5)
                status.voltage_84v = (voltage_id == 6)
                status.voltage_96v = (voltage_id == 7)
        else:
            status.voltage_36v = False
            status.voltage_48v = False
            status.voltage_60v = False
            status.voltage_64v = False
            status.voltage_72v = False
            status.voltage_80v = False
            status.voltage_84v = False
            status.voltage_96v = False
        
        return status
    
    def get_xinri_status_from_ui(self) -> StatusBits:
        """从UI获取新日协议的Status位配置"""
        status = StatusBits()
        status.protocol_name = PROTOCOL_XINRI
        
        # 车辆状态映射
        if hasattr(self, 'xinri_motor_running_cb'):
            status.motor_running = self.xinri_motor_running_cb.isChecked()
        if hasattr(self, 'xinri_brake_cb'):
            status.brake = self.xinri_brake_cb.isChecked()
        if hasattr(self, 'xinri_cruise_cb'):
            status.cruise = self.xinri_cruise_cb.isChecked()
        
        # 故障状态映射
        if hasattr(self, 'xinri_motor_fault_cb') and self.xinri_motor_fault_cb.isChecked():
            status.hall_fault = True
        if hasattr(self, 'xinri_hall_fault_cb'):
            status.hall_fault = status.hall_fault or self.xinri_hall_fault_cb.isChecked()
        if hasattr(self, 'xinri_controller_fault_cb'):
            status.controller_fault = self.xinri_controller_fault_cb.isChecked()
        if hasattr(self, 'xinri_throttle_fault_cb'):
            status.throttle_fault = self.xinri_throttle_fault_cb.isChecked()
        if hasattr(self, 'xinri_under_voltage_cb'):
            status.low_voltage_alarm = self.xinri_under_voltage_cb.isChecked()
        
        # 档位状态映射
        if hasattr(self, 'xinri_gear_p_cb'):
            status.p_gear_protect = self.xinri_gear_p_cb.isChecked()
        if hasattr(self, 'xinri_gear_boost_cb') and self.xinri_gear_boost_cb.isChecked():
            status.speed_mode = 4
        elif hasattr(self, 'xinri_gear_3_cb') and self.xinri_gear_3_cb.isChecked():
            status.speed_mode = 3
        elif hasattr(self, 'xinri_gear_2_cb') and self.xinri_gear_2_cb.isChecked():
            status.speed_mode = 2
        elif hasattr(self, 'xinri_gear_1_cb') and self.xinri_gear_1_cb.isChecked():
            status.speed_mode = 1
        else:
            status.speed_mode = 0
        
        # 设置默认值（新日协议当前 UI 未提供原始电流/霍尔计数，保持 0）
        status.voltage_48v = False
        status.speed_kmh = 0.0
        status.soc_percent = 0
        
        return status

    def get_xinchi_status_from_ui(self) -> StatusBits:
        """从 UI 获取芯驰 BMS 协议配置。"""
        status = StatusBits()
        status.protocol_name = PROTOCOL_XINCHI

        status.xinchi_charge_mos = self.xinchi_charge_mos_cb.isChecked()
        status.xinchi_discharge_mos = self.xinchi_discharge_mos_cb.isChecked()
        status.xinchi_high_temp_fault = self.xinchi_high_temp_fault_cb.isChecked()
        status.xinchi_low_temp_fault = self.xinchi_low_temp_fault_cb.isChecked()
        status.xinchi_over_voltage_fault = self.xinchi_over_voltage_fault_cb.isChecked()
        status.xinchi_under_voltage_fault = self.xinchi_under_voltage_fault_cb.isChecked()
        status.xinchi_bms_fault = self.xinchi_bms_fault_cb.isChecked()

        status.soc_percent = self.xinchi_soc_spin.value()
        status.xinchi_cycle_count = self.xinchi_cycle_count_spin.value()
        status.xinchi_temperature_c = self.xinchi_temperature_spin.value()
        status.xinchi_total_voltage_v = self.xinchi_total_voltage_spin.value()
        status.xinchi_total_current_a = self.xinchi_total_current_spin.value()

        return status
    
    def get_changzhou_xinsiwei_status_from_ui(self) -> StatusBits:
        """从UI获取常州新思维协议的Status位配置"""
        status = StatusBits()
        status.protocol_name = PROTOCOL_CHANGZHOU_XINSIWEI
        
        # Status1 - 预留位D0-D3
        if hasattr(self, 'xinsiwei_reserved_d0_cb'):
            status.xinsiwei_reserved_d0 = self.xinsiwei_reserved_d0_cb.isChecked()
        if hasattr(self, 'xinsiwei_reserved_d1_cb'):
            status.xinsiwei_reserved_d1 = self.xinsiwei_reserved_d1_cb.isChecked()
        if hasattr(self, 'xinsiwei_reserved_d2_cb'):
            status.xinsiwei_reserved_d2 = self.xinsiwei_reserved_d2_cb.isChecked()
        if hasattr(self, 'xinsiwei_reserved_d3_cb'):
            status.xinsiwei_reserved_d3 = self.xinsiwei_reserved_d3_cb.isChecked()
        
        # Status2 - 故障状态（使用实际创建的控件名称）
        if hasattr(self, 'hall_fault_cb'):
            status.hall_fault = self.hall_fault_cb.isChecked()
        if hasattr(self, 'motor_phase_loss_cb'):
            status.motor_phase_loss = self.motor_phase_loss_cb.isChecked()
        if hasattr(self, 'controller_fault_cb'):
            status.controller_fault = self.controller_fault_cb.isChecked()
        if hasattr(self, 'throttle_fault_cb'):
            status.throttle_fault = self.throttle_fault_cb.isChecked()
        if hasattr(self, 'under_voltage_cb'):
            status.under_voltage = self.under_voltage_cb.isChecked()
        if hasattr(self, 'cruise_cb'):
            status.cruise = self.cruise_cb.isChecked()
        if hasattr(self, 'assist_cb'):
            status.assist = self.assist_cb.isChecked()
        
        # Status3 - 运行状态（使用实际创建的控件名称）
        if hasattr(self, 'gear_four_cb'):
            status.gear_four = self.gear_four_cb.isChecked()
        if hasattr(self, 'motor_running_cb'):
            status.motor_running = self.motor_running_cb.isChecked()
        if hasattr(self, 'brake_cb'):
            status.brake = self.brake_cb.isChecked()
        if hasattr(self, 'controller_protect_cb'):
            status.controller_protect = self.controller_protect_cb.isChecked()
        if hasattr(self, 'regen_charging_cb'):
            status.regen_charging = self.regen_charging_cb.isChecked()
        if hasattr(self, 'anti_runaway_cb'):
            status.anti_runaway = self.anti_runaway_cb.isChecked()
        if hasattr(self, 'speed_mode_spin'):
            status.speed_mode = self.speed_mode_spin.value()
        
        # Status4 - 保护状态（使用实际创建的控件名称）
        if hasattr(self, 'current_70_flag_cb'):
            status.current_70_flag = self.current_70_flag_cb.isChecked()
        if hasattr(self, 'one_key_enable_cb'):
            status.one_key_enable = self.one_key_enable_cb.isChecked()
        if hasattr(self, 'ekk_enable_cb'):
            status.ekk_enable = self.ekk_enable_cb.isChecked()
        if hasattr(self, 'over_current_cb'):
            status.over_current = self.over_current_cb.isChecked()
        if hasattr(self, 'stall_protect_cb'):
            status.stall_protect = self.stall_protect_cb.isChecked()
        if hasattr(self, 'reverse_cb'):
            status.reverse = self.reverse_cb.isChecked()
        if hasattr(self, 'electronic_brake_cb'):
            status.electronic_brake = self.electronic_brake_cb.isChecked()
        if hasattr(self, 'speed_limit_cb'):
            status.speed_limit = self.speed_limit_cb.isChecked()
        
        # Status5-9 - 新思维特有控件（使用实际创建的控件名称）
        if hasattr(self, 'current_spin'):
            status.current_a = self.current_spin.value()
        if hasattr(self, 'xinsiwei_hall_count_spin'):
            status.xinsiwei_hall_count = self.xinsiwei_hall_count_spin.value()
        if hasattr(self, 'soc_spin'):
            status.soc_percent = self.soc_spin.value()
        if hasattr(self, 'soc_fault_cb'):
            status.soc_fault = self.soc_fault_cb.isChecked()
        
        # 系统电压选择（使用实际创建的控件名称）
        if hasattr(self, 'voltage_24v_rb') and self.voltage_24v_rb.isChecked():
            status.voltage_24v = True
            status.voltage_36v = False
            status.voltage_48v = False
            status.voltage_60v = False
            status.voltage_72v = False
        elif hasattr(self, 'voltage_36v_rb') and self.voltage_36v_rb.isChecked():
            status.voltage_24v = False
            status.voltage_36v = True
            status.voltage_48v = False
            status.voltage_60v = False
            status.voltage_72v = False
        elif hasattr(self, 'voltage_48v_rb') and self.voltage_48v_rb.isChecked():
            status.voltage_24v = False
            status.voltage_36v = False
            status.voltage_48v = True
            status.voltage_60v = False
            status.voltage_72v = False
        elif hasattr(self, 'voltage_60v_rb') and self.voltage_60v_rb.isChecked():
            status.voltage_24v = False
            status.voltage_36v = False
            status.voltage_48v = False
            status.voltage_60v = True
            status.voltage_72v = False
        elif hasattr(self, 'voltage_72v_rb') and self.voltage_72v_rb.isChecked():
            status.voltage_24v = False
            status.voltage_36v = False
            status.voltage_48v = False
            status.voltage_60v = False
            status.voltage_72v = True
        else:
            # 默认48V
            status.voltage_24v = False
            status.voltage_36v = False
            status.voltage_48v = True
            status.voltage_60v = False
            status.voltage_72v = False
        
        # 新思维特有字段
        # 设置协议标识，确保协议路由正确识别
        status.xinsiwei_protocol = True
        
        # 协议标识符和流水号（使用实际创建的控件名称）
        if hasattr(self, 'protocol_id_spin'):
            status.protocol_identifier = self.protocol_id_spin.value()
        if hasattr(self, 'sequence_num_spin'):
            status.sequence_number = self.sequence_num_spin.value()
        
        # 序号由自动递增功能管理，这里不需要从UI获取
        # if hasattr(self, 'xinsiwei_sequence_spinbox'):
        #     status.xinsiwei_sequence = self.xinsiwei_sequence_spinbox.value()
        
        return status
    
    def generate_protocol_frame(self, status):
        """
        根据当前协议类型生成协议帧（用于实际发送，会递增序号）
        
        Args:
            status: StatusBits对象
            
        Returns:
            (success, frame_data, error_message)
        """
        # 统一使用StatusBits对象和generate_frame方法
        return self.protocol_handler.generate_frame(status)
    
    def generate_protocol_frame_for_preview(self, status):
        """
        根据当前协议类型生成协议帧（用于预览显示，不递增序号）
        
        Args:
            status: StatusBits对象
            
        Returns:
            (success, frame_data, error_message)
        """
        # 使用预览专用的帧生成方法
        return self.protocol_handler.generate_frame_for_preview(status)
    
    def update_current_frame_display(self):
        """更新当前帧数据显示（使用预览方法，不影响流水号）"""
        # 检查当前模式
        if self.frame_custom_radio.isChecked():
            # 全部自定义模式 - 使用自定义帧数据
            if self.custom_frame_data is not None:
                display_text = self.protocol_handler.format_frame_display(self.custom_frame_data)
                self.current_frame_text.setPlainText(display_text)
            else:
                self.current_frame_text.setPlainText("请配置自定义帧数据")
        else:
            # 数据自定义或预设模式 - 使用Status生成帧数据（预览模式）
            # 获取当前Status配置
            if self.custom_radio.isChecked():
                status = self.get_current_status_from_ui()
            else:
                status = self.current_status
            
            # 生成协议帧（使用预览方法，不递增序号）
            success, frame_data, error_msg = self.generate_protocol_frame_for_preview(status)
            
            if success:
                # 格式化显示
                display_text = self.protocol_handler.format_frame_display(frame_data)
                self.current_frame_text.setPlainText(display_text)
            else:
                self.current_frame_text.setPlainText(f"帧生成失败: {error_msg}")
    
    @pyqtSlot()
    def send_single_frame(self):
        """发送单帧数据"""
        # 检查当前模式并获取帧数据
        if self.frame_custom_radio.isChecked():
            # 全部自定义模式 - 使用自定义帧数据
            if self.custom_frame_data is None:
                QMessageBox.warning(self, "数据错误", "请先配置自定义帧数据")
                return
            frame_data = self.custom_frame_data
        else:
            # 数据自定义或预设模式 - 使用Status生成帧数据
            # 获取当前Status配置
            if self.custom_radio.isChecked():
                status = self.get_current_status_from_ui()
            else:
                status = self.current_status
            
            # 生成协议帧
            success, frame_data, error_msg = self.generate_protocol_frame(status)
            
            if not success:
                QMessageBox.critical(self, "数据错误", error_msg)
                return
        
        # 发送数据
        success, error_msg = self.serial_manager.send_single_frame(frame_data)
        
        if not success:
            QMessageBox.critical(self, "发送失败", error_msg)
    
    @pyqtSlot()
    def toggle_cyclic_send(self):
        """切换循环发送状态"""
        if self.serial_manager.is_cyclic_sending():
            # 停止循环发送
            self.serial_manager.stop_cyclic_send()
            self.cyclic_send_btn.setText("循环发送")
            self.send_status.setText("就绪")
            self.send_status.setStyleSheet("color: blue; font-weight: bold;")
        else:
            # 开始循环发送
            # 检查当前模式并获取帧数据
            if self.frame_custom_radio.isChecked():
                # 全部自定义模式 - 使用自定义帧数据
                if self.custom_frame_data is None:
                    QMessageBox.warning(self, "数据错误", "请先配置自定义帧数据")
                    return
                frame_data = self.custom_frame_data
            else:
                # 数据自定义或预设模式 - 使用Status生成帧数据
                if self.custom_radio.isChecked():
                    status = self.get_current_status_from_ui()
                else:
                    status = self.current_status
                
                # 生成协议帧
                success, frame_data, error_msg = self.generate_protocol_frame(status)
                
                if not success:
                    QMessageBox.critical(self, "数据错误", error_msg)
                    return
            
            # 开始循环发送
            interval_ms = self.interval_spin.value()
            success, error_msg = self.serial_manager.start_cyclic_send(frame_data, interval_ms)
            
            if success:
                self.cyclic_send_btn.setText("停止发送")
                self.send_status.setText("循环发送中...")
                self.send_status.setStyleSheet("color: orange; font-weight: bold;")
            else:
                QMessageBox.critical(self, "发送失败", error_msg)
    
    @pyqtSlot(list, str)
    def on_data_sent(self, frame_data, timestamp):
        """数据发送成功"""
        # 添加到待更新缓冲区，而不是立即更新UI
        hex_str = " ".join([f"{b:02X}" for b in frame_data])
        history_line = f"[{timestamp}] 发送成功: {hex_str}"
        
        self.pending_history_updates.append(history_line)
        
        # 如果缓冲区过大，立即刷新
        if len(self.pending_history_updates) > 50:
            self._flush_history_updates()
    
    @pyqtSlot(str)
    def on_send_error(self, error_msg):
        """发送错误"""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        history_line = f"[{timestamp}] 发送失败: {error_msg}"
        
        # 错误信息立即显示，不使用缓冲
        self.history_text.append(history_line)
        
        # 自动滚动到底部
        if self.auto_scroll_cb.isChecked():
            cursor = self.history_text.textCursor()
            cursor.movePosition(cursor.End)
            self.history_text.setTextCursor(cursor)
        
        # 停止循环发送
        if self.serial_manager.is_cyclic_sending():
            self.serial_manager.stop_cyclic_send()
            self.cyclic_send_btn.setText("循环发送")
            self.send_status.setText("发送失败")
            self.send_status.setStyleSheet("color: red; font-weight: bold;")
    
    @pyqtSlot(str)
    def on_connection_error(self, error_msg):
        """连接错误"""
        QMessageBox.critical(self, "连接错误", error_msg)
    
    @pyqtSlot()
    def clear_send_history(self):
        """清空发送历史"""
        self.history_text.clear()
        # 同时清空待更新的缓冲区
        self.pending_history_updates.clear()
    
    @pyqtSlot()
    def open_frame_config(self):
        """打开帧配置窗口"""
        frame_length = self.protocol_handler.get_protocol_frame_length(self.current_protocol)

        if self.custom_frame_data is None:
            success, frame_data, _ = self.generate_protocol_frame(self.current_status)
            if success:
                self.custom_frame_data = frame_data
            else:
                self.custom_frame_data = [0] * frame_length
        elif len(self.custom_frame_data) != frame_length:
            self.custom_frame_data = [0] * frame_length
        
        byte_descriptions = self.protocol_handler.get_byte_descriptions(self.current_protocol)
        self.frame_config_dialog = FrameConfigDialog(
            self,
            self.custom_frame_data,
            byte_descriptions=byte_descriptions,
            dialog_title=f"{self.current_protocol} 帧配置",
            checksum_mode=self.protocol_handler.get_protocol_checksum_mode(self.current_protocol),
        )
        self.frame_config_dialog.frameChanged.connect(self.on_custom_frame_changed)
        
        # 显示窗口
        if self.frame_config_dialog.exec_() == QDialog.Accepted:
            self.custom_frame_data = self.frame_config_dialog.get_frame_data()
            self.update_current_frame_display()
    
    @pyqtSlot(list)
    def on_custom_frame_changed(self, frame_data):
        """
        处理自定义帧数据变化
        
        Args:
            frame_data: 新的帧数据列表
        """
        self.custom_frame_data = frame_data.copy()
        # 如果当前处于全部自定义模式，立即更新显示
        if self.frame_custom_radio.isChecked():
            self.update_current_frame_display()
    
    def closeEvent(self, event):
        """窗口关闭事件"""
        # 停止历史更新定时器
        if hasattr(self, 'history_update_timer'):
            self.history_update_timer.stop()
        
        # 刷新剩余的历史更新
        self._flush_history_updates()
        
        # 停止串口检测
        self.port_detector.stop_detection()
        
        # 断开串口连接
        if self.serial_manager.is_connected:
            self.serial_manager.disconnect_port()
        
        event.accept()
