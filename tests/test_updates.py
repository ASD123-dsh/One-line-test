#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""更新元数据、下载、完整包和协调层测试，逐文件事务回归见 test_managed_update。"""

import hashlib
import io
import json
import os
import stat
import unittest
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch
from urllib.error import HTTPError

from app_info import (
    APP_EXE_NAME, APP_ID, APP_NAME, GITHUB_REPOSITORY,
    PRIVATE_CONTENTS_DIR, PRIVATE_MANIFEST_NAME,
)
from tools.build_release import create_release_zip
from updating import controller, installer, package, releases


class FakeResponse(io.BytesIO):
    """模拟具有下载地址的网络响应。"""

    def __init__(self, data, url):
        """记录响应数据和最终下载地址。"""
        super().__init__(data)
        self.url = url

    def geturl(self):
        """返回模拟的最终 HTTPS 地址。"""
        return self.url


def release_data(version="1.58.0", payload=b"zip-content"):
    """生成与 GitHub 稳定发行版一致的测试元数据。"""
    tag = "v" + version
    name = releases.asset_name_for_version(version)
    return {
        "tag_name": tag, "name": "新版本", "body": "支持更多协议",
        "draft": False, "prerelease": False,
        "assets": [{
            "name": name, "state": "uploaded", "size": len(payload),
            "digest": "sha256:" + hashlib.sha256(payload).hexdigest(),
            "browser_download_url": f"https://github.com/{GITHUB_REPOSITORY}/releases/download/{tag}/{name}",
        }],
    }


def make_program(root, version, isolated=False):
    """生成小型但结构完整的模拟发布目录，不运行任何测试 EXE。"""
    root.mkdir(parents=True)
    contents = PRIVATE_CONTENTS_DIR if isolated else "_internal"
    (root / contents).mkdir()
    (root / APP_EXE_NAME).write_bytes(b"MZ-program-" + version.encode("ascii"))
    (root / contents / "updater.exe").write_bytes(b"MZ-helper")
    (root / contents / "python311.dll").write_bytes(b"runtime-" + version.encode("ascii"))
    package.build_manifest(root, version)
    return root


