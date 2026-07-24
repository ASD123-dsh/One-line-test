#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Offline activation helpers for the distributed desktop build."""

from __future__ import annotations

import base64
import json
import os
import subprocess
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, List, Optional, Tuple

import rsa

LICENSE_SCOPE = "sifexe-offline-activation-v2"
LEGACY_LICENSE_SCOPE = "sifexe-offline-activation-v1"
LICENSE_FILE_NAME = "activation_license.json"
ACTIVATION_TOKEN_VERSION = 2
DEFAULT_VALIDITY_VALUE = 30
DEFAULT_VALIDITY_UNIT = "days"
INVALID_UUID_MARKERS = {
    "",
    "00000000-0000-0000-0000-000000000000",
    "FFFFFFFF-FFFF-FFFF-FFFF-FFFFFFFFFFFF",
}
PUBLIC_KEY_PEM = """-----BEGIN RSA PUBLIC KEY-----
MIIBCgKCAQEAj9grUqF7QHBnm4f3xKRRLPOo2HFIoRkmy/UNtDoj9LN85CHgyFUL
pi/EEabz5cDjTAQhQE1WfTzXw5iTV3BWLbUGdXqQpo/2At47hXPKQc36e65Nbxfq
+AvLCRBGl6wuJZDOxE3BLyBGLA9SGOrcOBft+Tx/ET8JehNplZjkRVI+YoBPZeJQ
vkgiRMDq5CyLA5bMmNqFECY+Zm3ZsPnhsgv5ICy9XnPH6zcil2MXtxsHHn8u6Lph
g9jBxh7med26lhXlLzyupBxzCfJRu8qyaNobQHE1LHlv4vO3jBKJIMSzOpgAqC+s
+4mIfygzNKjfcIokCa7SrR7J59kWLcm9QQIDAQAB
-----END RSA PUBLIC KEY-----"""

DURATION_UNITS = {
    "hours": ("小时", 3600),
    "days": ("天", 86400),
    "weeks": ("周", 7 * 86400),
    "months": ("月", 30 * 86400),
    "years": ("年", 365 * 86400),
}


def _normalize_base64_token(token: str) -> str:
    if not isinstance(token, str):
        return ""
    return "".join(token.strip().split())


def _encode_token_part(raw_bytes: bytes) -> str:
    return base64.urlsafe_b64encode(raw_bytes).decode("ascii").rstrip("=")


def _decode_token_part(encoded: str) -> bytes:
    padding = "=" * (-len(encoded) % 4)
    return base64.urlsafe_b64decode(encoded + padding)


