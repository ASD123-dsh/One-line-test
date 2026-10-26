#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""本地激活码生成工具防上传回归，不读取私钥、客户授权或真实激活码。"""

import ast
import io
import unittest
from unittest.mock import patch

from tools import check_project


class PrivateToolsTests(unittest.TestCase):
    """限制例外路径，验证 CI 防重新跟踪以及运行时与私有工具解耦。"""

    def test_private_paths_are_exact(self):
        """私有例外仅限用户指定的两个生成工具，不能放宽到整个 tools 目录。"""
        self.assertEqual(check_project.PRIVATE_LOCAL_SOURCES, {
            "tools/activation_tool.py", "tools/generate_activation_code.py",
        })

    def test_private_tools_are_not_reported_as_missing_public_sources(self):
        """本机保留私有文件不会被遗漏检查要求重新提交。"""
        paths = [check_project.ROOT / name for name in check_project.PRIVATE_LOCAL_SOURCES]
        with patch.object(check_project, "tracked_source_names", return_value=set()):
            missing = check_project.untracked_sources(paths)
        self.assertTrue(check_project.PRIVATE_LOCAL_SOURCES.isdisjoint(missing))

    def test_other_untracked_tool_is_still_reported(self):
        """其他新增工具仍必须提交，不能让私有工具例外掩盖源码遗漏。"""
        name = "tools/new_public_tool.py"
        with patch.object(check_project, "tracked_source_names", return_value=set()):
            self.assertIn(name, check_project.untracked_sources([check_project.ROOT / name]))

    def test_force_added_private_tools_are_detected(self):
        """即使用强制添加绕过忽略规则，CI 仍能准确列出两个私有路径。"""
        tracked = set(check_project.PRIVATE_LOCAL_SOURCES) | {"licensing/activation.py", "tools/build_release.py"}
        with patch.object(check_project, "tracked_source_names", return_value=tracked):
            self.assertEqual(check_project.tracked_private_sources(), sorted(check_project.PRIVATE_LOCAL_SOURCES))

    def test_tracking_guard_stops_before_test_execution(self):
        """发现私有工具被跟踪时检查入口返回失败，不能带着违规内容继续验证。"""
        with patch.object(check_project.sys, "argv", ["check_project", "--require-tracked"]), \
                patch.object(check_project, "source_files", return_value=[]), \
                patch.object(check_project, "check_sources", return_value=[]), \
                patch.object(check_project, "untracked_sources", return_value=[]), \
                patch.object(check_project, "tracked_private_sources", return_value=["tools/activation_tool.py"]), \
                patch.object(check_project.subprocess, "run") as runner, \
                patch.object(check_project.sys, "stderr", new_callable=io.StringIO) as errors:
            self.assertEqual(check_project.main(), 1)
            self.assertIn("本地私有工具不得纳入 Git", errors.getvalue())
            runner.assert_not_called()

    def test_actual_index_does_not_track_private_tools(self):
        """同时检查真实 Git 索引，后续若误加私有工具则本地与 CI 回归都失败。"""
        self.assertEqual(check_project.tracked_private_sources(), [])

    def test_runtime_does_not_import_private_generators(self):
        """正常激活、协议和更新入口不能依赖本地私有生成工具。"""
        private_modules = {name[:-3].replace("/", ".") for name in check_project.PRIVATE_LOCAL_SOURCES}
        sources = [check_project.ROOT / name for name in check_project.ROOT_SOURCES]
        for directory in ("gui", "protocol", "serial_comm", "licensing", "updating"):
            sources.extend((check_project.ROOT / directory).rglob("*.py"))
        for path in sources:
            tree = ast.parse(path.read_text(encoding="utf-8-sig"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imports = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom):
                    imports = [node.module or ""] + [(node.module + "." + alias.name) if node.module else alias.name
                                                      for alias in node.names]
                else:
                    continue
                self.assertTrue(private_modules.isdisjoint(imports), str(path.relative_to(check_project.ROOT)))


if __name__ == "__main__":
    unittest.main()
