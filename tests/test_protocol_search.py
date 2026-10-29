#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""协议拼音搜索、输入法事件和焦点回归，不切换系统输入法，不使用真实串口。"""

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QEvent, Qt
from PyQt5.QtGui import QInputMethodEvent, QInputMethodQueryEvent, QKeyEvent
from PyQt5.QtTest import QSignalSpy, QTest
from PyQt5.QtWidgets import QApplication, QPushButton, QVBoxLayout, QWidget

from app_settings import SettingsStore
from gui.main_window import MainWindow
from gui.protocol_search import PROTOCOL_SEARCH_ALIASES, normalize_search_text, protocol_search_keys
from gui.protocol_selector import ProtocolSelector
from protocol.definitions import (
    PROTOCOL_BATTERY_SINGLE_WIRE, PROTOCOL_CHANGZHOU_XINSIWEI, PROTOCOL_FZ_SIF,
    PROTOCOL_LISHEN_BMS, PROTOCOL_LUYUAN_BMS, PROTOCOL_RUILUN, PROTOCOL_SXSY,
    PROTOCOL_TAILING_Y34B, PROTOCOL_TAILING_Y34F, PROTOCOL_XINRI, SUPPORTED_PROTOCOLS,
)
from serial_comm.serial_manager import SerialManager, SerialPortDetector

_APP = QApplication.instance() or QApplication([])


def click_window_result(combo, name):
    """通过 QWindow 投递鼠标点击，覆盖真实窗口事件先于列表控件的分发路径。"""
    item = next(combo._results.item(row) for row in range(combo._results.count())
                if combo._results.item(row).text() == name)
    assert not item.isHidden()
    combo._results.scrollToItem(item)
    _APP.processEvents()
    viewport = combo._results.viewport()
    point = combo._results.visualItemRect(item).center()
    assert viewport.rect().contains(point)
    QTest.mouseClick(combo._popup.windowHandle(), Qt.LeftButton,
                     pos=viewport.mapTo(combo._popup, point))
    _APP.processEvents()


class ProtocolSearchIndexTests(unittest.TestCase):
    """检查全部索引覆盖及原名称回退，不把搜索别名作为协议注册名。"""

    def test_aliases_cover_all_registered_protocols(self):
        """新增协议必须同步补充全拼和首字母索引，不遗漏中文名称的拼音能力。"""
        self.assertEqual(set(PROTOCOL_SEARCH_ALIASES), set(SUPPORTED_PROTOCOLS))
        for name, aliases in PROTOCOL_SEARCH_ALIASES.items():
            self.assertGreaterEqual(len(aliases), 2, name)
            self.assertTrue(all(alias.isascii() and alias.isalnum() for alias in aliases), name)

    def test_normalization_handles_spacing_case_width_and_umlaut(self):
        """常见拼音分隔、全角输入和绿源的 ü/v 写法使用一致索引。"""
        for query, expected in ((" RUI-LUN ", "ruilun"), ("ＲＬ", "rl"), ("rui'lun", "ruilun"),
                                ("LÜ YUAN", "lvyuan"), ("瑞轮", "瑞轮"), ("不存在?", "不存在?")):
            with self.subTest(query=query):
                self.assertEqual(normalize_search_text(query), expected)

    def test_aliases_are_immutable(self):
        """界面过滤不能把别名表改成另一份可发送协议注册表。"""
        with self.assertRaises(TypeError):
            PROTOCOL_SEARCH_ALIASES[PROTOCOL_RUILUN] = ("other",)

    def test_unknown_name_still_supports_original_name_search(self):
        """未补充别名的控件项目仍保留原中文和型号搜索，不产生未知协议。"""
        self.assertEqual(protocol_search_keys("未来厂家 X99"), ("未来厂家x99",))


