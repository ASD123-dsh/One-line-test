#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
瑞轮仪表一线通协议测试软件 V1.56
主程序入口文件

基于协议文档：瑞轮仪表一线通协议_协议电压_铅酸锂电SOC_能量回收滑行充电_TCS V1.56_20240522.pdf
功能：模拟电动车控制器通过串口向多功能仪表发送合规的一线通协议数据
"""

import sys
import os
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon, QFont
from gui.activation_dialog import ActivationDialog
from gui.main_window import MainWindow
from licensing.activation import ActivationService


def resource_path(*parts) -> str:
    if hasattr(sys, "_MEIPASS"):
        base_dir = sys._MEIPASS
    else:
        base_dir = os.path.abspath(os.path.dirname(__file__))
    return os.path.join(base_dir, *parts)

def main():
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
    except Exception as e:
        with open("error.log", "w") as f:
            f.write(str(e))
        raise e

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        with open("crash.log", "w") as f:
            import traceback
            traceback.print_exc(file=f)
        print(f"Crash: {e}")
