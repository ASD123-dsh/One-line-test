#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""更新元数据、下载、完整包和安装回滚测试，使用独占临时目录与模拟网络。"""

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

from app_info import APP_EXE_NAME, APP_ID, APP_NAME, GITHUB_REPOSITORY
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


def make_program(root, version):
    """生成小型但结构完整的模拟发布目录，不运行任何测试 EXE。"""
    root.mkdir(parents=True)
    (root / "_internal").mkdir()
    (root / APP_EXE_NAME).write_bytes(b"MZ-program-" + version.encode("ascii"))
    (root / "_internal" / "updater.exe").write_bytes(b"MZ-helper")
    (root / "_internal" / "python311.dll").write_bytes(b"runtime-" + version.encode("ascii"))
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


class InstallationTests(unittest.TestCase):
    """使用模拟程序目录验证真实文件替换、跨盘准备和回滚，不执行假 EXE。"""

    def setUp(self):
        """准备旧版目录、新版完整包和独占更新任务。"""
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.target = make_program(self.root / APP_NAME, "1.57.0")
        self.staging = package.create_staging_directory()
        self.addCleanup(package.discard_staging_directory, self.staging)
        program = make_program(self.root / "new", "1.58.0")
        archive = create_release_zip(program, self.root / "releases", "1.58.0")
        (self.staging / "release.zip").write_bytes(archive.read_bytes())
        package.extract_package(archive, self.staging / "unpacked", "1.58.0")
        self.job_path = self.staging / installer.JOB_NAME
        self.job_data = {
            "schema": 1, "app_id": APP_ID, "parent_pid": os.getpid(),
            "target_dir": str(self.target.resolve()), "version": "1.58.0",
            "sha256": package.file_sha256(archive),
        }
        self.job_path.write_text(json.dumps(self.job_data), encoding="utf-8")

    def test_success_preserves_old_backup_and_user_exports_without_old_dlls(self):
        """新目录与目标同盘，用户文件保留，旧版完整备份且不复制过期运行库。"""
        (self.target / "用户包组.json").write_text("user packets", encoding="utf-8")
        (self.target / "_internal" / "obsolete.dll").write_bytes(b"old-dll")
        job = installer.load_install_job(self.job_path)
        plan = installer.prepare_installation(job)
        self.assertEqual(plan.candidate.parent, self.target.parent)
        launched = []
        backup = installer.apply_installation(plan, launcher=launched.append)
        self.assertEqual(package.read_manifest(self.target)["version"], "1.58.0")
        self.assertEqual(package.read_manifest(backup)["version"], "1.57.0")
        self.assertEqual((self.target / "用户包组.json").read_text(encoding="utf-8"), "user packets")
        self.assertFalse((self.target / "_internal" / "obsolete.dll").exists())
        self.assertTrue((backup / "_internal" / "obsolete.dll").exists())
        self.assertEqual(launched, [self.target / APP_EXE_NAME])

    def test_replace_failure_restores_old_version(self):
        """第二步目录改名失败时，旧版立即恢复且不启动新程序。"""
        plan = installer.prepare_installation(installer.load_install_job(self.job_path))
        original_rename = os.rename

        def failing_rename(source, destination):
            """模拟安装候选目录被系统拦截。"""
            if Path(source) == plan.candidate:
                raise OSError("模拟文件占用")
            return original_rename(source, destination)

        launcher = Mock()
        with patch.object(installer.os, "rename", side_effect=failing_rename):
            with self.assertRaisesRegex(releases.UpdateError, "旧版本已恢复"):
                installer.apply_installation(plan, launcher)
        self.assertEqual(package.read_manifest(self.target)["version"], "1.57.0")
        launcher.assert_not_called()

    def test_locked_main_executable_stops_before_directory_replacement(self):
        """主程序被其他实例占用时不移动或覆盖当前目录。"""
        plan = installer.prepare_installation(installer.load_install_job(self.job_path))
        with patch.object(Path, "open", side_effect=PermissionError("占用")):
            with patch.object(installer.os, "rename") as rename:
                with self.assertRaisesRegex(releases.UpdateError, "关闭其他工具窗口"):
                    installer.apply_installation(plan)
                rename.assert_not_called()
        self.assertEqual(package.read_manifest(self.target)["version"], "1.57.0")

    def test_transient_windows_directory_lock_is_retried(self):
        """Windows 目录短暂共享占用后重试成功，不提前恢复旧版或中断升级。"""
        plan = installer.prepare_installation(installer.load_install_job(self.job_path))
        original_rename = os.rename
        attempts = []

        def temporarily_locked(source, destination):
            """只让候选目录前两次改名失败，其他文件操作保持真实行为。"""
            if Path(source) == plan.candidate:
                attempts.append(source)
                if len(attempts) <= 2:
                    error = PermissionError(13, "模拟目录共享占用")
                    error.winerror = 32
                    raise error
            return original_rename(source, destination)

        launcher = Mock()
        with patch.object(installer.os, "rename", side_effect=temporarily_locked):
            with patch.object(installer.time, "sleep") as sleep:
                installer.apply_installation(plan, launcher)
        self.assertEqual(len(attempts), 3)
        self.assertEqual(sleep.call_count, 2)
        self.assertEqual(package.read_manifest(self.target)["version"], "1.58.0")
        self.assertEqual(package.read_manifest(plan.backup)["version"], "1.57.0")
        launcher.assert_called_once_with(self.target / APP_EXE_NAME)

    def test_directory_retry_is_bounded_and_keeps_original_windows_error(self):
        """持续占用不能无限等待，达到上限后仍保留原始系统错误对象。"""
        for winerror in (5, 32, 33):
            with self.subTest(winerror=winerror):
                error = PermissionError(13, "持续占用")
                error.winerror = winerror
                with patch.object(installer.os, "rename", side_effect=error) as rename:
                    with patch.object(installer.time, "sleep") as sleep:
                        with self.assertRaises(PermissionError) as raised:
                            installer._rename_directory("source", "destination")
                self.assertIs(raised.exception, error)
                self.assertEqual(error.rename_attempts, installer.RENAME_MAX_ATTEMPTS)
                self.assertEqual(error.rename_errors, [winerror] * installer.RENAME_MAX_ATTEMPTS)
                self.assertEqual(rename.call_count, installer.RENAME_MAX_ATTEMPTS)
                self.assertEqual(sleep.call_count, installer.RENAME_MAX_ATTEMPTS - 1)

    def test_nontransient_rename_error_is_not_retried(self):
        """路径冲突、路径丢失和没有 Windows 错误码的异常不能被重试掩盖。"""
        for winerror in (183, 2, None):
            with self.subTest(winerror=winerror):
                error = OSError(17, "路径冲突或丢失")
                if winerror is not None:
                    error.winerror = winerror
                with patch.object(installer.os, "rename", side_effect=error) as rename:
                    with patch.object(installer.time, "sleep") as sleep:
                        with self.assertRaises(OSError):
                            installer._rename_directory("source", "destination")
                rename.assert_called_once_with("source", "destination")
                sleep.assert_not_called()

    def test_temporary_backup_directory_lock_is_retried(self):
        """备份旧目录遇到短暂占用时也能重试，不局限于新版候选目录。"""
        plan = installer.prepare_installation(installer.load_install_job(self.job_path))
        original_rename = os.rename
        attempts = []

        def temporarily_locked_backup(source, destination):
            """只让旧目录的前两次备份改名出现原生共享错误。"""
            if Path(source) == plan.target:
                attempts.append(source)
                if len(attempts) <= 2:
                    error = PermissionError(13, "模拟备份目录占用")
                    error.winerror = 32
                    raise error
            return original_rename(source, destination)

        with patch.object(installer.os, "rename", side_effect=temporarily_locked_backup):
            with patch.object(installer.time, "sleep") as sleep:
                installer.apply_installation(plan, Mock())
        self.assertEqual(len(attempts), 3)
        self.assertEqual(sleep.call_count, 2)
        self.assertEqual(package.read_manifest(self.target)["version"], "1.58.0")
        self.assertEqual(package.read_manifest(plan.backup)["version"], "1.57.0")

    def test_rollback_directory_rename_also_retries_temporary_lock(self):
        """安装失败后的恢复也使用有限重试，尽量避免备份不能恢复。"""
        plan = installer.prepare_installation(installer.load_install_job(self.job_path))
        original_rename = os.rename
        recoveries = []

        def locked_recovery(source, destination):
            """候选目录永久冲突，旧版恢复目录只有前两次短暂占用。"""
            if Path(source) == plan.candidate:
                raise OSError("模拟候选目录安装失败")
            if Path(source) == plan.backup:
                recoveries.append(source)
                if len(recoveries) <= 2:
                    error = PermissionError(13, "模拟恢复目录占用")
                    error.winerror = 5
                    raise error
            return original_rename(source, destination)

        launcher = Mock()
        with patch.object(installer.os, "rename", side_effect=locked_recovery):
            with patch.object(installer.time, "sleep") as sleep:
                with self.assertRaisesRegex(releases.UpdateError, "模拟候选目录安装失败"):
                    installer.apply_installation(plan, launcher)
        self.assertEqual(len(recoveries), 3)
        self.assertEqual(sleep.call_count, 2)
        self.assertEqual(package.read_manifest(self.target)["version"], "1.57.0")
        launcher.assert_not_called()

    def test_backup_conflict_does_not_overwrite_existing_directory(self):
        """已有非空备份目录不能被删除或覆盖，原程序保持完整。"""
        plan = installer.prepare_installation(installer.load_install_job(self.job_path))
        plan.backup.mkdir()
        sentinel = plan.backup / "keep.txt"
        sentinel.write_text("do not overwrite", encoding="utf-8")
        with self.assertRaisesRegex(releases.UpdateError, "原程序目录未替换"):
            installer.apply_installation(plan, Mock())
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "do not overwrite")
        self.assertEqual(package.read_manifest(self.target)["version"], "1.57.0")

    def test_failure_status_records_root_windows_error_and_traceback(self):
        """错误记录保留失败阶段、原始 Windows 错误码及完整异常链。"""
        native_error = PermissionError(13, "原始共享占用详情")
        native_error.winerror = 32
        error = releases.UpdateError("外层安装失败提示")
        error.__cause__ = native_error
        parent = Mock()
        parent.wait.side_effect = error
        with patch.object(installer, "WindowsParentProcess", return_value=parent):
            self.assertEqual(installer.run_installer(self.job_path), 1)
        status = json.loads((self.staging / installer.HANDOFF_NAME).read_text(encoding="utf-8"))
        self.assertEqual(status["stage"], "等待主程序退出")
        self.assertEqual(status["winerror"], 32)
        self.assertEqual(status["errno"], 13)
        self.assertEqual(status["error_type"], "UpdateError")
        self.assertIn("原始共享占用详情", status["detail"])
        self.assertIn("外层安装失败提示", status["detail"])
        self.assertEqual(package.read_manifest(self.target)["version"], "1.57.0")

    def test_restart_failure_restores_and_relaunches_old_version(self):
        """无法创建新版进程时回滚，并尝试重新启动旧版。"""
        plan = installer.prepare_installation(installer.load_install_job(self.job_path))
        launcher = Mock(side_effect=[OSError("无法启动"), None])
        with self.assertRaisesRegex(releases.UpdateError, "旧版本已恢复"):
            installer.apply_installation(plan, launcher)
        self.assertEqual(package.read_manifest(self.target)["version"], "1.57.0")
        self.assertEqual(launcher.call_count, 2)

    def test_job_rejects_foreign_directory_and_tampered_archive(self):
        """没有本工具清单的目录或下载后被修改的包不能作为安装目标。"""
        self.job_data["target_dir"] = str(self.root)
        self.job_path.write_text(json.dumps(self.job_data), encoding="utf-8")
        with self.assertRaises(releases.UpdateError):
            installer.load_install_job(self.job_path)
        self.job_data["target_dir"] = str(self.target.resolve())
        self.job_path.write_text(json.dumps(self.job_data), encoding="utf-8")
        (self.staging / "release.zip").write_bytes(b"changed")
        with self.assertRaisesRegex(releases.UpdateError, "发生变化"):
            installer.load_install_job(self.job_path)
        self.assertEqual(package.read_manifest(self.target)["version"], "1.57.0")

    def test_parent_timeout_keeps_old_program_untouched(self):
        """主程序没有退出时不替换文件，就绪握手之后的失败会被记录。"""
        parent = Mock()
        parent.wait.side_effect = releases.UpdateError("等待退出超时")
        with patch.object(installer, "WindowsParentProcess", return_value=parent):
            result = installer.run_installer(self.job_path)
        self.assertEqual(result, 1)
        self.assertEqual(package.read_manifest(self.target)["version"], "1.57.0")
        status = json.loads((self.staging / installer.HANDOFF_NAME).read_text(encoding="utf-8"))
        self.assertEqual(status["status"], "error")
        self.assertIn("超时", status["message"])
        self.assertEqual(list(self.target.parent.glob(".sifexe-install-*")), [])

    def test_restarted_application_gets_independent_packaged_environment(self):
        """新程序不能依赖即将退出的更新器的临时运行库环境。"""
        executable = self.target / APP_EXE_NAME
        with patch.object(installer.subprocess, "Popen") as popen:
            installer.launch_application(executable)
        self.assertEqual(popen.call_args.kwargs["env"]["PYINSTALLER_RESET_ENVIRONMENT"], "1")
        self.assertEqual(popen.call_args.kwargs["cwd"], str(self.target))

    @unittest.skipUnless(os.name == "nt", "仅 Windows 有进程句柄校验")
    def test_windows_parent_handle_verifies_real_process_image(self):
        """实际读取本测试进程路径，确认 64 位句柄与路径校验工作正常。"""
        import sys
        parent = installer.WindowsParentProcess(os.getpid(), Path(sys.executable))
        try:
            with self.assertRaises(releases.UpdateCancelled):
                parent.wait(cancelled=lambda: True)
        finally:
            parent.close()
        self.assertIsNone(parent.handle)


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
