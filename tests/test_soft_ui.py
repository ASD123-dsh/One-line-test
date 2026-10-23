#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""柔和主题、参数页、协议搜索及只读预览回归；不访问网络或真实串口。"""

import os
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QFont, QFontDatabase, QPixmap
from PyQt5.QtTest import QSignalSpy, QTest
from PyQt5.QtWidgets import QAbstractItemView, QApplication, QScrollArea

from app_paths import resource_path
from app_settings import SettingsStore
from gui.frame_preview import FramePreview
from gui.main_window import MainWindow
from gui.protocol_selector import ProtocolSelector
from gui.soft_theme import PALETTE
from protocol.definitions import PROTOCOL_DEFINITIONS, PROTOCOL_LISHEN_BMS, PROTOCOL_RUILUN, PROTOCOL_SXSY
from serial_comm.serial_manager import SerialManager, SerialPortDetector

_APP = QApplication.instance() or QApplication([])


class FramePreviewTests(unittest.TestCase):
    """预览只接受字节快照，复制和高亮不能成为另一条编码或发送路径。"""

    def setUp(self):
        """每项使用独立视图，避免高亮比较和剪贴板状态相互污染。"""
        self.preview = FramePreview()
        self.addCleanup(self.preview.close)

    def test_preview_controls_are_read_only(self):
        """表格、十六进制和原格式均不可直接编辑。"""
        self.assertTrue(self.preview.hex_text.isReadOnly())
        self.assertTrue(self.preview.legacy_text.isReadOnly())
        self.assertEqual(self.preview.table.editTriggers(), QAbstractItemView.NoEditTriggers)
        self.assertFalse(self.preview.copy_button.isEnabled())

    def test_six_byte_snapshot_copy_and_signed_description(self):
        """原始 F6 对应十进制 246，说明仍可表达负温度，不擅自改变字节。"""
        data = [0, 50, 48, 246, 0, 88]
        self.assertTrue(self.preview.set_frame(PROTOCOL_LISHEN_BMS, data, ["", "SOC", "总压", "温度补码", "", "SUM"]))
        self.assertEqual(self.preview.table.rowCount(), 6)
        self.assertEqual(self.preview.table.item(3, 1).text(), "F6")
        self.assertEqual(self.preview.table.item(3, 2).text(), "246")
        self.assertEqual(self.preview.table.item(3, 3).text(), "温度 -10℃")
        self.assertIn("温度补码", self.preview.table.item(3, 3).toolTip())
        data[0] = 255
        self.preview.copy_button.click()
        self.assertEqual(_APP.clipboard().text(), "00 32 30 F6 00 58")

    def test_unchanged_frame_does_not_rebuild_table(self):
        """连续相同预览保留单元格对象，避免新增周期性整表重建。"""
        frame = [0, 50, 48, 25, 0, 123]
        self.preview.set_frame(PROTOCOL_LISHEN_BMS, frame, [])
        first = self.preview.table.item(0, 1)
        for _ in range(50):
            self.assertFalse(self.preview.set_frame(PROTOCOL_LISHEN_BMS, frame, []))
        self.assertIs(self.preview.table.item(0, 1), first)

    def test_highlight_only_compares_frames_of_same_protocol(self):
        """温度与校验变化单独高亮，切换到等长其他协议时不沿用比较基线。"""
        self.preview.set_frame(PROTOCOL_LISHEN_BMS, [0, 50, 48, 25, 0, 123], [])
        self.preview.set_frame(PROTOCOL_LISHEN_BMS, [0, 50, 48, 246, 0, 88], [])
        self.assertEqual(self.preview.table.item(3, 1).background().color(), QColor(PALETTE["changed_row"]))
        self.assertEqual(self.preview.table.item(5, 1).background().color(), QColor(PALETTE["changed_row"]))
        self.assertEqual(self.preview.table.item(0, 1).background().color().alpha(), 0)
        self.preview.set_frame("另一个协议", [0, 50, 1, 1, 1, 53], [])
        self.assertEqual(self.preview.table.item(3, 1).background().color().alpha(), 0)

    def test_invalid_snapshot_clears_stale_data_and_copy(self):
        """无效预览不保留旧表格、旧原始文本或可用复制按钮。"""
        self.preview.set_frame(PROTOCOL_LISHEN_BMS, [0, 50, 48, 25, 0, 123], [])
        self.preview.legacy_text.setPlainText("旧数据")
        self.assertFalse(self.preview.set_frame(PROTOCOL_LISHEN_BMS, [0, True], []))
        self.assertEqual(self.preview.table.rowCount(), 0)
        self.assertEqual(self.preview.hex_text.text(), "")
        self.assertFalse(self.preview.copy_button.isEnabled())
        self.assertNotEqual(self.preview.legacy_text.toPlainText(), "旧数据")

    def test_theme_indicators_load_as_real_svg_resources(self):
        """复选和单选标记是有效资源，不把填充方块误当成勾选状态。"""
        for name in ("check.svg", "radio.svg", "chevron-down.svg", "chevron-up.svg"):
            with self.subTest(name=name):
                self.assertFalse(QPixmap(resource_path("img", "ui", name)).isNull())


