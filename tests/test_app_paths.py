import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import app_paths


class ResourcePathTests(unittest.TestCase):
    def test_resource_path_uses_project_directory_without_meipass(self):
        with patch.object(sys, "_MEIPASS", None, create=True):
            result = app_paths.resource_path("img", "图标.ico")

        expected = Path(app_paths.__file__).resolve().parent / "img" / "图标.ico"
        self.assertEqual(Path(result), expected)
        self.assertTrue(Path(result).is_absolute())

    def test_resource_path_uses_meipass_when_running_from_bundle(self):
        with TemporaryDirectory() as temp_dir:
            bundle_dir = Path(temp_dir).resolve()
            with patch.object(sys, "_MEIPASS", str(bundle_dir), create=True):
                result = app_paths.resource_path("img", "联系我.jpg")

        self.assertEqual(Path(result), bundle_dir / "img" / "联系我.jpg")


if __name__ == "__main__":
    unittest.main()
