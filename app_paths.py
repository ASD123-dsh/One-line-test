#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
应用路径工具。

集中处理源码运行与 PyInstaller 打包后的资源定位，避免各界面重复实现。
"""

import sys
import os
from pathlib import Path
from app_info import APP_ID


def user_data_directory() -> Path:
    """返回本工具专属用户数据目录，不把配置或诊断写入混放安装目录。"""
    local = os.environ.get("LOCALAPPDATA")
    base = Path(local) if local and Path(local).is_absolute() else Path.home() / "AppData" / "Local"
    return base / APP_ID


def resource_path(*parts: str) -> str:
    """返回应用资源的绝对路径。"""

    bundle_dir = getattr(sys, "_MEIPASS", None)
    base_dir = Path(bundle_dir) if bundle_dir else Path(__file__).resolve().parent
    return str(base_dir.joinpath(*parts))
