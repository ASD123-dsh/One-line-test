#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""正式发布归档和安全清理回归测试；使用临时模拟附件，不联网、不编译。"""

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from app_info import APP_ID, GITHUB_REPOSITORY
from tools import archive_release as archiver
from updating.package import file_sha256
from updating.releases import UpdateError, asset_name_for_version


class ArchiveReleaseTests(unittest.TestCase):
    """归档冲突和清理仅在本测试独占目录中模拟，不访问现有发行包。"""

    def setUp(self):
        """建立两个附件、两个校验文件及已公开发行记录。"""
        self.temporary = TemporaryDirectory(prefix="sifexe-archive-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.source = self.root / "test-kit" / "release"
        self.source.mkdir(parents=True)
        self.archive = self.root / "archives"
        self.version = "1.58.2"
        self.assets = []
        for managed in (False, True):
            name = asset_name_for_version(self.version, managed=managed)
            path = self.source / name
            path.write_bytes(b"test-zip-content-" + name.encode("ascii"))
            checksum = self.source / (name + ".sha256")
            checksum.write_text(file_sha256(path) + "  " + name + "\n", encoding="ascii")
            for item in (path, checksum):
                self.assets.append({"name": item.name, "size": item.stat().st_size,
                                    "state": "uploaded", "digest": "sha256:" + file_sha256(item)})
        self.record = {
            "schema": 1, "repository": GITHUB_REPOSITORY, "version": self.version,
            "source": {"merge_commit": "a" * 40},
            "release": {"tag": "v" + self.version, "draft": False, "prerelease": False,
                        "published_at": "2026-10-15T10:11:39Z", "tag_commit_verified": True,
                        "target_commit": "a" * 40, "assets": self.assets},
        }
        self.record_path = self.root / "publication.json"
        self.save_record()
        self.notes = self.root / "notes.md"
        self.notes.write_text("测试发布说明\n", encoding="utf-8")
        self.verification = self.root / "packaging.json"
        self.verification.write_text(json.dumps({"version": self.version}), encoding="utf-8")

    def save_record(self):
        """仅重写本测试自行创建的发布记录。"""
        self.record_path.write_text(json.dumps(self.record), encoding="utf-8")

    def run_archive(self, prune=False, record=None, verification=None):
        """调用真实归档函数，默认包含说明及打包验证记录。"""
        return archiver.archive_release(self.source, record or self.record_path, self.archive,
                                        self.notes, verification or self.verification, prune)

    def target(self):
        """返回本测试版本的专属归档目录。"""
        return self.archive / ("v" + self.version)

    def test_complete_archive_has_seven_verified_files(self):
        """两个 ZIP、校验文件、发布记录和两种说明完整归档。"""
        result = self.run_archive()
        self.assertEqual(result["verified_files"], 7)
        self.assertEqual(result["copied_files"], 7)
        self.assertEqual({path.name for path in self.target().iterdir()},
                         {asset["name"] for asset in self.assets}
                         | {"release-publication.json", "发布说明.md", "packaging-verification.json"})
        for asset in self.assets:
            self.assertEqual(file_sha256(self.target() / asset["name"]), asset["digest"][7:])

    def test_identical_archive_is_not_rewritten(self):
        """重复归档只校验，保持既有文件的修改时间和文件标识。"""
        self.run_archive()
        original = {path.name: (path.stat().st_mtime_ns, path.stat().st_ino) for path in self.target().iterdir()}
        result = self.run_archive()
        self.assertEqual(result["copied_files"], 0)
        self.assertEqual(original, {path.name: (path.stat().st_mtime_ns, path.stat().st_ino)
                                    for path in self.target().iterdir()})

    def test_conflicting_archive_is_not_overwritten(self):
        """同版本归档有不同内容时，在复制其他文件之前停止。"""
        self.target().mkdir(parents=True)
        conflict = self.target() / self.assets[0]["name"]
        conflict.write_bytes(b"customer existing archive")
        with self.assertRaisesRegex(ValueError, "已有归档内容不同"):
            self.run_archive()
        self.assertEqual(conflict.read_bytes(), b"customer existing archive")
        self.assertEqual(len(list(self.target().iterdir())), 1)

    def test_modified_source_stops_before_creating_archive(self):
        """附件与 GitHub 发布摘要不符，不能进入正式归档。"""
        (self.source / self.assets[0]["name"]).write_bytes(b"modified")
        with self.assertRaisesRegex(ValueError, "正式发布记录不符"):
            self.run_archive()
        self.assertFalse(self.archive.exists())

    def test_invalid_publication_is_rejected(self):
        """草稿、预发布、错误仓库、源码不符和危险版本号均不能归档。"""
        mutations = [
            ("release", "draft", True), ("release", "prerelease", True),
            ("release", "tag_commit_verified", False), ("release", "target_commit", "b" * 40),
            (None, "repository", "other/repo"), (None, "version", "../../folder"),
        ]
        original = json.dumps(self.record)
        for section, name, value in mutations:
            with self.subTest(field=name):
                self.record = json.loads(original)
                target = self.record[section] if section else self.record
                target[name] = value
                self.save_record()
                with self.assertRaises((ValueError, UpdateError)):
                    self.run_archive()
                self.assertFalse(self.archive.exists())

    def test_checksum_text_must_match_zip_even_if_record_hash_matches(self):
        """校验文件自身摘要有效也不能掩盖其中 ZIP 摘要或文件名写错。"""
        checksum_asset = self.assets[1]
        checksum = self.source / checksum_asset["name"]
        checksum.write_text("0" * 64 + "  wrong.zip\n", encoding="ascii")
        checksum_asset.update(size=checksum.stat().st_size, digest="sha256:" + file_sha256(checksum))
        self.save_record()
        with self.assertRaisesRegex(ValueError, "校验文件内容"):
            self.run_archive()

    def test_duplicate_or_unowned_asset_is_rejected(self):
        """发布记录不能重复声明附件或带入其他应用及私有文件。"""
        self.record["release"]["assets"][0]["name"] = "other-app.exe"
        self.save_record()
        with self.assertRaisesRegex(ValueError, "正式附件"):
            self.run_archive()

    def test_copy_failure_removes_only_its_partial_file(self):
        """复制失败清掉自己创建的半成品，源包和其他数据不动。"""
        with patch.object(archiver.shutil, "copyfileobj", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                self.run_archive()
        self.assertEqual(list(self.target().iterdir()), [])
        self.assertEqual(len(list(self.source.iterdir())), 4)

    def test_prune_preserves_required_test_cache_and_unknown_files(self):
        """归档后只清理冗余生成文件，测试必需 managed ZIP 和用户数据仍可用。"""
        marker = self.source.parent / "local-test-kit.json"
        marker.write_text(json.dumps({"schema": 1, "app_id": APP_ID, "version": self.version}), encoding="utf-8")
        unknown = self.source / "用户数据.txt"
        unknown.write_text("保留", encoding="utf-8")
        result = self.run_archive(prune=True)
        self.assertEqual(len(result["removed_generated_files"]), 5)
        self.assertEqual({path.name for path in self.source.iterdir()},
                         {asset_name_for_version(self.version, managed=True), unknown.name})
        self.assertEqual(unknown.read_text(encoding="utf-8"), "保留")
        self.assertTrue(self.notes.exists())
        self.assertFalse(self.record_path.exists())
        self.assertFalse(self.verification.exists())

    def test_archive_can_be_revalidated_after_source_pruning(self):
        """源副本清理后可用正式归档记录重新核验，不复制或删除归档本身。"""
        self.run_archive(prune=True)
        result = self.run_archive(prune=True, record=self.target() / "release-publication.json",
                                  verification=self.target() / "packaging-verification.json")
        self.assertEqual(result["copied_files"], 0)
        self.assertEqual(result["removed_generated_files"], [])
        self.assertEqual(len(list(self.target().iterdir())), 7)

    def test_invalid_test_marker_prevents_cleanup(self):
        """测试标记不明确时保留生成输入，不因归档成功而误删。"""
        (self.source.parent / "local-test-kit.json").write_text("{}", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "测试包标记无效"):
            self.run_archive(prune=True)
        self.assertEqual(len(list(self.source.iterdir())), 4)
        self.assertTrue(self.record_path.exists())
        self.assertEqual(len(list(self.target().iterdir())), 7)

    def test_verification_version_mismatch_is_rejected(self):
        """不能把其他版本的打包结果混进当前版本归档。"""
        self.verification.write_text('{"version":"1.58.1"}', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "验证记录版本"):
            self.run_archive()

    def test_archive_links_are_rejected(self):
        """正式归档链路中发现链接时停止，不沿链接写入其他位置。"""
        original = archiver.is_reparse_point
        with patch.object(archiver, "is_reparse_point", side_effect=lambda path: Path(path) == self.source or original(path)):
            with self.assertRaisesRegex(ValueError, "不能包含链接"):
                self.run_archive()


if __name__ == "__main__":
    unittest.main()
