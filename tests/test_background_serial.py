#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""后台串口发送回归测试：使用可控假串口，不访问真实 COM 设备。"""

import os
import threading
import time
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QTimer
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication

from serial_comm.serial_manager import SerialManager
from serial_comm.timing import uart_frame_time_ms

_APP = QApplication.instance() or QApplication([])


class ControlledPort:
    """可阻塞、可失败的假串口，记录写线程和完整帧快照。"""

    def __init__(self):
        """创建已连接串口，默认立即写入。"""
        self.port = "TEST-PORT"
        self.baudrate = 9600
        self.is_open = True
        self.out_waiting = 0
        self.break_condition = False
        self.release = threading.Event()
        self.release.set()
        self.started = threading.Event()
        self.payloads = []
        self.thread_ids = []
        self.error = None

    def write(self, payload):
        """等待测试放行，再写完整快照或抛出预设异常。"""
        self.started.set()
        self.release.wait(1.0)
        if self.error:
            raise self.error
        self.thread_ids.append(threading.get_ident())
        self.payloads.append(payload)
        return len(payload)

    def close(self):
        """仅改变假串口状态。"""
        self.is_open = False


class BackgroundSerialTests(unittest.TestCase):
    """验证动态帧、单一在途任务、断开竞态和积压保护。"""

    def setUp(self):
        """为每个测试建立独立管理器和假串口。"""
        self.port = ControlledPort()
        self.manager = SerialManager(background_send=True)
        self.manager.serial_port = self.port
        self.manager.is_connected = True
        self.addCleanup(self.cleanup_sender)

    def cleanup_sender(self):
        """先放行写入，再等待线程退出，避免测试残留后台任务。"""
        self.port.release.set()
        self.assertTrue(self.manager.shutdown())
        _APP.processEvents()

    def wait_until(self, predicate, timeout=1500):
        """使用真实 Qt 事件循环等待结果，不阻塞管理器的完成槽。"""
        deadline = time.monotonic() + timeout / 1000.0
        while not predicate() and time.monotonic() < deadline:
            QTest.qWait(5)
        self.assertTrue(predicate(), "后台发送未在限定时间内完成")

    def test_slow_write_keeps_gui_responsive_and_uses_snapshot(self):
        """慢串口不阻塞界面；提交后修改原列表不会改变在途数据。"""
        self.port.release.clear()
        frame = [1, 2, 3]
        seen = []
        QTimer.singleShot(0, lambda: seen.append(True))
        started = time.monotonic()
        self.assertEqual(self.manager.send_single_frame(frame), (True, ""))
        self.assertLess(time.monotonic() - started, 0.2)
        frame[0] = 99
        self.wait_until(lambda: bool(seen) and self.port.started.is_set())
        self.assertNotEqual(self.port.thread_ids, [threading.get_ident()])
        self.port.release.set()
        self.wait_until(lambda: self.manager.statistics.sent_frames == 1)
        self.assertEqual(self.port.payloads, [bytes([1, 2, 3])])
        self.assertNotEqual(self.port.thread_ids[0], threading.get_ident())

    def test_busy_writer_does_not_consume_dynamic_sequence(self):
        """后台忙时跳过调度，不调用生成器或积压更多帧。"""
        self.port.release.clear()
        generated = []

        def provider():
            """每调用一次相当于消耗一个协议流水号。"""
            generated.append(len(generated) + 1)
            return [generated[-1]]

        self.assertTrue(self.manager.start_cyclic_send([1], 500, frame_provider=provider)[0])
        self.manager._send_cyclic_data()
        for _ in range(10):
            self.manager._send_cyclic_data()
        self.assertEqual(generated, [1])
        self.assertEqual(self.manager.statistics.deferred_ticks, 10)
        self.port.release.set()
        self.wait_until(lambda: self.manager.statistics.sent_frames == 1)
        self.manager._send_cyclic_data()
        self.wait_until(lambda: self.manager.statistics.sent_frames == 2)
        self.assertEqual(self.port.payloads, [b"\x01", b"\x02"])

    def test_buffer_backpressure_preserves_next_packet(self):
        """积压时不写入、不跳过包组；缓冲恢复后按原顺序发送。"""
        self.port.out_waiting = 100
        self.assertTrue(self.manager.start_cyclic_send_sequence([[1], [2]], 500)[0])
        self.manager._send_cyclic_data()
        self.wait_until(lambda: self.manager.statistics.backpressure_events == 1)
        self.assertEqual(self.port.payloads, [])
        self.port.out_waiting = 0
        self.manager._send_cyclic_data()
        self.wait_until(lambda: self.manager.statistics.sent_frames == 1)
        self.manager._send_cyclic_data()
        self.wait_until(lambda: self.manager.statistics.sent_frames == 2)
        self.assertEqual(self.port.payloads, [b"\x01", b"\x02"])

    def test_disconnect_waits_for_current_write_without_blocking_gui(self):
        """断开请求先停发，当前帧完成后才关闭串口。"""
        self.port.release.clear()
        self.manager.send_single_frame([1])
        self.wait_until(self.port.started.is_set)
        self.assertFalse(self.manager.disconnect_port())
        self.assertTrue(self.port.is_open)
        self.port.release.set()
        self.wait_until(lambda: not self.manager.is_connected)
        self.assertFalse(self.port.is_open)

    def test_io_failure_stops_cycle_and_reports_once(self):
        """后台写入失败后由界面线程停止循环，错误只报告一次。"""
        self.port.error = OSError("unplugged")
        errors = []
        self.manager.send_error.connect(errors.append)
        self.manager.start_cyclic_send([1], 500)
        self.manager._send_cyclic_data()
        self.wait_until(lambda: bool(errors))
        self.assertEqual(len(errors), 1)
        self.assertFalse(self.manager.is_cyclic_sending())
        self.assertFalse(self.manager.is_connected)

    def test_wire_budget_warns_but_keeps_10ms_setting(self):
        """线速不足给提示，不偷偷改用户的最小间隔配置。"""
        warnings = []
        self.manager.timing_warning.connect(warnings.append)
        self.manager.start_cyclic_send([0] * 12, 10)
        self.manager._send_cyclic_data()
        self.wait_until(lambda: self.manager.statistics.sent_frames > 0)
        self.assertTrue(warnings)
        self.assertEqual(self.manager.send_interval_ms, 10)
        self.assertAlmostEqual(uart_frame_time_ms(12, 9600), 12.5)

    def test_wire_budget_rejects_invalid_parameters(self):
        """估算接口拒绝布尔、零、负数和非整数。"""
        for value in (True, 0, -1, 1.5, "9600"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                uart_frame_time_ms(12, value)
        # 波特率状态异常时不能让循环静默停止或从 Qt 定时器槽抛出异常。
        self.port.baudrate = True
        errors = []
        self.manager.send_error.connect(errors.append)
        self.manager.start_cyclic_send([1], 500)
        self.manager._send_cyclic_data()
        self.assertEqual(len(errors), 1)
        self.assertFalse(self.manager.is_cyclic_sending())

    def test_continuous_backpressure_stops_without_growing_queue(self):
        """持续不排空的驱动必须停发，不能无限等待或堆积旧数据。"""
        errors = []
        self.manager.send_error.connect(errors.append)
        self.port.out_waiting = 100
        self.manager.start_cyclic_send([1], 500)
        self.manager._blocked_since = time.monotonic() - 4
        self.manager._send_cyclic_data()
        self.wait_until(lambda: bool(errors))
        self.assertFalse(self.manager.is_cyclic_sending())
        self.assertEqual(self.port.payloads, [])
        self.assertIsNone(self.manager._deferred_frame)
        self.assertEqual(self.manager.statistics.errors, 1)

    def test_stopped_cycle_discards_stale_completion_signal(self):
        """停发后在途字节可能完成，但旧完成信号不污染下一次循环。"""
        seen = []
        self.manager.data_sent.connect(lambda frame, timestamp: seen.append(frame))
        self.port.release.clear()
        self.manager.start_cyclic_send([1], 500)
        self.manager._send_cyclic_data()
        self.wait_until(self.port.started.is_set)
        self.manager.stop_cyclic_send()
        self.port.release.set()
        self.wait_until(lambda: not self.manager.is_write_pending())
        self.assertEqual(seen, [])
        self.assertEqual(self.manager.statistics.sent_frames, 1)
        self.assertTrue(self.manager.start_cyclic_send([9], 500)[0])
        self.manager._send_cyclic_data()
        self.wait_until(lambda: self.manager.statistics.sent_frames == 1)
        self.assertEqual(self.port.payloads, [b"\x01", b"\x09"])
        self.assertEqual(seen, [[9]])

    def test_shutdown_timeout_does_not_close_busy_port(self):
        """窗口关闭超时时保留仍在使用的串口，禁止强杀工作线程。"""
        self.port.release.clear()
        self.manager.send_single_frame([1])
        self.wait_until(self.port.started.is_set)
        self.assertFalse(self.manager.shutdown(timeout_ms=1))
        self.assertTrue(self.port.is_open)
        self.port.release.set()
        self.wait_until(lambda: not self.manager._worker.isRunning())
        self.assertTrue(self.manager.shutdown())
        self.assertFalse(self.port.is_open)

    def test_reconnection_during_pending_write_is_rejected(self):
        """后台还持有旧串口时不能打开新串口，避免完成回调关闭错误连接。"""
        self.port.release.clear()
        self.manager.send_single_frame([1])
        self.wait_until(self.port.started.is_set)
        errors = []
        self.manager.connection_error.connect(errors.append)
        self.assertFalse(self.manager.connect_port("NEW-PORT", 9600)[0])
        self.assertTrue(errors)
        self.assertIs(self.manager.serial_port, self.port)
        self.port.release.set()

    def test_repeated_10ms_cycles_use_latest_data_on_gui_thread(self):
        """真实 Qt 事件循环下连续运行，UI 帧提供器始终留在主线程。"""
        value = [1]
        provider_threads = []

        def provider():
            """在下一次可发送周期读取最新值。"""
            provider_threads.append(threading.get_ident())
            return value.copy()

        self.manager.start_cyclic_send([1], 10, frame_provider=provider)
        self.wait_until(lambda: self.manager.statistics.sent_frames >= 10)
        value[0] = 7
        self.wait_until(lambda: self.manager.statistics.sent_frames >= 20)
        self.manager.stop_cyclic_send()
        self.assertIn(b"\x01", self.port.payloads)
        self.assertIn(b"\x07", self.port.payloads)
        self.assertTrue(all(identifier == threading.get_ident() for identifier in provider_threads))


if __name__ == "__main__":
    unittest.main()
