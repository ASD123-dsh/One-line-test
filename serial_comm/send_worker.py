#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""有界串口写入线程：只处理不可变帧快照，不读取任何界面控件。"""

from queue import Empty, Full, Queue
from threading import Lock

from PyQt5.QtCore import QThread, pyqtSignal


class SendWorker(QThread):
    """同一时刻只接受一份任务，避免慢串口导致无界任务积压。"""

    completed = pyqtSignal(object)

    def __init__(self, writer, parent=None):
        """保存纯 I/O 执行函数，线程在首次提交任务时启动。"""
        super().__init__(parent)
        self._writer = writer
        self._queue = Queue(maxsize=1)
        self._lock = Lock()
        self._busy = False
        self._closing = False

    @property
    def busy(self):
        """完成结果被界面线程接收前仍视为忙，保持单一在途任务。"""
        with self._lock:
            return self._busy

    def submit(self, job):
        """独占提交帧快照，忙或关闭时明确拒绝，不排队累积旧数据。"""
        with self._lock:
            if self._busy or self._closing:
                return False
            self._busy = True
            self._queue.put_nowait(job)
            if not self.isRunning():
                self.start()
        return True

    def acknowledge(self):
        """由界面线程确认已处理完成结果，然后才允许下一份任务。"""
        with self._lock:
            self._busy = False

    def run(self):
        """串行执行 I/O；错误作为结果传回，不操作 Qt 定时器或控件。"""
        while not self.isInterruptionRequested():
            try:
                job = self._queue.get(timeout=0.05)
            except Empty:
                continue
            if job is None:
                break
            try:
                result = self._writer(job)
            except Exception as exc:
                result = {"job": job, "success": False, "error": f"串口后台发送失败：{exc}"}
            self.completed.emit(result)

    def shutdown(self, timeout_ms=2000):
        """等待在途写入结束，不强杀线程；超时由调用方保留窗口和串口。"""
        with self._lock:
            self._closing = True
        self.requestInterruption()
        try:
            self._queue.put_nowait(None)
        except Full:
            pass
        return self.wait(timeout_ms) if self.isRunning() else True
