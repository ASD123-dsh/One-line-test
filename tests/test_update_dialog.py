#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""验证问号菜单、自动下载、用户确认和更新器握手，不访问真实网络。"""

import os
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QMessageBox, QToolButton

from app_info import APP_VERSION
from gui.main_window import MainWindow
from gui.update_dialog import UpdateDialog, UpdateWorker
from serial_comm.serial_manager import SerialPortDetector
from updating.controller import PreparedUpdate
from updating.package import create_staging_directory, discard_staging_directory

_APP = QApplication.instance() or QApplication([])


class UpdateMenuTests(unittest.TestCase):
    """问号菜单沿用原位置和反馈页面。"""

    def setUp(self):
        """创建主窗口并禁用端口扫描，测试不操作真实串口。"""
        detector = patch.object(SerialPortDetector, "start_detection", autospec=True)
        detector.start()
        self.addCleanup(detector.stop)
        self.window = MainWindow()
        self.window.history_update_timer.stop()
        self.addCleanup(self.window.close)

    def test_question_button_has_exactly_two_menu_items(self):
        """按钮保留问号和尺寸，只增加检测更新与扫码反馈两项。"""
        self.assertEqual(self.window.feedback_btn.text(), "?")
        self.assertEqual(self.window.feedback_btn.popupMode(), QToolButton.InstantPopup)
        self.assertEqual(self.window.feedback_btn.width(), 42)
        self.assertEqual([action.text() for action in self.window.help_menu.actions()], ["检测更新", "扫码反馈"])
        self.assertIn(APP_VERSION, self.window.windowTitle())

    def test_update_action_opens_dialog_without_changing_feedback_route(self):
        """两项菜单各自调用更新对话框和原反馈对话框。"""
        with patch("gui.main_window.UpdateDialog") as update_class:
            self.window.check_update_action.trigger()
        update_class.assert_called_once_with(self.window)
        update_class.return_value.exec_.assert_called_once_with()
        with patch("gui.main_window.FeedbackDialog") as feedback_class:
            self.window.feedback_action.trigger()
        feedback_class.return_value.exec_.assert_called_once_with()


