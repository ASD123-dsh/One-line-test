#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""UART 线速估算与发送统计；估算不能代替转码硬件的实际时序验证。"""

import time


def uart_frame_time_ms(frame_length, baud_rate):
    """按现有 8N1 配置计算理论线速耗时，拒绝无效帧长和波特率。"""
    for value in (frame_length, baud_rate):
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError("帧长度和波特率必须是正整数")
    return frame_length * 10 * 1000.0 / baud_rate


class SendStatistics:
    """统计实际写入、缓冲限流和调度延迟，不把定时器次数当作成功发送。"""

    def __init__(self):
        """建立一次运行的空统计。"""
        self.reset()

    def reset(self):
        """在开始新的循环时重置，使用单调时钟避免系统校时影响。"""
        self.sent_frames = 0
        self.deferred_ticks = 0
        self.backpressure_events = 0
        self.errors = 0
        self.queue_bytes = 0
        self.write_ms = 0.0
        self.actual_interval_ms = None
        self._last_started = None

    def record(self, result):
        """只记录真实 I/O 结果，缓冲过载但未写入的帧不计成功。"""
        self.queue_bytes = result.get("queue_bytes", 0)
        self.write_ms = result.get("write_ms", 0.0)
        if result.get("throttled"):
            self.backpressure_events += 1
        elif result.get("success"):
            started = result.get("started", time.monotonic())
            if self._last_started is not None:
                self.actual_interval_ms = (started - self._last_started) * 1000.0
            self._last_started = started
            self.sent_frames += 1
        elif not result.get("cancelled"):
            self.errors += 1

    def snapshot(self):
        """返回独立、可导出且不包含串口身份或授权信息的统计快照。"""
        return {key: value for key, value in vars(self).items() if not key.startswith("_")}
