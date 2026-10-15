#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""查询公开 GitHub Release，并流式下载经过大小和 SHA-256 校验的更新包。"""

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from app_info import APP_VERSION, GITHUB_REPOSITORY

MAX_DOWNLOAD_BYTES = 256 * 1024 * 1024
MAX_METADATA_BYTES = 2 * 1024 * 1024
NETWORK_TIMEOUT_SECONDS = 15
ALLOWED_HOSTS = frozenset((
    "api.github.com", "github.com", "release-assets.githubusercontent.com",
    "objects.githubusercontent.com", "github-releases.githubusercontent.com",
))


class UpdateError(Exception):
    """向用户显示可理解的更新失败原因。"""


class UpdateCancelled(UpdateError):
    """用户主动取消更新，不作为程序错误处理。"""


def parse_version(value):
    """按数字比较两段或三段版本号，避免将 1.9 错判为高于 1.10。"""
    if not isinstance(value, str):
        raise UpdateError("版本号必须是字符串")
    match = re.fullmatch(r"[vV]?([0-9]{1,6})\.([0-9]{1,6})(?:\.([0-9]{1,6}))?", value)
    if match is None:
        raise UpdateError("版本号必须使用 v1.57.0 或 1.57.0 格式")
    return tuple(int(part or 0) for part in match.groups())


def normalized_version(value):
    """返回不带 v 前缀的三段软件版本号。"""
    return ".".join(str(part) for part in parse_version(value))


def asset_name_for_version(version):
    """生成与发布工具一致的 Windows 完整包附件名。"""
    return f"AD-OneLine-v{normalized_version(version)}-windows-x64.zip"


def validate_https_url(url):
    """仅允许官方 GitHub HTTPS 地址，重定向也不能降低为明文下载。"""
    if not isinstance(url, str):
        raise UpdateError("更新下载地址无效")
    try:
        parsed = urlsplit(url)
        valid = (
            parsed.scheme == "https" and parsed.hostname in ALLOWED_HOSTS
            and parsed.port in (None, 443) and not parsed.username
            and not parsed.password and not parsed.fragment
        )
    except ValueError as exc:
        raise UpdateError("更新下载地址无效") from exc
    if not valid:
        raise UpdateError("更新地址必须使用官方 GitHub HTTPS 域名")
    return url


class SafeRedirectHandler(HTTPRedirectHandler):
    """下载附件允许 GitHub 官方存储重定向，拒绝其他域名。"""

    def redirect_request(self, request, fp, code, message, headers, new_url):
        """在跟随重定向之前校验目标，避免下载到非指定来源。"""
        validate_https_url(new_url)
        return super().redirect_request(request, fp, code, message, headers, new_url)


def open_url(request):
    """使用系统证书和网络代理，并限制每次网络操作的超时。"""
    validate_https_url(request.full_url)
    return build_opener(SafeRedirectHandler()).open(
        request, timeout=NETWORK_TIMEOUT_SECONDS
    )


def check_cancelled(cancelled):
    """在分块操作之间响应用户取消。"""
    if cancelled is not None and cancelled():
        raise UpdateCancelled("已取消更新")


@dataclass(frozen=True)
class ReleaseInfo:
    """一次检测得到的稳定发行版和不可变的下载校验信息。"""

    version: str
    tag: str
    title: str
    notes: str
    page_url: str
    download_url: str
    sha256: str
    size: int


