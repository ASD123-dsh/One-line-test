#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""参考图细化的布局、有界日志模型和呈现兼容回归，不访问网络或真实设备。"""

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QModelIndex, QPoint, Qt
from PyQt5.QtGui import QColor
from PyQt5.QtTest import QSignalSpy
from PyQt5.QtWidgets import QAbstractItemView, QApplication, QLabel

from app_settings import SettingsStore
from gui.frame_preview import FramePreview
from gui.main_window import MainWindow
from gui.send_history import HistoryTableModel, SendHistoryView
from gui.ui_icons import StatusBadge, ui_icon
from gui.soft_theme import PALETTE
from protocol.definitions import PROTOCOL_LISHEN_BMS, PROTOCOL_RUILUN
from serial_comm.serial_manager import SerialManager, SerialPortDetector

_APP = QApplication.instance() or QApplication([])


class HistoryModelTests(unittest.TestCase):
    """批次增量更新、记录上限和结果来源都与现有日志保持一致。"""

    def test_success_error_and_hint_have_distinct_results(self):
        """只有原成功日志可称为已写入，不把错误或时序告警伪装为写入帧。"""
        model = HistoryTableModel()
        model.append_lines(["[10:20:30.123] 发送成功: 00 32", "[10:20:31.234] 发送失败: 设备断开", "[时序提示] 缓冲积压"])
        self.assertEqual(model.data(model.index(0, 0)), "10:20:30.123")
        self.assertEqual(model.data(model.index(0, 1)), "已写入")
        self.assertEqual(model.data(model.index(0, 2)), "00 32")
        self.assertEqual(model.data(model.index(1, 1)), "发送失败")
        self.assertEqual(model.data(model.index(1, 2)), "设备断开")
        self.assertEqual(model.data(model.index(2, 1)), "提示")
        self.assertEqual(model.data(model.index(2, 2)), "[时序提示] 缓冲积压")

    def test_model_is_bounded_and_appends_one_batch_without_reset(self):
        """连续插入只保留末尾记录，一批只发出一次插入，不逐行重建整表。"""
        model = HistoryTableModel(limit=5)
        inserted, reset = QSignalSpy(model.rowsInserted), QSignalSpy(model.modelReset)
        model.append_lines([f"[00:00:{index:02}.000] 发送成功: {index:02X}" for index in range(4)])
        model.append_lines([f"[00:01:{index:02}.000] 发送成功: {index:02X}" for index in range(9)])
        self.assertEqual(model.rowCount(), 5)
        self.assertEqual(model.data(model.index(0, 2)), "04")
        self.assertEqual(model.data(model.index(4, 2)), "08")
        self.assertEqual(len(inserted), 2)
        self.assertEqual(len(reset), 0)

    def test_large_batch_is_trimmed_before_insertion(self):
        """即使一次收到超上限批次，也不先建立无界表格或越界删除旧行。"""
        model = HistoryTableModel(limit=3)
        model.append_lines(["first", "second"])
        model.append_lines([str(index) for index in range(10020)])
        self.assertEqual(model.rowCount(), 3)
        self.assertEqual(model.data(model.index(0, 2)), "10017")
        self.assertEqual(model.data(model.index(2, 2)), "10019")

    def test_error_details_keep_unicode_newlines_and_markup_as_text(self):
        """错误和用户路径完整显示为文本，不把内容当 HTML 或丢掉换行后信息。"""
        model = HistoryTableModel()
        detail = "错误 <设备>\nD:/测试路径/数据.bin"
        model.append_lines(["[12:00:00.000] 发送失败: " + detail])
        self.assertEqual(model.data(model.index(0, 2), Qt.ToolTipRole), detail)
        self.assertEqual(model.data(model.index(0, 0), Qt.BackgroundRole), QColor(PALETTE["error_row"]))

    def test_model_is_flat_read_only_and_clears(self):
        """模型无子节点、无编辑标志，清空后没有旧数据或非法索引内容。"""
        model = HistoryTableModel()
        model.append_lines(["line"])
        index = model.index(0, 0)
        self.assertFalse(model.flags(index) & Qt.ItemIsEditable)
        self.assertEqual(model.rowCount(index), 0)
        self.assertEqual(model.columnCount(index), 0)
        self.assertIsNone(model.data(QModelIndex()))
        self.assertEqual(model.headerData(2, Qt.Horizontal), "已写入帧")
        model.clear()
        self.assertEqual(model.rowCount(), 0)

    def test_view_empty_state_and_disabled_auto_scroll(self):
        """有记录后隐藏空态，自动滚动关闭时新增批次不能移动用户视口。"""
        view = SendHistoryView()
        self.addCleanup(view.close)
        self.assertEqual(view.editTriggers(), QAbstractItemView.NoEditTriggers)
        self.assertFalse(view.empty_state.isHidden())
        with patch.object(view, "scrollToBottom") as scroll:
            view.append_lines(["[12:00:00.000] 发送成功: 00 32"], auto_scroll=False)
            scroll.assert_not_called()
            view.append_lines(["[12:00:01.000] 发送成功: 00 33"], auto_scroll=True)
            scroll.assert_called_once_with()
        self.assertTrue(view.empty_state.isHidden())
        view.clear()
        self.assertFalse(view.empty_state.isHidden())

    def test_short_empty_view_prioritizes_readable_text_over_icon(self):
        """低高度下隐藏装饰图标，空态文字不被表头或视口裁切。"""
        view = SendHistoryView()
        self.addCleanup(view.close)
        view.resize(350, 90)
        view.show()
        _APP.processEvents()
        self.assertTrue(view.empty_icon.isHidden())
        labels = [label for label in view.empty_state.findChildren(QLabel)
                  if label.text() == "暂无发送记录"]
        self.assertEqual(len(labels), 1)
        self.assertTrue(view.viewport().rect().contains(labels[0].geometry()))


