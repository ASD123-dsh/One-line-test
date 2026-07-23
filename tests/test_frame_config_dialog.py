import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QDialog

from gui.frame_config_dialog import FrameConfigDialog


_APP = QApplication.instance() or QApplication([])


class FrameConfigDialogValidationTests(unittest.TestCase):
    def _create_dialog(self, frame):
        dialog = FrameConfigDialog(initial_frame=frame)
        self.addCleanup(dialog.close)
        return dialog

    def test_initial_frame_rejects_empty_frame(self):
        with self.assertRaises(ValueError):
            FrameConfigDialog(initial_frame=[])

    def test_initial_frame_rejects_invalid_byte_values(self):
        invalid_values = (-1, 256, True, "01")

        for invalid_value in invalid_values:
            with self.subTest(invalid_value=invalid_value):
                with self.assertRaises(ValueError):
                    FrameConfigDialog(initial_frame=[0x01, invalid_value, 0x03])

    def test_set_frame_data_requires_original_frame_length(self):
        dialog = self._create_dialog([0x01, 0x02, 0x03])

        for invalid_frame in ([0x01, 0x02], [0x01, 0x02, 0x03, 0x04], []):
            with self.subTest(invalid_frame=invalid_frame):
                with self.assertRaises(ValueError):
                    dialog.set_frame_data(invalid_frame)

        self.assertEqual(dialog.get_frame_data(), [0x01, 0x02, 0x03])

    def test_set_frame_data_rejects_invalid_byte_values(self):
        dialog = self._create_dialog([0x01, 0x02, 0x03])
        invalid_values = (-1, 256, True, "01")

        for invalid_value in invalid_values:
            with self.subTest(invalid_value=invalid_value):
                with self.assertRaises(ValueError):
                    dialog.set_frame_data([0x01, invalid_value, 0x03])

        self.assertEqual(dialog.get_frame_data(), [0x01, 0x02, 0x03])

    def test_set_frame_data_updates_model_and_editors(self):
        dialog = self._create_dialog([0x01, 0x02, 0x03])

        dialog.set_frame_data([0x10, 0x20, 0x30])

        self.assertEqual(dialog.get_frame_data(), [0x10, 0x20, 0x30])
        self.assertEqual(
            [editor.get_value() for editor in dialog.byte_editors],
            [0x10, 0x20, 0x30],
        )

    def test_accept_rejects_blank_editor_instead_of_returning_stale_data(self):
        dialog = self._create_dialog([0x01, 0x02, 0x03])
        dialog.byte_editors[1].hex_edit.clear()

        with patch("gui.frame_config_dialog.QMessageBox.warning") as warning:
            dialog._on_accept()

        warning.assert_called_once()
        self.assertNotEqual(dialog.result(), QDialog.Accepted)
        self.assertEqual(dialog.get_frame_data(), [0x01, 0x02, 0x03])


if __name__ == "__main__":
    unittest.main()
