#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
应用路径工具。

集中处理源码运行与 PyInstaller 打包后的资源定位，避免各界面重复实现。
"""

import sys
from pathlib import Path


def resource_path(*parts: str) -> str:
    """返回应用资源的绝对路径。"""

    bundle_dir = getattr(sys, "_MEIPASS", None)
    base_dir = Path(bundle_dir) if bundle_dir else Path(__file__).resolve().parent
    return str(base_dir.joinpath(*parts))
