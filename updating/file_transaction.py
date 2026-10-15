#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""只操作一线通清单文件的安装事务，不搬动混放目录或扫描其他应用。"""

import json
import os
import shutil
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from app_info import APP_EXE_NAME, APP_ID
from .package import (
    file_sha256, is_reparse_point, manifest_path_for, read_manifest,
    safe_relative_path, validate_payload,
)
from .releases import UpdateError

WORK_PREFIX = ".ad-oneline-update-"
RECEIPT_NAME = "transaction.json"
LOCK_NAME = ".ad-oneline-update.lock"
FILE_MAX_ATTEMPTS = 80
FILE_RETRY_DELAY_SECONDS = 0.25
CLEANUP_MAX_ATTEMPTS = 8
RETRYABLE_WINDOWS_ERRORS = frozenset((5, 32, 33))


@dataclass
class InstallPlan:
    """记录本次逐文件事务、原文件摘要和已尝试修改的文件，不包含其他应用。"""

    target: Path
    candidate: Path
    backup: Path
    workspace: Path
    token: str
    old_files: dict
    new_files: dict
    changes: list
    retired: list
    old_manifest: dict
    new_manifest: dict
    mutated: list = field(default_factory=list)
    created_dirs: list = field(default_factory=list)
    state: str = "prepared"


def owned_path(root, name):
    """解析清单相对路径，拒绝其任意一级链接、联接点及文件类型冲突。"""
    root = Path(root)
    relative = safe_relative_path(name)
    if (
        not root.is_absolute() or is_reparse_point(root) or not root.is_dir()
        or root.resolve(strict=True) != root
    ):
        raise UpdateError("文件事务根目录无效")
    current = root
    for index, part in enumerate(relative.parts):
        current = current / part
        if current.exists() or current.is_symlink():
            if is_reparse_point(current):
                raise UpdateError(f"受管理文件路径包含链接：{name}")
            if index < len(relative.parts) - 1 and not current.is_dir():
                raise UpdateError(f"受管理文件的父路径不是目录：{name}")
    return current


def retry_file_operation(operation, *arguments, attempts=None):
    """仅对原生 Windows 临时占用有限重试，保留原始错误和既有日志字段。"""
    if attempts is None:
        attempts = FILE_MAX_ATTEMPTS
    if type(attempts) is not int or attempts < 1:
        raise UpdateError("文件操作重试次数必须是正整数")
    errors = []
    started = time.monotonic()
    for index in range(attempts):
        try:
            return operation(*arguments)
        except OSError as exc:
            errors.append(getattr(exc, "winerror", None))
            exc.rename_attempts = index + 1
            exc.rename_errors = errors.copy()
            exc.rename_elapsed_seconds = round(time.monotonic() - started, 3)
            if errors[-1] not in RETRYABLE_WINDOWS_ERRORS or index + 1 == attempts:
                raise
            time.sleep(FILE_RETRY_DELAY_SECONDS)


def _write_receipt(plan):
    """在每次修改前原子记录范围和恢复所需信息，更新中断时可追溯原文件。"""
    path = _workspace_location(plan) / RECEIPT_NAME
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    data = {
        "schema": 1, "app_id": APP_ID, "token": plan.token,
        "target": str(plan.target), "workspace": str(plan.workspace), "state": plan.state,
        "old_files": plan.old_files, "new_files": plan.new_files,
        "changes": plan.changes, "retired": plan.retired, "mutated": plan.mutated,
        "created_dirs": plan.created_dirs,
    }
    try:
        with temporary.open("x", encoding="utf-8") as output:
            json.dump(data, output, ensure_ascii=False)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _workspace_location(plan):
    """每次读写事务记录前核对精确目录位置，不能借链接跳到其他应用路径。"""
    workspace = Path(plan.workspace)
    if (
        not workspace.is_absolute() or workspace.parent != plan.target
        or workspace.name != WORK_PREFIX + plan.token
        or workspace.resolve(strict=True) != workspace or is_reparse_point(workspace)
        or is_reparse_point(plan.target)
    ):
        raise UpdateError("更新事务工作目录无效")
    if plan.backup != workspace / "backup" or plan.candidate != workspace / "candidate":
        raise UpdateError("备份或候选目录不属于本次事务")
    return workspace


