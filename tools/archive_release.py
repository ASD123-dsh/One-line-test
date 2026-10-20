#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""发布成功后的本地归档收尾：校验正式附件、保留历史版本、清理已归档的生成副本。"""

import argparse
import json
import os
import re
import shutil
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app_info import APP_ID, GITHUB_REPOSITORY  # noqa: E402
from updating.package import file_sha256, is_reparse_point  # noqa: E402
from updating.releases import UpdateError, asset_name_for_version, normalized_version  # noqa: E402

ARCHIVE_ROOT = ROOT_DIR / "dist" / "历史归档" / "正式发行版"


def checked_path(path):
    """核对完整路径各级链接属性，归档和清理不能通过联接点操作其他位置。"""
    path = Path(path).absolute()
    for item in (path, *path.parents):
        if (item.exists() or item.is_symlink()) and is_reparse_point(item):
            raise ValueError(f"归档路径不能包含链接：{item}")
    return path.resolve()


def read_json(path):
    """受限读取普通 JSON 记录，避免把未知或过大的文件用作发布凭证。"""
    path = checked_path(path)
    with path.open("rb") as source:
        raw = source.read(2 * 1024 * 1024 + 1)
    if len(raw) > 2 * 1024 * 1024:
        raise ValueError("归档记录超过 2 MiB")
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("归档记录必须是 JSON 对象")
    return data


def published_assets(record):
    """只接受已经公开、标签及源码确认过的本仓库发行记录，不把草稿误归为正式版。"""
    if type(record.get("schema")) is not int or record["schema"] != 1 or record.get("repository") != GITHUB_REPOSITORY:
        raise ValueError("发布记录的软件仓库或格式不匹配")
    version = normalized_version(record.get("version"))
    release = record.get("release")
    source = record.get("source")
    if not isinstance(release, dict) or not isinstance(source, dict):
        raise ValueError("发布记录缺少发行版或源码信息")
    commit = source.get("merge_commit")
    if (
        release.get("tag") != "v" + version or release.get("draft") is not False
        or release.get("prerelease") is not False or not release.get("published_at")
        or release.get("tag_commit_verified") is not True
        or not isinstance(commit, str) or re.fullmatch(r"[0-9a-f]{40}", commit) is None
        or release.get("target_commit") != commit
    ):
        raise ValueError("发行版尚未公开或版本标签、源码提交未经确认")
    names = {asset_name_for_version(version, managed=value) for value in (False, True)}
    names |= {name + ".sha256" for name in tuple(names)}
    assets = release.get("assets")
    if not isinstance(assets, list) or len(assets) != len(names):
        raise ValueError("正式发行版必须包含两个 ZIP 和两个校验文件")
    verified = {}
    for asset in assets:
        if not isinstance(asset, dict):
            raise ValueError("发布附件记录格式无效")
        name, digest, size = asset.get("name"), asset.get("digest"), asset.get("size")
        if (
            name not in names or name in verified or asset.get("state") != "uploaded"
            or not isinstance(digest, str) or re.fullmatch(r"sha256:[0-9a-f]{64}", digest) is None
            or type(size) is not int or size <= 0
        ):
            raise ValueError("正式附件名称、状态、大小或摘要无效")
        verified[name] = (digest[7:], size)
    return version, verified


def copy_verified(source, destination, digest):
    """独占创建归档文件，不覆盖已有版本；失败时只移除本函数创建的半成品。"""
    if destination.exists():
        if not destination.is_file() or file_sha256(destination) != digest:
            raise ValueError(f"已有归档内容不同，未覆盖：{destination.name}")
        return False
    identity = None
    try:
        with destination.open("xb") as output:
            info = os.fstat(output.fileno())
            identity = (info.st_dev, info.st_ino)
            with source.open("rb") as input_file:
                shutil.copyfileobj(input_file, output, 1024 * 1024)
        if file_sha256(destination) != digest:
            raise ValueError(f"复制后的归档摘要不符：{destination.name}")
    except Exception:
        path = checked_path(destination)
        if identity is not None and path.is_file():
            info = path.stat()
            if (info.st_dev, info.st_ino) == identity:
                path.unlink()
        raise
    return True


