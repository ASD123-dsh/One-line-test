#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""common_forms 协议配置页及状态绑定；不负责串口和升级。"""

from PyQt5.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QGridLayout,
    QGroupBox,
    QLabel,
    QSpinBox,
    QDoubleSpinBox,
    QCheckBox,
    QRadioButton,
    QButtonGroup,
)
from PyQt5.QtCore import Qt
from protocol.protocol_handler import (
    PROTOCOL_DONGWEI_GTXH,
    PROTOCOL_FZ_SIF,
    PROTOCOL_HANGZHOU_ANXIAN,
    PROTOCOL_JINGXIAN,
    PROTOCOL_RUILUN,
    PROTOCOL_SHENZHOUXING,
    PROTOCOL_SXSY,
    PROTOCOL_TAILING_Y34B,
    PROTOCOL_TAILING_Y34F,
    PROTOCOL_WUXI_YIGE,
    PROTOCOL_XINRI,
    PROTOCOL_YADEA,
    PROTOCOL_YOUYIBAO,
)


class CommonProtocolForms:
    """作为主窗口的界面组件，沿用现有控件名称和槽函数。"""

    def create_ruilun_status1_tab(self) -> QWidget:
        """创建瑞轮协议Status1配置标签页"""
        widget = QWidget()
        layout = QGridLayout(widget)
        if self.current_protocol == PROTOCOL_HANGZHOU_ANXIAN:
            layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)
            layout.setContentsMargins(8, 8, 8, 8)
            layout.setHorizontalSpacing(18)
            layout.setVerticalSpacing(6)
        layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)

        protocol = self.current_protocol
        if protocol == PROTOCOL_HANGZHOU_ANXIAN:
            layout.setContentsMargins(8, 8, 8, 8)
            layout.setHorizontalSpacing(18)
            layout.setVerticalSpacing(6)
            labels = [
                ("备用 (D3)", False),
                ("协议限速 (D2)", True),
                ("P档 (D1)", True),
                ("备用 (D0)", False),
            ]
        elif protocol == PROTOCOL_SXSY:
            # 规格书正文定义 D/E/F，四条官方样例使用 0，均显式保留。
            labels = [
                ("示例默认/未指定 (0x00)", True),
                ("无P档 (0x0F)", True),
                ("P档常亮 (0x0D)", True),
                ("P档闪烁 (0x0E)", True),
            ]
        elif protocol == PROTOCOL_XINRI:
            labels = [
                ("P档 (D3)", True),
                ("低压报警 (D2)", True),
                ("备用 (D1)", False),
                ("备用 (D0)", False),
            ]
        elif protocol == PROTOCOL_DONGWEI_GTXH:
            labels = [
                ("电压状态位 D2 (由下方电压状态控制)", False),
                ("电压状态位 D1 (由下方电压状态控制)", False),
                ("P驻车 (D3)", True),
                ("电压状态位 D0 (由下方电压状态控制)", False),
            ]
        elif protocol == PROTOCOL_FZ_SIF:
            labels = [
                ("侧撑指示 (D3)", True),
                ("限速中 (D2)", True),
                ("驻车指示(P档) (D1)", True),
                ("备用 (D0)", False),
            ]
        elif protocol == PROTOCOL_WUXI_YIGE:
            labels = [
                ("侧撑指示 (D3)", True),
                ("备用 (D2)", False),
                ("驻车指示(P档) (D1)", True),
                ("备用 (D0)", False),
            ]
        elif protocol in {PROTOCOL_TAILING_Y34B, PROTOCOL_TAILING_Y34F}:
            labels = [
                ("侧撑指示 (D3)", True),
                ("备用 (D2)", False),
                ("驻车指示(P档) (D1)", True),
                ("国标状态 (D0) - 1=国标/0=轻摩", True),
            ]
        elif protocol == PROTOCOL_SHENZHOUXING:
            labels = [
                ("侧撑指示 (D3)", True),
                ("HDC(陡坡缓降) (D2)", True),
                ("P挡 (D1)", True),
                ("HHC(坡道驻车) (D0)", True),
            ]
        elif protocol == PROTOCOL_YADEA:
            labels = [
                ("单撑断电检测 (D3)", True),
                ("备用 (D2)", False),
                ("启动保护 (D1)", True),
                ("备用 (D0)", False),
            ]
        elif protocol == PROTOCOL_YOUYIBAO:
            labels = [
                ("P档驻车 (D3)", True),
                ("侧撑标志 (D2)", True),
                ("备用 (D1)", False),
                ("备用 (D0)", False),
            ]
        elif protocol == PROTOCOL_JINGXIAN:
            labels = [
                ("侧撑标志 (D3)", True),
                ("备用 (D2)", False),
                ("P档驻车 (D1)", True),
                ("备用 (D0)", False),
            ]
        else:
            labels = [
                ("运动里程模式 (D3)", True),
                ("超速提示音 (D2)", True),
                ("P档启动保护 (D1)", True),
                ("TCS状态 (D0) - 1=亮/0=灭", True),
            ]

        status1_button_class = (
            QRadioButton if protocol == PROTOCOL_SXSY else QCheckBox
        )

        self.distance_mode_cb = status1_button_class(labels[0][0])
        self.distance_mode_cb.setEnabled(labels[0][1])
        layout.addWidget(self.distance_mode_cb, 0, 0)

        self.speed_alarm_cb = status1_button_class(labels[1][0])
        self.speed_alarm_cb.setEnabled(labels[1][1])
        layout.addWidget(self.speed_alarm_cb, 0, 1)

        self.p_gear_protect_cb = status1_button_class(labels[2][0])
        self.p_gear_protect_cb.setEnabled(labels[2][1])
        layout.addWidget(
            self.p_gear_protect_cb,
            0 if protocol == PROTOCOL_HANGZHOU_ANXIAN else 1,
            2 if protocol == PROTOCOL_HANGZHOU_ANXIAN else 0,
        )

        self.tcs_status_cb = status1_button_class(labels[3][0])
        self.tcs_status_cb.setEnabled(labels[3][1])
        layout.addWidget(
            self.tcs_status_cb,
            0 if protocol == PROTOCOL_HANGZHOU_ANXIAN else 1,
            3 if protocol == PROTOCOL_HANGZHOU_ANXIAN else 1,
        )

        if protocol == PROTOCOL_SXSY:
            self.sxsy_p_gear_group = QButtonGroup(widget)
            for state_code, button in (
                (0x00, self.distance_mode_cb),
                (0x0F, self.speed_alarm_cb),
                (0x0D, self.p_gear_protect_cb),
                (0x0E, self.tcs_status_cb),
            ):
                self.sxsy_p_gear_group.addButton(button, state_code)
            self.distance_mode_cb.setChecked(True)

        return widget

    def create_ruilun_status2_tab(self) -> QWidget:
        """创建瑞轮协议Status2配置标签页"""
        widget = QWidget()
        layout = QGridLayout(widget)

        status2_d7_enabled = self.current_protocol in {
            PROTOCOL_WUXI_YIGE,
            PROTOCOL_TAILING_Y34B,
            PROTOCOL_TAILING_Y34F,
            PROTOCOL_FZ_SIF,
            PROTOCOL_JINGXIAN,
        }
        if self.current_protocol == PROTOCOL_JINGXIAN:
            status2_d7_text = "6km巡航中 (D7)"
        else:
            status2_d7_text = "6KM推行/推车标志 (D7)" if status2_d7_enabled else "备用 (D7)"
        self.status2_d7_cb = QCheckBox(status2_d7_text)
        self.status2_d7_cb.setEnabled(status2_d7_enabled)
        layout.addWidget(self.status2_d7_cb, 0, 0)

        self.hall_fault_cb = QCheckBox("霍尔故障 (D6)")
        layout.addWidget(self.hall_fault_cb, 0, 1)

        self.throttle_fault_cb = QCheckBox("转把故障 (D5)")
        layout.addWidget(
            self.throttle_fault_cb,
            0 if self.current_protocol == PROTOCOL_HANGZHOU_ANXIAN else 1,
            2 if self.current_protocol == PROTOCOL_HANGZHOU_ANXIAN else 0,
        )

        self.controller_fault_cb = QCheckBox("控制器故障 (D4)")
        layout.addWidget(
            self.controller_fault_cb,
            0 if self.current_protocol == PROTOCOL_HANGZHOU_ANXIAN else 1,
            3 if self.current_protocol == PROTOCOL_HANGZHOU_ANXIAN else 1,
        )

        self.under_voltage_cb = QCheckBox("欠压保护 (D3)")
        layout.addWidget(
            self.under_voltage_cb,
            1 if self.current_protocol == PROTOCOL_HANGZHOU_ANXIAN else 2,
            0,
        )

        self.cruise_cb = QCheckBox("巡航 (D2)")
        layout.addWidget(
            self.cruise_cb,
            1 if self.current_protocol == PROTOCOL_HANGZHOU_ANXIAN else 2,
            1,
        )

        assist_text = (
            "胎压信号 (D1) - 1=胎压不足/0=正常"
            if self.current_protocol == PROTOCOL_TAILING_Y34F
            else "助力 (D1)"
        )
        if self.current_protocol == PROTOCOL_SHENZHOUXING:
            self.status2_d7_cb.setText("TCS (D7)")
            self.status2_d7_cb.setEnabled(True)
        self.assist_cb = QCheckBox(assist_text)
        layout.addWidget(
            self.assist_cb,
            1 if self.current_protocol == PROTOCOL_HANGZHOU_ANXIAN else 3,
            2 if self.current_protocol == PROTOCOL_HANGZHOU_ANXIAN else 0,
        )

        motor_phase_text = (
            "备用 (D0)"
            if self.current_protocol == PROTOCOL_TAILING_Y34F
            else "电机缺相 (D0)"
        )
        self.motor_phase_loss_cb = QCheckBox(motor_phase_text)
        self.motor_phase_loss_cb.setEnabled(self.current_protocol != PROTOCOL_TAILING_Y34F)
        layout.addWidget(
            self.motor_phase_loss_cb,
            1 if self.current_protocol == PROTOCOL_HANGZHOU_ANXIAN else 3,
            3 if self.current_protocol == PROTOCOL_HANGZHOU_ANXIAN else 1,
        )

        if self.current_protocol == PROTOCOL_XINRI:
            # 新日 DATA3 仅定义 D6、D5、D4、D2，未定义位禁止操作。
            self.status2_d7_cb.setText("备用 (D7)")
            self.status2_d7_cb.setEnabled(False)
            self.under_voltage_cb.setText("备用 (D3)")
            self.under_voltage_cb.setEnabled(False)
            self.assist_cb.setText("备用 (D1)")
            self.assist_cb.setEnabled(False)
            self.motor_phase_loss_cb.setText("备用 (D0)")
            self.motor_phase_loss_cb.setEnabled(False)

        return widget

    def create_ruilun_status3_tab(self) -> QWidget:
        """创建瑞轮协议Status3配置标签页"""
        widget = QWidget()
        layout = QGridLayout(widget)
        if self.current_protocol == PROTOCOL_HANGZHOU_ANXIAN:
            layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)
            layout.setContentsMargins(8, 8, 8, 8)
            layout.setHorizontalSpacing(18)
            layout.setVerticalSpacing(6)

        if self.current_protocol == PROTOCOL_SXSY:
            d7_text = "三速功能 (D7)"
        else:
            d7_text = (
                "速度模式高位 (D7)"
                if self.current_protocol in {
                    PROTOCOL_XINRI,
                    PROTOCOL_YADEA,
                    PROTOCOL_JINGXIAN,
                    PROTOCOL_DONGWEI_GTXH,
                }
                else "四档指示 (D7)"
            )
        if self.current_protocol == PROTOCOL_SXSY:
            speed_mode_label = "档位编码 (D1~D0：0=N档/1=D档/2=中速/3=高速):"
        else:
            speed_mode_label = (
                "档位模式 (D7+D1~D0):"
                if self.current_protocol == PROTOCOL_DONGWEI_GTXH
                else "速度模式 (D7+D1~D0):"
                if self.current_protocol
                in {PROTOCOL_XINRI, PROTOCOL_YADEA, PROTOCOL_JINGXIAN}
                else "三速模式 (D1~D0):"
            )

        self.gear_four_cb = QCheckBox(d7_text)
        layout.addWidget(self.gear_four_cb, 0, 0)

        motor_running_text = (
            "TCS指示 (D6) - 1=显示/0=默认"
            if self.current_protocol == PROTOCOL_TAILING_Y34F
            else "电机运行状态 (D6) - 1=运行/0=停止"
        )
        if self.current_protocol == PROTOCOL_SHENZHOUXING:
            motor_running_text = "电机运行中 (D6)"
        self.motor_running_cb = QCheckBox(motor_running_text)
        layout.addWidget(
            self.motor_running_cb,
            0,
            1,
            1,
            3 if self.current_protocol == PROTOCOL_HANGZHOU_ANXIAN else 1,
        )

        self.brake_cb = QCheckBox("刹车 (D5)")
        if self.current_protocol in {PROTOCOL_XINRI, PROTOCOL_SHENZHOUXING}:
            self.brake_cb.setText("刹车故障 (D5)")
        layout.addWidget(self.brake_cb, 1, 0)

        controller_protect_text = (
            "HDC指示 (D4) - 1=显示/0=默认"
            if self.current_protocol == PROTOCOL_TAILING_Y34F
            else "控制器保护 (D4)"
        )
        if self.current_protocol == PROTOCOL_SHENZHOUXING:
            controller_protect_text = "控制器保护 (D4)"
        self.controller_protect_cb = QCheckBox(controller_protect_text)
        layout.addWidget(self.controller_protect_cb, 1, 1)

        self.regen_charging_cb = QCheckBox("滑行充电 (D3) - 1=能量回收")
        layout.addWidget(
            self.regen_charging_cb,
            1 if self.current_protocol == PROTOCOL_HANGZHOU_ANXIAN else 2,
            2 if self.current_protocol == PROTOCOL_HANGZHOU_ANXIAN else 0,
            1,
            2 if self.current_protocol == PROTOCOL_HANGZHOU_ANXIAN else 1,
        )

        anti_runaway_text = (
            "备用 (D2)"
            if self.current_protocol == PROTOCOL_TAILING_Y34F
            else "防飞车保护 (D2)"
        )
        self.anti_runaway_cb = QCheckBox(anti_runaway_text)
        self.anti_runaway_cb.setEnabled(self.current_protocol != PROTOCOL_TAILING_Y34F)
        layout.addWidget(
            self.anti_runaway_cb,
            2 if self.current_protocol == PROTOCOL_HANGZHOU_ANXIAN else 2,
            0 if self.current_protocol == PROTOCOL_HANGZHOU_ANXIAN else 1,
        )

        layout.addWidget(
            QLabel(speed_mode_label),
            2 if self.current_protocol == PROTOCOL_HANGZHOU_ANXIAN else 3,
            1 if self.current_protocol == PROTOCOL_HANGZHOU_ANXIAN else 0,
        )
        self.speed_mode_spin = QSpinBox()
        self.speed_mode_spin.setRange(
            0,
            7
            if self.current_protocol in {
                PROTOCOL_XINRI,
                PROTOCOL_YADEA,
                PROTOCOL_JINGXIAN,
                PROTOCOL_DONGWEI_GTXH,
            }
            else 3,
        )
        if self.current_protocol == PROTOCOL_SXSY:
            self.speed_mode_spin.setToolTip(
                "0=N档，1=D档，2=中速（文档默认），3=高速"
            )
        layout.addWidget(
            self.speed_mode_spin,
            2 if self.current_protocol == PROTOCOL_HANGZHOU_ANXIAN else 3,
            2 if self.current_protocol == PROTOCOL_HANGZHOU_ANXIAN else 1,
        )

        if self.current_protocol == PROTOCOL_XINRI:
            # 新日 DATA4 的 D7 由档位数值统一生成，避免两个控件互相冲突。
            self.gear_four_cb.setText("速度模式高位由下方档位模式控制 (D7)")
            self.gear_four_cb.setEnabled(False)
            self.motor_running_cb.setText("备用 (D6)")
            self.motor_running_cb.setEnabled(False)
            self.controller_protect_cb.setText("备用 (D4)")
            self.controller_protect_cb.setEnabled(False)
            self.regen_charging_cb.setText("备用 (D3)")
            self.regen_charging_cb.setEnabled(False)
            self.anti_runaway_cb.setText("备用 (D2)")
            self.anti_runaway_cb.setEnabled(False)

        return widget

    def create_ruilun_status4_tab(self) -> QWidget:
        """创建瑞轮协议Status4配置标签页"""
        widget = QWidget()
        layout = QGridLayout(widget)
        if self.current_protocol == PROTOCOL_HANGZHOU_ANXIAN:
            layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)
            layout.setContentsMargins(8, 8, 8, 8)
            layout.setHorizontalSpacing(18)
            layout.setVerticalSpacing(6)

        if self.current_protocol in {
            PROTOCOL_WUXI_YIGE,
            PROTOCOL_TAILING_Y34B,
            PROTOCOL_TAILING_Y34F,
            PROTOCOL_FZ_SIF,
        }:
            d7_text = "云动力模式(速度提升) (D7)"
            d7_enabled = True
        elif self.current_protocol in {
            PROTOCOL_RUILUN,
            PROTOCOL_DONGWEI_GTXH,
            PROTOCOL_YOUYIBAO,
            PROTOCOL_JINGXIAN,
        }:
            d7_text = "70%电流标志 (D7)"
            d7_enabled = True
        else:
            d7_text = "备用 (D7)"
            d7_enabled = False

        if self.current_protocol == PROTOCOL_SHENZHOUXING:
            d7_enabled = True
        self.current_70_flag_cb = QCheckBox(d7_text)
        if self.current_protocol == PROTOCOL_SHENZHOUXING:
            self.current_70_flag_cb.setText("蓝牙指示 (D7)")
        self.current_70_flag_cb.setEnabled(d7_enabled)
        layout.addWidget(self.current_70_flag_cb, 0, 0)

        if self.current_protocol in {PROTOCOL_TAILING_Y34B, PROTOCOL_TAILING_Y34F}:
            d6_text = "速度协议指示位 (D6) - 1=实际车速/0=霍尔计数"
        else:
            d6_text = (
                "侧撑检测/单撑 (D6)"
                if self.current_protocol == PROTOCOL_DONGWEI_GTXH
                else "一键通启用 (D6)"
            )
        self.one_key_enable_cb = QCheckBox(d6_text)
        if self.current_protocol == PROTOCOL_SHENZHOUXING:
            self.one_key_enable_cb.setText("时间显示使能 (D6)")
        layout.addWidget(self.one_key_enable_cb, 0, 1)

        if self.current_protocol == PROTOCOL_TAILING_Y34B:
            ekk_text = "启用EKK备用电源/双欠压 (D5)"
        elif self.current_protocol == PROTOCOL_TAILING_Y34F:
            ekk_text = "双欠压指示 (D5)"
        else:
            ekk_text = "EKK启用 (D5)"
        self.ekk_enable_cb = QCheckBox(ekk_text)
        if self.current_protocol == PROTOCOL_SHENZHOUXING:
            self.ekk_enable_cb.setText("4G信号指示 (D5)")
        layout.addWidget(
            self.ekk_enable_cb,
            0 if self.current_protocol == PROTOCOL_HANGZHOU_ANXIAN else 1,
            2 if self.current_protocol == PROTOCOL_HANGZHOU_ANXIAN else 0,
        )

        over_current_text = (
            "过流保护(预留) (D4)"
            if self.current_protocol == PROTOCOL_TAILING_Y34F
            else "过流保护 (D4)"
        )
        self.over_current_cb = QCheckBox(over_current_text)
        if self.current_protocol == PROTOCOL_SHENZHOUXING:
            self.over_current_cb.setText("定位指示 (D4)")
        layout.addWidget(
            self.over_current_cb,
            0 if self.current_protocol == PROTOCOL_HANGZHOU_ANXIAN else 1,
            3 if self.current_protocol == PROTOCOL_HANGZHOU_ANXIAN else 1,
        )

        stall_protect_text = (
            "堵转保护(预留) (D3)"
            if self.current_protocol == PROTOCOL_TAILING_Y34F
            else "堵转保护 (D3)"
        )
        self.stall_protect_cb = QCheckBox(stall_protect_text)
        if self.current_protocol == PROTOCOL_SHENZHOUXING:
            self.stall_protect_cb.setText("堵转保护 (D3)")
        layout.addWidget(
            self.stall_protect_cb,
            1 if self.current_protocol == PROTOCOL_HANGZHOU_ANXIAN else 2,
            0,
        )

        self.reverse_cb = QCheckBox("倒车 (D2)")
        layout.addWidget(
            self.reverse_cb,
            1 if self.current_protocol == PROTOCOL_HANGZHOU_ANXIAN else 2,
            1,
        )

        electronic_brake_text = (
            "坐垫功能位 D1 (与 D0 组合)"
            if self.current_protocol == PROTOCOL_TAILING_Y34F
            else "电子刹车 (D1)"
        )
        self.electronic_brake_cb = QCheckBox(electronic_brake_text)
        if self.current_protocol == PROTOCOL_SHENZHOUXING:
            self.electronic_brake_cb.setText("刹车 (D1)")
        layout.addWidget(
            self.electronic_brake_cb,
            1 if self.current_protocol == PROTOCOL_HANGZHOU_ANXIAN else 3,
            2 if self.current_protocol == PROTOCOL_HANGZHOU_ANXIAN else 0,
        )

        if self.current_protocol == PROTOCOL_TAILING_Y34F:
            speed_limit_text = "坐垫功能位 D0 (与 D1 组合)"
        elif self.current_protocol == PROTOCOL_TAILING_Y34B:
            speed_limit_text = "备用 (D0)"
        else:
            speed_limit_text = "限速 (D0) - 1=限速/0=解除"
        self.speed_limit_cb = QCheckBox(speed_limit_text)
        if self.current_protocol == PROTOCOL_SHENZHOUXING:
            self.speed_limit_cb.setText("限速 (D0)")
            self.speed_limit_cb.setEnabled(True)
        self.speed_limit_cb.setEnabled(self.current_protocol != PROTOCOL_TAILING_Y34B)
        layout.addWidget(
            self.speed_limit_cb,
            1 if self.current_protocol == PROTOCOL_HANGZHOU_ANXIAN else 3,
            3 if self.current_protocol == PROTOCOL_HANGZHOU_ANXIAN else 1,
        )

        if self.current_protocol == PROTOCOL_XINRI:
            # 新日 DATA5 仅定义 D6（一键修复），其余位均按规格书保留。
            self.current_70_flag_cb.setText("备用 (D7)")
            self.current_70_flag_cb.setEnabled(False)
            for checkbox, bit_name in (
                (self.ekk_enable_cb, "D5"),
                (self.over_current_cb, "D4"),
                (self.stall_protect_cb, "D3"),
                (self.reverse_cb, "D2"),
                (self.electronic_brake_cb, "D1"),
                (self.speed_limit_cb, "D0"),
            ):
                checkbox.setText(f"备用 ({bit_name})")
                checkbox.setEnabled(False)

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
            "status8_label",
            "soc_spin",
            "sxsy_soc_spin",
            "lithium_soc_mode_cb",
        ):
            if hasattr(self, attr_name):
                delattr(self, attr_name)

        # Status5 - 运行电流
        if protocol == PROTOCOL_XINRI:
            current_label = "运行电流幅值 (0~51.0A，0.2A/LSB):"
        elif protocol == PROTOCOL_DONGWEI_GTXH:
            current_label = "运行电流 (A，发送按 0.2A/LSB 编码):"
        elif protocol == PROTOCOL_SXSY:
            current_label = "运行电流 (A，最高位为符号位):"
        else:
            current_label = "运行电流 (A):"
        layout.addWidget(QLabel(current_label), 0, 0)
        if protocol in {PROTOCOL_XINRI, PROTOCOL_DONGWEI_GTXH}:
            self.current_spin = QDoubleSpinBox()
            self.current_spin.setDecimals(1)
            self.current_spin.setSingleStep(0.2)
            if protocol == PROTOCOL_XINRI:
                self.current_spin.setRange(0.0, 51.0)
            else:
                self.current_spin.setRange(-25.6, 25.4)
        else:
            self.current_spin = QSpinBox()
            self.current_spin.setRange(
                -127 if protocol == PROTOCOL_SXSY else -128,
                127,
            )
        self.current_spin.setValue(0)
        layout.addWidget(self.current_spin, 0, 1)

        # Status6~7 - 霍尔计数
        layout.addWidget(QLabel("霍尔计数 (0.5s 三霍尔总数):"), 1, 0)
        self.hall_count_spin = QSpinBox()
        self.hall_count_spin.setRange(0, 65535)
        self.hall_count_spin.setValue(0)
        layout.addWidget(self.hall_count_spin, 1, 1)

        # 兼容旧 UI 的速度兜底值
        speed_label = QLabel("兼容速度输入 (km/h，可留 0):")
        layout.addWidget(speed_label, 2, 0)
        self.speed_spin = QDoubleSpinBox()
        self.speed_spin.setRange(0.0, 6553.5)
        self.speed_spin.setDecimals(1)
        self.speed_spin.setSingleStep(0.1)
        self.speed_spin.setValue(0.0)
        layout.addWidget(self.speed_spin, 2, 1)

        if protocol == PROTOCOL_XINRI:
            # 新日 DATA9、DATA10 固定为 00，不提供无效的 SOC/电压控件。
            speed_label.setText("备用 (DATA9/DATA10 固定为 00):")
            self.speed_spin.setEnabled(False)
            return widget

        if protocol == PROTOCOL_SXSY:
            status8_text = "电压比例 (Status8，0~100%):"
        elif protocol == PROTOCOL_HANGZHOU_ANXIAN:
            status8_text = "电压百分比 (Status8):"
        elif protocol == PROTOCOL_FZ_SIF:
            status8_text = "电池电量/电压比例值 (Status8):"
        elif protocol == PROTOCOL_JINGXIAN:
            status8_text = "电压百分比 (Status8):"
        elif protocol == PROTOCOL_YADEA:
            status8_text = "电量百分比 (Status8):"
        elif protocol == PROTOCOL_YOUYIBAO:
            status8_text = "电压/电量百分比 (Status8):"
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

        if protocol in {
            PROTOCOL_RUILUN,
            PROTOCOL_WUXI_YIGE,
            PROTOCOL_TAILING_Y34B,
            PROTOCOL_TAILING_Y34F,
            PROTOCOL_SHENZHOUXING,
        }:
            self.lithium_soc_mode_cb = QCheckBox(
                "锂电SOC模式" if protocol in {PROTOCOL_RUILUN, PROTOCOL_SHENZHOUXING} else "透传锂电SOC(D7=1)"
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
        if protocol == PROTOCOL_SXSY:
            layout.addWidget(QLabel("电池SOC (Status9，0~100%):"), row_index, 0)
            self.sxsy_soc_spin = QSpinBox()
            self.sxsy_soc_spin.setRange(0, 100)
            self.sxsy_soc_spin.setValue(50)
            layout.addWidget(self.sxsy_soc_spin, row_index, 1)
            return widget

        if protocol in {PROTOCOL_YADEA, PROTOCOL_YOUYIBAO, PROTOCOL_JINGXIAN, PROTOCOL_DONGWEI_GTXH}:
            layout.addWidget(QLabel("电流百分比 (Status9):"), row_index, 0)
            self.current_percent_spin = QSpinBox()
            self.current_percent_spin.setRange(0, 100)
            self.current_percent_spin.setValue(50)
            layout.addWidget(self.current_percent_spin, row_index, 1)
            row_index += 1

        if protocol in {PROTOCOL_YADEA, PROTOCOL_YOUYIBAO, PROTOCOL_JINGXIAN}:
            return widget

        # Status9 - 系统电压
        if protocol == PROTOCOL_DONGWEI_GTXH:
            voltage_group_title = "电压状态 (DATA2 D2~D0，仅支持默认/48V/60V/72V/80V/96V)"
        elif protocol == PROTOCOL_FZ_SIF:
            voltage_group_title = "系统电压 (FZ-sif：48V/60V/64V/72V/84V/96V)"
        else:
            voltage_group_title = "系统电压 (仅选一个，可全不选)"
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
        elif protocol == PROTOCOL_FZ_SIF:
            self.voltage_36v_rb.setEnabled(False)
            self.voltage_80v_rb.setEnabled(False)

        layout.addWidget(voltage_group, row_index, 0, 1, 2)

        return widget

    def create_shenzhouxing_extended_status_tab(self) -> QWidget:
        """创建神州行协议扩展状态页。"""
        widget = QWidget()
        layout = QGridLayout(widget)

        layout.addWidget(QLabel("实时电压(铅酸模式, 0-127V):"), 0, 0)
        self.shenzhouxing_real_time_voltage_spin = QSpinBox()
        self.shenzhouxing_real_time_voltage_spin.setRange(0, 127)
        layout.addWidget(self.shenzhouxing_real_time_voltage_spin, 0, 1)

        layout.addWidget(QLabel("4G信号强度 (0-31):"), 1, 0)
        self.shenzhouxing_signal_strength_spin = QSpinBox()
        self.shenzhouxing_signal_strength_spin.setRange(0, 31)
        layout.addWidget(self.shenzhouxing_signal_strength_spin, 1, 1)

        layout.addWidget(QLabel("时间 小时 (0-23):"), 2, 0)
        self.shenzhouxing_time_hour_spin = QSpinBox()
        self.shenzhouxing_time_hour_spin.setRange(0, 23)
        layout.addWidget(self.shenzhouxing_time_hour_spin, 2, 1)

        layout.addWidget(QLabel("时间 分钟 (0-59):"), 3, 0)
        self.shenzhouxing_time_minute_spin = QSpinBox()
        self.shenzhouxing_time_minute_spin.setRange(0, 59)
        layout.addWidget(self.shenzhouxing_time_minute_spin, 3, 1)

        self.shenzhouxing_push_assist_cb = QCheckBox("推到车 (DATA13 D7)")
        layout.addWidget(self.shenzhouxing_push_assist_cb, 4, 0)
        self.shenzhouxing_p_blink_cb = QCheckBox("P档闪烁 (DATA13 D6)")
        layout.addWidget(self.shenzhouxing_p_blink_cb, 4, 1)

        return widget

    def create_tailing_extended_status_tab(self) -> QWidget:
        """创建台铃 Y34 协议扩展状态页。"""
        widget = QWidget()
        layout = QGridLayout(widget)
        row = 0

        if self.current_protocol == PROTOCOL_TAILING_Y34F:
            self.tailing_display_voltage_from_data_cb = QCheckBox(
                "电压采集路径 DATA12/13 (D7)"
            )
            layout.addWidget(self.tailing_display_voltage_from_data_cb, row, 0)
            self.tailing_battery_over_temp_cb = QCheckBox("团标电池过温 (D6)")
            layout.addWidget(self.tailing_battery_over_temp_cb, row, 1)
            row += 1

            self.tailing_battery_over_current_cb = QCheckBox("团标电池过流 (D5)")
            layout.addWidget(self.tailing_battery_over_current_cb, row, 0)
            self.tailing_battery_over_voltage_cb = QCheckBox("电池过压 (D4)")
            layout.addWidget(self.tailing_battery_over_voltage_cb, row, 1)
            row += 1
        else:
            self.tailing_display_voltage_from_data_cb = None
            self.tailing_battery_over_temp_cb = None
            self.tailing_battery_over_current_cb = None
            self.tailing_battery_over_voltage_cb = None

        self.tailing_dual_soc_cb = QCheckBox("双显 SOC 指示位 (D3)")
        layout.addWidget(self.tailing_dual_soc_cb, row, 0)
        self.tailing_display_sleep_cb = QCheckBox("仪表休眠/黑屏 (D2)")
        layout.addWidget(self.tailing_display_sleep_cb, row, 1)
        row += 1

        self.tailing_speed_15_warning_cb = QCheckBox("15KM/H 超速预警 (D1)")
        layout.addWidget(self.tailing_speed_15_warning_cb, row, 0)
        self.tailing_brake_fault_cb = QCheckBox("刹车故障 (D0)")
        layout.addWidget(self.tailing_brake_fault_cb, row, 1)
        row += 1

        if self.current_protocol == PROTOCOL_TAILING_Y34F:
            layout.addWidget(QLabel("实时电压 (V，编码为 *10):"), row, 0)
            self.tailing_real_time_voltage_spin = QDoubleSpinBox()
            self.tailing_real_time_voltage_spin.setRange(0.0, 6553.5)
            self.tailing_real_time_voltage_spin.setDecimals(1)
            self.tailing_real_time_voltage_spin.setSingleStep(0.1)
            self.tailing_real_time_voltage_spin.setValue(48.0)
            layout.addWidget(self.tailing_real_time_voltage_spin, row, 1)
        else:
            self.tailing_real_time_voltage_spin = None

        return widget
