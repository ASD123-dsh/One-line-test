#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""只读识别精确安装目录中的更新事务，提供恢复指引，不自动回滚或删除文件。"""

import json
import re
from dataclasses import dataclass
from pathlib import Path

from app_info import APP_ID
from .file_transaction import LOCK_NAME, RECEIPT_NAME, WORK_PREFIX, owned_path
from .package import is_reparse_point, safe_relative_path
from .releases import UpdateError


@dataclass(frozen=True)
class RecoveryNotice:
    """已验证的事务状态或无法信任记录的明确提示。"""

    state: str
    message: str
    workspace: object = None


def _read_object(path, limit):
    """限制读取大小且拒绝链接，不跟随记录中未经验证的外部路径。"""
    if is_reparse_point(path) or not path.is_file():
        raise UpdateError("更新事务记录不是普通文件")
    with path.open("rb") as source:
        raw = source.read(limit + 1)
    if len(raw) > limit:
        raise UpdateError("更新事务记录过大")
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, dict):
        raise UpdateError("更新事务记录无效")
    return data


def inspect_recovery(target):
    """只读取目标目录的本工具专属锁和对应记录，不扫描同级软件或系统临时目录。"""
    target = Path(target).absolute()
    try:
        if target.resolve(strict=True) != target or is_reparse_point(target):
            raise UpdateError("安装目录包含链接或不是规范绝对路径")
        lock_path = owned_path(target, LOCK_NAME)
        if not (lock_path.exists() or lock_path.is_symlink()):
            return None
        lock = _read_object(lock_path, 8192)
        token = lock.get("token")
        if lock.get("app_id") != APP_ID or not isinstance(token, str) or re.fullmatch("[0-9a-f]{32}", token) is None:
            raise UpdateError("更新锁身份不匹配")
        workspace = owned_path(target, WORK_PREFIX + token)
        if lock.get("workspace") != str(workspace) or is_reparse_point(workspace) or not workspace.is_dir():
            raise UpdateError("更新记录指向非本工具事务目录")
        record = _read_object(owned_path(workspace, RECEIPT_NAME), 8 * 1024 * 1024)
        identity = {"schema": 1, "app_id": APP_ID, "token": token, "target": str(target), "workspace": str(workspace)}
        if type(record.get("schema")) is not int or any(record.get(key) != value for key, value in identity.items()):
            raise UpdateError("更新锁与事务记录不一致")
        state = record.get("state")
        if state not in ("prepared", "applied", "rolled_back", "rollback_failed", "committed"):
            raise UpdateError("事务状态无法识别")
        backup = owned_path(workspace, "backup")
        if backup.exists() and not backup.is_dir():
            raise UpdateError("事务备份位置不是目录")
        for key in ("old_files", "new_files"):
            files = record.get(key)
            if not isinstance(files, dict) or len(files) > 5001:
                raise UpdateError("事务文件清单无效")
            for name, digest in files.items():
                safe_relative_path(name)
                if not isinstance(digest, str) or re.fullmatch("[0-9a-f]{64}", digest) is None:
                    raise UpdateError("事务摘要无效")
        text = (
            f"检测到本工具的更新事务记录（状态：{state}）。更新可能仍在执行，也可能曾被中断。\n\n"
            "请先确认没有其他更新窗口正在运行，不要直接删除更新锁或备份。\n"
            f"本次事务目录：{workspace}\n"
            f"原文件备份位置：{backup}\n\n"
            "若升级确已中断，请保留以上目录及诊断记录，联系作者确认恢复方式；"
            "也可将官方完整包解压到新的独立目录使用，不覆盖混放目录中的其他软件。\n"
            "当前程序不会自动删除记录或未经确认地回滚。"
        )
        return RecoveryNotice(state, text, workspace)
    except (OSError, ValueError, UpdateError) as exc:
        return RecoveryNotice("untrusted", f"更新事务记录无法安全核验：{exc}\n请保留现场并联系作者；不要删除未知锁、备份或其他软件文件。")
