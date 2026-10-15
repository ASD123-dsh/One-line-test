#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""本地验收入口的身份与版本保护测试，不启动真实 EXE。"""

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from app_info import APP_ID, APP_NAME, APP_EXE_NAME
from test_updates import make_program
from tools.build_release import create_release_zip
from tools import local_update_test as local_test
from updating.package import file_sha256
from updating.releases import UpdateError


class LocalUpdateTestTests(unittest.TestCase):
    """只使用独占临时目录，校验测试工具不接收任意安装位置。"""

    def setUp(self):
        """建立配套的旧版基线和更高版本专属更新包。"""
        self.temporary = TemporaryDirectory(prefix="sifexe-local-test-kit-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.baseline = make_program(self.root / "baseline" / APP_NAME, "1.58.1")
        candidate = make_program(self.root / "candidate", "1.58.2", isolated=True)
        self.archive = create_release_zip(candidate, self.root / "release", "1.58.2")
        self.identity = {"schema": 1, "app_id": APP_ID, "baseline_version": "1.58.1",
                         "version": "1.58.2", "sha256": file_sha256(self.archive)}
        self.save_identity()

    def save_identity(self):
        """仅重写测试自己创建的身份文件。"""
        (self.root / local_test.KIT_NAME).write_text(json.dumps(self.identity), encoding="utf-8")

    def test_valid_kit_is_read_without_modifying_baseline(self):
        """正常配套基线可读取，真实安装始终另外创建副本。"""
        before = local_test.snapshot(self.baseline / APP_EXE_NAME)
        root, data, baseline, archive = local_test.load_kit(self.root)
        self.assertEqual((root, baseline, archive), (self.root, self.baseline, self.archive))
        self.assertEqual(data["version"], "1.58.2")
        self.assertEqual(local_test.snapshot(self.baseline / APP_EXE_NAME), before)

    def test_wrong_identity_is_rejected(self):
        """没有匹配身份记录的目录不是测试包。"""
        self.identity["app_id"] = "other-application"
        self.save_identity()
        with self.assertRaisesRegex(UpdateError, "不是本工具"):
            local_test.load_kit(self.root)

    def test_modified_baseline_is_rejected(self):
        """旧版基线发生修改时停止，不用不确定的程序测试升级。"""
        (self.baseline / APP_EXE_NAME).write_bytes(b"modified")
        with self.assertRaisesRegex(UpdateError, "校验失败"):
            local_test.load_kit(self.root)

    def test_modified_archive_is_rejected(self):
        """候选 ZIP 与测试记录摘要不符时停止。"""
        self.archive.write_bytes(b"modified archive")
        with self.assertRaisesRegex(UpdateError, "摘要不匹配"):
            local_test.load_kit(self.root)

    def test_non_increasing_version_is_rejected(self):
        """本地测试也必须使用更高版本，不绕过正式版本比较。"""
        self.identity["version"] = "1.58.1"
        self.save_identity()
        with self.assertRaisesRegex(UpdateError, "必须高于旧版"):
            local_test.load_kit(self.root)

    def test_legacy_runtime_is_in_foreign_snapshot(self):
        """旧共享运行库纳入保护比较，但主 EXE 和自有清单不属于其他文件。"""
        from updating.package import read_manifest
        result = local_test.foreign_snapshots(self.baseline, read_manifest(self.baseline))
        self.assertEqual(set(result), {"_internal/updater.exe", "_internal/python311.dll"})

    def test_result_file_does_not_overwrite_existing_data(self):
        """生成结果只允许新文件，不能覆盖用户已有测试记录。"""
        output = self.root / "existing.json"
        output.write_text("original", encoding="utf-8")
        with self.assertRaises(FileExistsError):
            local_test.write_json(output, {})
        self.assertEqual(output.read_text(encoding="utf-8"), "original")

    def test_oversized_record_is_rejected(self):
        """异常大的测试记录不会被完整加载。"""
        output = self.root / "oversized.json"
        output.write_bytes(b" " * 65537)
        with self.assertRaisesRegex(UpdateError, "过大"):
            local_test.read_json(output)


if __name__ == "__main__":
    unittest.main()
