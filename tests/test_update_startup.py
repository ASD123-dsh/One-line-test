#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""验证新版界面启动握手、超时和早退保护，不运行或替换用户程序。"""

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from app_info import APP_EXE_NAME, APP_VERSION
from updating import installer, package, startup
from updating.releases import UpdateError


class StartupConfirmationTests(unittest.TestCase):
    """启动确认必须绑定本次任务、正确程序版本和实际新进程。"""

    def setUp(self):
        """只准备带所有权标记的独占暂存目录和模拟主程序路径。"""
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.executable = Path(self.temporary.name) / APP_EXE_NAME
        self.executable.write_bytes(b"MZ-test")
        self.staging = package.create_staging_directory()
        self.addCleanup(package.discard_staging_directory, self.staging)
        self.request_path = startup.create_startup_request(
            self.staging, self.executable, APP_VERSION
        )

    def write_ready(self, pid=1234, **changes):
        """生成与本次请求一致的确认，按需模拟错版或其他进程的响应。"""
        response = dict(startup.read_startup_request(self.request_path), pid=pid, status="ready")
        response.update(changes)
        (self.staging / startup.STARTUP_READY_NAME).write_text(
            json.dumps(response), encoding="utf-8"
        )

    def test_normal_launch_does_not_touch_startup_files(self):
        """普通启动没有请求时不访问文件，也不会触发备份清理。"""
        with patch.dict(os.environ, {}, clear=True):
            with patch.object(startup, "read_startup_request") as reader:
                self.assertFalse(startup.notify_startup_ready())
                reader.assert_not_called()

    def test_ready_notification_binds_version_path_token_and_pid(self):
        """正确版本和路径的 GUI 可以发出可验证的就绪确认。"""
        with patch.dict(os.environ, {startup.STARTUP_REQUEST_ENV: str(self.request_path)}):
            with patch.object(startup.sys, "executable", str(self.executable)):
                self.assertTrue(startup.notify_startup_ready())
            self.assertNotIn(startup.STARTUP_REQUEST_ENV, os.environ)
        self.assertTrue(startup.startup_is_ready(self.request_path, os.getpid()))
        self.assertEqual(list(self.staging.glob("*.tmp")), [])

    def test_wrong_program_path_cannot_confirm_new_version(self):
        """其他安装目录中的程序不能替本次升级发出就绪确认。"""
        with patch.dict(os.environ, {startup.STARTUP_REQUEST_ENV: str(self.request_path)}):
            self.assertFalse(startup.notify_startup_ready())
        self.assertFalse((self.staging / startup.STARTUP_READY_NAME).exists())

    def test_wrong_program_version_cannot_confirm_new_version(self):
        """即使程序路径相同，旧版本也不能确认新版成功。"""
        with patch.dict(os.environ, {startup.STARTUP_REQUEST_ENV: str(self.request_path)}):
            with patch.object(startup.sys, "executable", str(self.executable)):
                with patch.object(startup, "APP_VERSION", "0.0.1"):
                    self.assertFalse(startup.notify_startup_ready())
        self.assertFalse((self.staging / startup.STARTUP_READY_NAME).exists())

    def test_retry_gets_new_token_and_discards_old_confirmation(self):
        """同一下载任务重试安装时不能沿用上次的就绪文件。"""
        old_token = startup.read_startup_request(self.request_path)["token"]
        self.write_ready()
        startup.create_startup_request(self.staging, self.executable, APP_VERSION)
        self.assertNotEqual(startup.read_startup_request(self.request_path)["token"], old_token)
        self.assertFalse(startup.startup_is_ready(self.request_path, 1234))

    def test_confirmation_rejects_other_pid_token_version_or_executable(self):
        """不匹配的任何确认都不能作为删除备份的依据。"""
        mutations = (
            {"pid": True}, {"pid": 9999}, {"token": "0" * 32}, {"version": "0.0.1"},
            {"executable": str(self.executable.parent / "other.exe")},
            {"schema": 2}, {"schema": True}, {"app_id": "other-tool"}, {"status": "error"},
        )
        for changes in mutations:
            with self.subTest(changes=changes):
                self.write_ready(**changes)
                with self.assertRaisesRegex(UpdateError, "不匹配"):
                    startup.startup_is_ready(self.request_path, 1234)

    def test_unowned_staging_directory_is_rejected(self):
        """其他临时目录即使包含同名 JSON，也不能作为启动确认目录。"""
        foreign = Path(self.temporary.name) / startup.STARTUP_REQUEST_NAME
        foreign.write_bytes(self.request_path.read_bytes())
        with self.assertRaises((OSError, UpdateError)):
            startup.read_startup_request(foreign)
        with patch.dict(os.environ, {startup.STARTUP_REQUEST_ENV: str(foreign)}):
            self.assertFalse(startup.notify_startup_ready())

    def test_malformed_oversized_or_linked_request_is_rejected(self):
        """损坏、过大或链接请求不会影响普通启动，也不会写入确认。"""
        original = self.request_path.read_bytes()
        for content in (b"{broken", b"x" * 8193, b"[]"):
            with self.subTest(size=len(content)):
                self.request_path.write_bytes(content)
                with self.assertRaises(UpdateError):
                    startup.read_startup_request(self.request_path)
        self.request_path.write_bytes(original)
        with patch.object(startup, "is_reparse_point", return_value=True):
            with self.assertRaisesRegex(UpdateError, "链接"):
                startup.read_startup_request(self.request_path)

    def test_live_process_without_ready_confirmation_times_out(self):
        """仅有进程存活不足以判定成功，缺少界面确认必须超时。"""
        process = Mock(pid=1234)
        process.poll.return_value = None
        with patch.object(installer, "STARTUP_TIMEOUT_SECONDS", 0):
            with self.assertRaisesRegex(UpdateError, "超时"):
                installer.wait_for_application_startup(process, self.request_path)

    def test_process_exit_before_ready_is_failure(self):
        """创建成功但立即退出的程序不能进入备份清理阶段。"""
        process = Mock(pid=1234)
        process.poll.return_value = 1
        with self.assertRaisesRegex(UpdateError, "退出"):
            installer.wait_for_application_startup(process, self.request_path)

    def test_process_exit_during_stability_window_is_failure(self):
        """收到就绪后仍要观察存活，短时间内崩溃仍判定为失败。"""
        self.write_ready()
        process = Mock(pid=1234)
        process.poll.side_effect = [None, 1]
        with patch.object(installer.time, "sleep"):
            with self.assertRaisesRegex(UpdateError, "退出"):
                installer.wait_for_application_startup(process, self.request_path)

    def test_ready_process_must_survive_full_stability_window(self):
        """就绪确认与五秒观察窗口同时满足后才返回成功。"""
        self.write_ready()
        process = Mock(pid=1234)
        process.poll.return_value = None
        with patch.object(installer.time, "monotonic", side_effect=[0, 0, 2, 5]):
            with patch.object(installer.time, "sleep") as sleep:
                installer.wait_for_application_startup(process, self.request_path)
        self.assertEqual(sleep.call_count, 2)

    def test_late_ready_confirmation_still_gets_full_stability_window(self):
        """确认接近超时到达时仍有完整观察窗口，不因观察跨过原超时点失败。"""
        process = Mock(pid=1234)
        process.poll.return_value = None
        with patch.object(installer, "startup_is_ready", side_effect=[False, True]):
            with patch.object(installer.time, "monotonic", side_effect=[0, 0, 59, 64]):
                with patch.object(installer.time, "sleep"):
                    installer.wait_for_application_startup(process, self.request_path)

    def test_real_qt_child_process_confirms_startup(self):
        """真实独立 Python/Qt 事件循环完成握手；不运行用户安装目录中的 EXE。"""
        script = """
import os
from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QApplication, QWidget
from updating import startup
startup.sys.executable = os.environ['SIFEXE_TEST_EXECUTABLE']
app = QApplication([])
window = QWidget()
window.show()
QTimer.singleShot(0, startup.notify_startup_ready)
QTimer.singleShot(10000, app.quit)
app.exec_()
"""
        environment = os.environ.copy()
        environment.update({
            "QT_QPA_PLATFORM": "offscreen",
            startup.STARTUP_REQUEST_ENV: str(self.request_path),
            "SIFEXE_TEST_EXECUTABLE": str(self.executable),
        })
        process = subprocess.Popen(
            [sys.executable, "-c", script],
            cwd=str(Path(__file__).resolve().parents[1]), env=environment,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        try:
            with patch.object(installer, "STARTUP_STABLE_SECONDS", 0.2):
                with patch.object(installer, "STARTUP_TIMEOUT_SECONDS", 10):
                    installer.wait_for_application_startup(process, self.request_path)
            self.assertTrue(startup.startup_is_ready(self.request_path, process.pid))
        finally:
            if process.poll() is None:
                process.terminate()
            process.communicate(timeout=5)


class MainStartupNotificationTests(unittest.TestCase):
    """确认启动握手挂在正常 GUI 事件循环上，不改变授权流程。"""

    def test_main_window_schedules_notification_after_show(self):
        """主窗口显示后才注册零延时确认，不在窗口构造前确认。"""
        import main as entry
        app = Mock()
        app.exec_.return_value = 0
        window = Mock()
        with patch.object(entry, "QApplication", return_value=app):
            with patch.object(entry, "ActivationService") as service:
                service.return_value.is_activated.return_value = True
                with patch.object(entry, "MainWindow", return_value=window):
                    with patch.object(entry.QTimer, "singleShot") as timer:
                        with self.assertRaises(SystemExit):
                            entry.main()
                        window.show.assert_called_once_with()
                        timer.assert_called_once_with(0, entry.notify_startup_ready)

    def test_activation_dialog_also_schedules_notification(self):
        """激活窗口可正常显示不应被误判为升级启动失败。"""
        import main as entry
        with patch.object(entry, "QApplication"):
            with patch.object(entry, "ActivationService") as service:
                service.return_value.is_activated.return_value = False
                with patch.object(entry, "ActivationDialog") as dialog:
                    dialog.Accepted = 1
                    dialog.return_value.exec_.return_value = 0
                    with patch.object(entry.QTimer, "singleShot") as timer:
                        entry.main()
                    dialog.return_value.exec_.assert_called_once_with()
                    timer.assert_called_once_with(0, entry.notify_startup_ready)


if __name__ == "__main__":
    unittest.main()
