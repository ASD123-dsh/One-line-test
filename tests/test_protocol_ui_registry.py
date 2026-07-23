import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from gui.main_window import MainWindow
from gui.protocol_ui_registry import PROTOCOL_UI_SPECS, get_protocol_ui_spec
from protocol.definitions import SUPPORTED_PROTOCOLS


class ProtocolUiRegistryTests(unittest.TestCase):
    """验证协议核心与 GUI 路由保持同步。"""

    def test_registry_covers_every_supported_protocol(self):
        self.assertEqual(set(PROTOCOL_UI_SPECS), set(SUPPORTED_PROTOCOLS))

    def test_registered_handlers_exist_on_main_window(self):
        for protocol_name, ui_spec in PROTOCOL_UI_SPECS.items():
            with self.subTest(protocol=protocol_name):
                self.assertTrue(callable(getattr(MainWindow, ui_spec.switch_handler, None)))
                self.assertTrue(callable(getattr(MainWindow, ui_spec.preset_loader, None)))
                self.assertTrue(callable(getattr(MainWindow, ui_spec.status_reader, None)))

    def test_unknown_protocol_has_explicit_error(self):
        with self.assertRaisesRegex(ValueError, "不支持的协议界面"):
            get_protocol_ui_spec("不存在的协议")

    def test_registry_is_read_only(self):
        with self.assertRaises(TypeError):
            PROTOCOL_UI_SPECS["测试协议"] = next(iter(PROTOCOL_UI_SPECS.values()))


if __name__ == "__main__":
    unittest.main()
