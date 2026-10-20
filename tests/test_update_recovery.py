#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""中断事务的只读识别测试，不执行文件替换或自动回滚。"""

import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication

from app_info import APP_ID
from updating.file_transaction import LOCK_NAME, RECEIPT_NAME, WORK_PREFIX
from updating.recovery import inspect_recovery
from updating.recovery import RecoveryNotice
from updating.startup import STARTUP_REQUEST_ENV
from app_settings import SettingsStore
from gui.main_window import MainWindow
from serial_comm.serial_manager import SerialPortDetector

_APP = QApplication.instance() or QApplication([])


class RecoveryInspectionTests(unittest.TestCase):
    """只访问明确归属的锁和记录，混放文件始终保持原样。"""

    def setUp(self):
        """建立一个模拟中断事务及完全无关的客户文件。"""
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.token = "a" * 32
        self.workspace = self.root / (WORK_PREFIX + self.token)
        self.workspace.mkdir()
        self.foreign = self.root / "其他应用.exe"
        self.foreign.write_bytes(b"customer")
        self.lock = {"app_id": APP_ID, "token": self.token, "workspace": str(self.workspace)}
        self.record = {"schema": 1, "app_id": APP_ID, "token": self.token,
                       "target": str(self.root), "workspace": str(self.workspace), "state": "applied",
                       "old_files": {"tool.exe": "b" * 64}, "new_files": {"tool.exe": "c" * 64}}
        self.save_records()

    def save_records(self):
        """只写入本测试拥有的模拟记录。"""
        (self.root / LOCK_NAME).write_text(json.dumps(self.lock), encoding="utf-8")
        (self.workspace / RECEIPT_NAME).write_text(json.dumps(self.record), encoding="utf-8")

    def test_known_states_produce_guidance_without_modifying_files(self):
        """可能仍在运行的事务不能被误当作失败自动回滚。"""
        for state in ("prepared", "applied", "rollback_failed", "rolled_back", "committed"):
            self.record["state"] = state
            self.save_records()
            before = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
            notice = inspect_recovery(self.root)
            self.assertEqual(notice.state, state)
            self.assertEqual(notice.workspace, self.workspace)
            self.assertEqual(before, {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob("*") if p.is_file()})

    def test_no_lock_does_not_scan_other_directories(self):
        """没有专属锁则不扫描名称相似的目录或其他软件。"""
        (self.root / LOCK_NAME).unlink()
        with patch.object(Path, "iterdir", side_effect=AssertionError("must not scan")):
            self.assertIsNone(inspect_recovery(self.root))

    def test_foreign_workspace_or_identity_is_not_followed(self):
        """路径和身份不匹配只给警告，绝不读取记录指定的任意路径。"""
        for field, value in (("workspace", str(self.root.parent)), ("app_id", "other-app"), ("token", "../escape")):
            with self.subTest(field=field):
                original = self.lock.copy()
                self.lock[field] = value
                self.save_records()
                self.assertEqual(inspect_recovery(self.root).state, "untrusted")
                self.lock = original
        self.assertEqual(self.foreign.read_bytes(), b"customer")

    def test_damaged_or_oversized_lock_remains_untouched(self):
        """坏记录不影响程序启动，原记录保留供人工排查。"""
        for content in (b"not-json", b"x" * 9000):
            (self.root / LOCK_NAME).write_bytes(content)
            self.assertEqual(inspect_recovery(self.root).state, "untrusted")
            self.assertEqual((self.root / LOCK_NAME).read_bytes(), content)

    def test_receipt_identity_and_file_paths_are_validated(self):
        """锁不能为其他目录的记录或危险文件名背书。"""
        self.record["old_files"] = {"../other.exe": "b" * 64}
        self.save_records()
        self.assertEqual(inspect_recovery(self.root).state, "untrusted")
        self.record["old_files"] = {}
        self.record["token"] = "b" * 32
        self.save_records()
        self.assertEqual(inspect_recovery(self.root).state, "untrusted")

    def test_linked_lock_is_rejected(self):
        """重解析点不能作为事务凭证。"""
        with patch("updating.recovery.is_reparse_point", side_effect=lambda path: Path(path).name == LOCK_NAME):
            self.assertEqual(inspect_recovery(self.root).state, "untrusted")


class RecoveryWindowTests(unittest.TestCase):
    """启动握手与恢复提示的界面集成，不启动真实更新器。"""

    def setUp(self):
        """隔离配置和端口检测，普通源码启动不检查 Python 安装目录。"""
        detector = patch.object(SerialPortDetector, "start_detection")
        detector.start()
        self.addCleanup(detector.stop)
        self.window = MainWindow(settings_store=SettingsStore())
        self.addCleanup(self.window.close)

    def test_source_launch_does_not_inspect_interpreter_directory(self):
        """仅 Windows 打包版需要检查真实安装目录中的事务。"""
        with patch("gui.main_window.sys.frozen", False, create=True), patch("gui.main_window.inspect_recovery") as inspector:
            self.window.refresh_recovery_notice()
        inspector.assert_not_called()

    def test_active_upgrade_startup_handshake_is_not_misreported(self):
        """正常升级启动时即使存在事务记录，也不能妨碍本次就绪握手。"""
        with patch("gui.main_window.sys.frozen", True, create=True), patch.dict(os.environ, {STARTUP_REQUEST_ENV: "test-handshake"}), patch("gui.main_window.inspect_recovery") as inspector:
            self.window.refresh_recovery_notice()
        inspector.assert_not_called()
        self.assertEqual(self.window._recovery_notice, "")

    def test_existing_transaction_blocks_new_update_and_shows_guidance(self):
        """未核验的旧事务先保留现场，不再创建第二个安装任务。"""
        notice = RecoveryNotice("applied", "保留备份并确认恢复方式")
        with patch("gui.main_window.sys.frozen", True, create=True), patch.dict(os.environ, {}, clear=True), patch("gui.main_window.inspect_recovery", return_value=notice), patch.object(self.window, "show_recovery_guidance") as guide, patch("gui.main_window.UpdateDialog") as updater:
            self.window.show_update_dialog()
        guide.assert_called_once_with()
        updater.assert_not_called()
        self.assertEqual(self.window._recovery_notice, notice.message)


if __name__ == "__main__":
    unittest.main()
