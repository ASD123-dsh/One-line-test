#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""验证混放目录中的逐文件升级、最小备份、回滚和自动清理，不运行测试 EXE。"""

import json
import os
import unittest
import uuid
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from app_info import APP_EXE_NAME, APP_ID, MANIFEST_NAME, PRIVATE_CONTENTS_DIR, PRIVATE_MANIFEST_NAME
from test_updates import make_program
from tools.build_release import create_release_zip
from updating import file_transaction as transaction
from updating import installer, package, releases


class ManagedInstallationTests(unittest.TestCase):
    """所有文件和锁均位于测试独占目录，其他应用用普通文件模拟。"""

    def setUp(self):
        """准备任意名称的混放目录、旧专属运行库和完整新版候选包。"""
        self.temporary = TemporaryDirectory(prefix="sifexe-managed-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.target = make_program(self.root / "自制程序_解密", "1.57.0", isolated=True)
        program = make_program(self.root / "new", "1.58.0", isolated=True)
        self.set_payload(program)

    def set_payload(self, program):
        """每次使用新的自有暂存目录和附件，不覆盖用户发布包。"""
        self.staging = package.create_staging_directory()
        self.addCleanup(package.discard_staging_directory, self.staging)
        version = package.read_manifest(program)["version"]
        archive = create_release_zip(program, self.root / ("release-" + uuid.uuid4().hex), version)
        (self.staging / "release.zip").write_bytes(archive.read_bytes())
        package.extract_package(archive, self.staging / "unpacked", version)
        self.job_data = {
            "schema": 1, "app_id": APP_ID, "parent_pid": os.getpid(),
            "target_dir": str(self.target), "version": version, "sha256": package.file_sha256(archive),
        }
        self.job_path = self.staging / installer.JOB_NAME
        self.job_path.write_text(json.dumps(self.job_data), encoding="utf-8")

    def prepare(self):
        """通过正式任务解析入口准备文件事务。"""
        self.job = installer.load_install_job(self.job_path)
        return installer.prepare_installation(self.job)

    def add_foreign_files(self):
        """放入其他 EXE、共享运行库、同名通用清单和用户数据，记录内容与文件身份。"""
        files = {
            "其他应用.exe": b"other application", "其他应用/config.ini": b"other config",
            "用户包组.json": b"user packets", "notes.txt": b"user notes",
            "_internal/updater.exe": b"foreign updater",
            "_internal/python311.dll": b"foreign runtime",
            MANIFEST_NAME: b"foreign application manifest",
        }
        for name, contents in files.items():
            path = self.target / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(contents)
        return {name: self.snapshot(self.target / name) for name in files}

    def snapshot(self, path):
        """同时比较字节、修改时间和文件标识，确认其他文件没有被搬动或重写。"""
        info = path.stat()
        return path.read_bytes(), info.st_mtime_ns, info.st_ino

    def assert_foreign_unchanged(self, snapshots):
        """验证其他应用及用户文件保留在原位置且身份不变。"""
        for name, snapshot in snapshots.items():
            with self.subTest(foreign=name):
                self.assertEqual(self.snapshot(self.target / name), snapshot)

    def status(self):
        """读取本测试更新任务的状态记录。"""
        return json.loads((self.staging / installer.HANDOFF_NAME).read_text(encoding="utf-8"))

    def test_mixed_directory_name_is_supported_without_changing_other_files(self):
        """任意目录名可升级，其他应用、共享依赖和用户文件保持原位不变。"""
        snapshots = self.add_foreign_files()
        directory_id = self.target.stat().st_ino
        plan = self.prepare()
        installer.apply_installation(plan, Mock())
        installer.complete_installation(self.job, plan)
        self.assertEqual(package.read_manifest(self.target)["version"], "1.58.0")
        self.assertEqual(self.target.stat().st_ino, directory_id)
        self.assert_foreign_unchanged(snapshots)
        self.assertFalse(plan.workspace.exists())
        self.assertFalse((self.target / transaction.LOCK_NAME).exists())
        self.assertTrue(self.status()["backup_removed"])

    def test_backup_contains_only_changed_owned_files(self):
        """最小备份只包含本工具的待替换文件，不包含其他应用或未改动依赖。"""
        snapshots = self.add_foreign_files()
        plan = self.prepare()
        actual = {path.relative_to(plan.backup).as_posix() for path in package.iter_regular_files(plan.backup)}
        self.assertEqual(actual, set(plan.old_files))
        self.assertEqual(actual, {APP_EXE_NAME, PRIVATE_MANIFEST_NAME, PRIVATE_CONTENTS_DIR + "/python311.dll"})
        self.assertNotIn(PRIVATE_CONTENTS_DIR + "/updater.exe", actual)
        self.assert_foreign_unchanged(snapshots)

    def test_legacy_migration_does_not_touch_or_backup_shared_runtime(self):
        """旧版迁移到专属运行库时，共用的整个 _internal 保留且不进入本次备份。"""
        self.target = make_program(self.root / "旧版混放目录", "1.57.0")
        (self.target / "_internal" / "foreign.dll").write_bytes(b"other app")
        original = {path.name: self.snapshot(path) for path in (self.target / "_internal").iterdir()}
        program = make_program(self.root / "migration-new", "1.58.0", isolated=True)
        self.set_payload(program)
        plan = self.prepare()
        self.assertEqual(set(plan.old_files), {APP_EXE_NAME, MANIFEST_NAME})
        installer.apply_installation(plan, Mock())
        installer.complete_installation(self.job, plan)
        self.assertEqual(package.read_manifest(self.target)["layout"], "isolated")
        self.assertFalse((self.target / MANIFEST_NAME).exists())
        for path in (self.target / "_internal").iterdir():
            self.assertEqual(self.snapshot(path), original[path.name])

    def test_unchanged_managed_file_is_not_rewritten_or_backed_up(self):
        """摘要相同的本工具依赖不重复改写，避免不必要占用和备份开销。"""
        path = self.target / PRIVATE_CONTENTS_DIR / "updater.exe"
        original = self.snapshot(path)
        plan = self.prepare()
        self.assertNotIn(PRIVATE_CONTENTS_DIR + "/updater.exe", plan.changes)
        installer.apply_installation(plan, Mock())
        self.assertEqual(self.snapshot(path), original)

    def test_old_private_obsolete_file_is_retired_but_foreign_neighbor_stays(self):
        """只移除旧清单中废弃的专属文件，未列入清单的同目录文件不动。"""
        obsolete = self.target / PRIVATE_CONTENTS_DIR / "obsolete.dll"
        obsolete.write_bytes(b"owned old dll")
        package.build_manifest(self.target, "1.57.0")
        foreign = self.target / PRIVATE_CONTENTS_DIR / "customer-file.txt"
        foreign.write_bytes(b"unknown file")
        original = self.snapshot(foreign)
        plan = self.prepare()
        installer.apply_installation(plan, Mock())
        self.assertFalse(obsolete.exists())
        self.assertEqual((plan.backup / PRIVATE_CONTENTS_DIR / "obsolete.dll").read_bytes(), b"owned old dll")
        self.assertEqual(self.snapshot(foreign), original)

    def test_unowned_new_file_collision_is_rejected_before_any_update(self):
        """新版本文件撞上未受管理的同名文件时停止，不覆盖并冒认其他文件。"""
        program = make_program(self.root / "collision-new", "1.58.0", isolated=True)
        (program / PRIVATE_CONTENTS_DIR / "new.dll").write_bytes(b"new owned dll")
        package.build_manifest(program, "1.58.0")
        self.set_payload(program)
        collision = self.target / PRIVATE_CONTENTS_DIR / "new.dll"
        collision.write_bytes(b"other app dll")
        with self.assertRaisesRegex(releases.UpdateError, "非本工具文件占用"):
            self.prepare()
        self.assertEqual(collision.read_bytes(), b"other app dll")
        self.assertEqual(package.read_manifest(self.target)["version"], "1.57.0")
        self.assertEqual(list(self.target.glob(transaction.WORK_PREFIX + "*")), [])

    def test_new_collision_after_preparation_is_not_overwritten_or_deleted(self):
        """准备后出现的新路径冲突同样不覆盖，回滚也不能删除该外来文件。"""
        program = make_program(self.root / "racing-new", "1.58.0", isolated=True)
        (program / PRIVATE_CONTENTS_DIR / "new.dll").write_bytes(b"owned dll")
        package.build_manifest(program, "1.58.0")
        self.set_payload(program)
        plan = self.prepare()
        collision = self.target / PRIVATE_CONTENTS_DIR / "new.dll"
        collision.write_bytes(b"appeared after prepare")
        with self.assertRaisesRegex(releases.UpdateError, "旧版本文件已恢复"):
            installer.apply_installation(plan, Mock())
        self.assertEqual(collision.read_bytes(), b"appeared after prepare")
        self.assertEqual(package.read_manifest(self.target)["version"], "1.57.0")

    def test_modified_owned_file_is_not_silently_overwritten(self):
        """受管理文件与安装清单不符时停止，避免吞掉人工修改。"""
        (self.target / APP_EXE_NAME).write_bytes(b"user customized exe")
        with self.assertRaisesRegex(releases.UpdateError, "已被修改"):
            self.prepare()
        self.assertEqual((self.target / APP_EXE_NAME).read_bytes(), b"user customized exe")

    def test_unrelated_links_are_not_traversed_or_rejected(self):
        """其他应用目录即使包含链接，也不参与一线通的文件检查和迁移。"""
        foreign = self.target / "foreign-link"
        foreign.mkdir()
        original = transaction.is_reparse_point

        def reject_foreign_inspection(path):
            """如果升级器触碰无关目录，测试立即失败。"""
            if foreign == Path(path) or foreign in Path(path).parents:
                raise AssertionError("不应检查其他应用目录")
            return original(path)

        with patch.object(transaction, "is_reparse_point", side_effect=reject_foreign_inspection):
            plan = self.prepare()
            installer.apply_installation(plan, Mock())
            installer.complete_installation(self.job, plan)
        self.assertTrue(foreign.exists())

    def test_owned_path_link_is_rejected_before_backup(self):
        """只对本工具会访问的路径拒绝链接，防止写入安装目录之外。"""
        original = transaction.is_reparse_point
        private = self.target / PRIVATE_CONTENTS_DIR

        def private_is_link(path):
            """模拟专属依赖目录变成联接点。"""
            return Path(path) == private or original(path)

        with patch.object(transaction, "is_reparse_point", side_effect=private_is_link):
            with self.assertRaisesRegex(releases.UpdateError, "链接"):
                self.prepare()
        noncanonical = self.target / ".." / self.target.name
        with self.assertRaisesRegex(releases.UpdateError, "根目录无效"):
            transaction.owned_path(noncanonical, APP_EXE_NAME)

    def test_manifest_cannot_claim_same_level_other_application(self):
        """即使清单被修改，也不能把同级其他 EXE 或用户文件纳入更新范围。"""
        path = self.target / PRIVATE_MANIFEST_NAME
        data = json.loads(path.read_text(encoding="utf-8"))
        data["files"]["other.exe"] = "0" * 64
        path.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaisesRegex(releases.UpdateError, "非本工具"):
            installer.load_install_job(self.job_path)

    def test_shared_runtime_payload_is_rejected_without_touching_current_files(self):
        """新事务不把共享运行库包安装进混放目录，旧布局仅作为迁移来源读取。"""
        program = make_program(self.root / "legacy-payload", "1.58.0")
        self.set_payload(program)
        with self.assertRaisesRegex(releases.UpdateError, "专属运行库"):
            self.prepare()
        self.assertEqual(package.read_manifest(self.target)["version"], "1.57.0")

    def test_second_update_is_blocked_without_deleting_first_lock(self):
        """同目录并行更新被拦截，不覆盖或删除第一个任务的锁和备份。"""
        plan = self.prepare()
        lock = self.snapshot(self.target / transaction.LOCK_NAME)
        with self.assertRaisesRegex(releases.UpdateError, "已有更新任务"):
            installer.prepare_installation(self.job)
        self.assertEqual(self.snapshot(self.target / transaction.LOCK_NAME), lock)
        self.assertTrue(plan.backup.exists())

    def test_partial_file_replacement_failure_restores_owned_files_only(self):
        """替换途中失败时恢复已改动文件，其他应用字节、时间与文件身份不变。"""
        snapshots = self.add_foreign_files()
        plan = self.prepare()
        original = transaction.os.replace

        def fail_main_replace(source, destination):
            """先允许运行库更新，再模拟主 EXE 替换被拒绝。"""
            if Path(source) == plan.candidate / APP_EXE_NAME:
                raise OSError("模拟主程序替换失败")
            return original(source, destination)

        with patch.object(transaction.os, "replace", side_effect=fail_main_replace):
            with self.assertRaisesRegex(releases.UpdateError, "旧版本文件已恢复"):
                installer.apply_installation(plan, Mock())
        self.assertEqual(package.read_manifest(self.target)["version"], "1.57.0")
        self.assertEqual((self.target / PRIVATE_CONTENTS_DIR / "python311.dll").read_bytes(), b"runtime-1.57.0")
        self.assertEqual(plan.state, "rolled_back")
        self.assert_foreign_unchanged(snapshots)

    def test_each_mutation_failure_can_restore_original_owned_files(self):
        """逐一在新建、替换和废弃文件步骤注入失败，验证每个中间状态均可恢复。"""
        program = make_program(self.root / "all-steps-new", "1.58.0", isolated=True)
        (program / PRIVATE_CONTENTS_DIR / "new.dll").write_bytes(b"new private file")
        package.build_manifest(program, "1.58.0")
        for failure_index in range(1, 6):
            with self.subTest(step=failure_index):
                self.target = make_program(self.root / ("step-" + str(failure_index)), "1.57.0", isolated=True)
                (self.target / PRIVATE_CONTENTS_DIR / "obsolete.dll").write_bytes(b"old private file")
                package.build_manifest(self.target, "1.57.0")
                before = {path.relative_to(self.target).as_posix(): path.read_bytes() for path in package.iter_regular_files(self.target)}
                snapshots = self.add_foreign_files()
                self.set_payload(program)
                plan = self.prepare()
                self.assertEqual(len(plan.changes) + len(plan.retired), 5)
                original_replace = transaction.os.replace
                original_rename = transaction.os.rename
                mutations = []

                def mutate_or_fail(operation, source, destination):
                    """仅拦截安装动作，事务日志和回滚动作仍实际执行。"""
                    source = Path(source)
                    destination = Path(destination)
                    if plan.candidate in source.parents or plan.backup in destination.parents:
                        mutations.append(source)
                        if len(mutations) == failure_index:
                            raise OSError("模拟第 %d 步失败" % failure_index)
                    return operation(source, destination)

                def replace_or_fail(source, destination):
                    """在覆盖式文件替换中注入指定步骤失败。"""
                    return mutate_or_fail(original_replace, source, destination)

                def rename_or_fail(source, destination):
                    """在新文件无覆盖移动中注入指定步骤失败。"""
                    return mutate_or_fail(original_rename, source, destination)

                with patch.object(transaction.os, "replace", side_effect=replace_or_fail):
                    with patch.object(transaction.os, "rename", side_effect=rename_or_fail):
                        with self.assertRaisesRegex(releases.UpdateError, "旧版本文件已恢复"):
                            installer.apply_installation(plan, Mock())
                for name, content in before.items():
                    self.assertEqual((self.target / name).read_bytes(), content)
                self.assertFalse((self.target / PRIVATE_CONTENTS_DIR / "new.dll").exists())
                self.assert_foreign_unchanged(snapshots)

    def test_modified_unchanged_dependency_is_detected_before_success(self):
        """准备后未替换的依赖被改动时最终校验报错，不误认完整安装成功。"""
        plan = self.prepare()
        helper = self.target / PRIVATE_CONTENTS_DIR / "updater.exe"
        helper.write_bytes(b"changed after prepare")
        with self.assertRaisesRegex(releases.UpdateError, "已安装的本工具文件校验失败"):
            installer.apply_installation(plan, Mock())
        self.assertEqual(package.read_manifest(self.target)["version"], "1.57.0")
        self.assertEqual(helper.read_bytes(), b"changed after prepare")

    def test_committed_transaction_cannot_be_applied_or_rolled_back_again(self):
        """提交成功后重复调用不能触发第二次写入或把已运行的软件降级。"""
        plan = self.prepare()
        installer.apply_installation(plan, Mock())
        transaction.mark_committed(plan)
        with self.assertRaisesRegex(releases.UpdateError, "不能重复安装"):
            transaction.apply_files(plan)
        with self.assertRaisesRegex(releases.UpdateError, "不能再次回滚"):
            transaction.rollback_files(plan)
        self.assertEqual(package.read_manifest(self.target)["version"], "1.58.0")

    def test_new_private_files_are_removed_on_legacy_rollback(self):
        """旧版迁移失败时删除本次新建依赖，恢复旧 EXE 和清单，共享依赖始终不动。"""
        self.target = make_program(self.root / "legacy-rollback", "1.57.0")
        original_runtime = self.snapshot(self.target / "_internal" / "python311.dll")
        program = make_program(self.root / "legacy-rollback-new", "1.58.0", isolated=True)
        self.set_payload(program)
        plan = self.prepare()
        launcher = Mock(side_effect=[OSError("不能启动新版"), None])
        with self.assertRaisesRegex(releases.UpdateError, "旧版本已恢复"):
            installer.apply_installation(plan, launcher)
        self.assertEqual(package.read_manifest(self.target)["version"], "1.57.0")
        self.assertFalse((self.target / PRIVATE_CONTENTS_DIR).exists())
        self.assertEqual(self.snapshot(self.target / "_internal" / "python311.dll"), original_runtime)

    def test_rollback_failure_retains_backup_journal_and_lock(self):
        """恢复被系统阻止时保留最小备份和事务记录，锁阻止再次覆盖。"""
        plan = self.prepare()
        original = transaction.os.replace

        def fail_restore(source, destination):
            """只让恢复主 EXE 的操作失败，已安装新版文件可用于检查。"""
            if Path(source) == plan.workspace / "restore" / APP_EXE_NAME:
                raise OSError("模拟恢复失败")
            return original(source, destination)

        with patch.object(transaction.os, "replace", side_effect=fail_restore):
            with self.assertRaisesRegex(releases.UpdateError, "请从以下目录恢复"):
                installer.apply_installation(plan, Mock(side_effect=OSError("无法启动")))
        transaction.release_lock(plan)
        self.assertTrue((plan.backup / APP_EXE_NAME).exists())
        self.assertTrue((plan.workspace / transaction.RECEIPT_NAME).exists())
        self.assertTrue((self.target / transaction.LOCK_NAME).exists())
        self.assertEqual(plan.state, "rollback_failed")

    def test_startup_timeout_stops_only_launched_process_then_restores_old_files(self):
        """未确认启动时只停止本次创建的进程，恢复旧文件并保留其他应用。"""
        snapshots = self.add_foreign_files()
        plan = self.prepare()
        process = Mock()
        process.poll.return_value = None
        launcher = Mock(side_effect=[process, Mock()])
        with self.assertRaisesRegex(releases.UpdateError, "旧版本已恢复"):
            installer.apply_installation(plan, launcher, Mock(side_effect=releases.UpdateError("启动超时")))
        process.terminate.assert_called_once_with()
        process.wait.assert_called_once_with(timeout=10)
        self.assertEqual(package.read_manifest(self.target)["version"], "1.57.0")
        self.assert_foreign_unchanged(snapshots)

    def test_early_crash_restores_without_terminating_other_processes(self):
        """新程序已经退出时不再停止任何进程，仍恢复旧版。"""
        plan = self.prepare()
        process = Mock()
        process.poll.return_value = 1
        with self.assertRaisesRegex(releases.UpdateError, "旧版本已恢复"):
            installer.apply_installation(plan, Mock(side_effect=[process, None]), Mock(side_effect=OSError("早退")))
        process.terminate.assert_not_called()
        self.assertEqual(package.read_manifest(self.target)["version"], "1.57.0")

    def test_process_exit_race_does_not_block_rollback(self):
        """停止前进程恰好退出时，不因此遗留新版而放弃文件恢复。"""
        plan = self.prepare()
        process = Mock()
        process.poll.side_effect = [None, 1]
        process.terminate.side_effect = ProcessLookupError("已退出")
        with self.assertRaisesRegex(releases.UpdateError, "旧版本已恢复"):
            installer.apply_installation(plan, Mock(side_effect=[process, None]), Mock(side_effect=OSError("失败")))
        self.assertEqual(package.read_manifest(self.target)["version"], "1.57.0")

    def test_unstoppable_new_process_keeps_backup_and_lock(self):
        """无法停止未就绪新进程时不冒险回滚其运行库，保留恢复材料及锁。"""
        plan = self.prepare()
        process = Mock()
        process.poll.return_value = None
        process.terminate.side_effect = OSError("不能停止")
        with self.assertRaisesRegex(releases.UpdateError, "旧版备份已保留"):
            installer.apply_installation(plan, Mock(return_value=process), Mock(side_effect=OSError("未就绪")))
        transaction.release_lock(plan)
        self.assertTrue((plan.backup / APP_EXE_NAME).exists())
        self.assertTrue((self.target / transaction.LOCK_NAME).exists())

    def test_backup_cleanup_requires_committed_transaction(self):
        """尚未确认成功的事务不能直接删除恢复副本。"""
        plan = self.prepare()
        installer.apply_installation(plan, Mock())
        with self.assertRaisesRegex(releases.UpdateError, "尚未提交"):
            installer.cleanup_successful_backup(plan, self.job["old_manifest"])
        self.assertTrue(plan.backup.exists())

    def test_cleanup_leaves_unknown_files_in_transaction_directory(self):
        """即便有人向备份目录放入其他文件，成功清理也不能递归删除这些文件。"""
        plan = self.prepare()
        installer.apply_installation(plan, Mock())
        unknown = plan.backup / "客户临时文件.txt"
        unknown.write_bytes(b"do not delete")
        installer.complete_installation(self.job, plan)
        self.assertEqual(unknown.read_bytes(), b"do not delete")
        self.assertEqual(self.status()["status"], "complete")
        self.assertFalse(self.status()["backup_removed"])
        self.assertTrue(self.status()["cleanup_warning"])

    def test_changed_backup_is_not_deleted(self):
        """备份摘要被修改时保留该文件，避免自动删除新的用户内容。"""
        plan = self.prepare()
        installer.apply_installation(plan, Mock())
        changed = plan.backup / APP_EXE_NAME
        changed.write_bytes(b"modified backup")
        installer.complete_installation(self.job, plan)
        self.assertEqual(changed.read_bytes(), b"modified backup")
        self.assertIn("已变化", self.status()["cleanup_warning"])

    def test_cleanup_path_or_receipt_tampering_is_rejected(self):
        """伪造清理路径或更改事务身份不能删除父目录、安装目录和历史备份。"""
        plan = self.prepare()
        installer.apply_installation(plan, Mock())
        transaction.mark_committed(plan)
        for foreign in (self.root, self.target, self.staging):
            bad = replace(plan, workspace=foreign)
            with self.subTest(path=foreign), self.assertRaises(releases.UpdateError):
                transaction.cleanup_transaction(bad)
        receipt = plan.workspace / transaction.RECEIPT_NAME
        data = json.loads(receipt.read_text(encoding="utf-8"))
        data["token"] = "other"
        receipt.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaisesRegex(releases.UpdateError, "身份已变化"):
            transaction.cleanup_transaction(plan)
        self.assertTrue((plan.backup / APP_EXE_NAME).exists())

    def test_same_level_historical_backups_are_never_touched(self):
        """本次自动清理不扫描其他任务备份，用户历史备份保持原位。"""
        history = self.target / "AD仪表一线通协议测试工具.backup-历史"
        history.mkdir()
        sentinel = history / "keep.txt"
        sentinel.write_bytes(b"history")
        original = self.snapshot(sentinel)
        plan = self.prepare()
        installer.apply_installation(plan, Mock())
        installer.complete_installation(self.job, plan)
        self.assertEqual(self.snapshot(sentinel), original)

    def test_live_unmanaged_exports_are_not_reverted_on_startup_failure(self):
        """新版启动期间用户导出或修改的文件，回滚时同样保持原位。"""
        plan = self.prepare()

        def fail_after_export(process):
            """模拟新版写出用户文件后启动观察失败。"""
            (self.target / "new-export.json").write_bytes(b"new user packets")
            raise releases.UpdateError("模拟短期退出")

        process = Mock()
        process.poll.return_value = 1
        with self.assertRaisesRegex(releases.UpdateError, "旧版本已恢复"):
            installer.apply_installation(plan, Mock(side_effect=[process, None]), fail_after_export)
        self.assertEqual((self.target / "new-export.json").read_bytes(), b"new user packets")

    def test_parent_timeout_cleans_preparation_without_modifying_any_installed_file(self):
        """原程序未退出时仅清理准备材料，安装文件和其他应用均不变化。"""
        snapshots = self.add_foreign_files()
        parent = Mock()
        parent.wait.side_effect = releases.UpdateError("等待退出超时")
        with patch.object(installer, "WindowsParentProcess", return_value=parent):
            self.assertEqual(installer.run_installer(self.job_path), 1)
        self.assertEqual(package.read_manifest(self.target)["version"], "1.57.0")
        self.assert_foreign_unchanged(snapshots)
        self.assertEqual(list(self.target.glob(transaction.WORK_PREFIX + "*")), [])
        self.assertFalse((self.target / transaction.LOCK_NAME).exists())

    def test_run_entry_cleans_only_after_new_process_confirmation(self):
        """正式入口在确认函数返回前保持最小备份完整，之后清理且不留下工作目录。"""
        process = Mock()

        def confirm(launched, request_path):
            """确认瞬间备份和版本信息必须仍存在且只属于本工具。"""
            workspaces = list(self.target.glob(transaction.WORK_PREFIX + "*"))
            self.assertEqual(len(workspaces), 1)
            backup_files = {path.relative_to(workspaces[0] / "backup").as_posix() for path in package.iter_regular_files(workspaces[0] / "backup")}
            self.assertEqual(backup_files, {APP_EXE_NAME, PRIVATE_MANIFEST_NAME, PRIVATE_CONTENTS_DIR + "/python311.dll"})
            self.assertIs(launched, process)
            self.assertTrue(request_path.is_file())

        with patch.object(installer, "WindowsParentProcess"):
            with patch.object(installer, "launch_application", return_value=process):
                with patch.object(installer, "wait_for_application_startup", side_effect=confirm):
                    self.assertEqual(installer.run_installer(self.job_path), 0)
        self.assertEqual(list(self.target.glob(transaction.WORK_PREFIX + "*")), [])
        self.assertFalse((self.target / transaction.LOCK_NAME).exists())

    def test_run_entry_startup_failure_restores_old_without_success_cleanup(self):
        """正式入口确认失败后回滚，不进入成功清理分支，旧版重启不携带新版请求。"""
        process = Mock()
        process.poll.return_value = None
        with patch.object(installer, "WindowsParentProcess"):
            with patch.object(installer, "launch_application", side_effect=[process, None]) as launcher:
                with patch.object(installer, "wait_for_application_startup", side_effect=OSError("未就绪")):
                    with patch.object(installer, "complete_installation") as complete:
                        with patch.object(installer.ctypes, "windll", create=True):
                            self.assertEqual(installer.run_installer(self.job_path), 1)
                        complete.assert_not_called()
        self.assertIsNone(launcher.call_args.args[1])
        self.assertEqual(package.read_manifest(self.target)["version"], "1.57.0")
        self.assertFalse((self.target / transaction.LOCK_NAME).exists())

    def test_logging_failure_after_confirmed_success_does_not_fail_upgrade(self):
        """成功后写状态失败不再恢复已提交的版本。"""
        plan = self.prepare()
        installer.apply_installation(plan, Mock())
        with patch.object(installer, "write_status", side_effect=PermissionError("只读")):
            installer.complete_installation(self.job, plan)
        self.assertEqual(package.read_manifest(self.target)["version"], "1.58.0")
        self.assertFalse(plan.workspace.exists())

    def test_retry_is_bounded_and_preserves_windows_error_details(self):
        """Windows 5、32、33 有限重试，其他错误立即返回，旧日志字段保持可用。"""
        for code in (5, 32, 33, 183, None):
            error = PermissionError(13, "模拟系统错误")
            if code is not None:
                error.winerror = code
            operation = Mock(side_effect=error)
            with self.subTest(code=code), patch.object(transaction.time, "sleep") as sleep:
                with self.assertRaises(PermissionError) as raised:
                    transaction.retry_file_operation(operation, attempts=3)
                expected = 3 if code in (5, 32, 33) else 1
                self.assertIs(raised.exception, error)
                self.assertEqual(operation.call_count, expected)
                self.assertEqual(sleep.call_count, expected - 1)
                self.assertEqual(error.rename_errors, [code] * expected)

    def test_invalid_retry_count_never_silently_skips_file_operation(self):
        """零次、负数和布尔次数不能让文件操作被静默跳过。"""
        for count in (0, -1, True, "3"):
            operation = Mock()
            with self.subTest(count=count), self.assertRaisesRegex(releases.UpdateError, "正整数"):
                transaction.retry_file_operation(operation, attempts=count)
            operation.assert_not_called()

    def test_failure_log_preserves_native_windows_cause_and_stage(self):
        """换用文件事务后仍保留原系统错误码、完整异常链和失败阶段。"""
        native = PermissionError(13, "原始共享错误")
        native.winerror = 32
        error = releases.UpdateError("等待退出失败")
        error.__cause__ = native
        parent = Mock()
        parent.wait.side_effect = error
        with patch.object(installer, "WindowsParentProcess", return_value=parent):
            self.assertEqual(installer.run_installer(self.job_path), 1)
        self.assertEqual(self.status()["winerror"], 32)
        self.assertEqual(self.status()["stage"], "等待主程序退出")
        self.assertIn("原始共享错误", self.status()["detail"])

    def test_restarted_process_environment_remains_independent(self):
        """新版和旧版重启均使用独立打包环境，回滚时移除继承的启动请求。"""
        with patch.dict(os.environ, {installer.STARTUP_REQUEST_ENV: "stale"}):
            with patch.object(installer.subprocess, "Popen") as popen:
                installer.launch_application(self.target / APP_EXE_NAME, self.job_path)
                self.assertEqual(popen.call_args.kwargs["env"][installer.STARTUP_REQUEST_ENV], str(self.job_path))
                installer.launch_application(self.target / APP_EXE_NAME)
                self.assertNotIn(installer.STARTUP_REQUEST_ENV, popen.call_args.kwargs["env"])
                self.assertEqual(popen.call_args.kwargs["env"]["PYINSTALLER_RESET_ENVIRONMENT"], "1")

    @contextmanager
    def native_windows_handle(self, path, directory=False):
        """打开本测试文件的禁止删除共享句柄，退出时只关闭此自有句柄。"""
        import ctypes
        import threading
        from ctypes import wintypes
        api = ctypes.WinDLL("kernel32", use_last_error=True)
        api.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
        api.CreateFileW.restype = wintypes.HANDLE
        api.CloseHandle.argtypes = [wintypes.HANDLE]
        api.CloseHandle.restype = wintypes.BOOL
        handle = api.CreateFileW(str(path), 1 if directory else 0x80000000, 3, None, 3, 0x02000000 if directory else 0x80, None)
        self.assertNotEqual(handle, ctypes.c_void_p(-1).value)
        closed = []
        guard = threading.Lock()

        def release_owned_handle():
            """允许测试定时释放句柄，但无论路径如何退出都只关闭一次。"""
            with guard:
                if not closed:
                    api.CloseHandle(handle)
                    closed.append(True)

        try:
            yield release_owned_handle
        finally:
            release_owned_handle()

    @unittest.skipUnless(os.name == "nt", "原生 Windows 句柄验证")
    def test_locked_foreign_application_and_parent_directory_do_not_block_update(self):
        """其他应用文件和混放目录本身被禁止删除占用时，文件级升级仍成功。"""
        snapshots = self.add_foreign_files()
        plan = self.prepare()
        with self.native_windows_handle(self.target, directory=True):
            with self.native_windows_handle(self.target / "其他应用.exe"):
                installer.apply_installation(plan, Mock())
                installer.complete_installation(self.job, plan)
        self.assert_foreign_unchanged(snapshots)
        self.assertFalse(plan.workspace.exists())

    @unittest.skipUnless(os.name == "nt", "原生 Windows 句柄验证")
    def test_locked_legacy_shared_runtime_does_not_block_migration(self):
        """其他应用仍使用旧共享运行库时，迁移只新增专属依赖，不替换共享 DLL。"""
        self.target = make_program(self.root / "locked-legacy", "1.57.0")
        dll = self.target / "_internal" / "python311.dll"
        original = self.snapshot(dll)
        program = make_program(self.root / "locked-legacy-new", "1.58.0", isolated=True)
        self.set_payload(program)
        plan = self.prepare()
        with self.native_windows_handle(dll):
            installer.apply_installation(plan, Mock())
            installer.complete_installation(self.job, plan)
        self.assertEqual(self.snapshot(dll), original)
        self.assertFalse(plan.workspace.exists())

    @unittest.skipUnless(os.name == "nt", "原生 Windows 句柄验证")
    def test_locked_owned_dependency_fails_safely_and_restores_other_owned_files(self):
        """本工具依赖持续被占用时有限等待并回滚，不影响同级其他软件。"""
        snapshots = self.add_foreign_files()
        plan = self.prepare()
        dll = self.target / PRIVATE_CONTENTS_DIR / "python311.dll"
        with self.native_windows_handle(dll):
            with patch.object(transaction, "FILE_MAX_ATTEMPTS", 2):
                with patch.object(transaction.time, "sleep"):
                    with self.assertRaisesRegex(releases.UpdateError, "旧版本文件已恢复"):
                        installer.apply_installation(plan, Mock())
        self.assertEqual(package.read_manifest(self.target)["version"], "1.57.0")
        self.assert_foreign_unchanged(snapshots)

    @unittest.skipUnless(os.name == "nt", "原生 Windows 句柄验证")
    def test_locked_backup_cleanup_is_warning_not_upgrade_failure(self):
        """备份自有文件持续占用时记录清理警告，其他应用和已安装新版仍保持正常。"""
        plan = self.prepare()
        installer.apply_installation(plan, Mock())
        with self.native_windows_handle(plan.backup / APP_EXE_NAME):
            with patch.object(transaction, "CLEANUP_MAX_ATTEMPTS", 2):
                with patch.object(transaction.time, "sleep"):
                    installer.complete_installation(self.job, plan)
        self.assertEqual(self.status()["status"], "complete")
        self.assertFalse(self.status()["backup_removed"])
        self.assertTrue(self.status()["cleanup_warning"])
        self.assertEqual(package.read_manifest(self.target)["version"], "1.58.0")

    @unittest.skipUnless(os.name == "nt", "原生 Windows 句柄验证")
    def test_transient_backup_lock_released_then_cleanup_succeeds(self):
        """真实备份文件短暂占用释放后，有限重试完成清理，不留下本次工作目录。"""
        import threading
        plan = self.prepare()
        installer.apply_installation(plan, Mock())
        with self.native_windows_handle(plan.backup / APP_EXE_NAME) as release:
            timer = threading.Timer(0.2, release)
            timer.start()
            try:
                installer.complete_installation(self.job, plan)
            finally:
                timer.cancel()
                timer.join(timeout=2)
        self.assertTrue(self.status()["backup_removed"])
        self.assertFalse(plan.workspace.exists())

    @unittest.skipUnless(os.name == "nt", "原生 Windows 句柄验证")
    def test_windows_parent_handle_still_verifies_actual_process(self):
        """正式入口仍校验真实进程路径，不依赖任意提供的 PID。"""
        import sys
        parent = installer.WindowsParentProcess(os.getpid(), Path(sys.executable))
        try:
            with self.assertRaises(releases.UpdateCancelled):
                parent.wait(cancelled=lambda: True)
        finally:
            parent.close()


if __name__ == "__main__":
    unittest.main()
