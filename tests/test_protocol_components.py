#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""协议组件组织与兼容门面契约，防止后续新增协议重新堆回集中式文件。"""

import unittest

from gui.main_window import MainWindow
from gui.protocol_ui_registry import PROTOCOL_UI_SPECS
from protocol.definitions import PROTOCOL_DEFINITIONS
from protocol.protocol_handler import ProtocolHandler


class ProtocolComponentTests(unittest.TestCase):
    """逐一检查所有注册协议的实现与说明，不接触真实设备。"""

    def test_every_generator_is_implemented_in_protocol_component(self):
        """公共门面仍可调用原方法，但具体编码留在独立协议组件内。"""
        handler = ProtocolHandler()
        for definition in PROTOCOL_DEFINITIONS.values():
            with self.subTest(protocol=definition.name):
                generator = getattr(handler, definition.generator_method)
                self.assertTrue(generator.__module__.startswith("protocol.codecs."))
                if definition.preview_generator_method:
                    preview = getattr(handler, definition.preview_generator_method)
                    self.assertTrue(preview.__module__.startswith("protocol.codecs."))

    def test_descriptions_are_independent_and_match_frame_lengths(self):
        """调用方改写说明副本不能污染其他界面或下一次查询。"""
        handler = ProtocolHandler()
        for definition in PROTOCOL_DEFINITIONS.values():
            with self.subTest(protocol=definition.name):
                original = handler.get_byte_descriptions(definition.name)
                modified = handler.get_byte_descriptions(definition.name)
                modified[0] = "modified by caller"
                self.assertEqual(handler.get_byte_descriptions(definition.name), original)
                self.assertEqual(len(original), definition.frame_length)

    def test_readers_and_writers_are_separate_gui_components(self):
        """每个界面读写入口真实存在，且不在主窗口堆叠实现。"""
        for spec in PROTOCOL_UI_SPECS.values():
            for name in (spec.status_reader, spec.status_writer):
                method = getattr(MainWindow, name)
                self.assertTrue(method.__module__.startswith("gui.protocol_pages."))


if __name__ == "__main__":
    unittest.main()