class ReleaseTests(unittest.TestCase):
    """校验版本判断、官方来源、网络失败和完整下载。"""

    def test_numeric_versions_and_old_release_do_not_downgrade(self):
        """数字版本顺序正确，仓库旧的单 EXE 发行版不触发降级。"""
        self.assertGreater(releases.parse_version("v1.10"), releases.parse_version("1.9.9"))
        self.assertEqual(releases.parse_version("1.57"), releases.parse_version("v1.57.0"))
        self.assertIsNone(releases.parse_release({"tag_name": "v1.0.0"}, "1.57.0"))
        for version in (None, "latest", "1.58.0-beta", "-1.58.0", "1.2.3.4"):
            with self.subTest(version=version), self.assertRaises(releases.UpdateError):
                releases.parse_version(version)

    def test_new_release_requires_complete_package_and_valid_digest(self):
        """新版本必须匹配附件名、仓库地址、上传状态、大小及 SHA-256。"""
        release = releases.parse_release(release_data(), "1.57.0")
        self.assertEqual(release.version, "1.58.0")
        mutations = (
            ("name", "AD.exe"), ("digest", ""), ("size", True),
            ("browser_download_url", "https://example.com/update.zip"),
            ("state", "new"),
        )
        for key, value in mutations:
            with self.subTest(key=key):
                data = release_data()
                data["assets"][0][key] = value
                with self.assertRaises(releases.UpdateError):
                    releases.parse_release(data, "1.57.0")

    def test_drafts_and_prereleases_are_not_offered(self):
        """手动检测也只提供稳定版本。"""
        for key in ("draft", "prerelease"):
            data = release_data()
            data[key] = True
            self.assertIsNone(releases.parse_release(data, "1.57.0"))

    def test_metadata_request_and_no_releases_response(self):
        """公开接口不携带令牌，未发布版本和请求限流有明确处理。"""
        response = FakeResponse(json.dumps(release_data()).encode(), "https://api.github.com/test")
        opener = Mock(return_value=response)
        self.assertEqual(releases.fetch_latest_release("1.57.0", opener).version, "1.58.0")
        request = opener.call_args[0][0]
        self.assertNotIn("Authorization", request.headers)
        opener = Mock(side_effect=HTTPError(request.full_url, 404, "Not Found", {}, None))
        self.assertIsNone(releases.fetch_latest_release(opener=opener))
        opener = Mock(side_effect=HTTPError(request.full_url, 403, "Forbidden", {}, None))
        with self.assertRaisesRegex(releases.UpdateError, "受到限制"):
            releases.fetch_latest_release(opener=opener)

    def test_insecure_or_foreign_redirect_is_rejected(self):
        """下载重定向不能改用明文连接或其他站点。"""
        for url in ("http://github.com/a", "https://evil.example/a", "https://user@github.com/a"):
            with self.subTest(url=url), self.assertRaises(releases.UpdateError):
                releases.validate_https_url(url)
        self.assertEqual(
            releases.validate_https_url("https://release-assets.githubusercontent.com/test"),
            "https://release-assets.githubusercontent.com/test",
        )

    def test_download_checks_size_and_hash_and_reports_progress(self):
        """完整下载通过校验，损坏或截断的下载不能保留为可安装文件。"""
        body = b"contents" * 100
        release = releases.parse_release(release_data(payload=body), "1.57.0")
        with TemporaryDirectory() as temporary:
            output = Path(temporary) / "release.zip"
            progress = Mock()
            releases.download_release(
                release, output, progress=progress,
                opener=lambda request: FakeResponse(body, release.download_url),
            )
            self.assertEqual(output.read_bytes(), body)
            progress.assert_called_with(len(body), len(body))
            output.unlink()
            for received in (body[:-1], body + b"extra", b"x" * len(body)):
                with self.subTest(size=len(received)), self.assertRaises(releases.UpdateError):
                    releases.download_release(
                        release, output,
                        opener=lambda request: FakeResponse(received, release.download_url),
                    )
                self.assertFalse(output.exists())

    def test_cancelled_download_cleans_partial_file(self):
        """用户取消后只清理本次未完成下载。"""
        body = b"download"
        release = releases.parse_release(release_data(payload=body), "1.57.0")
        with TemporaryDirectory() as temporary:
            output = Path(temporary) / "release.zip"
            with self.assertRaises(releases.UpdateCancelled):
                releases.download_release(
                    release, output, cancelled=Mock(side_effect=[False, False, True]),
                    opener=lambda request: FakeResponse(body, release.download_url),
                )
            self.assertFalse(output.exists())

    def test_managed_asset_is_preferred_while_legacy_asset_remains_compatible(self):
        """同时存在两个附件时新版选专属包，只有旧附件时仍能检测和下载。"""
        data = release_data()
        managed = dict(data["assets"][0])
        managed["name"] = releases.asset_name_for_version("1.58.0", managed=True)
        managed["browser_download_url"] = managed["browser_download_url"].replace(
            releases.asset_name_for_version("1.58.0"), managed["name"]
        )
        data["assets"].append(managed)
        self.assertEqual(releases.parse_release(data, "1.57.0").download_url, managed["browser_download_url"])
        data["assets"] = [managed]
        self.assertEqual(releases.parse_release(data, "1.57.0").download_url, managed["browser_download_url"])

    def test_invalid_or_duplicate_managed_asset_does_not_fall_back_to_shared_runtime(self):
        """专属包存在但损坏或重复时拒绝升级，不能悄悄回退到共享运行库附件。"""
        for duplicate in (False, True):
            data = release_data()
            managed = dict(data["assets"][0])
            managed["name"] = releases.asset_name_for_version("1.58.0", managed=True)
            managed["browser_download_url"] = managed["browser_download_url"].replace(
                releases.asset_name_for_version("1.58.0"), managed["name"]
            )
            if duplicate:
                data["assets"].extend([managed, managed.copy()])
            else:
                managed["digest"] = "invalid"
                data["assets"].append(managed)
            with self.subTest(duplicate=duplicate), self.assertRaises(releases.UpdateError):
                releases.parse_release(data, "1.57.0")