def parse_release(data, current_version=APP_VERSION):
    """解析高于当前版本的稳定发行版，旧版本和预发布版本不触发升级。"""
    if not isinstance(data, dict):
        raise UpdateError("服务器返回的发行版信息无效")
    if data.get("draft") or data.get("prerelease"):
        return None
    tag = data.get("tag_name")
    version = normalized_version(tag)
    if parse_version(version) <= parse_version(current_version):
        return None
    asset_name = asset_name_for_version(version)
    assets = data.get("assets")
    if not isinstance(assets, list):
        raise UpdateError("新版本未提供更新附件")
    matches = [asset for asset in assets if isinstance(asset, dict) and asset.get("name") == asset_name]
    if len(matches) != 1:
        raise UpdateError(f"新版本缺少唯一的完整更新包：{asset_name}")
    asset = matches[0]
    expected_url = f"https://github.com/{GITHUB_REPOSITORY}/releases/download/{tag}/{asset_name}"
    if asset.get("browser_download_url") != expected_url:
        raise UpdateError("更新包地址与指定仓库或版本不一致")
    digest = asset.get("digest", "")
    if not isinstance(digest, str) or re.fullmatch(r"sha256:[0-9a-fA-F]{64}", digest) is None:
        raise UpdateError("新版本附件缺少有效的 SHA-256 校验信息，请联系作者")
    size = asset.get("size")
    if isinstance(size, bool) or not isinstance(size, int) or not (0 < size <= MAX_DOWNLOAD_BYTES):
        raise UpdateError("更新包大小无效或超过 256MB")
    if asset.get("state") != "uploaded":
        raise UpdateError("更新包尚未上传完成")
    return ReleaseInfo(
        version=version, tag=tag,
        title=str(data.get("name") or tag)[:200],
        notes=str(data.get("body") or "此版本没有填写更新说明。")[:16000],
        page_url=f"https://github.com/{GITHUB_REPOSITORY}/releases/tag/{tag}",
        download_url=validate_https_url(expected_url), sha256=digest[7:].lower(), size=size,
    )


def fetch_latest_release(current_version=APP_VERSION, opener=open_url):
    """手动查询最新稳定版，仓库尚无发行版时视为没有可用更新。"""
    request = Request(
        f"https://api.github.com/repos/{GITHUB_REPOSITORY}/releases/latest",
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": f"AD-OneLine/{APP_VERSION}",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with opener(request) as response:
            validate_https_url(response.geturl())
            raw = response.read(MAX_METADATA_BYTES + 1)
        if len(raw) > MAX_METADATA_BYTES:
            raise UpdateError("更新信息过大，已停止读取")
        return parse_release(json.loads(raw.decode("utf-8")), current_version)
    except HTTPError as exc:
        if exc.code == 404:
            return None
        if exc.code in (403, 429):
            raise UpdateError("GitHub 请求受到限制，请稍后再试") from exc
        raise UpdateError(f"检测更新失败，服务器状态码：{exc.code}") from exc
    except (URLError, OSError, TimeoutError) as exc:
        raise UpdateError(f"无法连接 GitHub，请检查网络后重试：{exc}") from exc
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise UpdateError("服务器返回的更新信息无法解析") from exc


def download_release(release, destination, progress=None, cancelled=None, opener=open_url):
    """分块下载到新文件，校验真实大小和摘要；失败或取消时移除未完成文件。"""
    destination = Path(destination)
    created = False
    try:
        check_cancelled(cancelled)
        request = Request(validate_https_url(release.download_url), headers={
            "User-Agent": f"AD-OneLine/{APP_VERSION}", "Accept": "application/octet-stream",
        })
        with opener(request) as response, destination.open("xb") as output:
            created = True
            validate_https_url(response.geturl())
            digest = hashlib.sha256()
            received = 0
            while True:
                check_cancelled(cancelled)
                chunk = response.read(256 * 1024)
                if not chunk:
                    break
                received += len(chunk)
                if received > release.size or received > MAX_DOWNLOAD_BYTES:
                    raise UpdateError("实际下载大小超过发行版声明的大小")
                output.write(chunk)
                digest.update(chunk)
                if progress is not None:
                    progress(received, release.size)
        check_cancelled(cancelled)
        if received != release.size:
            raise UpdateError("更新包下载不完整，请重新下载")
        if digest.hexdigest() != release.sha256:
            raise UpdateError("更新包 SHA-256 校验失败，请重新下载")
    except Exception as exc:
        if created:
            destination.unlink(missing_ok=True)
        if isinstance(exc, UpdateError):
            raise
        raise UpdateError(f"下载更新失败：{exc}") from exc