class UpdateDialogTests(unittest.TestCase):
    """下载可以自动进行，但替换软件必须经用户确认且更新器就绪。"""

    def setUp(self):
        """关闭自动联网，通过信号处理入口模拟更新流程。"""
        self.dialog = UpdateDialog(start_immediately=False)
        self.addCleanup(self.dialog.close)
        self.release = Mock(version="1.58.0", notes="修复协议问题")

    def prepared(self):
        """创建带所有权标记的轻量暂存目录供界面清理测试使用。"""
        staging = create_staging_directory()
        self.addCleanup(discard_staging_directory, staging)
        return PreparedUpdate(self.release, staging, staging / "unpacked")

    def test_found_release_automatically_queues_download_after_check_worker_finishes(self):
        """发现新版本后无需再次点击下载，不会同时启动两个后台线程。"""
        worker = Mock()
        self.dialog._worker = worker
        self.dialog._on_release_found(self.release)
        with patch.object(self.dialog, "_start_worker") as start_worker:
            start_worker.assert_not_called()
            self.dialog._on_worker_finished()
        start_worker.assert_called_once_with(self.release)
        worker.deleteLater.assert_called_once_with()
        self.assertEqual(self.dialog.notes_text.toPlainText(), "修复协议问题")

    def test_no_update_does_not_download(self):
        """没有更新时不发起附件下载。"""
        self.dialog._on_release_found(None)
        with patch.object(self.dialog, "_start_worker") as start_worker:
            self.dialog._on_worker_finished()
        start_worker.assert_not_called()
        self.assertIn("最新版本", self.dialog.status_label.text())

    def test_ready_package_waits_for_explicit_confirmation(self):
        """下载校验完成不会立即退出或启动更新器，用户拒绝后可继续使用。"""
        ready = self.prepared()
        with patch("gui.update_dialog.can_install_update", return_value=True):
            with patch("gui.update_dialog.launch_update_helper") as launch:
                self.dialog._on_package_ready(ready)
                self.dialog._refresh_buttons()
                self.assertTrue(self.dialog.install_btn.isEnabled())
                launch.assert_not_called()
                with patch.object(QMessageBox, "question", return_value=QMessageBox.No):
                    self.dialog.install_update()
                launch.assert_not_called()

    def test_main_program_exits_only_after_updater_ready_handshake(self):
        """用户确认后仍需更新器就绪，不能在复制和校验尚未完成时退出。"""
        self.dialog._prepared = self.prepared()
        handoff = Mock()
        handoff.process.poll.return_value = None
        handoff.status.return_value = None
        ready_signal = Mock()
        self.dialog.ready_to_restart.connect(ready_signal)
        with patch("gui.update_dialog.can_install_update", return_value=True):
            with patch.object(QMessageBox, "question", return_value=QMessageBox.Yes):
                with patch("gui.update_dialog.launch_update_helper", return_value=handoff):
                    self.dialog.install_update()
        self.dialog._poll_handoff()
        ready_signal.assert_not_called()
        handoff.status.return_value = {"status": "ready"}
        self.dialog._poll_handoff()
        ready_signal.assert_called_once_with()
        self.assertTrue(self.dialog._handed_off)

    def test_updater_error_does_not_exit_main_program(self):
        """更新器预检失败时保留主程序和已下载包，允许重试。"""
        ready = self.prepared()
        self.dialog._prepared = ready
        handoff = Mock()
        handoff.status.return_value = {"status": "error", "message": "没有写权限"}
        handoff.process.poll.return_value = 1
        self.dialog._handoff = handoff
        ready_signal = Mock()
        self.dialog.ready_to_restart.connect(ready_signal)
        self.dialog._poll_handoff()
        ready_signal.assert_not_called()
        self.assertIsNone(self.dialog._handoff)
        self.assertIn("没有写权限", self.dialog.status_label.text())
        self.assertTrue(ready.staging.exists())

    def test_dead_updater_with_stale_ready_status_cannot_close_main_program(self):
        """即使曾写入就绪标记，更新器异常退出后也不能关闭主程序。"""
        self.dialog._prepared = self.prepared()
        handoff = Mock()
        handoff.status.return_value = {"status": "ready"}
        handoff.process.poll.return_value = 1
        self.dialog._handoff = handoff
        ready_signal = Mock()
        self.dialog.ready_to_restart.connect(ready_signal)
        self.dialog._poll_handoff()
        ready_signal.assert_not_called()
        self.assertIsNone(self.dialog._handoff)

    def test_closing_busy_dialog_requests_cancel_before_destroying_thread(self):
        """关闭下载窗口必须等后台线程结束，避免线程运行中被销毁。"""
        worker = Mock()
        self.dialog._worker = worker
        self.dialog.reject()
        worker.requestInterruption.assert_called_once_with()
        self.assertTrue(self.dialog._closing)
        self.dialog._on_worker_finished()
        self.assertIsNone(self.dialog._worker)

    def test_source_mode_cannot_replace_python_or_source_tree(self):
        """源码运行的检测入口不会开放程序自替换。"""
        self.dialog._prepared = self.prepared()
        with patch("gui.update_dialog.can_install_update", return_value=False):
            with patch("gui.update_dialog.launch_update_helper") as launch:
                self.dialog._refresh_buttons()
                self.assertFalse(self.dialog.install_btn.isEnabled())
                self.dialog.install_update()
                launch.assert_not_called()

    def test_cancel_race_cleans_package_returned_by_finishing_worker(self):
        """用户取消与下载完成相邻发生时，返回的更新包也必须被清理。"""
        worker = Mock()
        self.dialog._worker = worker
        self.dialog.reject()
        ready = self.prepared()
        self.dialog._on_package_ready(ready)
        self.assertTrue(ready.staging.exists())
        self.dialog._on_worker_finished()
        self.assertFalse(ready.staging.exists())

    def test_cancel_install_waits_until_helper_exits_before_cleanup(self):
        """独立更新器尚在准备时只写取消标记，待它退出后再清理包。"""
        ready = self.prepared()
        self.dialog._prepared = ready
        handoff = Mock(staging=ready.staging)
        handoff.process.poll.return_value = None
        handoff.status.return_value = None
        self.dialog._handoff = handoff
        self.dialog.reject()
        self.assertTrue((ready.staging / "cancel.request").exists())
        self.assertTrue(ready.staging.exists())
        handoff.process.poll.return_value = 1
        handoff.status.return_value = {"status": "error", "message": "已取消安装"}
        self.dialog._poll_handoff()
        self.assertFalse(ready.staging.exists())

    def test_worker_cancel_after_preparation_cleans_without_emitting_ready(self):
        """后台完成校验后若收到取消，不把更新包交给界面或安装器。"""
        ready = self.prepared()
        worker = UpdateWorker(self.release)
        ready_signal = Mock()
        cancelled_signal = Mock()
        worker.package_ready.connect(ready_signal)
        worker.cancelled.connect(cancelled_signal)
        with patch("gui.update_dialog.prepare_update", return_value=ready):
            with patch.object(worker, "isInterruptionRequested", side_effect=[False, True]):
                worker.run()
        ready_signal.assert_not_called()
        cancelled_signal.assert_called_once_with()
        self.assertFalse(ready.staging.exists())


if __name__ == "__main__":
    unittest.main()
