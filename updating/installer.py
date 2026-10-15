#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""独立更新器：先准备同盘候选目录，等待主进程退出后替换并保留旧版备份。"""

import ctypes
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import traceback
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from app_info import APP_EXE_NAME, APP_ID, APP_NAME, MANIFEST_NAME
from .package import (
    file_sha256, is_reparse_point, read_manifest, validate_payload,
    validate_staging_directory,
)
from .releases import UpdateCancelled, UpdateError, parse_version

JOB_NAME = "update-job.json"
HANDOFF_NAME = "handoff.json"
RENAME_MAX_ATTEMPTS = 80
RENAME_RETRY_DELAY_SECONDS = 0.25
RETRYABLE_WINDOWS_ERRORS = frozenset((5, 32, 33))


def write_status(root, status, message="", **extra):
    """原子写入更新器状态，主窗口在得到就绪确认后才退出。"""
    path = Path(root) / HANDOFF_NAME
    temporary = path.with_suffix(".tmp")
    data = {"status": status, "message": message}
    data.update(extra)
    temporary.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary, path)


def load_install_job(job_path):
    """验证任务身份、暂存位置、目标程序和版本，禁止任意目录替换。"""
    job_path = Path(job_path)
    if job_path.name != JOB_NAME or is_reparse_point(job_path):
        raise UpdateError("更新任务文件无效")
    staging = validate_staging_directory(job_path.parent)
    with job_path.open("rb") as source:
        raw = source.read(65537)
    if len(raw) > 65536:
        raise UpdateError("更新任务文件过大")
    job = json.loads(raw.decode("utf-8"))
    if not isinstance(job, dict) or type(job.get("schema")) is not int or job.get("schema") != 1 or job.get("app_id") != APP_ID:
        raise UpdateError("更新任务身份不匹配")
    pid = job.get("parent_pid")
    if isinstance(pid, bool) or not isinstance(pid, int) or not (0 < pid < 2 ** 32):
        raise UpdateError("主程序进程标识无效")
    if not isinstance(job.get("sha256"), str) or re.fullmatch(r"[0-9a-f]{64}", job["sha256"]) is None:
        raise UpdateError("更新任务摘要无效")
    target_value = job.get("target_dir")
    if not isinstance(target_value, str) or not Path(target_value).is_absolute():
        raise UpdateError("更新目标必须是程序的绝对路径")
    target = Path(target_value)
    if not target.is_dir() or is_reparse_point(target) or len(target.parts) < 2:
        raise UpdateError("更新目标不是普通程序目录")
    target = target.resolve()
    if target.name != APP_NAME or target == Path.home().resolve():
        raise UpdateError("请保留完整程序文件夹名称，并将程序放在独立目录中再升级")
    if target == staging or target in staging.parents or staging in target.parents:
        raise UpdateError("程序目录与更新暂存目录不能互相包含")
    old_manifest = read_manifest(target)
    if not (target / APP_EXE_NAME).is_file() or is_reparse_point(target / APP_EXE_NAME):
        raise UpdateError("目标目录中不存在当前主程序")
    if parse_version(job.get("version")) <= parse_version(old_manifest["version"]):
        raise UpdateError("更新版本必须高于已安装的软件版本")
    payload = staging / "unpacked" / APP_NAME
    if file_sha256(staging / "release.zip") != job["sha256"]:
        raise UpdateError("更新包在下载后发生变化，已停止安装")
    validate_payload(payload, job["version"])
    job["staging"] = staging
    job["target"] = target
    job["payload"] = payload
    job["old_manifest"] = old_manifest
    return job


def preserve_user_files(target, candidate, old_manifest):
    """保留程序目录内的用户导出文件，不混入旧运行库或覆盖新版程序文件。"""
    managed = {name.casefold() for name in old_manifest["files"]} | {MANIFEST_NAME.casefold()}
    pending = [target]
    while pending:
        directory = pending.pop()
        for source in directory.iterdir():
            relative = source.relative_to(target)
            if relative.parts[0].casefold() == "_internal":
                continue
            if is_reparse_point(source):
                raise UpdateError(f"用户文件包含链接，请先移出程序目录：{relative}")
            if source.is_dir():
                pending.append(source)
                continue
            if relative.as_posix().casefold() in managed:
                continue
            destination = candidate / relative
            if destination.exists():
                # 同名新版文件优先；原用户文件仍完整保存在旧版备份中。
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)