class ReferencePreviewTests(unittest.TestCase):
    """表格数字索引与简短含义只是显示变化，复制仍是原字节快照。"""

    def setUp(self):
        """每项使用独立只读预览，隔离比较基线与原格式页。"""
        self.preview = FramePreview()
        self.addCleanup(self.preview.close)

    def test_standard_protocol_uses_three_columns_and_keeps_description_in_tooltip(self):
        """普通协议按参考图显示三列，详细说明仍可通过悬停或原格式访问。"""
        self.preview.set_frame(PROTOCOL_RUILUN, [8, 97, 0], ["设备", "流水号", "Status1"])
        self.assertTrue(self.preview.table.isColumnHidden(3))
        self.assertEqual(self.preview.table.item(2, 0).text(), "2")
        self.assertIn("Status1", self.preview.table.item(2, 1).toolTip())
        self.assertFalse(self.preview.change_hint.isVisible())

    def test_lishen_signed_meaning_keeps_raw_byte_decimal(self):
        """含义列显示负温度，十六进制与无符号十进制不被有符号解释改写。"""
        for raw, temperature in ((128, -128), (246, -10), (127, 127)):
            with self.subTest(raw=raw):
                self.preview.set_frame(PROTOCOL_LISHEN_BMS, [0, 50, 48, raw, 0, 0], [])
                self.assertFalse(self.preview.table.isColumnHidden(3))
                self.assertEqual(self.preview.table.item(3, 1).text(), f"{raw:02X}")
                self.assertEqual(self.preview.table.item(3, 2).text(), str(raw))
                self.assertEqual(self.preview.table.item(3, 3).text(), f"温度 {temperature}℃")

    def test_raw_view_context_actions_do_not_encode_or_copy_new_bytes(self):
        """隐藏页签后原始说明仍能切换并返回，界面动作不改变快照。"""
        self.preview.set_frame(PROTOCOL_LISHEN_BMS, [0, 50, 48, 246, 0, 88], [])
        self.preview.table.actions()[0].trigger()
        self.assertEqual(self.preview.views.currentIndex(), 1)
        self.preview.legacy_text.actions()[0].trigger()
        self.assertEqual(self.preview.views.currentIndex(), 0)
        self.assertEqual(self.preview.hex_text.text(), "00 32 30 F6 00 58")
        self.assertTrue(self.preview.views.tabBar().isHidden())

    def test_change_legend_resets_on_protocol_switch(self):
        """变化提示只比较同协议，切换等长协议时恢复无变化状态。"""
        self.preview.set_frame(PROTOCOL_RUILUN, [8, 97, 0], [])
        self.preview.set_frame(PROTOCOL_RUILUN, [8, 97, 1], [])
        self.assertFalse(self.preview.change_hint.isHidden())
        self.assertFalse(self.preview.change_swatch.isHidden())
        self.preview.set_frame("另一个协议", [8, 97, 1], [])
        self.assertTrue(self.preview.change_hint.isHidden())

    def test_painted_icons_and_badge_preserve_text_contract(self):
        """图标有效且可缓存，徽标文本不夹带图标字符或 HTML。"""
        for name in ("settings", "refresh", "copy", "file", "trash", "eye", "edit", "loop", "alert", "empty"):
            with self.subTest(name=name):
                self.assertFalse(ui_icon(name).isNull())
                self.assertIs(ui_icon(name), ui_icon(name))
        badge = StatusBadge("未连接", "connection")
        self.addCleanup(badge.close)
        badge.setText("发送失败")
        self.assertEqual(badge.text(), "发送失败")