def _serialize_payload(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def normalize_device_code(device_code: str) -> str:
    if not isinstance(device_code, str):
        return ""

    raw = device_code.strip().upper()
    filtered = "".join(ch for ch in raw if ch.isalnum())
    if len(filtered) == 32 and all(ch in "0123456789ABCDEF" for ch in filtered):
        return (
            f"{filtered[0:8]}-{filtered[8:12]}-{filtered[12:16]}-"
            f"{filtered[16:20]}-{filtered[20:32]}"
        )
    return raw


def build_legacy_activation_message(device_code: str) -> bytes:
    normalized_code = normalize_device_code(device_code)
    return f"{LEGACY_LICENSE_SCOPE}|{normalized_code}".encode("utf-8")


def build_validity_seconds(validity_value: int, validity_unit: str) -> int:
    if (
        isinstance(validity_value, bool)
        or not isinstance(validity_value, int)
        or validity_value <= 0
    ):
        raise ValueError("有效时长必须大于 0")
    unit_info = DURATION_UNITS.get(validity_unit)
    if unit_info is None:
        raise ValueError("不支持的有效时长单位")
    return validity_value * unit_info[1]


def describe_validity_duration(validity_value: int, validity_unit: str) -> str:
    if (
        isinstance(validity_value, bool)
        or not isinstance(validity_value, int)
        or validity_value <= 0
    ):
        raise ValueError("有效时长必须大于 0")
    unit_info = DURATION_UNITS.get(validity_unit)
    if unit_info is None:
        raise ValueError("不支持的有效时长单位")
    return f"{validity_value}{unit_info[0]}"


def format_remaining_duration(remaining_seconds: Optional[int]) -> str:
    if remaining_seconds is None:
        return "长期有效"
    if remaining_seconds <= 0:
        return "已到期"

    minutes, _ = divmod(remaining_seconds, 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)

    parts = []
    if days:
        parts.append(f"{days}天")
    if hours and len(parts) < 2:
        parts.append(f"{hours}小时")
    if minutes and len(parts) < 2:
        parts.append(f"{minutes}分钟")
    if not parts:
        return "不足1分钟"
    return "".join(parts)


def _build_signed_payload(
    device_code: str,
    *,
    issued_at: datetime,
    expires_at: datetime,
) -> dict:
    return {
        "scope": LICENSE_SCOPE,
        "version": ACTIVATION_TOKEN_VERSION,
        "device_code": normalize_device_code(device_code),
        "issued_at": issued_at.isoformat(timespec="seconds"),
        "expires_at": expires_at.isoformat(timespec="seconds"),
    }


def generate_activation_code(
    device_code: str,
    private_key: rsa.PrivateKey,
    *,
    validity_seconds: Optional[int] = None,
    issued_at: Optional[datetime] = None,
) -> str:
    if validity_seconds is None:
        signature = rsa.sign(
            build_legacy_activation_message(device_code),
            private_key,
            "SHA-256",
        )
        return _encode_token_part(signature)

    if validity_seconds <= 0:
        raise ValueError("有效时长必须大于 0")

    issued_at = issued_at or datetime.now()
    expires_at = issued_at + timedelta(seconds=validity_seconds)
    payload = _build_signed_payload(
        device_code,
        issued_at=issued_at,
        expires_at=expires_at,
    )
    payload_bytes = _serialize_payload(payload)
    signature = rsa.sign(payload_bytes, private_key, "SHA-256")
    return f"{_encode_token_part(payload_bytes)}.{_encode_token_part(signature)}"


def inspect_activation_code(
    device_code: str,
    activation_code: str,
    public_key: rsa.PublicKey,
    *,
    now: Optional[datetime] = None,
) -> dict:
    normalized_device_code = normalize_device_code(device_code)
    normalized_token = _normalize_base64_token(activation_code)
    current_time = now or datetime.now()

    invalid_result = {
        "valid": False,
        "reason": "invalid",
        "is_legacy": False,
        "is_expired": False,
        "expires_at": None,
        "issued_at": None,
        "remaining_seconds": None,
        "remaining_text": "未激活",
    }

    if not normalized_token:
        return invalid_result

    if "." not in normalized_token:
        try:
            signature = _decode_token_part(normalized_token)
            rsa.verify(
                build_legacy_activation_message(normalized_device_code),
                signature,
                public_key,
            )
        except (ValueError, rsa.VerificationError):
            return invalid_result

        return {
            "valid": True,
            "reason": "",
            "is_legacy": True,
            "is_expired": False,
            "expires_at": None,
            "issued_at": None,
            "remaining_seconds": None,
            "remaining_text": "长期有效",
        }

    try:
        payload_part, signature_part = normalized_token.split(".", 1)
        payload_bytes = _decode_token_part(payload_part)
        signature = _decode_token_part(signature_part)
        payload = json.loads(payload_bytes.decode("utf-8"))
        rsa.verify(_serialize_payload(payload), signature, public_key)
    except (ValueError, json.JSONDecodeError, rsa.VerificationError):
        return invalid_result

    if (
        not isinstance(payload, dict)
        or payload.get("scope") != LICENSE_SCOPE
        or payload.get("version") != ACTIVATION_TOKEN_VERSION
    ):
        return invalid_result

    if normalize_device_code(payload.get("device_code", "")) != normalized_device_code:
        result = invalid_result.copy()
        result["reason"] = "device_mismatch"
        return result

    issued_at = _parse_datetime(payload.get("issued_at"))
    expires_at = _parse_datetime(payload.get("expires_at"))
    if expires_at is None:
        return invalid_result

    remaining_seconds = int((expires_at - current_time).total_seconds())
    is_expired = remaining_seconds <= 0
    return {
        "valid": not is_expired,
        "reason": "expired" if is_expired else "",
        "is_legacy": False,
        "is_expired": is_expired,
        "expires_at": expires_at,
        "issued_at": issued_at,
        "remaining_seconds": max(remaining_seconds, 0),
        "remaining_text": format_remaining_duration(max(remaining_seconds, 0)),
    }


def verify_activation_code(
    device_code: str,
    activation_code: str,
    public_key: rsa.PublicKey,
    *,
    now: Optional[datetime] = None,
) -> bool:
    return inspect_activation_code(
        device_code,
        activation_code,
        public_key,
        now=now,
    )["valid"]


def get_default_license_path() -> Path:
    """返回默认授权文件路径，不在查询阶段创建目录。"""

    appdata_dir = os.getenv("APPDATA")
    if appdata_dir:
        base_dir = Path(appdata_dir) / "AD仪表一线通协议测试工具"
    else:
        base_dir = Path.home() / ".ad_meter_single_wire_tool"
    return base_dir / LICENSE_FILE_NAME


def _run_identifier_command(command: List[str]) -> str:
    """执行设备标识命令，并用短超时避免阻塞应用启动。"""

    startupinfo = None
    if os.name == "nt":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

    try:
        output = subprocess.check_output(
            command,
            stderr=subprocess.DEVNULL,
            startupinfo=startupinfo,
            text=True,
            encoding="utf-8",
            errors="ignore",
            timeout=3.0,
        )
    except Exception:
        return ""

    lines = [line.strip() for line in output.splitlines() if line.strip()]
    if not lines:
        return ""

    candidate = lines[-1].upper()
    if candidate in INVALID_UUID_MARKERS:
        return ""
    return candidate


def _read_windows_machine_guid() -> str:
    if os.name != "nt":
        return ""

    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Cryptography",
        ) as key:
            value, _ = winreg.QueryValueEx(key, "MachineGuid")
    except Exception:
        return ""

    value = str(value).strip().upper()
    if not value:
        return ""
    return value


