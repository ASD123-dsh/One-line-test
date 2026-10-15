#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""完整更新包的清单、路径和文件校验，安装前拒绝残缺或危险压缩包。"""

import hashlib
import json
import re
import shutil
import stat
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

from app_info import (
    APP_EXE_NAME, APP_ID, APP_NAME, MANIFEST_NAME, PACKAGE_PLATFORM,
    PRIVATE_CONTENTS_DIR, PRIVATE_MANIFEST_NAME, UPDATER_EXE_NAME,
)
from .releases import UpdateError, check_cancelled, normalized_version

MAX_FILES = 5000
MAX_EXPANDED_BYTES = 1024 * 1024 * 1024
STAGING_PREFIX = "sifexe-update-"
STAGING_MARKER = ".sifexe-update-staging"
RESERVED_NAMES = frozenset(("CON", "PRN", "AUX", "NUL") + tuple(
    f"{prefix}{index}" for prefix in ("COM", "LPT") for index in range(1, 10)
))


def safe_relative_path(value):
    """校验 ZIP 和清单中的 Windows 相对路径，拒绝穿越、盘符及特殊设备名。"""
    if not isinstance(value, str) or not value or "\\" in value:
        raise UpdateError("更新包包含无效路径")
    parts = value.split("/")
    if any(
        not part or part in (".", "..") or part.endswith((".", " "))
        or len(part) > 255 or part.split(".")[0].upper() in RESERVED_NAMES
        or any(ord(char) < 32 or char in '<>:"|?*' for char in part)
        for part in parts
    ):
        raise UpdateError(f"更新包包含不安全路径：{value}")
    return PurePosixPath(*parts)


def is_reparse_point(path):
    """同时识别符号链接和 Windows 联接点，防止操作跳出程序目录。"""
    info = Path(path).lstat()
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, "st_file_attributes", 0) & 0x400)


def iter_regular_files(root):
    """遍历普通文件，拒绝链接和设备文件，不跟随目录重解析点。"""
    root = Path(root)
    if is_reparse_point(root):
        raise UpdateError("更新目录不能是链接或联接点")
    pending = [root]
    while pending:
        directory = pending.pop()
        for path in directory.iterdir():
            if is_reparse_point(path):
                raise UpdateError(f"更新目录不能包含链接：{path.name}")
            if path.is_dir():
                pending.append(path)
            elif path.is_file():
                yield path
            else:
                raise UpdateError("更新目录包含非普通文件")


def file_sha256(path, cancelled=None):
    """分块计算摘要，校验较大运行库时也可响应取消。"""
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        while True:
            check_cancelled(cancelled)
            chunk = source.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def manifest_path_for(root):
    """优先使用本工具专属清单，旧版通用清单只用于迁移，不覆盖其他应用清单。"""
    root = Path(root)
    private = root / PRIVATE_MANIFEST_NAME
    if private.exists() or private.is_symlink():
        return private
    return root / MANIFEST_NAME


def managed_contents_directory(manifest):
    """按清单格式区分专属运行库和旧版共享目录，不按目录中其他软件猜测归属。"""
    layout = manifest.get("layout", "legacy")
    if layout == "isolated":
        return PRIVATE_CONTENTS_DIR
    if layout == "legacy":
        return "_internal"
    raise UpdateError("更新清单的运行库布局无效")


def read_manifest(root, expected_version=None):
    """读取受限大小的清单，并验证软件身份、平台、版本及所有文件路径。"""
    try:
        manifest_path = manifest_path_for(root)
        if is_reparse_point(manifest_path):
            raise UpdateError("更新清单不能是链接")
        with manifest_path.open("rb") as source:
            raw = source.read(2 * 1024 * 1024 + 1)
        if len(raw) > 2 * 1024 * 1024:
            raise UpdateError("更新清单过大")
        manifest = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise UpdateError("缺少有效的完整更新清单，请使用发布工具生成的 ZIP") from exc
    if not isinstance(manifest, dict) or (
        type(manifest.get("schema")) is not int or manifest.get("schema") != 1
        or manifest.get("app_id") != APP_ID
        or manifest.get("platform") != PACKAGE_PLATFORM
        or manifest.get("executable") != APP_EXE_NAME
    ):
        raise UpdateError("更新清单的软件身份、格式或平台不匹配")
    version = normalized_version(manifest.get("version"))
    if expected_version is not None and version != normalized_version(expected_version):
        raise UpdateError("更新包版本与 GitHub 发行版不一致")
    files = manifest.get("files")
    if not isinstance(files, dict) or not files or len(files) > MAX_FILES:
        raise UpdateError("更新清单的文件列表无效")
    contents = managed_contents_directory(manifest)
    expected_manifest = PRIVATE_MANIFEST_NAME if contents == PRIVATE_CONTENTS_DIR else MANIFEST_NAME
    if manifest_path.name != expected_manifest:
        raise UpdateError("更新清单名称与运行库布局不匹配")
    normalized_names = set()
    reserved_names = (MANIFEST_NAME.casefold(), PRIVATE_MANIFEST_NAME.casefold())
    for name, digest in files.items():
        relative = safe_relative_path(name)
        normalized_name = name.casefold()
        if normalized_name in reserved_names or normalized_name in normalized_names:
            raise UpdateError("更新清单包含重复或保留文件名")
        # 修复混放时归属不明确的问题：清单不能把同级任意应用纳入升级范围。
        if name != APP_EXE_NAME and (len(relative.parts) < 2 or relative.parts[0] != contents):
            raise UpdateError(f"更新清单包含非本工具管理的路径：{name}")
        normalized_names.add(normalized_name)
        if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
            raise UpdateError("更新清单包含无效的文件摘要")
    if APP_EXE_NAME not in files or f"{contents}/{UPDATER_EXE_NAME}" not in files:
        raise UpdateError("更新包缺少主程序或独立更新器")
    if not any(name.startswith(contents + "/python") and name.endswith(".dll") for name in files):
        raise UpdateError("更新包缺少 Python 运行库")
    return manifest