def validate_workspace(plan):
    """只接受本次计划创建且身份吻合的子目录，禁止递归操作安装根目录。"""
    workspace = _workspace_location(plan)
    receipt = owned_path(workspace, RECEIPT_NAME)
    with receipt.open("rb") as source:
        raw = source.read(8 * 1024 * 1024 + 1)
    if len(raw) > 8 * 1024 * 1024:
        raise UpdateError("更新事务记录过大")
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise UpdateError("更新事务记录损坏") from exc
    identity = (
        ("app_id", APP_ID), ("token", plan.token), ("target", str(plan.target)),
        ("workspace", str(workspace)), ("old_files", plan.old_files), ("new_files", plan.new_files),
    )
    if (
        not isinstance(data, dict) or type(data.get("schema")) is not int
        or data["schema"] != 1 or any(data.get(key) != value for key, value in identity)
    ):
        raise UpdateError("更新事务记录身份已变化")
    return workspace


def _acquire_lock(plan):
    """通过独占创建锁文件阻止同一目录并行升级，不覆盖其他文件或未完成事务。"""
    path = owned_path(plan.target, LOCK_NAME)
    try:
        with path.open("x", encoding="utf-8") as output:
            json.dump({"app_id": APP_ID, "token": plan.token, "workspace": str(plan.workspace)}, output)
    except FileExistsError as exc:
        raise UpdateError("此目录已有更新任务或未完成事务，请先检查 .ad-oneline-update.lock") from exc


def release_lock(plan):
    """只删除随机标识匹配的本次锁，恢复未完成时继续保留锁防止再次覆盖。"""
    if plan.state not in ("prepared", "rolled_back", "committed"):
        return
    path = owned_path(plan.target, LOCK_NAME)
    if not path.exists():
        return
    with path.open("rb") as source:
        raw = source.read(8193)
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise UpdateError("更新锁已变化，未删除其他文件") from exc
    if data != {"app_id": APP_ID, "token": plan.token, "workspace": str(plan.workspace)}:
        raise UpdateError("更新锁不属于本次事务，未删除")
    retry_file_operation(path.unlink, attempts=CLEANUP_MAX_ATTEMPTS)


def _current_digest(root, name):
    """读取单个受管理文件，不枚举同级目录或其他应用的文件。"""
    path = owned_path(root, name)
    if not path.exists():
        return None
    if not path.is_file():
        raise UpdateError(f"受管理文件位置被目录占用：{name}")
    return file_sha256(path)


