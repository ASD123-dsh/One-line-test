#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""新版界面启动确认，只使用本次更新独占暂存目录，不访问授权或协议数据。"""

import json
import os
import re
import sys
import uuid
from pathlib import Path

from app_info import APP_EXE_NAME, APP_ID, APP_VERSION
from .package import is_reparse_point, validate_staging_directory
from .releases import UpdateError, normalized_version

STARTUP_REQUEST_ENV = "AD_ONELINE_UPDATE_STARTUP"
STARTUP_REQUEST_NAME = "startup-request.json"
STARTUP_READY_NAME = "startup-ready.json"


def _read_json(path):
    """限制启动握手文件大小，并拒绝符号链接和不完整 JSON。"""
    path = Path(path)
    if is_reparse_point(path):
        raise UpdateError("启动确认文件不能是链接")
    with path.open("rb") as source:
        raw = source.read(8193)
    if len(raw) > 8192:
        raise UpdateError("启动确认文件过大")
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise UpdateError("启动确认文件无效") from exc
    if not isinstance(data, dict):
        raise UpdateError("启动确认文件无效")
    return data


def _write_json(path, data):
    """先写本次独占文件再原子替换，避免更新器读到半写入状态。"""
    path = Path(path)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with temporary.open("x", encoding="utf-8") as output:
            json.dump(data, output, ensure_ascii=False)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def create_startup_request(staging, executable, version):
    """为本次安装生成随机握手标识，旧的启动确认不能复用。"""
    staging = validate_staging_directory(staging)
    executable = Path(executable).resolve()
    if executable.name != APP_EXE_NAME:
        raise UpdateError("启动确认目标不是本工具主程序")
    (staging / STARTUP_READY_NAME).unlink(missing_ok=True)
    path = staging / STARTUP_REQUEST_NAME
    _write_json(path, {
        "schema": 1, "app_id": APP_ID, "token": uuid.uuid4().hex,
        "executable": str(executable), "version": normalized_version(version),
    })
    return path


def read_startup_request(path):
    """确认请求属于本工具暂存目录，且绑定绝对程序路径和目标版本。"""
    path = Path(path)
    if not path.is_absolute() or path.name != STARTUP_REQUEST_NAME:
        raise UpdateError("启动确认请求路径无效")
    validate_staging_directory(path.parent)
    data = _read_json(path)
    executable = data.get("executable")
    token = data.get("token")
    if (
        type(data.get("schema")) is not int or data["schema"] != 1
        or data.get("app_id") != APP_ID
        or not isinstance(token, str) or re.fullmatch(r"[0-9a-f]{32}", token) is None
        or not isinstance(executable, str) or not Path(executable).is_absolute()
        or Path(executable).name != APP_EXE_NAME
    ):
        raise UpdateError("启动确认请求身份无效")
    data["version"] = normalized_version(data.get("version"))
    return data


def notify_startup_ready():
    """界面进入事件循环后报告就绪；普通启动或无效请求不影响软件使用。"""
    request_path = os.environ.pop(STARTUP_REQUEST_ENV, None)
    if not request_path:
        return False
    try:
        request = read_startup_request(request_path)
        if (
            Path(request["executable"]).resolve() != Path(sys.executable).resolve()
            or request["version"] != normalized_version(APP_VERSION)
        ):
            return False
        # 修复只创建进程就删除备份的风险：此确认只能由实际新版界面发出。
        response = dict(request, pid=os.getpid(), status="ready")
        _write_json(Path(request_path).parent / STARTUP_READY_NAME, response)
        return True
    except (OSError, UpdateError, ValueError):
        return False


def startup_is_ready(request_path, expected_pid):
    """校验随机标识、版本、程序路径和进程号，拒绝过期或其他实例的确认。"""
    request = read_startup_request(request_path)
    path = Path(request_path).parent / STARTUP_READY_NAME
    if not path.exists():
        return False
    response = _read_json(path)
    if (
        response.get("status") != "ready" or type(response.get("schema")) is not int
        or type(response.get("pid")) is not int
        or response["pid"] != expected_pid
        or any(response.get(key) != value for key, value in request.items())
    ):
        raise UpdateError("新版启动确认与本次更新任务不匹配")
    return True
