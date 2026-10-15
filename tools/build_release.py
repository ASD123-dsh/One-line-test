#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成带独立更新器、完整性清单和 ZIP 的 GitHub Release 附件，不自动上传。"""

import argparse
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app_info import APP_NAME, APP_VERSION, PRIVATE_CONTENTS_DIR, UPDATER_EXE_NAME  # noqa: E402
from updating.package import build_manifest, file_sha256, iter_regular_files  # noqa: E402
from updating.releases import asset_name_for_version  # noqa: E402


def create_release_zip(program_dir, output_dir, version=APP_VERSION):
    """为完整候选程序建立清单并打包，附件名与客户端选择规则保持一致。"""
    program_dir = Path(program_dir)
    output_dir = Path(output_dir)
    manifest = build_manifest(program_dir, version)
    output_dir.mkdir(parents=True, exist_ok=True)
    zip_path = output_dir / asset_name_for_version(version, managed=manifest.get("layout") == "isolated")
    with zipfile.ZipFile(zip_path, "x", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(iter_regular_files(program_dir)):
            name = (Path(APP_NAME) / path.relative_to(program_dir)).as_posix()
            archive.write(path, name)
    checksum_path = zip_path.with_suffix(".zip.sha256")
    checksum_path.write_text(f"{file_sha256(zip_path)}  {zip_path.name}\n", encoding="ascii")
    return zip_path


def run_pyinstaller(arguments):
    """复用当前 Python 环境的 PyInstaller，构建失败立即停止发布打包。"""
    subprocess.run(
        [sys.executable, "-m", "PyInstaller", "--noconfirm"] + arguments,
        cwd=str(ROOT_DIR), check=True,
    )


def build_main_program(temporary, helper, contents_directory, label):
    """复用同一源码构建不同目录布局，旧客户端过渡包不改变原附件约定。"""
    run_pyinstaller([
        "--windowed", "--onedir", "--name", APP_NAME,
        "--contents-directory", contents_directory,
        "--paths", str(ROOT_DIR),
        "--icon", str(ROOT_DIR / "img" / "图标.ico"),
        "--add-data", str(ROOT_DIR / "img") + ";img",
        "--add-binary", str(helper) + ";.",
        "--distpath", str(temporary / label),
        "--workpath", str(temporary / (label + "-work")),
        "--specpath", str(temporary / ("spec-" + label)),
        str(ROOT_DIR / "main.py"),
    ])
    return temporary / label / APP_NAME


def build_release(output_dir):
    """构建专属运行库主包和旧客户端过渡包，不覆盖已有发布目录或自动上传。"""
    output_dir = Path(output_dir).resolve()
    if output_dir.exists():
        raise ValueError(f"输出目录已经存在，请指定新目录：{output_dir}")
    build_root = ROOT_DIR / "build"
    build_root.mkdir(exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix="release-build-", dir=str(build_root)))
    try:
        run_pyinstaller([
            "--windowed", "--onefile", "--name", "updater",
            "--paths", str(ROOT_DIR),
            "--distpath", str(temporary / "helper"),
            "--workpath", str(temporary / "helper-work"),
            "--specpath", str(temporary / "spec-helper"),
            str(ROOT_DIR / "tools" / "update_installer.py"),
        ])
        helper = temporary / "helper" / UPDATER_EXE_NAME
        program_dir = build_main_program(temporary, helper, PRIVATE_CONTENTS_DIR, "program")
        build_manifest(program_dir, APP_VERSION)
        output_dir.mkdir(parents=True)
        shutil.copytree(program_dir, output_dir / APP_NAME)
        package = create_release_zip(output_dir / APP_NAME, output_dir)
        legacy_program = build_main_program(temporary, helper, "_internal", "legacy-program")
        # 避免留下第二份可运行程序：过渡包直接从独占临时目录打 ZIP，随后统一清理。
        legacy_package = create_release_zip(legacy_program, output_dir)
        print(f"软件版本：v{APP_VERSION}")
        print(f"完整程序：{output_dir / APP_NAME}")
        print(f"Release 附件：{package}")
        print(f"旧客户端过渡附件：{legacy_package}")
        print(f"SHA-256：{file_sha256(package)}")
        return package
    finally:
        # 临时目录由本函数独占创建，不触碰既有 dist 程序和用户备份。
        shutil.rmtree(temporary)


def main():
    """按集中版本号生成一个可手动上传 GitHub 的独立发布目录。"""
    parser = argparse.ArgumentParser(description="打包一线通工具完整更新版")
    parser.add_argument(
        "--output", type=Path, default=ROOT_DIR / "dist" / "releases" / f"v{APP_VERSION}",
        help="新的输出目录，默认 dist/releases/v软件版本",
    )
    args = parser.parse_args()
    build_release(args.output)


if __name__ == "__main__":
    main()