class ReferenceWindowTests(unittest.TestCase):
    """接入主窗口后旧文本接口、发送信号和参数数据保持原契约。"""

    def setUp(self):
        """屏蔽扫描，使用空内存配置，不读取客户环境或连接硬件。"""
        for target, name, result in ((SerialPortDetector, "start_detection", None), (SerialManager, "scan_ports", [])):
            stub = patch.object(target, name, return_value=result)
            stub.start()
            self.addCleanup(stub.stop)
        self.window = MainWindow(settings_store=SettingsStore())
        self.window.history_update_timer.stop()
        self.addCleanup(self.window.close)

    def test_serial_fields_and_centered_frame_button_follow_reference(self):
        """三项串口配置纵向排列，帧配置位于场景下方且水平居中。"""
        window = self.window
        window.resize(1200, 800)
        window.show()
        _APP.processEvents()
        y = [control.mapTo(window, QPoint()).y() for control in (window.port_combo, window.baud_combo, window.tosc_spin, window.connect_btn)]
        self.assertTrue(all(a < b for a, b in zip(y, y[1:])))
        button = window.frame_config_btn
        radio_y = window.normal_radio.mapTo(button.parentWidget(), QPoint()).y()
        self.assertGreater(button.y(), radio_y)
        self.assertLess(abs(button.geometry().center().x() - button.parentWidget().rect().center().x()), 3)

    def test_initial_parameter_header_is_not_blank(self):
        """首次启动不需要切换协议就应有章节标题和只读编辑指引。"""
        page = self.window.status_tabs.currentWidget()
        self.assertEqual(page._section_title.text(), "运行指示 · Status1")
        self.assertIn("数据自定义", page._section_hint.text())
        self.window.custom_radio.click()
        self.assertIn("后续发送帧", page._section_hint.text())

    def test_batch_history_keeps_legacy_text_and_visible_table_in_sync(self):
        """接收时不逐帧刷新，批次到达后原文本与新表格同时看到同一写入数据。"""
        window = self.window
        window.on_data_sent([0, 50], "12:00:00.000")
        self.assertEqual(window.history_view.model().rowCount(), 0)
        self.assertEqual(window.history_text.toPlainText(), "")
        window._flush_history_updates()
        self.assertIn("[12:00:00.000] 发送成功: 00 32", window.history_text.toPlainText())
        self.assertEqual(window.history_view.model().data(window.history_view.model().index(0, 2)), "00 32")

    def test_clear_discards_pending_rows_without_stopping_sender(self):
        """清空按钮同时清除已显示与待显示的记录，但不停止循环任务。"""
        window = self.window
        window.on_data_sent([0], "12:00:00.000")
        window._flush_history_updates()
        window.on_data_sent([1], "12:00:01.000")
        with patch.object(window.serial_manager, "stop_cyclic_send") as stop:
            window.clear_send_history()
            stop.assert_not_called()
        window._flush_history_updates()
        self.assertEqual(window.history_view.model().rowCount(), 0)
        self.assertEqual(window.history_text.toPlainText(), "")
        self.assertEqual(window.pending_history_updates, [])

    def test_error_is_immediate_and_not_hidden_by_disconnected_hint(self):
        """断开后到达的失败信号仍立即可见，结果行和原错误文本同步保留。"""
        window = self.window
        window.on_port_disconnected("COM5")
        window.on_send_error("测试错误")
        self.assertEqual(window.history_view.model().data(window.history_view.model().index(0, 1)), "发送失败")
        self.assertIn("测试错误", window.history_text.toPlainText())
        self.assertFalse(window.send_status.isHidden())
        self.assertTrue(window.send_connection_hint.isHidden())

    def test_icons_do_not_change_configuration_or_communication_state(self):
        """装饰绘图不推进序号、改变配置或自行启动发送。"""
        window = self.window
        configuration = window.capture_configuration()
        for button in (window.tools_btn, window.refresh_ports_btn, window.frame_config_btn,
                       window.frame_preview.copy_button, window.clear_history_btn):
            self.assertFalse(button.icon().isNull())
        self.assertEqual(window.capture_configuration(), configuration)
        self.assertFalse(window.serial_manager.is_connected)
        self.assertFalse(window.serial_manager.is_cyclic_sending())


if __name__ == "__main__":
    unittest.main()