def prepare_installation(job):
    """准备新文件和本工具受影响文件的备份，不复制混放目录中的其他内容。"""
    target = job["target"]
    new_manifest = validate_payload(job["payload"], job["version"])
    if new_manifest.get("layout") != "isolated":
        raise UpdateError("逐文件升级需要专属运行库更新包，请使用带 managed 的完整发行包")
    old_manifest = read_manifest(target)
    if old_manifest != job["old_manifest"]:
        raise UpdateError("当前程序清单在检测后发生变化，请重新检测更新")
    old_name = manifest_path_for(target).name
    new_name = manifest_path_for(job["payload"]).name
    # 旧共享运行库不做替换、删除或备份；回滚旧主程序时仍使用原位置的依赖。
    old_owned = {
        name: digest for name, digest in old_manifest["files"].items()
        if name == APP_EXE_NAME or old_manifest.get("layout") == "isolated"
    }
    old_owned[old_name] = file_sha256(owned_path(target, old_name))
    new_files = dict(new_manifest["files"])
    new_files[new_name] = file_sha256(job["payload"] / new_name)
    current = {}
    for name in sorted(set(old_owned) | set(new_files)):
        digest = _current_digest(target, name)
        if name in old_owned:
            if digest is not None and digest != old_owned[name]:
                raise UpdateError(f"本工具文件已被修改，未覆盖：{name}")
        elif digest is not None:
            raise UpdateError(f"新文件路径被非本工具文件占用，未覆盖：{name}")
        current[name] = digest
    changes = [name for name, digest in new_files.items() if current[name] != digest]
    changes.sort(key=lambda name: (2 if name == new_name else 1 if name == APP_EXE_NAME else 0, name))
    retired = sorted(name for name in old_owned if name not in new_files and current[name] is not None)
    old_files = {name: current[name] for name in changes + retired if current[name] is not None}
    token = uuid.uuid4().hex
    workspace = target / (WORK_PREFIX + token)
    workspace.mkdir()
    plan = InstallPlan(
        target, workspace / "candidate", workspace / "backup", workspace, token,
        old_files, new_files, changes, retired, old_manifest, new_manifest,
    )
    try:
        _write_receipt(plan)
        _acquire_lock(plan)
        shutil.copytree(job["payload"], plan.candidate)
        validate_payload(plan.candidate, job["version"])
        plan.backup.mkdir()
        for name, digest in old_files.items():
            source = owned_path(target, name)
            destination = owned_path(plan.backup, name)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            if file_sha256(destination) != digest or _current_digest(target, name) != digest:
                raise UpdateError(f"备份期间文件发生变化，原程序未替换：{name}")
        return plan
    except Exception:
        try:
            discard_prepared_installation(plan)
        except (OSError, UpdateError):
            pass
        raise


def _ensure_target_parent(plan, name):
    """仅创建本次管理路径缺少的父目录，回滚时只移除这些空目录。"""
    destination = owned_path(plan.target, name)
    missing = []
    parent = destination.parent
    while parent != plan.target and not parent.exists():
        missing.append(parent)
        parent = parent.parent
    for directory in reversed(missing):
        directory.mkdir()
        plan.created_dirs.append(directory.relative_to(plan.target).as_posix())
    return destination


def apply_files(plan):
    """逐文件原子替换并最后切换清单，任何失败均留有本工具文件的恢复副本。"""
    validate_workspace(plan)
    if plan.state != "prepared" or plan.mutated:
        raise UpdateError("本次事务已经执行，不能重复安装")
    for name in plan.changes + plan.retired:
        if _current_digest(plan.target, name) != plan.old_files.get(name):
            raise UpdateError(f"文件在准备后发生变化，已停止升级：{name}")
    for name in plan.changes + plan.retired:
        destination = _ensure_target_parent(plan, name)
        if _current_digest(plan.target, name) != plan.old_files.get(name):
            raise UpdateError(f"文件在替换前发生变化，已停止升级：{name}")
        plan.mutated.append(name)
        _write_receipt(plan)
        if name in plan.retired:
            retry_file_operation(os.replace, destination, owned_path(plan.backup, name))
        else:
            source = owned_path(plan.candidate, name)
            if file_sha256(source) != plan.new_files[name]:
                raise UpdateError(f"候选文件在准备后发生变化：{name}")
            # 新路径不用覆盖式替换，防止同级其他应用在检查后创建同名文件。
            operation = os.replace if name in plan.old_files else os.rename
            retry_file_operation(operation, source, destination)
    verify_installed_files(plan)
    plan.state = "applied"
    _write_receipt(plan)


