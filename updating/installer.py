#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""独立更新器：按本工具文件清单安装和回滚，新版确认启动后清理自有备份。"""

import ctypes
import json
import os
import re
import shutil
import subprocess
import time
import traceback
from pathlib import Path

from app_info import APP_EXE_NAME, APP_ID, APP_NAME
from .package import (
    file_sha256, is_reparse_point, read_manifest, validate_payload,
    validate_staging_directory,
)
from .releases import UpdateCancelled, UpdateError, parse_version
from .startup import STARTUP_REQUEST_ENV, create_startup_request, startup_is_ready
# 保留已有安装入口和事务类型的导入名称，调用方无需调整导入。
from .file_transaction import (
    InstallPlan, apply_files, cleanup_transaction, discard_prepared_installation,
    mark_committed, prepare_installation, release_lock, rollback_files, verify_installed_files,
)

JOB_NAME = "update-job.json"
HANDOFF_NAME = "handoff.json"
STARTUP_TIMEOUT_SECONDS = 60
STARTUP_STABLE_SECONDS = 5
STARTUP_POLL_SECONDS = 0.1


def write_status(root, status, message="", **extra):
    """原子写入更新器状态，主窗口在得到就绪确认后才退出。"""
    path = Path(root) / HANDOFF_NAME
    temporary = path.with_suffix(".tmp")
    data = {"status": status, "message": message}
    data.update(extra)
    temporary.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary, path)


def load_install_job(job_path):
    """验证任务身份、暂存位置、目标程序和版本，不再要求混放目录名称固定。"""
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
    if target == Path.home().resolve():
        raise UpdateError("请勿直接在用户主目录执行升级")
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