class ProtocolSearchInputTests(unittest.TestCase):
    """模拟文本合成及普通按键，验证浮层不抢占系统输入法快捷键。"""

    def setUp(self):
        """每项建立独立主窗口和搜索控件，避免焦点或应用过滤器跨测试残留。"""
        self.owner = QWidget()
        self.owner.resize(640, 520)
        layout = QVBoxLayout(self.owner)
        self.combo = ProtocolSelector()
        self.combo.addItems(SUPPORTED_PROTOCOLS)
        layout.addWidget(self.combo)
        self.outside = QPushButton("其他动作")
        layout.addWidget(self.outside)
        self.owner.show()
        _APP.processEvents()
        self.addCleanup(self.owner.close)
        self.addCleanup(self.combo.hidePopup)

    def visible_names(self):
        """只读取已存在结果的显隐状态，不触发协议编码或发送。"""
        return [self.combo._results.item(row).text() for row in range(self.combo._results.count())
                if not self.combo._results.item(row).isHidden()]

    def open_search(self):
        """等待实际 Qt 焦点事件完成，验证目标是真正的文本编辑框。"""
        self.combo.showPopup()
        _APP.processEvents()

    def test_full_pinyin_initials_chinese_and_models_match(self):
        """覆盖截图中的 rui，并保留中文、混合型号及多结果搜索。"""
        cases = (("rui", [PROTOCOL_RUILUN]), ("ruilun", [PROTOCOL_RUILUN]), ("RL", [PROTOCOL_RUILUN]),
                 ("瑞轮", [PROTOCOL_RUILUN]), ("RUI LUN", [PROTOCOL_RUILUN]), ("ＲＬ", [PROTOCOL_RUILUN]),
                 ("xinri", [PROTOCOL_XINRI]), ("xr", [PROTOCOL_XINRI]), ("xinsiwei", [PROTOCOL_CHANGZHOU_XINSIWEI]),
                 ("lishen", [PROTOCOL_LISHEN_BMS]), ("ls", [PROTOCOL_LISHEN_BMS]),
                 ("lvyuan", [PROTOCOL_LUYUAN_BMS]), ("lüyuan", [PROTOCOL_LUYUAN_BMS]),
                 ("luyuan", [PROTOCOL_LUYUAN_BMS]), ("dcdx", [PROTOCOL_BATTERY_SINGLE_WIRE]),
                 ("fz sif", [PROTOCOL_FZ_SIF]), ("sxsy", [PROTOCOL_SXSY]),
                 ("Y34B", [PROTOCOL_TAILING_Y34B]), ("y34", [PROTOCOL_TAILING_Y34B, PROTOCOL_TAILING_Y34F]))
        self.open_search()
        changes = QSignalSpy(self.combo.currentTextChanged)
        for query, expected in cases:
            with self.subTest(query=query):
                self.combo._search.setText(query)
                self.assertEqual(self.visible_names(), expected)
                self.assertEqual(self.combo.currentText(), PROTOCOL_RUILUN)
        self.assertEqual(len(changes), 0)

    def test_every_complete_alias_matches_its_original_item(self):
        """全部现有协议的全拼及首字母都能命中，结果名称始终使用原注册名。"""
        self.open_search()
        for name, aliases in PROTOCOL_SEARCH_ALIASES.items():
            for alias in aliases:
                with self.subTest(name=name, alias=alias):
                    self.combo._search.setText(alias)
                    self.assertIn(name, self.visible_names())
                    self.assertTrue(set(self.visible_names()).issubset(SUPPORTED_PROTOCOLS))

    def test_search_is_focusable_non_grabbing_tool_window(self):
        """搜索获得真实编辑焦点及 IME 能力，不再进入 Qt 菜单弹层或键盘独占状态。"""
        self.open_search()
        self.assertEqual(self.combo._popup.windowType(), Qt.Tool)
        self.assertFalse(self.combo._popup.windowFlags() & Qt.WindowDoesNotAcceptFocus)
        self.assertIsNot(_APP.activePopupWidget(), self.combo._popup)
        self.assertIsNone(QWidget.keyboardGrabber())
        self.assertIs(_APP.focusWidget(), self.combo._search)
        self.assertTrue(self.combo._search.testAttribute(Qt.WA_InputMethodEnabled))
        query = QInputMethodQueryEvent(Qt.ImEnabled)
        QApplication.sendEvent(self.combo._search, query)
        self.assertTrue(query.value(Qt.ImEnabled))
        self.assertEqual(self.combo._search.inputMethodHints(), Qt.ImhNone)

    def test_shift_and_language_shortcuts_are_not_consumed(self):
        """过滤器不能拦截中英文模式切换键，也不把组合键当成结果导航。"""
        self.open_search()
        for key, modifiers in ((Qt.Key_Shift, Qt.ShiftModifier), (Qt.Key_Control, Qt.ControlModifier),
                               (Qt.Key_Alt, Qt.AltModifier), (Qt.Key_Space, Qt.MetaModifier),
                               (Qt.Key_Shift, Qt.ControlModifier | Qt.ShiftModifier),
                               (Qt.Key_Down, Qt.ControlModifier)):
            with self.subTest(key=key, modifiers=modifiers):
                event = QKeyEvent(QEvent.KeyPress, key, modifiers)
                self.assertFalse(self.combo.eventFilter(self.combo._search, event))
                self.assertTrue(self.combo._popup.isVisible())

    def test_preedit_does_not_commit_protocol_and_chinese_commit_filters(self):
        """IME 候选文本与最终中文分别处理，确认候选不等于确认协议。"""
        self.combo.setCurrentText(PROTOCOL_LISHEN_BMS)
        changes = QSignalSpy(self.combo.currentTextChanged)
        self.open_search()
        QApplication.sendEvent(self.combo._search, QInputMethodEvent("rui", []))
        self.assertTrue(self.combo._ime_composing)
        self.assertEqual(self.combo._search.text(), "")
        self.combo._search.returnPressed.emit()
        self.combo._commit_selection(self.combo._results.item(0))
        self.assertEqual(len(changes), 0)
        self.assertTrue(self.combo._popup.isVisible())
        commit = QInputMethodEvent()
        commit.setCommitString("瑞轮")
        QApplication.sendEvent(self.combo._search, commit)
        self.assertFalse(self.combo._ime_composing)
        self.assertEqual(self.combo._search.text(), "瑞轮")
        self.assertEqual(self.visible_names(), [PROTOCOL_RUILUN])
        self.assertEqual(len(changes), 0)
        self.combo._search.returnPressed.emit()
        self.assertEqual(self.combo.currentText(), PROTOCOL_RUILUN)
        self.assertEqual(len(changes), 1)

    def test_composition_keys_and_ime_deactivation_do_not_close_search(self):
        """合成期间的 Esc/方向键及候选窗短暂激活不会被误当作取消搜索。"""
        self.open_search()
        QApplication.sendEvent(self.combo._search, QInputMethodEvent("rui", []))
        for key in (Qt.Key_Escape, Qt.Key_Down, Qt.Key_Up, Qt.Key_Return):
            self.assertFalse(self.combo.eventFilter(self.combo._search, QKeyEvent(QEvent.KeyPress, key, Qt.NoModifier)))
        QApplication.sendEvent(self.combo._popup, QEvent(QEvent.WindowDeactivate))
        self.assertTrue(self.combo._popup.isVisible())
        self.assertEqual(self.combo.currentText(), PROTOCOL_RUILUN)

    def test_navigation_skips_hidden_results_without_switching_protocol(self):
        """上下键只移动可见高亮，回车才提交型号对应的原协议。"""
        self.open_search()
        self.combo._search.setText("y34")
        changes = QSignalSpy(self.combo.currentTextChanged)
        QTest.keyClick(self.combo._search, Qt.Key_Down)
        self.assertEqual(self.combo._results.currentItem().text(), PROTOCOL_TAILING_Y34F)
        self.assertEqual(len(changes), 0)
        QTest.keyClick(self.combo._search, Qt.Key_Return)
        self.assertEqual(self.combo.currentText(), PROTOCOL_TAILING_Y34F)
        self.assertEqual(len(changes), 1)
        self.assertFalse(self.combo._popup.isVisible())

    def test_escape_cancels_without_changing_protocol(self):
        """未处于 IME 合成时 Esc 收起浮层，不选择第一条结果。"""
        self.open_search()
        self.combo._search.setText("lishen")
        QTest.keyClick(self.combo._search, Qt.Key_Escape)
        self.assertFalse(self.combo._popup.isVisible())
        self.assertEqual(self.combo.currentText(), PROTOCOL_RUILUN)

    def test_outside_click_closes_search_and_preserves_clicked_action(self):
        """不用鼠标抓取也能收起浮层，外部原有按钮仍只执行一次。"""
        self.open_search()
        clicked = QSignalSpy(self.outside.clicked)
        QTest.mouseClick(self.outside, Qt.LeftButton)
        self.assertFalse(self.combo._popup.isVisible())
        self.assertEqual(len(clicked), 1)

    def test_clicking_combo_again_collapses_instead_of_reopening(self):
        """重复点击下拉框收起搜索，不在同一个鼠标事件里立即重新弹出。"""
        self.open_search()
        QTest.mouseClick(self.combo, Qt.LeftButton)
        self.assertFalse(self.combo._popup.isVisible())

    def test_no_result_enter_does_not_change_selection(self):
        """未知拼音和无结果回车不会切换到首个协议。"""
        self.combo.setCurrentText(PROTOCOL_LISHEN_BMS)
        self.open_search()
        self.combo._search.setText("not-a-real-protocol")
        QTest.keyClick(self.combo._search, Qt.Key_Return)
        self.assertEqual(self.visible_names(), [])
        self.assertEqual(self.combo.currentText(), PROTOCOL_LISHEN_BMS)

    def test_reopen_resets_filter_and_composition_state(self):
        """收起再打开时显示全部合法项，不带入上次搜索或候选状态。"""
        self.open_search()
        self.combo._search.setText("rui")
        QApplication.sendEvent(self.combo._search, QInputMethodEvent("lun", []))
        self.combo.hidePopup()
        self.open_search()
        self.assertFalse(self.combo._ime_composing)
        self.assertEqual(self.combo._search.text(), "")
        self.assertEqual(self.visible_names(), SUPPORTED_PROTOCOLS)

    def test_owner_hide_closes_search(self):
        """主窗口关闭或隐藏时不遗留独立浮层。"""
        self.open_search()
        self.owner.hide()
        _APP.processEvents()
        self.assertFalse(self.combo._popup.isVisible())

    def test_window_mouse_click_selects_every_registered_protocol(self):
        """逐项鼠标选择原始列表，防止只测控件信号而漏掉窗口层提前收起的问题。"""
        for name in SUPPORTED_PROTOCOLS:
            with self.subTest(protocol=name):
                self.combo.setCurrentText(PROTOCOL_LISHEN_BMS if name == PROTOCOL_RUILUN else PROTOCOL_RUILUN)
                self.open_search()
                changes = QSignalSpy(self.combo.currentTextChanged)
                click_window_result(self.combo, name)
                self.assertEqual(self.combo.currentText(), name)
                self.assertEqual(len(changes), 1)
                self.assertFalse(self.combo._popup.isVisible())

    def test_window_mouse_click_commits_filtered_original_index(self):
        """过滤及滚动不改变结果绑定的原协议索引，鼠标选中后只提交一次。"""
        for query, name in (("y34", PROTOCOL_TAILING_Y34F), ("lishen", PROTOCOL_LISHEN_BMS)):
            with self.subTest(query=query):
                self.combo.setCurrentText(PROTOCOL_RUILUN)
                self.open_search()
                self.combo._search.setText(query)
                changes = QSignalSpy(self.combo.currentTextChanged)
                click_window_result(self.combo, name)
                self.assertEqual(self.combo.currentText(), name)
                self.assertEqual(len(changes), 1)
                self.assertFalse(self.combo._popup.isVisible())

    def test_window_outside_click_closes_and_preserves_action(self):
        """窗口层外部点击最终交给目标按钮，收起弹层但不能吞掉原有动作。"""
        self.open_search()
        clicked = QSignalSpy(self.outside.clicked)
        point = self.outside.mapTo(self.owner, self.outside.rect().center())
        QTest.mouseClick(self.owner.windowHandle(), Qt.LeftButton, pos=point)
        _APP.processEvents()
        self.assertFalse(self.combo._popup.isVisible())
        self.assertEqual(len(clicked), 1)
        self.assertEqual(self.combo.currentText(), PROTOCOL_RUILUN)

    def test_window_combo_click_again_collapses_without_reopening(self):
        """真实窗口路径重复点击下拉框仍是收起，不被鼠标事件再次打开。"""
        self.open_search()
        point = self.combo.mapTo(self.owner, self.combo.rect().center())
        QTest.mouseClick(self.owner.windowHandle(), Qt.LeftButton, pos=point)
        _APP.processEvents()
        self.assertFalse(self.combo._popup.isVisible())

    def test_window_click_empty_results_keeps_popup_and_selection(self):
        """无匹配结果时点击列表空白不能误选首项或被误当作浮层外点击。"""
        self.open_search()
        self.combo._search.setText("not-a-real-protocol")
        changes = QSignalSpy(self.combo.currentTextChanged)
        point = self.combo._results.viewport().mapTo(self.combo._popup, self.combo._results.viewport().rect().center())
        QTest.mouseClick(self.combo._popup.windowHandle(), Qt.LeftButton, pos=point)
        _APP.processEvents()
        self.assertEqual(self.combo.currentText(), PROTOCOL_RUILUN)
        self.assertEqual(len(changes), 0)
        self.assertTrue(self.combo._popup.isVisible())

    def test_window_click_current_protocol_closes_without_change_signal(self):
        """点击已选协议只收起列表，不额外触发协议切换或旧协议循环停止。"""
        self.open_search()
        changes = QSignalSpy(self.combo.currentTextChanged)
        click_window_result(self.combo, PROTOCOL_RUILUN)
        self.assertEqual(self.combo.currentText(), PROTOCOL_RUILUN)
        self.assertEqual(len(changes), 0)
        self.assertFalse(self.combo._popup.isVisible())


