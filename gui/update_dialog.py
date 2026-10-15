#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""手动检测后自动下载，下载校验完成后由用户确认升级的更新界面。"""

from PyQt5.QtCore import QThread, QTimer, Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QMessageBox, QProgressBar, QPushButton,
    QTextEdit, QVBoxLayout,
)

from app_info import APP_VERSION
from updating.controller import can_install_update, launch_update_helper, prepare_update
from updating.package import discard_staging_directory
from updating.releases import UpdateCancelled, UpdateError, check_cancelled, fetch_latest_release


class UpdateWorker(QThread):
    """网络、解压和摘要校验在后台执行，避免阻塞串口循环和界面。"""

    release_found = pyqtSignal(object)
    package_ready = pyqtSignal(object)
    progress = pyqtSignal(int, int)
    failed = pyqtSignal(str)
    cancelled = pyqtSignal()

    def __init__(self, release=None, parent=None):
        """未指定发行版时检测更新，指定后下载并准备完整更新包。"""
        super().__init__(parent)
        self.release = release

    def run(self):
        """执行后台任务，取消或异常时不会把未校验的包交给界面。"""
        prepared = None
        try:
            check_cancelled(self.isInterruptionRequested)
            if self.release is None:
                release = fetch_latest_release()
                check_cancelled(self.isInterruptionRequested)
                self.release_found.emit(release)
            else:
                prepared = prepare_update(
                    self.release, self.progress.emit, self.isInterruptionRequested
                )
                check_cancelled(self.isInterruptionRequested)
                self.package_ready.emit(prepared)
                prepared = None
        except UpdateCancelled:
            self.cancelled.emit()
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            if prepared is not None:
                try:
                    discard_staging_directory(prepared.staging)
                except (OSError, UpdateError) as exc:
                    self.failed.emit(f"暂存文件未能完全清理：{exc}")