class ProtocolSearchTests(unittest.TestCase):
    """搜索与合法协议选择解耦，键入、无结果和取消都不切换协议。"""

    def setUp(self):
        """使用全部注册项，不添加任何可发送的伪协议。"""
        self.combo = ProtocolSelector()
        self.combo.addItems(list(PROTOCOL_DEFINITIONS))
        self.combo.resize(360, 32)
        self.combo.show()
        self.addCleanup(self.combo.close)
        self.addCleanup(self.combo.hidePopup)

    def test_search_does_not_change_protocol_until_result_committed(self):
        """输入关键字只过滤弹层，明确选中结果后只发出一次切换信号。"""
        signal = QSignalSpy(self.combo.currentTextChanged)
        self.combo.showPopup()
        self.combo._search.setText("锂神")
        self.assertEqual(self.combo.currentText(), PROTOCOL_RUILUN)
        self.assertEqual(len(signal), 0)
        visible = [self.combo._results.item(row) for row in range(self.combo._results.count())
                   if not self.combo._results.item(row).isHidden()]
        self.assertEqual([item.text() for item in visible], [PROTOCOL_LISHEN_BMS])
        self.combo._commit_selection()
        self.assertEqual(self.combo.currentText(), PROTOCOL_LISHEN_BMS)
        self.assertEqual(len(signal), 1)
        self.assertFalse(self.combo._popup.isVisible())

    def test_no_result_and_cancel_keep_original_selection(self):
        """未找到结果时回车不能回退到第一种协议，取消也不变更状态。"""
        self.combo.setCurrentText(PROTOCOL_LISHEN_BMS)
        signal = QSignalSpy(self.combo.currentTextChanged)
        self.combo.showPopup()
        self.combo._search.setText("不存在的协议")
        self.combo._search.returnPressed.emit()
        self.assertIn("未找到", self.combo._result_hint.text())
        self.combo.hidePopup()
        self.assertEqual(self.combo.currentText(), PROTOCOL_LISHEN_BMS)
        self.assertEqual(len(signal), 0)

    def test_programmatic_selection_keeps_standard_combo_contract(self):
        """配置恢复和已有测试继续使用 setCurrentText 与原信号。"""
        signal = QSignalSpy(self.combo.currentTextChanged)
        self.combo.setCurrentText(PROTOCOL_SXSY)
        self.assertEqual(self.combo.currentText(), PROTOCOL_SXSY)
        self.assertEqual(len(signal), 1)

    def test_changed_or_hidden_search_result_is_not_committed(self):
        """弹层数据不再对应注册项时拒绝提交，不产生未知协议。"""
        self.combo.showPopup()
        item = self.combo._results.item(0)
        item.setData(Qt.UserRole, -1)
        self.combo._commit_selection(item)
        self.assertEqual(self.combo.currentText(), PROTOCOL_RUILUN)
        self.assertTrue(self.combo._popup.isVisible())


