#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""本地与 CI 共用的只读源码检查入口，不调用编译器、打包器或 Git 写操作。"""

import argparse
import ast
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIRS = ("gui", "protocol", "serial_comm", "updating", "licensing", "tools", "tests")
ROOT_SOURCES = ("main.py", "app_info.py", "app_paths.py", "app_settings.py", "diagnostics.py")
PRIVATE_LOCAL_SOURCES = frozenset(("tools/activation_tool.py", "tools/generate_activation_code.py"))


def source_files():
    """只列出源码白名单，不扫描 dist、PDF、硬件驱动或私钥目录。"""
    paths = [ROOT / name for name in ROOT_SOURCES]
    for name in SOURCE_DIRS:
        paths.extend((ROOT / name).rglob("*.py"))
    return sorted(set(paths))


def check_sources(paths):
    """解析 Python 语法与冲突标记，不生成字节码或构建产物。"""
    errors = []
    for path in paths:
        try:
            source = path.read_text(encoding="utf-8-sig")
            ast.parse(source, filename=str(path))
            if any(line.startswith(("<<<<<<< ", ">>>>>>> ")) for line in source.splitlines()):
                errors.append(f"{path.relative_to(ROOT)} 含有未解决的合并标记")
        except (OSError, SyntaxError, UnicodeError) as exc:
            errors.append(f"{path.relative_to(ROOT)}: {exc}")
    return errors


def tracked_source_names():
    """只读读取 Git 清单，供遗漏检查及本地私有工具防上传检查复用。"""
    result = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True)
    return set(result.stdout.decode("utf-8").split("\0"))


def untracked_sources(paths):
    """只读检查公开源码遗漏；本地私有工具仍做语法检查，但不能要求把它们提交。"""
    tracked = tracked_source_names()
    # 修复私有工具取消跟踪后本地 --require-tracked 误报，例外仅限两个明确路径。
    required = [path.relative_to(ROOT).as_posix() for path in paths
                if path.relative_to(ROOT).as_posix() not in PRIVATE_LOCAL_SOURCES]
    required.extend((
        ".github/workflows/source-checks.yml", "requirements-lock.txt", "requirements-build.txt",
        "README.md", "AGENTS.md", "docs/adding_protocol.md", "docs/releasing.md",
        "docs/optimization-20261019.md", "docs/release-archive-20261015.md",
    ))
    return sorted(name for name in required if name not in tracked)


def tracked_private_sources():
    """阻止私有工具被强制加入 Git，避免后续发布时意外再次上传。"""
    return sorted(tracked_source_names() & PRIVATE_LOCAL_SOURCES)


def main():
    """先静态校验再运行现有回归；是否要求已纳入 Git 由调用方明确选择。"""
    parser = argparse.ArgumentParser(description="只读源码检查及回归测试，不编译、不发布")
    parser.add_argument("--static-only", action="store_true", help="只做语法解析，不运行测试")
    parser.add_argument("--require-tracked", action="store_true", help="CI 中拒绝未纳入 Git 的源码与工作流")
    args = parser.parse_args()
    paths = source_files()
    errors = check_sources(paths)
    if args.require_tracked:
        try:
            errors.extend("未纳入 Git：" + name for name in untracked_sources(paths))
            errors.extend("本地私有工具不得纳入 Git：" + name for name in tracked_private_sources())
        except (OSError, subprocess.CalledProcessError, UnicodeError) as exc:
            errors.append(f"无法读取 Git 源码清单：{exc}")
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(f"源码语法与冲突检查通过：{len(paths)} 个文件", flush=True)
    if args.static_only:
        return 0
    environment = os.environ.copy()
    environment.update(QT_QPA_PLATFORM="offscreen", PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1")
    return subprocess.run([sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests"], cwd=ROOT, env=environment).returncode


if __name__ == "__main__":
    sys.exit(main())