class UpdateDialog(QDialog):
    """显示版本、说明和下载进度；只有用户确认且更新器就绪后才退出主程序。"""

    ready_to_restart = pyqtSignal()

    def __init__(self, parent=None, start_immediately=True):
        """创建更新对话框，检测动作只由用户点击菜单触发。"""
        super().__init__(parent)
        self.setWindowTitle("检测软件更新")
        self.resize(580, 420)
        self._worker = None
        self._release = None
        self._prepared = None
        self._pending_download = None
        self._handoff = None
        self._handed_off = False
        self._closing = False
        layout = QVBoxLayout(self)
        self.version_label = QLabel(f"当前软件版本：V{APP_VERSION}")
        self.status_label = QLabel("准备检测 GitHub 最新稳定版…")
        self.status_label.setTextFormat(Qt.PlainText)
        self.status_label.setWordWrap(True)
        self.notes_text = QTextEdit()
        self.notes_text.setReadOnly(True)
        self.notes_text.setAcceptRichText(False)
        self.notes_text.setPlaceholderText("新版本的更新说明会显示在这里")
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.version_label)
        layout.addWidget(self.status_label)
        layout.addWidget(self.notes_text, 1)
        layout.addWidget(self.progress_bar)
        buttons = QHBoxLayout()
        self.check_btn = QPushButton("重新检测")
        self.install_btn = QPushButton("升级并重启")
        self.close_btn = QPushButton("关闭")
        self.install_btn.setEnabled(False)
        self.check_btn.clicked.connect(self.start_check)
        self.install_btn.clicked.connect(self.install_update)
        self.close_btn.clicked.connect(self.reject)
        buttons.addWidget(self.check_btn)
        buttons.addStretch()
        buttons.addWidget(self.install_btn)
        buttons.addWidget(self.close_btn)
        layout.addLayout(buttons)
        self.handoff_timer = QTimer(self)
        self.handoff_timer.setInterval(100)
        self.handoff_timer.timeout.connect(self._poll_handoff)
        if start_immediately:
            QTimer.singleShot(0, self.start_check)

    def _refresh_buttons(self):
        """根据后台任务和更新器状态更新操作按钮。"""
        busy = self._worker is not None or self._handoff is not None
        self.check_btn.setEnabled(not busy)
        self.install_btn.setEnabled(
            not busy and self._prepared is not None and can_install_update()
        )
        self.close_btn.setText("取消" if busy else "关闭")
        self.close_btn.setEnabled(not self._closing)

    def _start_worker(self, release=None):
        """启动一个后台任务，并保持线程对象存活直到任务结束。"""
        worker = UpdateWorker(release, self)
        self._worker = worker
        worker.release_found.connect(self._on_release_found)
        worker.package_ready.connect(self._on_package_ready)
        worker.progress.connect(self._on_progress)
        worker.failed.connect(self._on_failure)
        worker.cancelled.connect(self._on_cancelled)
        worker.finished.connect(self._on_worker_finished)
        self._refresh_buttons()
        worker.start()

    def _discard_prepared(self):
        """关闭界面或重新检测时清理已下载但尚未交接的更新包。"""
        if self._prepared is not None:
            try:
                discard_staging_directory(self._prepared.staging)
            except (OSError, UpdateError) as exc:
                # 临时文件被系统占用时不能让关闭窗口的 Qt 槽函数异常退出。
                self.status_label.setText(f"暂存文件未能完全清理，可稍后清理临时目录：{exc}")
            self._prepared = None

    def start_check(self):
        """由用户主动检测，不在软件启动时静默联网。"""
        if self._closing or self._worker is not None or self._handoff is not None:
            return
        self._discard_prepared()
        self._release = None
        self.notes_text.clear()
        self.progress_bar.setRange(0, 0)
        self.status_label.setText("正在检测 GitHub 最新稳定版…")
        self._start_worker()

    def _on_release_found(self, release):
        """发现新版后自动排队下载，无新版时明确提示。"""
        self._release = release
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        if release is None:
            self.status_label.setText("当前已是最新版本，暂无可用更新。")
            return
        self.version_label.setText(
            f"当前版本：V{APP_VERSION}    最新版本：V{release.version}"
        )
        self.notes_text.setPlainText(release.notes)
        self.status_label.setText(f"发现新版本 V{release.version}，正在准备自动下载…")
        self._pending_download = release

    def _on_progress(self, received, total):
        """显示下载进度，下载完后继续校验而不是提前开放安装。"""
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(int(received * 100 / total) if total else 0)
        if received == total:
            self.status_label.setText("下载完成，正在解压并校验完整程序文件…")
        else:
            self.status_label.setText(
                f"正在下载：{received / 1048576:.1f} / {total / 1048576:.1f} MB"
            )

    def _on_package_ready(self, prepared):
        """校验全部通过后提示用户确认升级，保留取消和稍后升级的选择。"""
        self._prepared = prepared
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        if can_install_update():
            self.status_label.setText("新版已下载并通过完整性校验。点击“升级并重启”安装。")
        else:
            self.status_label.setText("新版已下载。源码运行不支持自替换，请使用正式发布包升级。")

    def _on_failure(self, message):
        """显示可重试的错误，不因网络错误关闭主程序。"""
        self.progress_bar.setRange(0, 100)
        self.status_label.setText(f"更新未完成：{message}")

    def _on_cancelled(self):
        """取消仅终止本次更新任务，主程序继续运行。"""
        self.status_label.setText("已取消更新。")

    def _on_worker_finished(self):
        """检测完成后自动下载；取消时等后台退出后再销毁界面。"""
        worker = self._worker
        self._worker = None
        if worker is not None:
            worker.deleteLater()
        if self._closing:
            self._pending_download = None
            self.reject()
            return
        if self._pending_download is not None:
            release = self._pending_download
            self._pending_download = None
            self._start_worker(release)
            return
        self._refresh_buttons()

    def install_update(self):
        """用户确认后启动独立更新器，仍等待就绪握手才退出原程序。"""
        if self._prepared is None or self._worker is not None or self._handoff is not None:
            return
        if not can_install_update():
            return
        answer = QMessageBox.question(
            self, "确认升级并重启",
            "升级将停止发送、关闭串口并退出软件。\n"
            "请先导出需要保留的自定义包组。激活信息会保留。\n\n是否现在升级并重启？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        try:
            self._handoff = launch_update_helper(self._prepared)
        except Exception as exc:
            self._on_failure(str(exc))
            return
        self.status_label.setText("正在准备安装和旧版备份，请稍候…")
        self._refresh_buttons()
        self.handoff_timer.start()

    def _poll_handoff(self):
        """只有独立更新器完成预检后才退出主程序，预检失败可以继续使用原版。"""
        if self._handoff is None:
            return
        try:
            status = self._handoff.status()
            exited = self._handoff.process.poll() is not None
            if status and status.get("status") == "ready" and not self._closing and not exited:
                self.handoff_timer.stop()
                self._handed_off = True
                self._prepared = None
                self._handoff = None
                self.accept()
                self.ready_to_restart.emit()
                return
            if exited:
                self.handoff_timer.stop()
                self._handoff = None
                message = (status or {}).get("message") or "独立更新器未能就绪，请重试"
                self._on_failure(message)
                if self._closing:
                    self.reject()
                else:
                    self._refresh_buttons()
        except Exception as exc:
            self._on_failure(str(exc))
            if self._handoff is not None and self._handoff.process.poll() is not None:
                self.handoff_timer.stop()
                self._handoff = None
                if self._closing:
                    self.reject()
                else:
                    self._refresh_buttons()

    def reject(self):
        """后台工作时先请求取消，禁止在线程或更新器仍使用暂存文件时删除它们。"""
        if self._worker is not None:
            self._closing = True
            self._worker.requestInterruption()
            self.status_label.setText("正在取消，请稍候…")
            self._refresh_buttons()
            return
        if self._handoff is not None and self._handoff.process.poll() is None:
            self._closing = True
            (self._handoff.staging / "cancel.request").write_text("cancel", encoding="ascii")
            self.status_label.setText("正在取消安装准备，请稍候…")
            self._refresh_buttons()
            return
        self.handoff_timer.stop()
        if not self._handed_off:
            self._discard_prepared()
        super().reject()

    def closeEvent(self, event):
        """窗口关闭按钮遵循相同取消流程，避免销毁正在运行的后台线程。"""
        if self._handed_off:
            event.accept()
            return
        if self._worker is not None or self._handoff is not None:
            self.reject()
            event.ignore()
            return
        if not self._handed_off:
            self._discard_prepared()
        event.accept()