class SoftWindowTests(unittest.TestCase):
    """主窗口新视图与原协议、配置和发送入口保持同一数据来源。"""

    def setUp(self):
        """隔离端口扫描和本机配置，不启动真实网络或串口。"""
        for target, name, value in ((SerialPortDetector, "start_detection", None), (SerialManager, "scan_ports", [])):
            stub = patch.object(target, name, return_value=value)
            stub.start()
            self.addCleanup(stub.stop)
        self.window = MainWindow(settings_store=SettingsStore())
        self.window.history_update_timer.stop()
        self.addCleanup(self.window.close)

    def test_presets_can_be_browsed_without_editing_parameters(self):
        """预设页可切换浏览，但输入仍被父页禁用，不改变预设数据。"""
        window = self.window
        state = window.capture_configuration()
        self.assertTrue(window.status_tabs.isEnabled())
        self.assertEqual(window.parameter_mode_label.text(), "预设预览")
        self.assertFalse(window.distance_mode_cb.isEnabled())
        self.assertIsInstance(window.status_tabs.widget(0), QScrollArea)
        window.status_tabs.setCurrentIndex(2)
        self.assertEqual(window.capture_configuration(), state)
        window.custom_radio.click()
        self.assertTrue(window.distance_mode_cb.isEnabled())
        self.assertEqual(window.parameter_mode_label.text(), "可编辑")

    def test_reserved_controls_stay_disabled_in_custom_mode(self):
        """解除父页只读不能启用协议原本明确禁用的保留位。"""
        self.window.protocol_combo.setCurrentText(PROTOCOL_SXSY)
        self.window.custom_radio.click()
        self.assertFalse(self.window.status2_d7_cb.isEnabled())
        self.assertFalse(self.window.current_70_flag_cb.isEnabled())

    def test_copy_and_tab_browsing_do_not_consume_sequence_or_send(self):
        """复制和浏览使用已生成快照，不能推进 SXSY 序号或触发发送。"""
        window = self.window
        window.protocol_combo.setCurrentText(PROTOCOL_SXSY)
        sequence = window.protocol_handler.get_current_sxsy_sequence()
        with patch.object(window.serial_manager, "send_single_frame") as send:
            with patch.object(window, "generate_protocol_frame_for_preview", wraps=window.generate_protocol_frame_for_preview) as preview:
                window.frame_preview.copy_button.click()
                window.status_tabs.setCurrentIndex(3)
        send.assert_not_called()
        preview.assert_not_called()
        self.assertEqual(window.protocol_handler.get_current_sxsy_sequence(), sequence)

    def test_preview_rows_and_raw_text_match_all_protocols(self):
        """所有协议仍由同一预览入口编码，表格字节与原格式一致。"""
        window = self.window
        for name, definition in PROTOCOL_DEFINITIONS.items():
            with self.subTest(protocol=name):
                window.protocol_combo.setCurrentText(name)
                frame = window.protocol_handler.generate_frame_for_preview(window.current_status)[1]
                self.assertEqual(window.frame_preview.table.rowCount(), definition.frame_length)
                self.assertEqual(window.frame_preview.hex_text.text(), " ".join(f"{value:02X}" for value in frame))
                self.assertEqual(window.current_frame_text.toPlainText(), window.protocol_handler.format_frame_display(frame))

    def test_original_frame_editing_remains_only_custom_frame_path(self):
        """原始帧模式不启用参数输入，表格和原格式同步且不擅自重算用户帧。"""
        window = self.window
        window.protocol_combo.setCurrentText(PROTOCOL_LISHEN_BMS)
        window.frame_custom_radio.click()
        raw = [0, 50, 48, 246, 0, 88]
        window.on_custom_frame_changed(raw)
        self.assertEqual(window.frame_preview.hex_text.text(), "00 32 30 F6 00 58")
        self.assertEqual(window.custom_frame_data, raw)
        self.assertFalse(window.lishen_soc_spin.isEnabled())
        self.assertTrue(window.frame_config_btn.isEnabled())

    def test_invalid_parameters_do_not_leave_old_preview_copyable(self):
        """预设对象无效时两个视图都显示错误，旧帧不能继续复制。"""
        window = self.window
        window.protocol_combo.setCurrentText(PROTOCOL_LISHEN_BMS)
        window.current_status.soc_percent = 101
        window.update_current_frame_display()
        self.assertEqual(window.frame_preview.table.rowCount(), 0)
        self.assertFalse(window.frame_preview.copy_button.isEnabled())
        self.assertIn("帧生成失败", window.current_frame_text.toPlainText())

    def test_search_while_sending_does_not_stop_until_real_protocol_selected(self):
        """搜索不产生临时协议切换；真正选择另一协议仍执行原停止旧循环逻辑。"""
        window = self.window
        window.active_send_mode = "single"
        with patch.object(window.serial_manager, "is_cyclic_sending", return_value=True):
            with patch.object(window.serial_manager, "stop_cyclic_send") as stop:
                window.protocol_combo.showPopup()
                window.protocol_combo._search.setText("锂神")
                stop.assert_not_called()
                window.protocol_combo._commit_selection()
                stop.assert_called_once_with()
        self.assertEqual(window.current_protocol, PROTOCOL_LISHEN_BMS)

    def test_log_keeps_read_only_bounded_batch_mechanism(self):
        """历史仍使用原有有界文档和批量追加，不为外观另起线程或逐帧重建表格。"""
        window = self.window
        self.assertTrue(window.history_text.isReadOnly())
        self.assertEqual(window.history_text.document().maximumBlockCount(), 10000)
        window.on_data_sent([0, 50, 48, 25, 0, 123], "12:00:00.000")
        self.assertEqual(window.history_text.toPlainText(), "")
        window._flush_history_updates()
        self.assertIn("00 32 30 19 00 7B", window.history_text.toPlainText())

    def test_compact_window_scrolls_instead_of_collapsing_parameter_content(self):
        """低高度下发送按钮不重叠，参数页保留基本高度，左栏多余内容可以滚动访问。"""
        window = self.window
        window.resize(1000, 640)
        window.show()
        _APP.processEvents()
        self.assertGreater(window.status_tabs.height(), 100)
        self.assertGreater(window.control_scroll.verticalScrollBar().maximum(), 0)
        self.assertLessEqual(window.single_send_btn.geometry().bottom(), window.packet_sequence_btn.geometry().top())

    def test_default_window_keeps_controls_and_twelve_byte_preview_visible(self):
        """默认大小不出现整栏滚动，瑞轮十二字节均在表格可视区域内。"""
        font_path = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts/msyh.ttc"
        if not font_path.is_file():
            self.skipTest("像素布局检查需要实际分发环境的微软雅黑字体")
        font_id = QFontDatabase.addApplicationFont(str(font_path))
        families = QFontDatabase.applicationFontFamilies(font_id)
        self.assertTrue(families)
        original_font = _APP.font()
        window = None
        try:
            # 与 main.py 一致：先设置应用字体，再建立控件及数值框的宽度。
            _APP.setFont(QFont(families[0], 9))
            window = MainWindow(settings_store=SettingsStore())
            window.resize(1200, 800)
            window.show()
            _APP.processEvents()
            _APP.processEvents()
            self.assertEqual(window.control_scroll.verticalScrollBar().maximum(), 0)
            table = window.frame_preview.table
            self.assertEqual(table.rowCount(), 12)
            self.assertGreaterEqual(table.viewport().height(), sum(table.rowHeight(row) for row in range(12)))
        finally:
            if window is not None:
                window.close()
            _APP.setFont(original_font)
            QFontDatabase.removeApplicationFont(font_id)

    def test_manual_monitor_ratio_is_not_reset_by_parameter_changes(self):
        """用户调节的预览/历史比例保持不变，参数更新不触发自动跳动。"""
        window = self.window
        window.resize(1200, 800)
        window.show()
        _APP.processEvents()
        window.monitor_splitter.moveSplitter(400, 1)
        self.assertTrue(window._monitor_user_sized)
        sizes = window.monitor_splitter.sizes()
        window.custom_radio.click()
        window.tcs_status_cb.setChecked(True)
        _APP.processEvents()
        self.assertEqual(window.monitor_splitter.sizes(), sizes)

    def test_numeric_inputs_keep_negative_and_full_range_values_visible(self):
        """数值框外观增宽后仍保留原量程，负数和末位不会被增减按钮遮住。"""
        window = self.window
        window.protocol_combo.setCurrentText(PROTOCOL_LISHEN_BMS)
        window.custom_radio.click()
        window.show()
        _APP.processEvents()
        for control, value in ((window.lishen_soc_spin, 100), (window.lishen_total_voltage_spin, 255),
                               (window.lishen_temperature_spin, -128)):
            with self.subTest(value=value):
                control.setValue(value)
                self.assertGreaterEqual(control.lineEdit().width(), control.fontMetrics().horizontalAdvance(control.text()))


if __name__ == "__main__":
    unittest.main()