class PackageTests(unittest.TestCase):
    """完整包验证和恶意路径检查。"""

    def test_release_builder_produces_installable_zip_and_checksum(self):
        """发布工具生成的清单和附件可由客户端原样解压校验。"""
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            program = make_program(root / "program", "1.58.0")
            archive = create_release_zip(program, root / "releases", "1.58.0")
            payload = package.extract_package(archive, root / "unpacked", "1.58.0")
            self.assertEqual(payload.name, APP_NAME)
            self.assertEqual(package.read_manifest(payload)["version"], "1.58.0")
            self.assertIn(package.file_sha256(archive), archive.with_suffix(".zip.sha256").read_text())

    def test_manifest_rejects_tampering_missing_files_and_wrong_version(self):
        """任一文件被修改、丢失或版本不符均禁止安装。"""
        with TemporaryDirectory() as temporary:
            program = make_program(Path(temporary) / "program", "1.58.0")
            with self.assertRaisesRegex(releases.UpdateError, "版本"):
                package.validate_payload(program, "1.59.0")
            executable = program / APP_EXE_NAME
            original = executable.read_bytes()
            executable.write_bytes(b"tampered")
            with self.assertRaisesRegex(releases.UpdateError, "校验失败"):
                package.validate_payload(program, "1.58.0")
            executable.write_bytes(original)
            (program / "_internal" / "python311.dll").unlink()
            with self.assertRaisesRegex(releases.UpdateError, "文件集合"):
                package.validate_payload(program, "1.58.0")

    def test_archive_paths_are_checked_before_extracting_any_file(self):
        """路径穿越、盘符、Windows 设备名和反斜杠不会写入任何解压文件。"""
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            for index, bad_name in enumerate((
                "../outside.txt", APP_NAME + "/../outside.txt", "C:/outside.txt",
                APP_NAME + "/NUL.txt", APP_NAME + "/dir\\file", APP_NAME + "/bad. ",
            )):
                with self.subTest(path=bad_name):
                    archive = root / f"bad-{index}.zip"
                    with zipfile.ZipFile(archive, "w") as output:
                        info = zipfile.ZipInfo("placeholder")
                        # 保留恶意 ZIP 的原始名称，不让测试写入器先规范化反斜杠。
                        info.filename = bad_name
                        output.writestr(info, b"bad")
                    destination = root / f"unpacked-{index}"
                    with self.assertRaises(releases.UpdateError):
                        package.extract_package(archive, destination, "1.58.0")
                    self.assertFalse(destination.exists())
            self.assertFalse((root / "outside.txt").exists())

    def test_archive_rejects_symlinks_duplicates_and_expansion_limit(self):
        """拒绝符号链接、大小写重复路径及超限解压大小。"""
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "symlink.zip"
            with zipfile.ZipFile(archive, "w") as output:
                link = zipfile.ZipInfo(APP_NAME + "/link")
                link.external_attr = (stat.S_IFLNK | 0o777) << 16
                output.writestr(link, "outside")
            with self.assertRaises(releases.UpdateError):
                package.extract_package(archive, root / "links", "1.58.0")
            archive = root / "duplicate.zip"
            with zipfile.ZipFile(archive, "w") as output:
                output.writestr(APP_NAME + "/file.dll", b"1")
                output.writestr(APP_NAME + "/FILE.dll", b"2")
            with self.assertRaises(releases.UpdateError):
                package.extract_package(archive, root / "duplicate", "1.58.0")
            archive = root / "expanded.zip"
            with zipfile.ZipFile(archive, "w") as output:
                output.writestr(APP_NAME + "/large.bin", b"1234")
            with patch.object(package, "MAX_EXPANDED_BYTES", 1):
                with self.assertRaisesRegex(releases.UpdateError, "解压大小"):
                    package.extract_package(archive, root / "oversize", "1.58.0")

    def test_staging_cleanup_requires_ownership_marker(self):
        """缺少本程序身份标记的目录不能被更新清理逻辑删除。"""
        with TemporaryDirectory(prefix=package.STAGING_PREFIX) as temporary:
            root = Path(temporary)
            (root / "keep.txt").write_text("user-data")
            with self.assertRaises((releases.UpdateError, OSError)):
                package.discard_staging_directory(root)
            self.assertTrue((root / "keep.txt").exists())
        staging = package.create_staging_directory()
        package.discard_staging_directory(staging)
        self.assertFalse(staging.exists())

    def test_isolated_package_uses_private_runtime_manifest_and_asset_name(self):
        """专属包的 ZIP 名、清单名和运行库目录一致，仍通过完整性验证。"""
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            program = make_program(root / "program", "1.58.0", isolated=True)
            archive = create_release_zip(program, root / "releases", "1.58.0")
            self.assertEqual(archive.name, releases.asset_name_for_version("1.58.0", managed=True))
            payload = package.extract_package(archive, root / "unpacked", "1.58.0")
            self.assertEqual(package.read_manifest(payload)["layout"], "isolated")
            self.assertTrue((payload / PRIVATE_MANIFEST_NAME).is_file())
            self.assertFalse((payload / "_internal").exists())
            self.assertTrue((payload / PRIVATE_CONTENTS_DIR / "updater.exe").is_file())

    def test_private_manifest_does_not_read_unrelated_generic_manifest(self):
        """混放目录有其他应用的通用清单时，本工具只读取自己的专属清单。"""
        with TemporaryDirectory() as temporary:
            program = make_program(Path(temporary) / "program", "1.58.0", isolated=True)
            (program / "update-manifest.json").write_text("other application", encoding="utf-8")
            self.assertEqual(package.read_manifest(program)["version"], "1.58.0")
            # 安装目录允许未知文件；下载候选包仍必须严格匹配自己的清单。
            with self.assertRaisesRegex(releases.UpdateError, "文件集合"):
                package.validate_payload(program)

    def test_manifest_cannot_claim_files_outside_its_runtime_namespace(self):
        """两种清单均拒绝外部软件路径，专属清单也不能声明旧共享 DLL。"""
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            for isolated in (False, True):
                program = make_program(root / str(isolated), "1.58.0", isolated=isolated)
                path = package.manifest_path_for(program)
                original = json.loads(path.read_text(encoding="utf-8"))
                bad_names = ["other.exe", "other/config.json"]
                if isolated:
                    bad_names.append("_internal/foreign.dll")
                for name in bad_names:
                    data = dict(original, files=dict(original["files"]))
                    data["files"][name] = "0" * 64
                    path.write_text(json.dumps(data), encoding="utf-8")
                    with self.subTest(isolated=isolated, path=name), self.assertRaisesRegex(releases.UpdateError, "非本工具"):
                        package.read_manifest(program)

    def test_manifest_name_layout_and_identity_must_agree(self):
        """名称、运行库布局、软件身份不一致时不进行猜测或回退。"""
        with TemporaryDirectory() as temporary:
            program = make_program(Path(temporary) / "program", "1.58.0", isolated=True)
            path = package.manifest_path_for(program)
            original = json.loads(path.read_text(encoding="utf-8"))
            for key, value in (("layout", "legacy"), ("layout", "unknown"), ("app_id", "other-tool")):
                path.write_text(json.dumps(dict(original, **{key: value})), encoding="utf-8")
                with self.subTest(key=key, value=value), self.assertRaises(releases.UpdateError):
                    package.read_manifest(program)

    def test_build_script_generates_both_layouts_without_invoking_compiler(self):
        """模拟 PyInstaller 产物验证构建参数和双附件，不执行编译或用户 EXE。"""
        from app_info import APP_VERSION
        from tools import build_release as builder
        calls = []

        def simulate_pyinstaller(arguments):
            """仅在构建器自有临时目录生成少量测试字节，代替真实编译。"""
            calls.append(arguments)
            destination = Path(arguments[arguments.index("--distpath") + 1])
            if "--onefile" in arguments:
                destination.mkdir(parents=True)
                (destination / "updater.exe").write_bytes(b"test helper")
            else:
                contents = arguments[arguments.index("--contents-directory") + 1]
                make_program(destination / APP_NAME, APP_VERSION, isolated=contents == PRIVATE_CONTENTS_DIR)

        with TemporaryDirectory() as temporary:
            output = Path(temporary) / "release"
            with patch.object(builder, "run_pyinstaller", side_effect=simulate_pyinstaller):
                with patch("builtins.print"):
                    primary = builder.build_release(output)
            self.assertEqual(len(calls), 3)
            self.assertEqual(primary.name, releases.asset_name_for_version(APP_VERSION, managed=True))
            self.assertTrue((output / releases.asset_name_for_version(APP_VERSION)).is_file())
            self.assertTrue((output / APP_NAME / PRIVATE_MANIFEST_NAME).is_file())
            self.assertFalse((output / "legacy").exists())
            with zipfile.ZipFile(output / releases.asset_name_for_version(APP_VERSION)) as archive:
                self.assertIn(APP_NAME + "/update-manifest.json", archive.namelist())