def launch_application(executable, startup_request=None):
    """从完整安装目录启动 GUI 主程序，不继承更新器的工作目录。"""
    environment = os.environ.copy()
    # 新程序独立于即将退出的更新器，避免运行库依赖更新器的临时解压目录。
    environment["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    environment.pop(STARTUP_REQUEST_ENV, None)
    if startup_request is not None:
        environment[STARTUP_REQUEST_ENV] = str(startup_request)
    return subprocess.Popen(
        [str(executable)], cwd=str(Path(executable).parent), env=environment
    )


def wait_for_application_startup(process, request_path):
    """等待新版界面确认并稳定运行，早退或一直未就绪均不能删除旧版备份。"""
    deadline = time.monotonic() + STARTUP_TIMEOUT_SECONDS
    ready_since = None
    while True:
        if process.poll() is not None:
            raise UpdateError("新版程序在启动确认期间退出")
        now = time.monotonic()
        if ready_since is None and startup_is_ready(request_path, process.pid):
            ready_since = now
        if ready_since is not None and now - ready_since >= STARTUP_STABLE_SECONDS:
            return
        if ready_since is None and now >= deadline:
            raise UpdateError("等待新版界面启动确认超时")
        time.sleep(STARTUP_POLL_SECONDS)


def _stop_unconfirmed_application(process):
    """回滚前仅停止本更新器刚启动的未就绪进程，不操作其他用户实例。"""
    if process.poll() is None:
        try:
            process.terminate()
        except OSError:
            # 修复检查存活后进程恰好退出的竞态，不能因此放弃可正常执行的回滚。
            if process.poll() is None:
                raise
        process.wait(timeout=10)


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


def apply_installation(plan, launcher=launch_application, verifier=None):
    """只替换本工具清单文件；替换或启动失败时只恢复本次事务涉及的文件。"""
    try:
        # Windows 上仍有其他实例映射主 EXE 时，可写打开会失败；只检查，不写入数据。
        with (plan.target / APP_EXE_NAME).open("r+b"):
            pass
    except OSError as exc:
        raise UpdateError(
            f"程序仍被占用或没有写权限，请关闭其他工具窗口后重试\n系统原因：{exc}"
        ) from exc
    try:
        apply_files(plan)
    except Exception as exc:
        try:
            rollback_files(plan)
        except Exception as restore_error:
            raise UpdateError(
                f"安装失败且恢复未完成，请从以下目录恢复：{plan.backup}\n"
                f"安装原因：{exc}\n恢复原因：{restore_error}"
            ) from restore_error
        try:
            launcher(plan.target / APP_EXE_NAME)
        except OSError:
            pass
        raise UpdateError(f"安装失败，旧版本文件已恢复\n系统原因：{exc}") from exc
    process = None
    try:
        process = launcher(plan.target / APP_EXE_NAME)
        if verifier is not None:
            verifier(process)
    except Exception as exc:
        if process is not None and verifier is not None:
            try:
                _stop_unconfirmed_application(process)
            except Exception as stop_error:
                plan.state = "rollback_failed"
                raise UpdateError(
                    f"新版未确认启动且无法停止，旧版备份已保留：{plan.backup}\n"
                    f"启动原因：{exc}\n停止原因：{stop_error}"
                ) from stop_error
        try:
            rollback_files(plan)
        except Exception as restore_error:
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


def cleanup_successful_backup(plan, old_manifest):
    """只清理已确认成功的本次文件事务，不检查、复制或删除其他应用和用户文件。"""
    if plan.state != "committed" or plan.old_manifest != old_manifest:
        raise UpdateError("事务尚未提交或备份身份不符，未自动清理")
    cleanup_transaction(plan)


def complete_installation(job, plan):
    """成功后尽力清理备份；清理受阻只记录警告，不把已成功的升级误报为失败。"""
    warnings = []
    backup_removed = False
    try:
        mark_committed(plan)
        cleanup_successful_backup(plan, job["old_manifest"])
        backup_removed = True
    except Exception as exc:
        warnings.append(f"旧版备份清理未完成：{exc}")
    try:
        release_lock(plan)
    except (OSError, UpdateError) as exc:
        warnings.append(f"本次更新锁清理未完成：{exc}")
    staging = job["staging"]
    try:
        (staging / "release.zip").unlink(missing_ok=True)
        shutil.rmtree(staging / "unpacked", ignore_errors=True)
    except OSError as exc:
        warnings.append(f"下载暂存清理未完成：{exc}")
    try:
        write_status(
            staging, "complete", "升级完成" if not warnings else "升级完成，部分文件清理未完成",
            backup=str(plan.backup), backup_removed=backup_removed, cleanup_warning="\n".join(warnings),
        )
    except OSError:
        # 新版已经确认启动，写日志失败不能再触发回滚或弹出升级失败提示。
        pass


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
        stage = "准备本工具文件和同盘备份"
        plan = prepare_installation(job)
        startup_request = create_startup_request(
            staging, job["target"] / APP_EXE_NAME, job["version"]
        )
        if (staging / "cancel.request").exists():
            raise UpdateCancelled("已取消安装准备")
        write_status(staging, "ready")
        stage = "等待主程序退出"
        parent.wait(lambda: (staging / "cancel.request").exists())
        parent_exited = True

        def launch_for_update(executable):
            """仅已替换完成的新版启动携带握手请求，回滚旧版不携带。"""
            request = startup_request if plan.state == "applied" else None
            return launch_application(executable, request)

        def verify_new_application(process):
            """把本次启动的进程和确认请求绑定，旧版回滚不进入此验证。"""
            wait_for_application_startup(process, startup_request)
            verify_installed_files(plan)

        stage = "替换本工具文件并确认新版启动"
        apply_installation(plan, launch_for_update, verify_new_application)
        complete_installation(job, plan)
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
        if plan is not None:
            try:
                if plan.state == "prepared" and not plan.mutated:
                    discard_prepared_installation(plan)
                else:
                    release_lock(plan)
            except (OSError, UpdateError):
                # 只释放本次事务资源；未知文件或恢复未完成时保留记录，禁止整目录删除。
                pass
