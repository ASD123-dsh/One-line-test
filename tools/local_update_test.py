#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""仅供本地验收：复制旧版后调用真实更新器，不联网、不更新用户现有安装。"""

import argparse
import ctypes
import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if not getattr(sys, "frozen", False) and str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app_info import APP_EXE_NAME, APP_ID, APP_NAME, PRIVATE_CONTENTS_DIR, UPDATER_EXE_NAME  # noqa: E402
from updating.controller import UpdateHandoff  # noqa: E402
from updating.file_transaction import LOCK_NAME, RECEIPT_NAME, WORK_PREFIX  # noqa: E402
from updating.installer import JOB_NAME, WindowsParentProcess  # noqa: E402
from updating.package import (  # noqa: E402
    create_staging_directory, extract_package, file_sha256, is_reparse_point,
    iter_regular_files, manifest_path_for, read_manifest, validate_payload,
)
from updating.releases import UpdateError, asset_name_for_version, parse_version  # noqa: E402
from updating.startup import STARTUP_READY_NAME, STARTUP_REQUEST_ENV  # noqa: E402

KIT_NAME = "local-test-kit.json"


def read_json(path):
    """读取测试记录，不接受链接、过大文件或非对象数据。"""
    path = Path(path)
    if is_reparse_point(path):
        raise UpdateError("测试记录不能是链接")
    with path.open("rb") as source:
        raw = source.read(65537)
    if len(raw) > 65536:
        raise UpdateError("测试记录过大")
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, dict):
        raise UpdateError("测试记录格式无效")
    return data


def write_json(path, data):
    """独占创建测试记录，不覆盖已有结果或用户文件。"""
    with Path(path).open("x", encoding="utf-8") as output:
        json.dump(data, output, ensure_ascii=False, indent=2)


def load_kit(root):
    """只接受配套测试包，基线和候选版本、文件摘要均需匹配。"""
    root = Path(root).resolve(strict=True)
    data = read_json(root / KIT_NAME)
    if type(data.get("schema")) is not int or data["schema"] != 1 or data.get("app_id") != APP_ID:
        raise UpdateError("不是本工具的本地升级测试包")
    baseline = root / "baseline" / APP_NAME
    manifest = validate_payload(baseline, data["baseline_version"])
    if parse_version(data["version"]) <= parse_version(manifest["version"]):
        raise UpdateError("测试候选版本必须高于旧版")
    archive = root / "release" / asset_name_for_version(data["version"], managed=True)
    if file_sha256(archive) != data["sha256"]:
        raise UpdateError("本地测试更新包摘要不匹配")
    return root, data, baseline, archive


def snapshot(path):
    """同时记录内容、修改时间和文件标识，检查其他文件没有被重写或搬动。"""
    info = path.stat()
    return {"sha256": file_sha256(path), "mtime_ns": info.st_mtime_ns, "file_id": info.st_ino}


def foreign_snapshots(target, manifest):
    """只在新建测试副本中记录其他文件；旧共享运行库也属于必须保留的范围。"""
    owned = {APP_EXE_NAME, manifest_path_for(target).name}
    if manifest.get("layout") == "isolated":
        owned.update(manifest["files"])
    return {
        path.relative_to(target).as_posix(): snapshot(path)
        for path in iter_regular_files(target)
        if path.relative_to(target).as_posix() not in owned
    }


@contextmanager
def replacement_blocker(executable, enabled):
    """回滚场景只占用新建测试副本的主 EXE，允许读写但暂时禁止替换和删除。"""
    handle = None
    api = None
    if enabled:
        from ctypes import wintypes
        api = ctypes.WinDLL("kernel32", use_last_error=True)
        api.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                   wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
        api.CreateFileW.restype = wintypes.HANDLE
        api.CloseHandle.argtypes = [wintypes.HANDLE]
        api.CloseHandle.restype = wintypes.BOOL
        handle = api.CreateFileW(str(executable), 0x80000000, 3, None, 3, 0, None)
        if handle == ctypes.c_void_p(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())
    try:
        yield
    finally:
        if handle is not None:
            api.CloseHandle(handle)