def prune_generated_copies(plans, source_directory):
    """归档完整后才删除已验证的生成副本，保留测试入口必需的 managed ZIP 和未知文件。"""
    keep = set()
    kit_path = checked_path(source_directory.parent / "local-test-kit.json")
    if kit_path.exists():
        kit = read_json(kit_path)
        if kit.get("app_id") != APP_ID or type(kit.get("schema")) is not int or kit["schema"] != 1:
            raise ValueError("测试包标记无效，已归档但未清理测试输入")
        # 修复清理正式包时可能破坏已打包测试入口的问题：该入口固定读取本地缓存。
        keep.add(asset_name_for_version(kit.get("version"), managed=True))
    removable = []
    for source, target, digest, kind in plans:
        if source == target or kind == "notes" or (kind == "asset" and source.name in keep):
            continue
        source, target = checked_path(source), checked_path(target)
        if file_sha256(source) != digest or file_sha256(target) != digest:
            raise ValueError(f"清理前文件发生变化，保留生成副本：{source.name}")
        removable.append(source)
    removed = []
    for source in removable:
        source.unlink()
        removed.append(str(source))
    return removed


def archive_release(source_dir, record_path, archive_root=ARCHIVE_ROOT, notes=None, verification=None, prune_source=False):
    """归档发布附件和记录，支持重复执行、补齐中断任务，不修改程序或 GitHub Release。"""
    source_dir, record_path, archive_root = map(checked_path, (source_dir, record_path, archive_root))
    version, assets = published_assets(read_json(record_path))
    destination = checked_path(archive_root / ("v" + version))
    plans = []
    for name, (digest, size) in assets.items():
        target = checked_path(destination / name)
        source = checked_path(source_dir / name)
        if not source.exists():
            source = target  # 已清理的源附件可以从上次成功归档复核，不重新生成。
        if not source.is_file() or source.stat().st_size != size or file_sha256(source) != digest:
            raise ValueError(f"待归档附件与正式发布记录不符：{name}")
        plans.append((source, target, digest, "asset"))
    for source, name, kind in (
        (record_path, "release-publication.json", "record"),
        (notes, "发布说明.md", "notes"),
        (verification, "packaging-verification.json", "verification"),
    ):
        if source is not None:
            source = checked_path(source)
            if kind == "verification" and normalized_version(read_json(source).get("version")) != version:
                raise ValueError("打包验证记录版本与正式发行版不同")
            plans.append((source, checked_path(destination / name), file_sha256(source), kind))
    for managed in (False, True):
        name = asset_name_for_version(version, managed=managed)
        checksum = next(source for source, target, digest, kind in plans if target.name == name + ".sha256")
        if checksum.read_text(encoding="ascii").split() != [assets[name][0], name]:
            raise ValueError(f"校验文件内容与正式 ZIP 不匹配：{name}")
    # 所有冲突先检查，不能复制一半后才发现已有归档需要被覆盖。
    for source, target, digest, kind in plans:
        if target.exists() and (not target.is_file() or file_sha256(target) != digest):
            raise ValueError(f"已有归档内容不同，未覆盖：{target.name}")
    destination.mkdir(parents=True, exist_ok=True)
    copied = sum(copy_verified(source, target, digest) for source, target, digest, kind in plans)
    for source, target, digest, kind in plans:
        if file_sha256(checked_path(target)) != digest:
            raise ValueError(f"归档复核失败：{target.name}")
    removed = prune_generated_copies(plans, source_dir) if prune_source else []
    return {"version": version, "archive": str(destination), "verified_files": len(plans),
            "copied_files": copied, "removed_generated_files": removed}


def main():
    """只在发布及线上核验成功后调用，不联网、不编译、不触发新版本发布。"""
    parser = argparse.ArgumentParser(description="正式发布成功后的本地归档和生成副本清理")
    parser.add_argument("--source", type=Path, required=True, help="正式附件原输出目录")
    parser.add_argument("--record", type=Path, required=True, help="已确认发布成功的 JSON 记录")
    parser.add_argument("--notes", type=Path, help="版本发布说明 Markdown")
    parser.add_argument("--verification", type=Path, help="同版本打包验证 JSON")
    parser.add_argument("--prune-source", action="store_true", help="完整归档后清理冗余生成副本，保留测试必需输入")
    args = parser.parse_args()
    try:
        result = archive_release(args.source, args.record, notes=args.notes,
                                 verification=args.verification, prune_source=args.prune_source)
    except (OSError, ValueError, UpdateError) as exc:
        parser.exit(1, f"归档未完成：{exc}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