class ControllerTests(unittest.TestCase):
    """验证协调层失败清理，不访问用户程序目录。"""

    def test_failed_download_removes_only_its_staging_directory(self):
        """下载失败后不遗留半成品暂存文件。"""
        staging = package.create_staging_directory()
        with patch.object(controller, "create_staging_directory", return_value=staging):
            with patch.object(controller, "download_release", side_effect=releases.UpdateError("断网")):
                with self.assertRaisesRegex(releases.UpdateError, "断网"):
                    controller.prepare_update(object())
        self.assertFalse(staging.exists())

    def test_helper_launch_clears_stale_status_and_uses_independent_environment(self):
        """更新器在主程序目录外启动，重试时不能沿用旧就绪标记。"""
        staging = package.create_staging_directory()
        self.addCleanup(package.discard_staging_directory, staging)
        with TemporaryDirectory() as temporary:
            helper = Path(temporary) / "helper.exe"
            helper.write_bytes(b"MZ-helper")
            (staging / installer.HANDOFF_NAME).write_text('{"status":"ready"}')
            (staging / "cancel.request").write_text("cancel")
            release = releases.parse_release(release_data(), "1.57.0")
            prepared = controller.PreparedUpdate(release, staging, staging / "unpacked")
            with patch.object(controller, "can_install_update", return_value=True):
                with patch.object(controller, "resource_path", return_value=str(helper)):
                    with patch.object(controller.subprocess, "Popen") as popen:
                        controller.launch_update_helper(prepared)
            self.assertFalse((staging / installer.HANDOFF_NAME).exists())
            self.assertFalse((staging / "cancel.request").exists())
            self.assertEqual(popen.call_args.kwargs["env"]["PYINSTALLER_RESET_ENVIRONMENT"], "1")
            self.assertEqual(Path(popen.call_args.args[0][0]).parent, staging)


if __name__ == "__main__":
    unittest.main()