def close_test_error_windows(helper):
    """无人值守时仅关闭本次暂存更新器的错误框，不操作其他程序窗口。"""
    from ctypes import wintypes
    api = ctypes.WinDLL("user32", use_last_error=True)
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    api.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
    api.EnumWindows.restype = wintypes.BOOL
    api.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    api.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]

    @callback_type
    def visit(window, parameter):
        """以可执行文件完整路径核对窗口进程，兼容独立更新器的引导父子进程。"""
        pid = wintypes.DWORD()
        api.GetWindowThreadProcessId(window, ctypes.byref(pid))
        try:
            process = WindowsParentProcess(pid.value, helper)
        except UpdateError:
            return True
        process.close()
        api.PostMessageW(window, 0x10, 0, 0)
        return True

    api.EnumWindows(visit, 0)


def wait_status(handoff, desired, timeout=180):
    """有限等待真实更新器状态，更新器提前退出时给出暂存记录位置。"""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        status = handoff.status()
        if status and status.get("status") in desired:
            return status
        if handoff.process.poll() is not None:
            raise UpdateError(f"更新器提前退出，记录位置：{handoff.staging}")
        time.sleep(0.1)
    raise UpdateError(f"等待更新器超时，记录位置：{handoff.staging}")


def wait_installer_exit(process, helper, dismiss_errors=False):
    """等待更新器释放句柄和锁；自动验收只确认本次更新器的错误框。"""
    deadline = time.monotonic() + 60
    while process.poll() is None and time.monotonic() < deadline:
        if dismiss_errors:
            close_test_error_windows(helper)
        time.sleep(0.2)
    if process.poll() is None:
        raise UpdateError("更新器尚未退出，请关闭本次升级失败提示框后检查记录")


def verify_case(target, old_manifest, kit, foreign, status, workspace, scenario, staging):
    """用正式文件清单验证升级或回滚，并逐一比较混放文件。"""
    current = read_manifest(target)
    expected = old_manifest if scenario == "rollback" else current
    expected_version = old_manifest["version"] if scenario == "rollback" else kit["version"]
    if current["version"] != expected_version:
        raise UpdateError("测试结果版本不符")
    for name, digest in expected["files"].items():
        if file_sha256(target / name) != digest:
            raise UpdateError(f"安装或回滚后文件不符：{name}")
    for name, record in foreign.items():
        if snapshot(target / name) != record:
            raise UpdateError(f"其他文件发生变化：{name}")
    if (target / LOCK_NAME).exists():
        raise UpdateError("本次测试更新锁未释放")
    if scenario == "success":
        if status.get("status") != "complete" or not status.get("backup_removed") or workspace.exists():
            raise UpdateError("成功升级后的备份未清理，请检查记录")
        ready = read_json(staging / STARTUP_READY_NAME)
        process = WindowsParentProcess(ready["pid"], target / APP_EXE_NAME)
        try:
            if process.api.WaitForSingleObject(process.handle, 0) != 258:
                raise UpdateError("确认成功后新版已退出")
        finally:
            process.close()
    else:
        receipt = read_json(workspace / RECEIPT_NAME)
        if status.get("status") != "error" or receipt.get("state") != "rolled_back":
            raise UpdateError("未得到预期的失败回滚结果")
        if (target / PRIVATE_CONTENTS_DIR).exists():
            raise UpdateError("回滚后仍有本次创建的新运行库")
    return {"version": current["version"], "foreign_files_unchanged": len(foreign),
            "rollback_verified": scenario == "rollback", "backup_cleaned": scenario == "success"}


