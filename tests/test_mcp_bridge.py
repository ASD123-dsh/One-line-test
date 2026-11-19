#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""可选官方SDK的真实STDIO＋HTTP＋Qt＋假串口端到端回归，不调用任何大模型。"""

import json
import os
from pathlib import Path
from queue import Empty, Queue
import subprocess
from tempfile import TemporaryDirectory
import threading
import time
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication

from app_settings import SettingsStore
from gui.ai_controller import AiController
from gui.main_window import MainWindow
from serial_comm.serial_manager import SerialManager, SerialPortDetector, SerialPortInfo

ROOT = Path(__file__).resolve().parents[1]
SDK_PYTHON = ROOT / ".venv-mcp/Scripts/python.exe"
_APP = QApplication.instance() or QApplication([])


@unittest.skipUnless(os.name == "nt" and SDK_PYTHON.is_file(), "可选MCP端到端验证需Windows及独立.venv-mcp环境")
class McpBridgeTests(unittest.TestCase):
    """原依赖的Qt宿主与独立SDK连接器分进程运行，模拟当前用户的真实DPAPI连接发现。"""

    def test_native_dpapi_and_real_stdio_for_legacy_and_current_protocols(self):
        """验证双协议工具发现、只读拒绝、动态循环、公有/原始帧和有界扫描步骤。"""
        with TemporaryDirectory() as directory, patch.object(SerialPortDetector, "start_detection"), \
                patch.object(SerialManager, "scan_ports", return_value=[SerialPortInfo("COM9", "Synthetic test device", "not-exposed")]), \
                patch.object(MainWindow, "refresh_recovery_notice"):
            license_service = Mock()
            license_service.is_activated.return_value = True
            window = MainWindow(activation_service=license_service, settings_store=SettingsStore())
            window.history_update_timer.stop()
            self.addCleanup(window.close)
            connection = Path(directory) / "connection.json"
            controller = AiController(window, connection)
            window.ai_controller = controller
            controller.connection_requested.connect(window._show_ai_connection_request)
            controller.state_changed.connect(window._refresh_ai_connection_badge)
            port = Mock()
            port.port, port.baudrate, port.out_waiting, port.is_open = "COM9", 115200, 0, True
            written = []
            port.write.side_effect = lambda data: written.append(bytes(data)) or len(data)
            controller.listen_for_requests()
            self.assertNotIn(controller.server.server.token, connection.read_text(encoding="utf-8"))
            with patch("serial_comm.serial_manager.serial.Serial", return_value=port):
                process = subprocess.Popen([str(SDK_PYTHON), "-B", "-X", "utf8", str(ROOT / "tests/mcp_client_probe.py"),
                                            "--connection-file", str(connection), "--server", str(ROOT / "tools/mcp_server.py")],
                                           cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
                queue = Queue()
                def collect(stream, kind):
                    """持续排空子进程输出，避免错误日志堵住协议或测试退出。"""
                    for line in stream:
                        queue.put((kind, line))
                readers = [threading.Thread(target=collect, args=(process.stdout, "out"), daemon=True), threading.Thread(target=collect, args=(process.stderr, "err"), daemon=True)]
                for thread in readers:
                    thread.start()
                completed, errors = None, []
                deadline = time.monotonic() + 40
                try:
                    while process.poll() is None and time.monotonic() < deadline:
                        QTest.qWait(5)
                        while True:
                            try:
                                kind, line = queue.get_nowait()
                            except Empty:
                                break
                            if kind == "err":
                                errors.append(line)
                                continue
                            event = json.loads(line)
                            if event.get("event") == "awaiting_test_decision":
                                self.assertIsNotNone(window.ai_connection_dialog)
                                self.assertEqual(window.ai_connection_dialog.request_id, event["request_id"])
                                window.ai_connection_dialog.read_only_button.click()
                            elif event.get("event") == "awaiting_test_grant":
                                controller.grant_writes()
                            elif event.get("event") == "completed":
                                completed = event
                    self.assertIsNotNone(process.poll(), "STDIO端到端检查超时")
                    for thread in readers:
                        thread.join(timeout=1)
                    while not queue.empty():
                        kind, line = queue.get_nowait()
                        if kind == "err":
                            errors.append(line)
                        elif json.loads(line).get("event") == "completed":
                            completed = json.loads(line)
                    self.assertEqual(process.returncode, 0, "".join(errors)[-8000:])
                    self.assertIsNotNone(completed)
                    self.assertEqual([item["mode"] for item in completed["checks"]], ["legacy", "auto"])
                    self.assertTrue(written)
                finally:
                    if process.poll() is None:
                        process.terminate()
                        process.wait(timeout=5)
                    process.stdout.close()
                    process.stderr.close()
                    window.close()
            self.assertFalse(connection.exists())