def validate_payload(root, expected_version=None, cancelled=None):
    """校验完整程序目录的文件集合和逐文件摘要，禁止只更新一个 EXE。"""
    root = Path(root)
    manifest = read_manifest(root, expected_version)
    actual = {path.relative_to(root).as_posix(): path for path in iter_regular_files(root)}
    if set(actual) != set(manifest["files"]) | {manifest_path_for(root).name}:
        raise UpdateError("更新包文件集合与清单不一致")
    for name, digest in manifest["files"].items():
        if file_sha256(actual[name], cancelled) != digest:
            raise UpdateError(f"更新文件校验失败：{name}")
    return manifest


def extract_package(archive_path, destination, expected_version, cancelled=None):
    """先检查全部 ZIP 项，再解压到新目录，拒绝路径穿越、重复项和压缩炸弹。"""
    destination = Path(destination)
    if destination.exists():
        raise UpdateError("更新解压目录已存在")
    try:
        with zipfile.ZipFile(archive_path) as archive:
            entries = archive.infolist()
            if not entries or len(entries) > MAX_FILES + 200:
                raise UpdateError("更新包文件数量无效")
            total = 0
            seen = set()
            for entry in entries:
                check_cancelled(cancelled)
                # Windows 的 zipfile 会规范化反斜杠并截断 NUL，必须检查未规范化的原始名称。
                original_name = entry.orig_filename
                name = original_name[:-1] if entry.is_dir() else original_name
                relative = safe_relative_path(name)
                if original_name != entry.filename:
                    raise UpdateError("更新包包含非标准文件路径")
                if relative.parts[0] != APP_NAME:
                    raise UpdateError("更新包必须只包含指定的完整程序文件夹")
                if name.casefold() in seen:
                    raise UpdateError("更新包包含重复文件路径")
                seen.add(name.casefold())
                mode = stat.S_IFMT(entry.external_attr >> 16)
                if mode not in (0, stat.S_IFREG, stat.S_IFDIR) or entry.flag_bits & 1:
                    raise UpdateError("更新包不能包含链接、特殊文件或加密文件")
                total += entry.file_size
                if total > MAX_EXPANDED_BYTES:
                    raise UpdateError("更新包解压大小超过 1GB")
            destination.mkdir()
            for entry in entries:
                check_cancelled(cancelled)
                relative = safe_relative_path(entry.filename.rstrip("/"))
                target = destination.joinpath(*relative.parts)
                if entry.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(entry) as source, target.open("xb") as output:
                    while True:
                        check_cancelled(cancelled)
                        chunk = source.read(256 * 1024)
                        if not chunk:
                            break
                        output.write(chunk)
        payload = destination / APP_NAME
        validate_payload(payload, expected_version, cancelled)
        return payload
    except (zipfile.BadZipFile, OSError, RuntimeError) as exc:
        raise UpdateError(f"更新包解压失败：{exc}") from exc


def create_staging_directory():
    """创建本次更新独占的临时目录，并写入所有权标记。"""
    root = Path(tempfile.mkdtemp(prefix=STAGING_PREFIX)).resolve()
    (root / STAGING_MARKER).write_text(APP_ID, encoding="utf-8")
    return root


def validate_staging_directory(root):
    """只接受本程序创建且带身份标记的临时目录。"""
    root = Path(root)
    if not root.name.startswith(STAGING_PREFIX) or is_reparse_point(root):
        raise UpdateError("更新暂存目录无效")
    marker = root / STAGING_MARKER
    if is_reparse_point(marker):
        raise UpdateError("更新暂存标记不能是链接")
    with marker.open("rb") as source:
        identity = source.read(128)
    if identity != APP_ID.encode("utf-8"):
        raise UpdateError("更新暂存目录身份不匹配")
    return root.resolve()


def discard_staging_directory(root):
    """只清理本程序拥有的暂存目录，避免错误删除其他路径。"""
    root = Path(root)
    if root.exists():
        shutil.rmtree(validate_staging_directory(root))


def build_manifest(root, version):
    """为发布工具生成逐文件校验清单，不把授权信息或源码加入分发包。"""
    root = Path(root)
    isolated = (root / PRIVATE_CONTENTS_DIR).is_dir()
    manifest_name = PRIVATE_MANIFEST_NAME if isolated else MANIFEST_NAME
    files = {}
    for path in sorted(iter_regular_files(root)):
        name = path.relative_to(root).as_posix()
        if name != manifest_name:
            safe_relative_path(name)
            files[name] = file_sha256(path)
    manifest = {
        "schema": 1, "app_id": APP_ID, "version": normalized_version(version),
        "platform": PACKAGE_PLATFORM, "executable": APP_EXE_NAME, "files": files,
    }
    if isolated:
        manifest["layout"] = "isolated"
    (root / manifest_name).write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    validate_payload(root, version)
    return manifest