@dataclass
class InstallPlan:
    """只描述已验证并位于目标同一磁盘的安装事务。"""

    target: Path
    candidate: Path
    backup: Path


def prepare_installation(job):
    """在主程序退出前完成复制和校验，权限不足或损坏时保持当前软件运行。"""
    target = job["target"]
    candidate = Path(tempfile.mkdtemp(prefix=".sifexe-install-", dir=str(target.parent)))
    try:
        shutil.copytree(job["payload"], candidate, dirs_exist_ok=True)
        validate_payload(candidate, job["version"])
        preserve_user_files(target, candidate, job["old_manifest"])
    except Exception:
        shutil.rmtree(candidate)
        raise
    backup = target.with_name(
        target.name + ".backup-" + datetime.now().strftime("%Y%m%d-%H%M%S")
        + "-" + uuid.uuid4().hex[:8]
    )
    return InstallPlan(target, candidate, backup)


def launch_application(executable):
    """从完整安装目录启动 GUI 主程序，不继承更新器的工作目录。"""
    environment = os.environ.copy()
    # 新程序独立于即将退出的更新器，避免运行库依赖更新器的临时解压目录。
    environment["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    return subprocess.Popen(
        [str(executable)], cwd=str(Path(executable).parent), env=environment
    )


def _rename_directory(source, destination):
    """对 Windows 临时访问拒绝和共享占用有限重试，不覆盖或删除冲突目录。"""
    started = time.monotonic()
    errors = []
    for attempt in range(RENAME_MAX_ATTEMPTS):
        try:
            os.rename(source, destination)
            return
        except OSError as exc:
            errors.append(getattr(exc, "winerror", None))
            exc.rename_attempts = attempt + 1
            exc.rename_errors = errors.copy()
            exc.rename_elapsed_seconds = round(time.monotonic() - started, 3)
            # 修复更新时目录被短暂占用就立即回滚的问题；其他错误直接保留原异常。
            if (
                getattr(exc, "winerror", None) not in RETRYABLE_WINDOWS_ERRORS
                or attempt + 1 == RENAME_MAX_ATTEMPTS
            ):
                raise
            time.sleep(RENAME_RETRY_DELAY_SECONDS)


def _record_install_error(staging, stage, exception):
    """保留原始系统错误和异常链，避免安装失败日志只剩概括提示。"""
    cause = exception
    for _ in range(16):
        if cause.__cause__ is None:
            break
        cause = cause.__cause__
    write_status(
        staging, "error", str(exception), stage=stage,
        error_type=type(exception).__name__,
        winerror=getattr(cause, "winerror", None), errno=getattr(cause, "errno", None),
        rename_attempts=getattr(cause, "rename_attempts", None),
        rename_errors=getattr(cause, "rename_errors", None),
        rename_elapsed_seconds=getattr(cause, "rename_elapsed_seconds", None),
        working_directory=os.getcwd(),
        detail=traceback.format_exc(),
    )


def apply_installation(plan, launcher=launch_application):
    """通过目录改名完成替换；替换或启动失败时恢复旧版。"""
    try:
        # Windows 上仍有其他实例映射主 EXE 时，可写打开会失败；只检查，不写入数据。
        with (plan.target / APP_EXE_NAME).open("r+b"):
            pass
    except OSError as exc:
        raise UpdateError(
            f"程序仍被占用或没有写权限，请关闭其他工具窗口后重试\n系统原因：{exc}"
        ) from exc
    try:
        _rename_directory(plan.target, plan.backup)
    except OSError as exc:
        raise UpdateError(f"备份旧版本失败，原程序目录未替换\n系统原因：{exc}") from exc
    try:
        _rename_directory(plan.candidate, plan.target)
    except Exception as exc:
        try:
            _rename_directory(plan.backup, plan.target)
        except OSError as restore_error:
            raise UpdateError(
                f"安装失败且恢复未完成，请从以下目录恢复：{plan.backup}\n"
                f"安装原因：{exc}\n恢复原因：{restore_error}"
            ) from restore_error
        raise UpdateError(f"安装失败，旧版本已恢复\n系统原因：{exc}") from exc
    try:
        launcher(plan.target / APP_EXE_NAME)
    except Exception as exc:
        try:
            _rename_directory(plan.target, plan.candidate)
            _rename_directory(plan.backup, plan.target)
        except OSError as restore_error:
            raise UpdateError(
                f"新版启动失败，请从以下目录恢复：{plan.backup}\n"
                f"启动原因：{exc}\n恢复原因：{restore_error}"
            ) from restore_error
        try:
            launcher(plan.target / APP_EXE_NAME)
        except OSError:
            pass
        raise UpdateError(f"新版未能启动，旧版本已恢复\n系统原因：{exc}") from exc
    return plan.backup