def run_case(root, scenario, unattended=False):
    """每次新建独立旧版副本，真实安装器执行升级；绝不覆盖现有安装和历史测试。"""
    if os.name != "nt":
        raise UpdateError("本地 EXE 升级验收仅支持 Windows")
    root, kit, baseline, archive = load_kit(root)
    cases = root / "cases"
    cases.mkdir(exist_ok=True)
    target = cases / (scenario + "-" + uuid.uuid4().hex[:10])
    shutil.copytree(baseline, target)
    (target / "其他应用示例").mkdir()
    (target / "其他应用示例" / "config.ini").write_bytes(b"foreign-app-config\r\n")
    (target / "other-app.exe").write_bytes(b"foreign-marker-only-not-an-executable\r\n")
    (target / "客户数据.txt").write_text("混放文件升级前后应保持不变。\n", encoding="utf-8")
    old_manifest = read_manifest(target)
    environment = os.environ.copy()
    environment["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    environment.pop(STARTUP_REQUEST_ENV, None)
    if unattended:
        environment["QT_QPA_PLATFORM"] = "offscreen"
    print(f"本次独立测试目录：{target}", flush=True)
    original = subprocess.Popen([str(target / APP_EXE_NAME)], cwd=target, env=environment)
    time.sleep(2)
    if original.poll() is not None:
        raise UpdateError("测试旧版无法启动，请检查该副本的 crash.log")
    if not unattended:
        print("可在此测试目录加入其他文件；不要连接串口。此过程不联网。", flush=True)
        input("旧版窗口出现后按回车准备本地升级（暂时不要关闭旧版）...")
    foreign = foreign_snapshots(target, old_manifest)
    staging = create_staging_directory()
    shutil.copy2(archive, staging / "release.zip")
    payload = extract_package(staging / "release.zip", staging / "unpacked", kit["version"])
    helper = staging / UPDATER_EXE_NAME
    shutil.copy2(payload / PRIVATE_CONTENTS_DIR / UPDATER_EXE_NAME, helper)
    write_json(staging / JOB_NAME, {
        "schema": 1, "app_id": APP_ID, "parent_pid": original.pid,
        "target_dir": str(target), "version": kit["version"], "sha256": kit["sha256"],
    })
    print(f"更新记录：{staging}", flush=True)
    with replacement_blocker(target / APP_EXE_NAME, scenario == "rollback"):
        installer = subprocess.Popen(
            [str(helper), "--job", str(staging / JOB_NAME)], cwd=staging, env=environment,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        handoff = UpdateHandoff(installer, staging)
        ready = wait_status(handoff, {"ready", "error"})
        if ready["status"] != "ready":
            raise UpdateError(ready.get("message", "更新准备失败"))
        workspaces = list(target.glob(WORK_PREFIX + "*"))
        if len(workspaces) != 1:
            raise UpdateError("本次测试事务目录数量异常")
        workspace = workspaces[0]
        receipt = read_json(workspace / RECEIPT_NAME)
        backup_files = sorted(receipt["old_files"])
        allowed_backup = {APP_EXE_NAME, manifest_path_for(target).name}
        if set(backup_files) - allowed_backup:
            raise UpdateError("旧共享布局迁移备份包含非本工具文件")
        print(f"备份只包含：{', '.join(backup_files)}", flush=True)
        if unattended:
            # 只结束本测试创建且持有 Popen 句柄的旧版，不搜索或终止用户现有工具。
            original.terminate()
            original.wait(timeout=10)
        else:
            print("准备完成：现在请手动关闭刚才的测试旧版窗口，更新器会继续。", flush=True)
        if scenario == "rollback":
            print("此场景故意占用测试 EXE，约 20 秒后应提示失败并恢复旧版。", flush=True)
        status = wait_status(handoff, {"complete", "error"})
        if status["status"] == "error":
            if not unattended:
                input("请点击升级失败弹窗的“确定”，再回到这里按回车检查回滚结果...")
        wait_installer_exit(installer, helper, unattended and status["status"] == "error")
    result = verify_case(target, old_manifest, kit, foreign, status, workspace, scenario, staging)
    result.update({"schema": 1, "app_id": APP_ID, "scenario": scenario, "target": str(target),
                   "staging": str(staging), "backup_files": backup_files, "status": status,
                   "passed": True, "startup_ready": None})
    if (staging / STARTUP_READY_NAME).exists():
        result["startup_ready"] = read_json(staging / STARTUP_READY_NAME)
    reports = root / "reports"
    reports.mkdir(exist_ok=True)
    report_path = reports / (target.name + ".json")
    write_json(report_path, result)
    print(f"验收通过：{'混放升级及自动清理' if scenario == 'success' else '升级失败及旧版回滚'}", flush=True)
    print(f"测试记录：{report_path}", flush=True)
    print("新建的测试副本和记录会保留，供人工复查；请自行关闭测试程序。", flush=True)
    return report_path


def main():
    """独立测试入口，不作为正式应用的功能或发布附件。"""
    parser = argparse.ArgumentParser(description="一线通工具本地升级验收（不联网、不发布）")
    parser.add_argument("--root", type=Path, default=Path(sys.executable).parent if getattr(sys, "frozen", False) else None)
    parser.add_argument("--scenario", choices=("success", "rollback"))
    parser.add_argument("--unattended", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    try:
        if args.root is None:
            raise UpdateError("源码运行需通过 --root 指定配套本地测试包")
        scenario = args.scenario
        if scenario is None:
            scenario = "rollback" if input("输入 1 测试成功升级，输入 2 测试失败回滚：").strip() == "2" else "success"
        run_case(args.root, scenario, args.unattended)
        return 0
    except Exception as exc:
        print(f"测试未完成：{exc}", flush=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