def rollback_files(plan):
    """只恢复已尝试替换的本工具文件，原位其他应用和用户文件完全不参与回滚。"""
    validate_workspace(plan)
    if plan.state == "committed":
        raise UpdateError("已提交的事务不能再次回滚")
    try:
        restore_root = plan.workspace / "restore"
        restore_root.mkdir(exist_ok=True)
        for name in reversed(plan.mutated):
            destination = owned_path(plan.target, name)
            observed = _current_digest(plan.target, name)
            old_digest = plan.old_files.get(name)
            if observed == old_digest:
                continue
            if observed is not None and observed != plan.new_files.get(name):
                raise UpdateError(f"回滚目标被修改，未覆盖其他内容：{name}")
            if old_digest is None:
                if observed is not None:
                    retry_file_operation(destination.unlink)
                continue
            backup = owned_path(plan.backup, name)
            if file_sha256(backup) != old_digest:
                raise UpdateError(f"回滚备份校验失败：{name}")
            temporary = owned_path(restore_root, name)
            temporary.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(backup, temporary)
            destination = _ensure_target_parent(plan, name)
            retry_file_operation(os.replace if observed is not None else os.rename, temporary, destination)
        for name in sorted(set(plan.created_dirs), key=lambda value: value.count("/"), reverse=True):
            directory = owned_path(plan.target, name)
            if directory.exists():
                try:
                    directory.rmdir()
                except OSError:
                    # 只移除空目录；用户或其他应用新增文件后保留该目录。
                    pass
        plan.state = "rolled_back"
        _write_receipt(plan)
    except Exception:
        plan.state = "rollback_failed"
        try:
            _write_receipt(plan)
        except OSError:
            pass
        raise


def mark_committed(plan):
    """新版确认启动后提交事务，此后清理失败只保留警告，不再回滚业务状态。"""
    validate_workspace(plan)
    if plan.state != "applied":
        raise UpdateError("文件尚未安装完成，不能提交事务")
    plan.state = "committed"
    _write_receipt(plan)


def verify_installed_files(plan):
    """只复核新版受管理文件的摘要，不把混放目录的未知文件判作损坏。"""
    for name, digest in plan.new_files.items():
        if _current_digest(plan.target, name) != digest:
            raise UpdateError(f"已安装的本工具文件校验失败：{name}")


def _cleanup_owned_tree(root, records):
    """只删除记录中且摘要匹配的文件，目录仅用 rmdir 删除空目录，不递归删未知数据。"""
    if not root.exists():
        return
    directories = {root}
    for name, digest in records.items():
        path = owned_path(root, name)
        parent = path.parent
        while parent != root:
            directories.add(parent)
            parent = parent.parent
        if path.exists():
            if not path.is_file() or file_sha256(path) != digest:
                raise UpdateError(f"事务文件已变化，未自动删除：{name}")
            retry_file_operation(path.unlink, attempts=CLEANUP_MAX_ATTEMPTS)
    for directory in sorted(directories, key=lambda value: len(value.parts), reverse=True):
        if directory.exists():
            if is_reparse_point(directory):
                raise UpdateError("事务清理目录变成链接，未自动删除")
            retry_file_operation(directory.rmdir, attempts=CLEANUP_MAX_ATTEMPTS)


def cleanup_transaction(plan):
    """核对本次事务身份后清理自有候选与备份文件，未知文件导致保留而不是被删除。"""
    workspace = validate_workspace(plan)
    for directory, records in (
        (plan.candidate, plan.new_files), (plan.backup, plan.old_files),
        (workspace / "restore", plan.old_files),
    ):
        _cleanup_owned_tree(directory, records)
    if {entry.name for entry in workspace.iterdir()} != {RECEIPT_NAME}:
        raise UpdateError("事务目录含未知文件，未自动删除")
    receipt = workspace / RECEIPT_NAME
    receipt.unlink()
    try:
        retry_file_operation(workspace.rmdir, attempts=CLEANUP_MAX_ATTEMPTS)
    except OSError:
        # 删除根目录受阻时恢复身份记录，后续人工检查仍能确认此目录归属。
        _write_receipt(plan)
        raise


def discard_prepared_installation(plan):
    """原程序未替换时清理本次准备文件，绝不删除安装目录或其他应用文件。"""
    try:
        if plan.state == "prepared" and not plan.mutated:
            cleanup_transaction(plan)
    finally:
        release_lock(plan)
