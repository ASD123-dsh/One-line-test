#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""统一配置、诊断、检测更新和扫码反馈入口，不改变各功能执行流程。"""

from dataclasses import asdict

from PyQt5.QtWidgets import QFileDialog, QMenu, QMessageBox, QToolButton

from app_info import APP_ID
from app_settings import read_config, validate_config, write_config
from diagnostics import LOGGER, export_diagnostics
from gui.protocol_ui_registry import get_protocol_ui_spec
from protocol.models import StatusBits


class SettingsPanel:
    """为主窗口提供可选配置记忆和脱敏导出，不自动连接串口或开始发送。"""

    def create_tools_button(self):
        """建立统一工具菜单，分组展示配置、诊断和更新反馈功能。"""
        button = QToolButton()
        button.setObjectName("toolsButton")
        button.setText("配置 / 诊断")
        button.setToolTip("配置管理 / 脱敏诊断 / 检测更新 / 扫码反馈")
        button.setPopupMode(QToolButton.InstantPopup)
        menu = QMenu(button)
        menu.addAction("导入配置…", self.import_configuration)
        menu.addAction("导出配置…", self.export_configuration)
        self.remember_settings_action = menu.addAction("记住本机配置（默认关闭）")
        self.remember_settings_action.setCheckable(True)
        menu.addSeparator()
        menu.addAction("导出脱敏诊断…", self.export_diagnostic_report)
        menu.addAction("查看升级恢复指引", self.show_recovery_guidance)
        # 按用户要求合并原问号入口，继续复用更新确认和扫码反馈的原处理方法。
        menu.addSeparator()
        self.check_update_action = menu.addAction("检测更新", self.show_update_dialog)
        self.feedback_action = menu.addAction("扫码反馈", self.show_feedback_dialog)
        button.setMenu(menu)
        return button

    def capture_configuration(self):
        """读取当前界面为独立配置，不保存串口身份、授权信息和自动发送开关。"""
        scenario = self.scenario_group.checkedId()
        state = self.get_current_status_from_ui() if scenario == 3 else self.current_status
        return validate_config({
            "schema": 1, "app_id": APP_ID,
            "remember": self.remember_settings_action.isChecked(),
            "protocol": self.current_protocol, "baud_rate": int(self.baud_combo.currentText()),
            "tosc_us": self.tosc_spin.value(), "interval_ms": self.interval_spin.value(),
            "scenario_id": scenario, "status": asdict(state),
            "custom_frame": self.custom_frame_data, "packet_sequences": self.packet_sequence_frames,
        })

    def apply_configuration(self, data):
        """先完整校验再应用配置；正在发送时拒绝导入，不影响在途协议帧。"""
        data = validate_config(data)
        if self.serial_manager.is_connected or self.serial_manager.is_cyclic_sending() or self.serial_manager.is_write_pending():
            raise ValueError("请先停止发送并断开串口，再导入配置；导入后不会自动重连")
        self.on_protocol_changed(data["protocol"])
        self.baud_combo.setCurrentText(str(data["baud_rate"]))
        self.tosc_spin.setValue(data["tosc_us"])
        self.interval_spin.setValue(data["interval_ms"])
        self.current_status = StatusBits(**data["status"])
        spec = get_protocol_ui_spec(self.current_protocol)
        getattr(self, spec.status_writer)()
        self.packet_sequence_frames = data["packet_sequences"]
        self.scenario_group.button(data["scenario_id"]).setChecked(True)
        self.on_scenario_changed()
        self.custom_frame_data = data["custom_frame"]
        self.update_current_frame_display()

    def load_remembered_configuration(self):
        """只恢复用户明确开启记忆的本机配置，损坏配置保留原件并回到默认值。"""
        self._settings_loaded = False
        try:
            data = self.settings_store.load()
            if data is not None:
                self._settings_loaded = True
                if data["remember"]:
                    self.apply_configuration(data)
                    self.remember_settings_action.setChecked(True)
        except (OSError, ValueError) as exc:
            LOGGER.warning("加载配置失败：%s", exc)
            self.status_bar.showMessage(f"本机配置未加载，使用默认设置：{exc}", 8000)

    def save_remembered_configuration(self):
        """关闭时保存用户选择，未开启记忆且没有旧配置时不新建文件。"""
        if not (self.remember_settings_action.isChecked() or self._settings_loaded):
            return
        try:
            self.settings_store.save(self.capture_configuration())
        except (OSError, ValueError) as exc:
            LOGGER.warning("保存配置失败：%s", exc)
            self.status_bar.showMessage(f"本机配置未保存：{exc}", 5000)

    def import_configuration(self):
        """由用户选择配置文件；验证失败时不改当前配置、不启动串口。"""
        path, _ = QFileDialog.getOpenFileName(self, "导入一线通配置", "", "配置文件 (*.json)")
        if not path:
            return
        try:
            self.apply_configuration(read_config(path))
            self.status_bar.showMessage("配置已导入；串口不会自动连接或开始发送", 5000)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "导入失败", str(exc))

    def export_configuration(self):
        """导出可复用参数，保存对话框负责确认已有目标文件的覆盖。"""
        path, _ = QFileDialog.getSaveFileName(self, "导出一线通配置", "一线通配置.json", "配置文件 (*.json)")
        if not path:
            return
        try:
            write_config(path, self.capture_configuration())
            self.status_bar.showMessage("配置已导出，不包含授权信息", 5000)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "导出失败", str(exc))

    def export_diagnostic_report(self):
        """仅导出参数和统计白名单，不导出机器标识、客户目录或原始日志。"""
        path, _ = QFileDialog.getSaveFileName(self, "导出脱敏诊断", "一线通诊断.json", "诊断文件 (*.json)")
        if not path:
            return
        try:
            export_diagnostics(path, self.current_protocol, self.serial_manager.get_port_status(), self._recovery_notice)
            self.status_bar.showMessage("脱敏诊断已导出，不含授权文件或客户目录", 5000)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "导出失败", str(exc))

    def show_recovery_guidance(self):
        """恢复只提供受验证记录的说明，绝不自动删除锁或恢复未知文件。"""
        self.refresh_recovery_notice()
        QMessageBox.information(self, "升级恢复指引", self._recovery_notice or "未检测到本工具的未完成升级记录。")