def get_current_device_code() -> str:
    """按优先级读取设备码，成功后立即停止后续慢速探测。"""

    identifier_commands = [
        [
            "powershell",
            "-NoProfile",
            "-Command",
            "(Get-CimInstance Win32_ComputerSystemProduct).UUID",
        ],
        ["wmic", "csproduct", "get", "uuid"],
    ]

    for command in identifier_commands:
        candidate = _run_identifier_command(command)
        normalized = normalize_device_code(candidate)
        if normalized and normalized not in INVALID_UUID_MARKERS:
            return normalized

    candidate = _read_windows_machine_guid()
    normalized = normalize_device_code(candidate)
    if normalized and normalized not in INVALID_UUID_MARKERS:
        return normalized

    fallback = os.getenv("COMPUTERNAME") or os.getenv("HOSTNAME") or "UNKNOWN-DEVICE"
    return normalize_device_code(fallback)


def _write_json_atomically(path: Path, payload: dict) -> None:
    """在目标目录写临时文件后原子替换，避免中断时破坏旧授权。"""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Optional[Path] = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=str(path.parent),
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as file_obj:
            temporary_path = Path(file_obj.name)
            json.dump(payload, file_obj, ensure_ascii=False, indent=2)
            file_obj.flush()
            os.fsync(file_obj.fileno())

        os.replace(str(temporary_path), str(path))
        temporary_path = None
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink()
            except OSError:
                pass


class ActivationService:
    """Manage offline activation state for the desktop app."""

    def __init__(
        self,
        *,
        public_key_pem: str = PUBLIC_KEY_PEM,
        license_path: Optional[Path] = None,
        device_code_provider: Optional[Callable[[], str]] = None,
        now_provider: Optional[Callable[[], datetime]] = None,
    ):
        self.public_key = rsa.PublicKey.load_pkcs1(public_key_pem.encode("ascii"))
        self.license_path = Path(license_path) if license_path else get_default_license_path()
        self.device_code_provider = device_code_provider or get_current_device_code
        self.now_provider = now_provider or datetime.now
        self._device_code_cache: Optional[str] = None

    def _now(self) -> datetime:
        return self.now_provider()

    def get_device_code(self) -> str:
        if self._device_code_cache is None:
            self._device_code_cache = normalize_device_code(self.device_code_provider())
        return self._device_code_cache

    def load_license_record(self) -> Optional[dict]:
        try:
            with self.license_path.open("r", encoding="utf-8") as file_obj:
                record = json.load(file_obj)
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            return None

        if not isinstance(record, dict):
            return None
        if not isinstance(record.get("device_code"), str):
            return None
        if not isinstance(record.get("activation_code"), str):
            return None
        return record

    def get_license_info(self) -> dict:
        record = self.load_license_record()
        if not record:
            return {
                "activated": False,
                "is_expired": False,
                "remaining_seconds": None,
                "remaining_text": "未激活",
                "expires_at": None,
                "is_legacy": False,
            }

        device_code = normalize_device_code(record.get("device_code", ""))
        activation_code = record.get("activation_code", "")
        if not device_code or not activation_code or device_code != self.get_device_code():
            return {
                "activated": False,
                "is_expired": False,
                "remaining_seconds": None,
                "remaining_text": "未激活",
                "expires_at": None,
                "is_legacy": False,
            }

        result = inspect_activation_code(
            device_code,
            activation_code,
            self.public_key,
            now=self._now(),
        )
        return {
            "activated": result["valid"],
            "is_expired": result["is_expired"],
            "remaining_seconds": result["remaining_seconds"],
            "remaining_text": (
                "长期有效" if result["is_legacy"] else result["remaining_text"]
            ),
            "expires_at": result["expires_at"],
            "is_legacy": result["is_legacy"],
        }

    def get_remaining_validity_text(self) -> str:
        return self.get_license_info()["remaining_text"]

    def is_activated(self) -> bool:
        return self.get_license_info()["activated"]

    def activate(self, activation_code: str) -> Tuple[bool, str]:
        device_code = self.get_device_code()
        result = inspect_activation_code(
            device_code,
            activation_code,
            self.public_key,
            now=self._now(),
        )
        if not result["valid"]:
            if result["reason"] == "expired":
                return False, "激活码已过期，请重新生成新的激活码。"
            if result["reason"] == "device_mismatch":
                return False, "激活码与当前设备码不匹配。"
            return False, "激活码无效，请检查后重新输入。"

        record = {
            "device_code": device_code,
            "activation_code": _normalize_base64_token(activation_code),
            "activated_at": self._now().isoformat(timespec="seconds"),
            "license_scope": LICENSE_SCOPE,
            "expires_at": (
                result["expires_at"].isoformat(timespec="seconds")
                if result["expires_at"] is not None
                else None
            ),
            "remaining_text": "长期有效" if result["is_legacy"] else result["remaining_text"],
        }

        try:
            _write_json_atomically(self.license_path, record)
        except OSError as exc:
            return False, f"激活信息保存失败：{exc}"

        return True, "激活成功。"
