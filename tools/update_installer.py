#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""供发布工具打包为 updater.exe 的独立入口，请从主程序发起升级。"""

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if not getattr(sys, "frozen", False) and str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from updating.installer import run_installer  # noqa: E402


def main():
    """仅处理主程序创建的安装任务，不直接接受任意覆盖路径。"""
    parser = argparse.ArgumentParser(description="一线通工具独立更新器")
    parser.add_argument("--job", required=True, help="主程序创建的更新任务文件")
    args = parser.parse_args()
    return run_installer(Path(args.job))


if __name__ == "__main__":
    sys.exit(main())
