#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""协调下载、完整包校验和更新器握手，不访问协议帧或授权内容。"""

import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from app_info import APP_ID, UPDATER_EXE_NAME
from app_paths import resource_path
from .installer import HANDOFF_NAME, JOB_NAME
from .package import (
    create_staging_directory, discard_staging_directory, extract_package,
    validate_staging_directory,
)
from .releases import UpdateError, check_cancelled, download_release


@dataclass(frozen=True)
class PreparedUpdate:
    """已下载和校验的版本，由对话框或独立更新器负责最终清理。"""

    release: object
    staging: Path
    payload: Path


def prepare_update(release, progress=None, cancelled=None):
    """下载并验证 ZIP，出错或取消时清理本次独占的暂存目录。"""
    staging = create_staging_directory()
    try:
        download_release(release, staging / "release.zip", progress, cancelled)
        payload = extract_package(
            staging / "release.zip", staging / "unpacked", release.version, cancelled
        )
        check_cancelled(cancelled)
        return PreparedUpdate(release, staging, payload)
    except Exception:
        discard_staging_directory(staging)
        raise


def can_install_update():
    """源码运行只提供检测功能，自动替换仅对 Windows 打包版开放。"""
    return os.name == "nt" and bool(getattr(sys, "frozen", False))


@dataclass
class UpdateHandoff:
    """保存独立更新进程和就绪状态位置，主程序不提前退出。"""

    process: object
    staging: Path

    def status(self):
        """读取完整写入的握手结果，尚未就绪时返回空值。"""
        path = self.staging / HANDOFF_NAME
        if not path.exists():
            return None
        with path.open("rb") as source:
            raw = source.read(65537)
        if len(raw) > 65536:
            raise UpdateError("更新器状态文件无效")
        data = json.loads(raw.decode("utf-8"))
        if not isinstance(data, dict):
            raise UpdateError("更新器返回了无效状态")
        return data


def launch_update_helper(prepared):
    """把更新器复制到暂存目录后启动，避免自身文件占用阻碍目录替换。"""
    if not can_install_update():
        raise UpdateError("请使用 Windows 正式打包版安装更新")
    staging = validate_staging_directory(prepared.staging)
    helper_source = Path(resource_path(UPDATER_EXE_NAME))
    if not helper_source.is_file():
        raise UpdateError("当前程序缺少独立更新器，请使用完整发布包")
    helper = staging / UPDATER_EXE_NAME
    shutil.copy2(helper_source, helper)
    # 失败后重试不能读取上次留下的就绪状态或取消标记。
    (staging / HANDOFF_NAME).unlink(missing_ok=True)
    (staging / "cancel.request").unlink(missing_ok=True)
    job = {
        "schema": 1, "app_id": APP_ID, "parent_pid": os.getpid(),
        "target_dir": str(Path(sys.executable).resolve().parent),
        "version": prepared.release.version, "sha256": prepared.release.sha256,
    }
    (staging / JOB_NAME).write_text(json.dumps(job, ensure_ascii=False), encoding="utf-8")
    environment = os.environ.copy()
    # 独立更新进程需在主程序退出后继续运行，不能复用主进程的打包临时环境。
    environment["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    process = subprocess.Popen(
        [str(helper), "--job", str(staging / JOB_NAME)], cwd=str(staging),
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), env=environment,
    )
    return UpdateHandoff(process, staging)
