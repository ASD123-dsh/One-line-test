#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""配置、脱敏诊断和界面恢复测试；隔离存储，不写入客户用户目录。"""

import json
import os
import unittest
from dataclasses import asdict
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication

from app_info import APP_ID
from app_settings import SettingsStore, read_config, validate_config, write_config
from diagnostics import diagnostic_report
from gui.main_window import MainWindow
from gui.protocol_ui_registry import PROTOCOL_UI_SPECS
from protocol.definitions import PROTOCOL_BATTERY_SINGLE_WIRE, PROTOCOL_DEFINITIONS, PROTOCOL_XINRI
from protocol.protocol_handler import PresetScenarios
from serial_comm.serial_manager import SerialPortDetector

_APP = QApplication.instance() or QApplication([])


def sample_config():
    """提供独立的合法电池配置，保持 00 帧头和 500ms 默认值。"""
    return {"schema": 1, "app_id": APP_ID, "remember": False,
            "protocol": PROTOCOL_BATTERY_SINGLE_WIRE, "baud_rate": 9600,
            "tosc_us": 100, "interval_ms": 500, "scenario_id": 3,
            "status": asdict(PresetScenarios.battery_single_wire_normal_running()),
            "custom_frame": None, "packet_sequences": {}}


class SettingsTests(unittest.TestCase):
    """文件校验和独立数据结构保护。"""

    def test_round_trip_and_memory_copy_are_independent(self):
        """文件及内存模式都保留数据，调用方不能修改内部存储。"""
        store = SettingsStore()
        data = sample_config()
        store.save(data)
        restored = store.load()
        restored["status"]["soc_percent"] = 1
        self.assertEqual(store.load()["status"]["soc_percent"], 80)
        with TemporaryDirectory() as temporary:
            path = Path(temporary) / "settings.json"
            write_config(path, data)
            self.assertEqual(read_config(path), validate_config(data))
            self.assertEqual(list(Path(temporary).glob("*.tmp")), [])

    def test_bad_config_does_not_overwrite_existing_file(self):
        """非法导出在替换前失败，原始客户配置仍保持不变。"""
        with TemporaryDirectory() as temporary:
            path = Path(temporary) / "settings.json"
            write_config(path, sample_config())
            before = path.read_bytes()
            invalid = sample_config()
            invalid["status"]["soc_percent"] = 101
            with self.assertRaises(ValueError):
                write_config(path, invalid)
            self.assertEqual(path.read_bytes(), before)

    def test_unknown_boolean_nan_and_invalid_intervals_are_rejected(self):
        """导入文件不能绕过协议校验、字段白名单或数值类型约束。"""
        mutations = (("protocol", "unknown"), ("baud_rate", True), ("interval_ms", 9), ("scenario_id", 5), ("extra", 1))
        for key, value in mutations:
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_config(dict(sample_config(), **{key: value}))
        for value in (True, float("nan"), float("inf")):
            data = sample_config()
            data["status"]["current_a"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_config(data)

    def test_float_annotation_accepts_fractional_current(self):
        """不能因为原默认值是整数 0 就错误拒绝新日的 0.2A 精度字段。"""
        data = sample_config()
        data["protocol"] = PROTOCOL_XINRI
        state = PresetScenarios.xinri_normal_running()
        state.current_a = 10.2
        data["status"] = asdict(state)
        self.assertEqual(validate_config(data)["status"]["current_a"], 10.2)

    def test_custom_frame_and_packet_groups_are_checked(self):
        """自定义帧和包组仍走原公共校验，不放宽长度或布尔字节。"""
        data = sample_config()
        data.update(scenario_id=4, custom_frame=[0, 50, 5, 6, 7, 68])
        data["packet_sequences"] = {PROTOCOL_BATTERY_SINGLE_WIRE: [[0, 50, 1, 1, 1, 53]]}
        self.assertEqual(validate_config(data)["custom_frame"], data["custom_frame"])
        data["custom_frame"][2] = True
        with self.assertRaises(ValueError):
            validate_config(data)

    def test_oversized_or_deeply_nested_json_is_rejected(self):
        """异常大文件或深嵌套 JSON 给出普通错误，不令 Qt 导入槽异常退出。"""
        with TemporaryDirectory() as temporary:
            path = Path(temporary) / "bad.json"
            for raw in (b"x" * (1024 * 1024 + 1), b"[" * 2000 + b"0" + b"]" * 2000):
                path.write_bytes(raw)
                with self.assertRaises(ValueError):
                    read_config(path)

    def test_diagnostics_uses_explicit_privacy_whitelist(self):
        """即使状态混入路径或授权等敏感字段，导出也不透传。"""
        report = diagnostic_report(PROTOCOL_BATTERY_SINGLE_WIRE, {
            "port_name": "sensitive-port", "machine_id": "secret-id", "license": "private-key",
            "statistics": {"sent_frames": 3, "customer_path": "C:/private"},
        }, "C:/private/update-error")
        text = json.dumps(report)
        for secret in ("sensitive-port", "secret-id", "private-key", "C:/private", "customer_path"):
            self.assertNotIn(secret, text)
        self.assertTrue(report["incomplete_update_detected"])
        self.assertEqual(report["statistics"]["sent_frames"], 3)


class SettingsWindowTests(unittest.TestCase):
    """每种协议使用真实配置页恢复，始终保持未连接且未发送。"""

    def setUp(self):
        """使用内存存储并禁止真实端口扫描。"""
        detector = patch.object(SerialPortDetector, "start_detection")
        detector.start()
        self.addCleanup(detector.stop)
        self.window = MainWindow(settings_store=SettingsStore())
        self.addCleanup(self.window.close)

    def test_all_protocol_configuration_round_trips(self):
        """18 个协议的正常、数据自定义、全部自定义模式恢复后帧保持一致。"""
        for protocol in PROTOCOL_DEFINITIONS:
            with self.subTest(protocol=protocol):
                self.window.on_protocol_changed(protocol)
                for scenario in (0, 3, 4):
                    self.window.scenario_group.button(scenario).click()
                    data = self.window.capture_configuration()
                    state = self.window.get_current_status_from_ui()
                    before = self.window.generate_protocol_frame_for_preview(state)
                    self.window.apply_configuration(data)
                    after = self.window.generate_protocol_frame_for_preview(self.window.get_current_status_from_ui())
                    self.assertEqual(before, after)
                    self.assertFalse(self.window.serial_manager.is_connected)
                    self.assertFalse(self.window.serial_manager.is_cyclic_sending())
                _APP.processEvents()

    def test_invalid_import_does_not_change_current_selection(self):
        """完整校验在界面变更前执行。"""
        before = self.window.current_protocol
        data = sample_config()
        data["baud_rate"] = -1
        with self.assertRaises(ValueError):
            self.window.apply_configuration(data)
        self.assertEqual(self.window.current_protocol, before)

    def test_remember_is_opt_in_and_does_not_change_fresh_default(self):
        """未开启记忆不保存，初次启动默认 500ms；开启后恢复仍不自动发送。"""
        self.assertFalse(self.window.remember_settings_action.isChecked())
        self.assertEqual(self.window.interval_spin.value(), 500)
        self.window.save_remembered_configuration()
        self.assertIsNone(self.window.settings_store.load())
        self.window.interval_spin.setValue(10)
        self.window.remember_settings_action.setChecked(True)
        self.window.save_remembered_configuration()
        restored = MainWindow(settings_store=self.window.settings_store)
        self.addCleanup(restored.close)
        self.assertEqual(restored.interval_spin.value(), 10)
        self.assertFalse(restored.serial_manager.is_connected)

    def test_each_registered_writer_exists(self):
        """新增协议必须同时登记可调用的状态恢复入口。"""
        for spec in PROTOCOL_UI_SPECS.values():
            self.assertTrue(callable(getattr(self.window, spec.status_writer)))


if __name__ == "__main__":
    unittest.main()
