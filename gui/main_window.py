#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
主窗口GUI界面

实现串口配置、场景选择、Status位配置、发送控制、数据监控等功能区域
"""

from datetime import datetime
from typing import Optional
import os
import sys
from pathlib import Path

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QGroupBox, QLabel, QComboBox, QPushButton, QSpinBox, QDoubleSpinBox,
    QCheckBox, QRadioButton, QButtonGroup, QTextEdit, QLineEdit,
    QMessageBox, QSplitter, QFrame, QScrollArea, QTabWidget,
    QStatusBar, QDialog, QApplication
)
from PyQt5.QtCore import Qt, QTimer, pyqtSlot
from PyQt5.QtGui import QFont

from protocol.protocol_handler import (
    PROTOCOL_BATTERY_SINGLE_WIRE,
    PROTOCOL_CHANGZHOU_XINSIWEI,
    PROTOCOL_DONGWEI_GTXH,
    PROTOCOL_FZ_SIF,
    PROTOCOL_HANGZHOU_ANXIAN,
    PROTOCOL_JINGXIAN,
    PROTOCOL_LITHIUM_BMS,
    PROTOCOL_LUYUAN_BMS,
    PROTOCOL_RUILUN,
    PROTOCOL_TAILING_Y34B,
    PROTOCOL_TAILING_Y34F,
    PROTOCOL_SHENZHOUXING,
    PROTOCOL_SXSY,
    PROTOCOL_WUXI_YIGE,
    PROTOCOL_XINCHI,
    PROTOCOL_XINRI,
    PROTOCOL_YADEA,
    PROTOCOL_YOUYIBAO,
    ProtocolHandler,
    SUPPORTED_PROTOCOLS,
    StatusBits,
    PresetScenarios,
)
from protocol.definitions import DEFAULT_PROTOCOL_DEFINITION, PROTOCOL_DEFINITIONS
from gui.feedback_dialog import FeedbackDialog
from gui.protocol_ui_registry import get_protocol_ui_spec
from serial_comm.serial_manager import SerialManager, SerialPortDetector
from gui.frame_config_dialog import FrameConfigDialog
from gui.packet_sequence_dialog import PacketSequenceDialog
from licensing.activation import ActivationService
from app_info import APP_NAME, APP_VERSION, PROTOCOL_VERSION
from gui.update_dialog import UpdateDialog
from gui.settings_panel import SettingsPanel
from app_paths import user_data_directory
from app_settings import SettingsStore
from diagnostics import LOGGER
from updating.recovery import inspect_recovery
from updating.startup import STARTUP_REQUEST_ENV

MAX_HISTORY_BLOCKS = 10000


from gui.protocol_pages import (
    XinchiPages,
    LuyuanBmsPages,
    LithiumBmsPages,
    BatterySingleWirePages,
    XinsiweiPages,
    XinriPages,
    CommonProtocolForms,
    CommonProtocolBindings,
)


class MainWindow(
    QMainWindow,
    XinchiPages,
    LuyuanBmsPages,
    LithiumBmsPages,
    BatterySingleWirePages,
    XinsiweiPages,
    XinriPages,
    CommonProtocolForms,
    CommonProtocolBindings,
    SettingsPanel,
):
    """主窗口协调器：协议界面由独立组件提供。"""

    def __init__(self, activation_service: Optional[ActivationService] = None, settings_store=None):
        """创建窗口，配置存储可注入；默认首次启动仍使用 500ms，不自动连接。"""
        super().__init__()
        self.settings_store = settings_store if settings_store is not None else SettingsStore(user_data_directory() / "settings.json")
        self._recovery_notice = ""
        self.activation_service = activation_service
        self.protocol_handler = ProtocolHandler()
        self.serial_manager = SerialManager(background_send=True)
        self.port_detector = SerialPortDetector()
        self.packet_sequence_frames = {}
        self.packet_sequence_dialog = None
        self.active_send_mode = None

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
        self.serial_manager.timing_warning.connect(self.on_timing_warning)
        self.serial_manager.statistics_changed.connect(self.on_send_statistics)

        # 启动串口检测
        self.port_detector.start_detection()
        self.refresh_recovery_notice()

    def init_ui(self):
        """初始化用户界面"""
        self.setWindowTitle(f"{APP_NAME} V{APP_VERSION}")
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
        """)

    def create_window_action_bar(self) -> QFrame:
        """创建右上角操作栏，使用一个菜单集中提供配置、诊断和帮助入口。"""
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

        self.tools_btn = self.create_tools_button()
        self.tools_btn.setCursor(Qt.PointingHandCursor)
        # 合并菜单后保留原控件引用名称，避免调用方因入口调整而失效。
        self.feedback_btn = self.tools_btn
        self.help_menu = self.tools_btn.menu()
        layout.addWidget(self.tools_btn)

        return bar

    def show_update_dialog(self):
        """用户点击菜单后检测更新，后台下载完成后再由用户确认升级。"""
        self.refresh_recovery_notice()
        if self._recovery_notice:
            self.show_recovery_guidance()
            return
        dialog = UpdateDialog(self)
        dialog.ready_to_restart.connect(self._exit_for_update)
        dialog.exec_()

    def _exit_for_update(self):
        """更新器就绪后停止发送并关闭窗口，原关闭流程负责断开串口。"""
        self.serial_manager.stop_cyclic_send()
        if self.close():
            QApplication.instance().quit()

    def show_feedback_dialog(self):
        """显示作者联系二维码。"""
        remaining_validity_text = "未激活"
        if self.activation_service is not None:
            remaining_validity_text = self.activation_service.get_remaining_validity_text()
        dialog = FeedbackDialog(self, remaining_validity_text=remaining_validity_text)
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
                if self.current_protocol == PROTOCOL_HANGZHOU_ANXIAN:
                    layout.setContentsMargins(8, 8, 8, 8)
                    layout.setHorizontalSpacing(18)
                    layout.setVerticalSpacing(6)
                else:
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
        self.protocol_combo.addItems(SUPPORTED_PROTOCOLS)
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

    def create_send_control_group(self) -> QGroupBox:
        """创建发送控制组"""
        group = QGroupBox("发送控制")
        layout = QGridLayout(group)

        # 发送间隔
        layout.addWidget(QLabel("发送间隔 (ms):"), 0, 0)
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(
            DEFAULT_PROTOCOL_DEFINITION.min_send_interval_ms,
            DEFAULT_PROTOCOL_DEFINITION.max_send_interval_ms,
        )
        self.interval_spin.setValue(
            DEFAULT_PROTOCOL_DEFINITION.default_send_interval_ms
        )
        self.interval_spin.setToolTip(
            "最低可选 10ms，默认 500ms；10ms 仅表示软件允许设置，"
            "低于 500ms 时请确认波特率、帧长及转码平台处理能力，"
            "过快可能造成覆盖、丢帧或实际周期变长。"
        )
        self.interval_spin.valueChanged.connect(self.on_interval_changed)
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
        self.packet_sequence_btn = QPushButton("包组配置")
        self.packet_sequence_btn.clicked.connect(self.open_packet_sequence_config)
        self.packet_sequence_btn.setEnabled(False)
        layout.addWidget(self.packet_sequence_btn, 2, 0)

        self.packet_sequence_send_btn = QPushButton("包组循环")
        self.packet_sequence_send_btn.clicked.connect(self.toggle_packet_sequence_send)
        self.packet_sequence_send_btn.setEnabled(False)
        layout.addWidget(self.packet_sequence_send_btn, 2, 1)

        # 发送状态
        self.send_status = QLabel("就绪")
        self.send_status.setStyleSheet("color: blue; font-weight: bold;")
        layout.addWidget(self.send_status, 3, 0, 1, 2)

        self.send_statistics_label = QLabel("已写入 0 帧 | 写入周期 -- | 缓冲 0 字节")
        self.send_statistics_label.setToolTip("统计为软件写入驱动的结果和调用间隔，不代表单线侧波形的实测周期。")
        self.send_statistics_label.setWordWrap(True)
        layout.addWidget(self.send_statistics_label, 4, 0, 1, 2)

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
        self.history_text.document().setMaximumBlockCount(MAX_HISTORY_BLOCKS)
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
        version_label = QLabel(f"软件: V{APP_VERSION}  |  协议: V{PROTOCOL_VERSION}")
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
        if getattr(self, "soc_spin", None) is not None:
            self.soc_spin.valueChanged.connect(self.update_current_frame_display)
        if getattr(self, "sxsy_soc_spin", None) is not None:
            self.sxsy_soc_spin.valueChanged.connect(
                self.update_current_frame_display
            )
        if getattr(self, "lithium_soc_mode_cb", None) is not None:
            self.lithium_soc_mode_cb.toggled.connect(self.update_current_frame_display)
        if getattr(self, "soc_fault_cb", None) is not None:
            self.soc_fault_cb.toggled.connect(self.update_current_frame_display)
        if getattr(self, "current_percent_spin", None) is not None:
            self.current_percent_spin.valueChanged.connect(self.update_current_frame_display)
        if getattr(self, "voltage_group", None) is not None:
            self.voltage_group.buttonClicked.connect(self.update_current_frame_display)
        if getattr(self, "tailing_display_voltage_from_data_cb", None) is not None:
            self.tailing_display_voltage_from_data_cb.toggled.connect(self.update_current_frame_display)
        if getattr(self, "tailing_battery_over_temp_cb", None) is not None:
            self.tailing_battery_over_temp_cb.toggled.connect(self.update_current_frame_display)
        if getattr(self, "tailing_battery_over_current_cb", None) is not None:
            self.tailing_battery_over_current_cb.toggled.connect(self.update_current_frame_display)
        if getattr(self, "tailing_battery_over_voltage_cb", None) is not None:
            self.tailing_battery_over_voltage_cb.toggled.connect(self.update_current_frame_display)
        if getattr(self, "tailing_dual_soc_cb", None) is not None:
            self.tailing_dual_soc_cb.toggled.connect(self.update_current_frame_display)
        if getattr(self, "tailing_display_sleep_cb", None) is not None:
            self.tailing_display_sleep_cb.toggled.connect(self.update_current_frame_display)
        if getattr(self, "tailing_speed_15_warning_cb", None) is not None:
            self.tailing_speed_15_warning_cb.toggled.connect(self.update_current_frame_display)
        if getattr(self, "tailing_brake_fault_cb", None) is not None:
            self.tailing_brake_fault_cb.toggled.connect(self.update_current_frame_display)
        if getattr(self, "tailing_real_time_voltage_spin", None) is not None:
            self.tailing_real_time_voltage_spin.valueChanged.connect(self.update_current_frame_display)

    def load_settings(self):
        """加载设置"""
        # 刷新串口列表
        self.refresh_ports()
        self.load_remembered_configuration()

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
            # 连接错误统一由 connection_error 信号展示，避免同一错误弹窗两次。
            self.serial_manager.connect_port(port_name, baud_rate)

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
        self.packet_sequence_btn.setEnabled(True)
        self.packet_sequence_send_btn.setEnabled(True)
        self.packet_sequence_send_btn.setText("包组循环")
        self.active_send_mode = None

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
        self.packet_sequence_btn.setEnabled(False)
        self.packet_sequence_send_btn.setEnabled(False)
        self.packet_sequence_send_btn.setText("包组循环")
        self.active_send_mode = None
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
        try:
            ui_spec = get_protocol_ui_spec(protocol_name)
        except ValueError as exc:
            self.status_bar.showMessage(str(exc), 5000)
            return

        # 修复协议已切换、串口却继续循环发送旧帧的问题。
        if self.serial_manager.is_cyclic_sending():
            self.serial_manager.stop_cyclic_send()
            self._reset_send_action_buttons()
            self.send_status.setText("就绪")
            self.send_status.setStyleSheet("color: blue; font-weight: bold;")

        self.current_protocol = protocol_name
        self.custom_frame_data = None
        self.apply_send_interval_constraints()

        # 协议界面入口由注册表统一路由，新增协议不再扩展条件分支。
        getattr(self, ui_spec.switch_handler)()

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

    def switch_to_fz_sif_protocol(self):
        """切换到 FZ-sif 协议"""
        self.current_status = PresetScenarios.fz_sif_normal_running()
        self.show_ruilun_status_config()
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

    def switch_to_sxsy_protocol(self):
        """切换到 SXSY 一线通协议。"""

        self.current_status = PresetScenarios.sxsy_normal_running()
        self.show_ruilun_status_config()
        self.normal_radio.setChecked(True)
        self.on_scenario_changed()

    def switch_to_wuxi_yige_protocol(self):
        """切换到无锡一格 Y67 协议"""
        self.current_status = PresetScenarios.wuxi_yige_normal_running()
        self.show_ruilun_status_config()
        self.normal_radio.setChecked(True)
        self.on_scenario_changed()

    def switch_to_tailing_y34b_protocol(self):
        """切换到无锡台铃 Y34B 协议"""
        self.current_status = PresetScenarios.tailing_y34b_normal_running()
        self.show_ruilun_status_config()
        self.normal_radio.setChecked(True)
        self.on_scenario_changed()

    def switch_to_tailing_y34f_protocol(self):
        """切换到无锡台铃 Y34F 协议"""
        self.current_status = PresetScenarios.tailing_y34f_normal_running()
        self.show_ruilun_status_config()
        self.normal_radio.setChecked(True)
        self.on_scenario_changed()

    def switch_to_shenzhouxing_protocol(self):
        """切换到神州行协议"""
        self.current_status = PresetScenarios.shenzhouxing_normal_running()
        self.show_ruilun_status_config()
        self.normal_radio.setChecked(True)
        self.on_scenario_changed()

    def switch_to_yadea_protocol(self):
        """切换到雅迪协议"""
        self.current_status = PresetScenarios.yadea_normal_running()
        self.show_ruilun_status_config()
        self.normal_radio.setChecked(True)
        self.on_scenario_changed()

    def switch_to_youyibao_protocol(self):
        """切换到优仪宝一线通协议"""
        self.current_status = PresetScenarios.youyibao_normal_running()
        self.show_ruilun_status_config()
        self.normal_radio.setChecked(True)
        self.on_scenario_changed()

    def switch_to_jingxian_protocol(self):
        """切换到精显一线通协议"""
        self.current_status = PresetScenarios.jingxian_normal_running()
        self.show_ruilun_status_config()
        self.normal_radio.setChecked(True)
        self.on_scenario_changed()

    def switch_to_dongwei_gtxh_protocol(self):
        """切换到东威 GTXH 协议"""
        self.current_status = PresetScenarios.dongwei_gtxh_normal_running()
        self.show_ruilun_status_config()
        self.normal_radio.setChecked(True)
        self.on_scenario_changed()

    def apply_send_interval_constraints(self):
        """根据协议约束循环发送间隔。"""
        if not hasattr(self, "interval_spin"):
            return

        definition = PROTOCOL_DEFINITIONS.get(
            self.current_protocol,
            DEFAULT_PROTOCOL_DEFINITION,
        )
        current_value = self.interval_spin.value()
        self.interval_spin.setRange(
            definition.min_send_interval_ms,
            definition.max_send_interval_ms,
        )
        if (
            definition.reset_send_interval_on_switch
            or not (
                definition.min_send_interval_ms
                <= current_value
                <= definition.max_send_interval_ms
            )
        ):
            self.interval_spin.setValue(definition.default_send_interval_ms)

    @pyqtSlot(int)
    def on_interval_changed(self, interval_ms):
        if not self.serial_manager.is_cyclic_sending():
            return

        success, error_msg = self.serial_manager.update_cyclic_send_interval(interval_ms)
        if not success:
            self.status_bar.showMessage(error_msg, 3000)
            return

        if self.active_send_mode == "sequence":
            self.send_status.setText(f"包组循环发送中... ({interval_ms} ms)")
        elif self.active_send_mode == "single":
            self.send_status.setText(f"循环发送中... ({interval_ms} ms)")

    def _clear_status_tabs(self):
        """移除并销毁旧协议标签页，避免反复切换协议时积累控件。"""

        while self.status_tabs.count():
            page = self.status_tabs.widget(0)
            self.status_tabs.removeTab(0)
            if page is not None:
                page.deleteLater()

    def show_hangzhou_anxian_status_config(self):
        """显示杭州安显协议Status配置界面"""
        # 清除现有标签页
        self._clear_status_tabs()

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
        self._compact_status_tab_pages()
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

            frame_length = self.protocol_handler.get_protocol_frame_length(self.current_protocol)
            needs_default_frame = (
                previous_scenario == 3
                or self.custom_frame_data is None
                or len(self.custom_frame_data) != frame_length
            )
            if needs_default_frame:
                try:
                    self.custom_frame_data = self._make_default_custom_frame()
                except ValueError as exc:
                    self.custom_frame_data = None
                    self.frame_config_btn.setEnabled(False)
                    QMessageBox.critical(self, "帧生成失败", str(exc))
                    return
        else:
            self.status_tabs.setEnabled(False)
            self.frame_config_btn.setEnabled(False)

            try:
                ui_spec = get_protocol_ui_spec(self.current_protocol)
            except ValueError as exc:
                self.status_bar.showMessage(str(exc), 5000)
                return

            getattr(self, ui_spec.preset_loader)(scenario_id)

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

    def load_fz_sif_preset_scenario(self, scenario_id):
        """加载 FZ-sif 协议预设场景"""
        if scenario_id == 0:  # 正常运行
            self.current_status = PresetScenarios.fz_sif_normal_running()
        elif scenario_id == 1:  # 能量回收
            self.current_status = PresetScenarios.fz_sif_energy_recovery()
        elif scenario_id == 2:  # 故障场景
            self.current_status = PresetScenarios.fz_sif_fault_scenario()
        else:
            self.current_status = StatusBits(protocol_name=PROTOCOL_FZ_SIF)

        self.update_ruilun_ui_from_status()

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

    def load_sxsy_preset_scenario(self, scenario_id):
        """加载 SXSY 一线通协议预设场景。"""

        if scenario_id == 0:
            self.current_status = PresetScenarios.sxsy_normal_running()
        elif scenario_id == 1:
            self.current_status = PresetScenarios.sxsy_energy_recovery()
        elif scenario_id == 2:
            self.current_status = PresetScenarios.sxsy_fault_scenario()
        else:
            self.current_status = StatusBits(protocol_name=PROTOCOL_SXSY)

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

    def load_tailing_y34b_preset_scenario(self, scenario_id):
        """加载无锡台铃 Y34B 协议预设场景"""
        if scenario_id == 0:
            self.current_status = PresetScenarios.tailing_y34b_normal_running()
        elif scenario_id == 1:
            self.current_status = PresetScenarios.tailing_y34b_energy_recovery()
        elif scenario_id == 2:
            self.current_status = PresetScenarios.tailing_y34b_fault_scenario()
        else:
            self.current_status = StatusBits(protocol_name=PROTOCOL_TAILING_Y34B)

        self.update_ruilun_ui_from_status()

    def load_tailing_y34f_preset_scenario(self, scenario_id):
        """加载无锡台铃 Y34F 协议预设场景"""
        if scenario_id == 0:
            self.current_status = PresetScenarios.tailing_y34f_normal_running()
        elif scenario_id == 1:
            self.current_status = PresetScenarios.tailing_y34f_energy_recovery()
        elif scenario_id == 2:
            self.current_status = PresetScenarios.tailing_y34f_fault_scenario()
        else:
            self.current_status = StatusBits(protocol_name=PROTOCOL_TAILING_Y34F)

        self.update_ruilun_ui_from_status()

    def load_shenzhouxing_preset_scenario(self, scenario_id):
        """加载神州行协议预设场景"""
        if scenario_id == 0:
            self.current_status = PresetScenarios.shenzhouxing_normal_running()
        elif scenario_id == 1:
            self.current_status = PresetScenarios.shenzhouxing_energy_recovery()
        elif scenario_id == 2:
            self.current_status = PresetScenarios.shenzhouxing_fault_scenario()
        else:
            self.current_status = StatusBits(protocol_name=PROTOCOL_SHENZHOUXING)

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

    def load_youyibao_preset_scenario(self, scenario_id):
        """加载优仪宝一线通协议预设场景"""
        if scenario_id == 0:
            self.current_status = PresetScenarios.youyibao_normal_running()
        elif scenario_id == 1:
            self.current_status = PresetScenarios.youyibao_energy_recovery()
        elif scenario_id == 2:
            self.current_status = PresetScenarios.youyibao_fault_scenario()
        else:
            self.current_status = StatusBits(protocol_name=PROTOCOL_YOUYIBAO)

        self.update_ruilun_ui_from_status()

    def load_jingxian_preset_scenario(self, scenario_id):
        """加载精显一线通协议预设场景"""
        if scenario_id == 0:
            self.current_status = PresetScenarios.jingxian_normal_running()
        elif scenario_id == 1:
            self.current_status = PresetScenarios.jingxian_energy_recovery()
        elif scenario_id == 2:
            self.current_status = PresetScenarios.jingxian_fault_scenario()
        else:
            self.current_status = StatusBits(protocol_name=PROTOCOL_JINGXIAN)

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

    @pyqtSlot(bool)
    def on_soc_fault_toggled(self, checked):
        """SOC故障状态切换"""
        self.soc_spin.setEnabled(not checked)

    def get_current_status_from_ui(self) -> StatusBits:
        """从UI获取当前Status位配置，统一返回StatusBits对象"""
        ui_spec = get_protocol_ui_spec(self.current_protocol)
        return getattr(self, ui_spec.status_reader)()

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
        send_mode = self.protocol_handler.get_protocol_send_mode(self.current_protocol)
        success, error_msg = self.serial_manager.send_single_frame(frame_data, send_mode=send_mode)

        if not success:
            QMessageBox.critical(self, "发送失败", error_msg)

    def _get_current_cyclic_frame(self):
        """在发送周期内读取当前场景和最新数据，生成一份实际发送帧。"""
        if self.frame_custom_radio.isChecked():
            if self.custom_frame_data is None:
                raise ValueError("请先配置自定义帧数据")
            return self.custom_frame_data.copy()

        status = (
            self.get_current_status_from_ui()
            if self.custom_radio.isChecked()
            else self.current_status
        )
        success, frame_data, error_msg = self.generate_protocol_frame(status)
        if not success:
            raise ValueError(error_msg or "生成当前协议帧失败")
        return frame_data

    @pyqtSlot()
    def toggle_cyclic_send(self):
        """切换循环发送状态"""
        if self.serial_manager.is_cyclic_sending():
            if self.active_send_mode == "single":
                self.serial_manager.stop_cyclic_send()
                self._reset_send_action_buttons()
                self.send_status.setText("就绪")
                self.send_status.setStyleSheet("color: blue; font-weight: bold;")
                return
            # 停止循环发送
            self.serial_manager.stop_cyclic_send()
            self.active_send_mode = None
            self.packet_sequence_send_btn.setText("包组循环")
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

                # 启动时只做预览校验，实际发送周期再生成帧，避免提前消耗流水号。
                success, frame_data, error_msg = self.generate_protocol_frame_for_preview(status)

                if not success:
                    QMessageBox.critical(self, "数据错误", error_msg)
                    return

            # 开始循环发送
            interval_ms = self.interval_spin.value()
            send_mode = self.protocol_handler.get_protocol_send_mode(self.current_protocol)
            definition = PROTOCOL_DEFINITIONS.get(
                self.current_protocol,
                DEFAULT_PROTOCOL_DEFINITION,
            )
            success, error_msg = self.serial_manager.start_cyclic_send(
                frame_data,
                interval_ms,
                send_mode=send_mode,
                min_interval_ms=definition.min_send_interval_ms,
                max_interval_ms=definition.max_send_interval_ms,
                frame_provider=self._get_current_cyclic_frame,
            )

            if success:
                self.active_send_mode = "single"
                self.packet_sequence_send_btn.setText("包组循环")
                self.cyclic_send_btn.setText("停止发送")
                self.send_status.setText("循环发送中...")
                self.send_status.setStyleSheet("color: orange; font-weight: bold;")
            else:
                QMessageBox.critical(self, "发送失败", error_msg)

    def _reset_send_action_buttons(self):
        connected = self.serial_manager.is_connected
        self.single_send_btn.setEnabled(connected)
        self.cyclic_send_btn.setEnabled(connected)
        self.packet_sequence_btn.setEnabled(connected)
        self.packet_sequence_send_btn.setEnabled(connected)
        self.cyclic_send_btn.setText("循环发送")
        self.packet_sequence_send_btn.setText("包组循环")
        self.active_send_mode = None

    def _get_packet_sequence_frames(self):
        frames = self.packet_sequence_frames.get(self.current_protocol)
        if frames:
            return [frame.copy() for frame in frames]

        default_frame = self._make_default_custom_frame()
        return [default_frame]

    @pyqtSlot()
    def open_packet_sequence_config(self):
        frame_length = self.protocol_handler.get_protocol_frame_length(self.current_protocol)
        current_frames = self.packet_sequence_frames.get(self.current_protocol)
        try:
            if not current_frames:
                current_frames = [self._make_default_custom_frame()]
            elif any(len(frame) != frame_length for frame in current_frames):
                current_frames = [self._make_default_custom_frame()]
        except ValueError as exc:
            QMessageBox.critical(self, "帧生成失败", str(exc))
            return

        byte_descriptions = self.protocol_handler.get_byte_descriptions(self.current_protocol)
        dialog = PacketSequenceDialog(
            self,
            initial_frames=current_frames,
            byte_descriptions=byte_descriptions,
            dialog_title=f"{self.current_protocol} 包组配置",
            checksum_mode=self.protocol_handler.get_protocol_checksum_mode(self.current_protocol),
            default_frame_provider=self._make_default_custom_frame,
        )
        self.packet_sequence_dialog = dialog
        if dialog.exec_() == QDialog.Accepted:
            self.packet_sequence_frames[self.current_protocol] = dialog.get_frames()

    @pyqtSlot()
    def toggle_packet_sequence_send(self):
        if self.serial_manager.is_cyclic_sending():
            if self.active_send_mode == "sequence":
                self.serial_manager.stop_cyclic_send()
                self._reset_send_action_buttons()
                self.send_status.setText("就绪")
                self.send_status.setStyleSheet("color: blue; font-weight: bold;")
                return
            self.serial_manager.stop_cyclic_send()
            self._reset_send_action_buttons()

        try:
            frame_sequence = self._get_packet_sequence_frames()
        except ValueError as exc:
            QMessageBox.critical(self, "帧生成失败", str(exc))
            return
        if not frame_sequence:
            QMessageBox.warning(self, "数据错误", "请先配置包组数据")
            return

        interval_ms = self.interval_spin.value()
        send_mode = self.protocol_handler.get_protocol_send_mode(self.current_protocol)
        definition = PROTOCOL_DEFINITIONS.get(
            self.current_protocol,
            DEFAULT_PROTOCOL_DEFINITION,
        )
        success, error_msg = self.serial_manager.start_cyclic_send_sequence(
            frame_sequence,
            interval_ms,
            send_mode=send_mode,
            min_interval_ms=definition.min_send_interval_ms,
            max_interval_ms=definition.max_send_interval_ms,
        )
        if success:
            self.active_send_mode = "sequence"
            self.cyclic_send_btn.setText("循环发送")
            self.packet_sequence_send_btn.setText("停止包组")
            self.send_status.setText("包组循环发送中...")
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
        LOGGER.warning("发送失败：%s", error_msg)

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

        # 即使串口异常已先停止定时器，也要保留最终失败状态。
        self._reset_send_action_buttons()
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

    def _make_default_custom_frame(self):
        """按当前协议和当前 UI 状态生成全自定义模式的初始帧。"""
        frame_length = self.protocol_handler.get_protocol_frame_length(self.current_protocol)

        status = self.current_status
        if self.custom_radio.isChecked():
            try:
                status = self.get_current_status_from_ui()
            except Exception as exc:
                raise ValueError(f"读取当前协议配置失败：{exc}") from exc

        try:
            success, frame_data, error_msg = self.generate_protocol_frame_for_preview(status)
        except Exception as exc:
            raise ValueError(f"生成当前协议帧失败：{exc}") from exc

        if not success:
            raise ValueError(error_msg or "生成当前协议帧失败")
        if len(frame_data) != frame_length:
            raise ValueError(
                f"生成帧长度错误：期望 {frame_length} 字节，实际 {len(frame_data)} 字节"
            )

        return frame_data

    @pyqtSlot()
    def open_frame_config(self):
        """打开帧配置窗口"""
        frame_length = self.protocol_handler.get_protocol_frame_length(self.current_protocol)

        if self.custom_frame_data is None or len(self.custom_frame_data) != frame_length:
            try:
                self.custom_frame_data = self._make_default_custom_frame()
            except ValueError as exc:
                QMessageBox.critical(self, "帧生成失败", str(exc))
                return

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

    def on_timing_warning(self, message):
        """显示非阻塞时序告警，不把允许设置 10ms 等同于硬件保证。"""
        self.status_bar.showMessage(message, 6000)
        LOGGER.info("发送时序提示：%s", message)
        self.pending_history_updates.append("[时序提示] " + message)

    def refresh_recovery_notice(self):
        """普通打包版启动只读检查；更新握手期间不把正在执行的本次事务误报为中断。"""
        if not getattr(sys, "frozen", False) or os.environ.get(STARTUP_REQUEST_ENV):
            return
        notice = inspect_recovery(Path(sys.executable).resolve().parent)
        self._recovery_notice = notice.message if notice is not None else ""
        if notice is not None:
            self.status_bar.showMessage("检测到更新事务记录，请从“配置 / 诊断”查看恢复指引")

    def on_send_statistics(self, statistics):
        """显示真实写入统计，详细信息通过诊断导出，不逐帧刷新历史文本。"""
        period = statistics.get("actual_interval_ms")
        period_text = "--" if period is None else f"{period:.1f}ms"
        self.send_statistics_label.setText(
            f"已写入 {statistics['sent_frames']} 帧 | 写入周期 {period_text} | "
            f"缓冲 {statistics['queue_bytes']} 字节 | 延后 {statistics['deferred_ticks']} 次"
        )

    def closeEvent(self, event):
        """窗口关闭事件"""
        # 修复关闭窗口后后台线程仍持有串口的问题，不能强杀正在写入的线程。
        if not self.serial_manager.shutdown():
            self.status_bar.showMessage("串口仍在完成当前帧，请稍后再次关闭窗口", 5000)
            event.ignore()
            return
        self.save_remembered_configuration()
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
