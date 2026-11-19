#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""本机连接发现：会话令牌用当前Windows用户的DPAPI保护，不写入工程或Codex配置。"""

import base64
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import stat
from urllib.parse import urlsplit

from app_info import APP_ID
from app_paths import user_data_directory

MAX_DESCRIPTOR_BYTES = 8192


def connection_path():
    """仅使用本工具专属用户目录，安装目录和授权记录均不参与连接发现。"""
    return user_data_directory() / "ai-control" / "connection.json"


def checked_path(path):
    """拒绝链接或联接点，避免连接记录覆盖或清理跳出明确的用户目录。"""
    path = Path(path).absolute()
    for item in (path, *path.parents):
        if item.exists() or item.is_symlink():
            attributes = item.lstat()
            if stat.S_ISLNK(attributes.st_mode) or getattr(attributes, "st_file_attributes", 0) & 0x400:
                raise ValueError("AI连接文件路径不能包含链接")
    return path


def _crypt_token(raw, decrypt=False):
    """DPAPI只绑定当前用户，不使用机器范围保护，不弹出系统授权窗口。"""
    if os.name != "nt":
        raise OSError("本机AI连接目前仅支持Windows用户保护")

    class DataBlob(ctypes.Structure):
        """与Windows DATA_BLOB保持一致，仅在本次调用内持有数据。"""
        _fields_ = [("size", wintypes.DWORD), ("data", ctypes.POINTER(ctypes.c_ubyte))]

    buffer = (ctypes.c_ubyte * len(raw)).from_buffer_copy(raw)
    source = DataBlob(len(raw), buffer)
    output = DataBlob()
    crypt = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    function = crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    function.argtypes = [ctypes.POINTER(DataBlob), ctypes.c_void_p, ctypes.c_void_p,
                         ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(DataBlob)]
    function.restype = wintypes.BOOL
    if not function(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(output)):
        raise OSError("当前Windows用户无法读取AI会话保护数据")
    try:
        return ctypes.string_at(output.data, output.size)
    finally:
        kernel.LocalFree(output.data)


def protect_token(token):
    """只将加密后的会话令牌写入本机发现文件。"""
    return base64.b64encode(_crypt_token(token.encode("ascii"))).decode("ascii")


def unprotect_token(value):
    """仅当前Windows用户能恢复令牌；错误不显示密文或令牌内容。"""
    try:
        token = _crypt_token(base64.b64decode(value, validate=True), decrypt=True).decode("ascii")
        if not 32 <= len(token) <= 128:
            raise ValueError("无效长度")
        return token
    except (ValueError, UnicodeError, OSError) as exc:
        raise ValueError("AI连接记录无效或不属于当前Windows用户") from exc


def validate_endpoint(endpoint):
    """客户端只允许固定路径的IPv4回环HTTP，拒绝代理、其他主机及重定向地址。"""
    try:
        parsed = urlsplit(endpoint)
        if (parsed.scheme != "http" or parsed.hostname != "127.0.0.1"
                or parsed.username or parsed.password or parsed.query or parsed.fragment
                or parsed.path != "/v1/command" or parsed.port is None
                or not 1024 <= parsed.port <= 65535):
            raise ValueError("无效端点")
        return parsed
    except (TypeError, ValueError) as exc:
        raise ValueError("AI连接地址必须是本机专属接口") from exc


def read_descriptor(path=None):
    """受限读取发现文件，不扫描目录、不读取授权数据、不接受任意远程地址。"""
    path = checked_path(path if path is not None else connection_path())
    try:
        with path.open("rb") as stream:
            raw = stream.read(MAX_DESCRIPTOR_BYTES + 1)
    except FileNotFoundError as exc:
        raise ValueError("请先在一线通工具的“AI 本机接口”中开启服务") from exc
    if len(raw) > MAX_DESCRIPTOR_BYTES:
        raise ValueError("AI连接记录过大")
    try:
        data = json.loads(raw.decode("utf-8"))
        if (not isinstance(data, dict) or data.get("app_id") != APP_ID
                or type(data.get("schema")) is not int or data["schema"] != 1
                or not isinstance(data.get("session"), str) or len(data["session"]) != 32
                or not isinstance(data.get("protected_token"), str)):
            raise ValueError("无效记录")
        features = data.get("features", [])
        if not isinstance(features, list) or len(features) > 8 or any(not isinstance(item, str) or len(item) > 40 for item in features):
            raise ValueError("无效能力说明")
        validate_endpoint(data.get("endpoint"))
        return data
    except (ValueError, UnicodeError, TypeError) as exc:
        raise ValueError("AI连接记录格式无效") from exc


class ConnectionFile:
    """独占发布当前会话记录，关闭时只删除仍属于本次会话的原文件。"""

    def __init__(self, path=None):
        """仅保存位置，不在构造时写入任何文件。"""
        self.path = checked_path(path if path is not None else connection_path())
        self._published = None

    def publish(self, endpoint, token, session):
        """拒绝覆盖其他实例或崩溃残留，避免静默抢占另一个工具窗口。"""
        validate_endpoint(endpoint)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        checked_path(self.path)
        data = {"schema": 1, "app_id": APP_ID, "pid": os.getpid(), "session": session,
                "features": ["connection_requests", "client_sessions"],
                "endpoint": endpoint, "protected_token": protect_token(token)}
        raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
        try:
            descriptor = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError as exc:
            raise ValueError("已有AI连接记录；请先关闭其他实例，崩溃残留请按接入文档检查") from exc
        try:
            with os.fdopen(descriptor, "wb") as output:
                output.write(raw)
        except BaseException:
            # 这里只清理本函数刚独占创建的半成品，不接触其他会话文件。
            self.path.unlink(missing_ok=True)
            raise
        self._published = raw

    def remove(self):
        """内容被改动时保留现场，不删除其他会话或未知文件。"""
        if self._published is None:
            return
        path = checked_path(self.path)
        try:
            with path.open("rb") as source:
                raw = source.read(MAX_DESCRIPTOR_BYTES + 1)
            if raw == self._published:
                path.unlink()
        except FileNotFoundError:
            pass
        self._published = None
