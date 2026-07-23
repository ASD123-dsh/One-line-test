#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
瑞轮仪表一线通协议测试软件 V1.56
主程序入口文件

基于协议文档：瑞轮仪表一线通协议_协议电压_铅酸锂电SOC_能量回收滑行充电_TCS V1.56_20240522.pdf
功能：模拟电动车控制器通过串口向多功能仪表发送合规的一线通协议数据
"""

import sys
import traceback

from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QIcon, QFont

from app_paths import resource_path
from gui.activation_dialog import ActivationDialog
from gui.main_window import MainWindow
from licensing.activation import ActivationService


def _write_exception_log(file_name: str) -> None:
    """记录当前异常，同时避免日志写入失败掩盖原始异常。"""

    try:
        with open(file_name, "w", encoding="utf-8") as file_obj:
            traceback.print_exc(file=file_obj)
    except OSError:
        pass


def main() -> None:
    """主程序入口"""
    # 创建应用程序实例
    app = QApplication(sys.argv)
    
    # 设置应用程序属性
    app.setApplicationName("瑞轮仪表一线通协议测试软件")
    app.setApplicationVersion("1.56")
    app.setOrganizationName("瑞轮仪表")
    
    # 设置全局字体
    font = QFont("Microsoft YaHei", 9)
    app.setFont(font)
    app_icon = QIcon(resource_path("img", "图标.ico"))
    app.setWindowIcon(app_icon)

    activation_service = ActivationService()
    if not activation_service.is_activated():
        activation_dialog = ActivationDialog(activation_service)
        activation_dialog.setWindowIcon(app_icon)
        if activation_dialog.exec_() != ActivationDialog.Accepted:
            return

    # 创建主窗口
    main_window = MainWindow(activation_service=activation_service)
    main_window.setWindowIcon(app_icon)
    main_window.show()
    
    # 运行应用程序
    try:
        sys.exit(app.exec_())
    except Exception:
        _write_exception_log("error.log")
        raise

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        _write_exception_log("crash.log")
        print(f"Crash: {exc}")