class ProtocolSearchSendSafetyTests(unittest.TestCase):
    """拼音查询与发送流程解耦，只有明确切换协议才停止旧协议循环。"""

    def test_search_and_cancel_keep_running_configuration_unchanged(self):
        """真实主窗口回归，不发送串口、不读取用户配置、不调用网络。"""
        with patch.object(SerialPortDetector, "start_detection"), patch.object(SerialManager, "scan_ports", return_value=[]):
            window = MainWindow(settings_store=SettingsStore())
        self.addCleanup(window.close)
        window.history_update_timer.stop()
        before = window.capture_configuration()
        window.active_send_mode = "single"
        with patch.object(window.serial_manager, "is_cyclic_sending", return_value=True), \
                patch.object(window.serial_manager, "stop_cyclic_send") as stop:
            window.protocol_combo.showPopup()
            for text in ("rui", "rl", "不存在", "lishen", "ls"):
                window.protocol_combo._search.setText(text)
                stop.assert_not_called()
                self.assertEqual(window.capture_configuration(), before)
            window.protocol_combo.hidePopup()
            stop.assert_not_called()
            window.protocol_combo.showPopup()
            window.protocol_combo._search.setText("ls")
            window.protocol_combo._commit_selection()
            stop.assert_called_once_with()
        self.assertEqual(window.current_protocol, PROTOCOL_LISHEN_BMS)

    def create_window(self):
        """创建可接收窗口鼠标事件的真实界面，隔离扫描、恢复提示和客户配置。"""
        with patch.object(SerialPortDetector, "start_detection"), \
                patch.object(SerialManager, "scan_ports", return_value=[]), \
                patch.object(MainWindow, "refresh_recovery_notice"):
            window = MainWindow(settings_store=SettingsStore())
        self.addCleanup(window.close)
        window.history_update_timer.stop()
        window.resize(1200, 800)
        window.show()
        _APP.processEvents()
        return window

    def test_window_mouse_selection_updates_all_protocols_and_preview(self):
        """鼠标逐项切换后，实际编码协议、参数状态和字节预览必须同步更新。"""
        window = self.create_window()
        window.protocol_combo.setCurrentText(PROTOCOL_LISHEN_BMS)
        for name in SUPPORTED_PROTOCOLS:
            with self.subTest(protocol=name):
                window.protocol_combo.showPopup()
                _APP.processEvents()
                click_window_result(window.protocol_combo, name)
                self.assertEqual(window.protocol_combo.currentText(), name)
                self.assertEqual(window.current_protocol, name)
                self.assertEqual(window.protocol_handler.resolve_protocol_name(window.current_status), name)
                success, frame, error = window.generate_protocol_frame_for_preview(window.current_status)
                self.assertTrue(success, error)
                self.assertEqual(window.frame_preview.hex_text.text(), " ".join(f"{byte:02X}" for byte in frame))

    def test_window_mouse_commit_stops_old_cycle_only_when_protocol_changes(self):
        """查找、取消及选择当前协议不中断循环，鼠标确认另一协议才停止旧帧发送一次。"""
        window = self.create_window()
        window.active_send_mode = "single"
        with patch.object(window.serial_manager, "is_cyclic_sending", return_value=True), \
                patch.object(window.serial_manager, "stop_cyclic_send") as stop:
            window.protocol_combo.showPopup()
            _APP.processEvents()
            click_window_result(window.protocol_combo, PROTOCOL_RUILUN)
            stop.assert_not_called()
            window.protocol_combo.showPopup()
            window.protocol_combo._search.setText("lishen")
            _APP.processEvents()
            stop.assert_not_called()
            click_window_result(window.protocol_combo, PROTOCOL_LISHEN_BMS)
            stop.assert_called_once_with()
            self.assertEqual(window.current_protocol, PROTOCOL_LISHEN_BMS)
            self.assertFalse(window.protocol_combo._popup.isVisible())


if __name__ == "__main__":
    unittest.main()