class WindowsParentProcess:
    """持有原进程句柄，避免仅轮询 PID 时遇到进程号复用。"""

    def __init__(self, pid, expected_executable):
        """打开并验证目标进程确实是待更新的软件。"""
        if os.name != "nt":
            raise UpdateError("自动安装更新仅支持 Windows")
        from ctypes import wintypes
        self.api = ctypes.WinDLL("kernel32", use_last_error=True)
        self.api.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        self.api.OpenProcess.restype = wintypes.HANDLE
        self.api.CloseHandle.argtypes = [wintypes.HANDLE]
        self.api.CloseHandle.restype = wintypes.BOOL
        self.api.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        self.api.WaitForSingleObject.restype = wintypes.DWORD
        self.api.QueryFullProcessImageNameW.argtypes = [
            wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD),
        ]
        self.api.QueryFullProcessImageNameW.restype = wintypes.BOOL
        self.handle = self.api.OpenProcess(0x100000 | 0x1000, False, pid)
        if not self.handle:
            raise UpdateError("无法打开主程序进程，已停止安装")
        try:
            buffer = ctypes.create_unicode_buffer(32768)
            size = wintypes.DWORD(len(buffer))
            if not self.api.QueryFullProcessImageNameW(self.handle, 0, buffer, ctypes.byref(size)):
                raise UpdateError("无法确认主程序路径")
            if Path(buffer.value).resolve() != Path(expected_executable).resolve():
                raise UpdateError("主程序进程与更新目录不一致")
        except Exception:
            self.close()
            raise

    def wait(self, cancelled=None, timeout_seconds=120):
        """等待原程序正常退出，并响应安装前取消，不强制终止用户进程。"""
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            if cancelled is not None and cancelled():
                raise UpdateCancelled("已取消安装")
            result = self.api.WaitForSingleObject(self.handle, 250)
            if result == 0:
                return
            if result != 258:
                raise UpdateError("等待主程序退出失败，原程序文件未替换")
        raise UpdateError("等待主程序退出超时，原程序文件未替换")

    def close(self):
        """释放持有的 Windows 进程句柄。"""
        if self.handle:
            self.api.CloseHandle(self.handle)
            self.handle = None


def run_installer(job_path):
    """独立更新器入口，握手成功后才允许主程序退出，结果留在暂存目录。"""
    staging = Path(job_path).parent
    parent = None
    plan = None
    parent_exited = False
    stage = "读取安装任务"
    try:
        job = load_install_job(job_path)
        staging = job["staging"]
        stage = "验证主程序进程"
        parent = WindowsParentProcess(job["parent_pid"], job["target"] / APP_EXE_NAME)
        stage = "准备同盘候选目录"
        plan = prepare_installation(job)
        if (staging / "cancel.request").exists():
            raise UpdateCancelled("已取消安装准备")
        write_status(staging, "ready")
        stage = "等待主程序退出"
        parent.wait(lambda: (staging / "cancel.request").exists())
        parent_exited = True
        stage = "替换目录并重启"
        backup = apply_installation(plan)
        write_status(staging, "complete", "升级完成", backup=str(backup))
        # 更新器自身仍在运行，保留它及结果文件，只清理已使用的大体积下载和解压副本。
        (staging / "release.zip").unlink(missing_ok=True)
        shutil.rmtree(staging / "unpacked", ignore_errors=True)
        return 0
    except Exception as exc:
        try:
            validate_staging_directory(staging)
            _record_install_error(staging, stage, exc)
        except (OSError, UpdateError):
            pass
        if parent_exited and os.name == "nt":
            ctypes.windll.user32.MessageBoxW(
                None, f"{exc}\n\n更新记录：{staging}", "软件更新未完成", 0x10
            )
        return 1
    finally:
        if parent is not None:
            parent.close()
        if plan is not None and plan.candidate.exists():
            shutil.rmtree(plan.candidate, ignore_errors=True)
