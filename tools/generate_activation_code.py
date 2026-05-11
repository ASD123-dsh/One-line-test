#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate an offline activation code from a customer device code."""

import argparse
import sys
from pathlib import Path

import rsa

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from licensing.activation import (  # noqa: E402
    DEFAULT_VALIDITY_UNIT,
    DEFAULT_VALIDITY_VALUE,
    DURATION_UNITS,
    build_validity_seconds,
    describe_validity_duration,
    generate_activation_code,
    normalize_device_code,
)

DEFAULT_PRIVATE_KEY_PATH = Path(__file__).resolve().parents[1] / "keys" / "activation_private.pem"


def load_private_key(path: Path) -> rsa.PrivateKey:
    with path.open("rb") as file_obj:
        return rsa.PrivateKey.load_pkcs1(file_obj.read())


def main():
    parser = argparse.ArgumentParser(description="根据设备码生成离线激活码")
    parser.add_argument("device_code", nargs="?", help="客户发来的设备码")
    parser.add_argument(
        "--key",
        default=str(DEFAULT_PRIVATE_KEY_PATH),
        help="私钥文件路径，默认读取 keys/activation_private.pem",
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=DEFAULT_VALIDITY_VALUE,
        help="有效时长数值，默认 30",
    )
    parser.add_argument(
        "--unit",
        choices=list(DURATION_UNITS.keys()),
        default=DEFAULT_VALIDITY_UNIT,
        help="有效时长单位，默认 days",
    )
    args = parser.parse_args()

    device_code = args.device_code or input("请输入设备码: ").strip()
    normalized_device_code = normalize_device_code(device_code)
    if not normalized_device_code:
        raise SystemExit("设备码不能为空")

    private_key_path = Path(args.key)
    if not private_key_path.exists():
        raise SystemExit(f"未找到私钥文件：{private_key_path}")

    validity_seconds = build_validity_seconds(args.duration, args.unit)
    private_key = load_private_key(private_key_path)
    activation_code = generate_activation_code(
        normalized_device_code,
        private_key,
        validity_seconds=validity_seconds,
    )

    print("设备码:")
    print(normalized_device_code)
    print()
    print("有效时长:")
    print(describe_validity_duration(args.duration, args.unit))
    print()
    print("激活码:")
    print(activation_code)


if __name__ == "__main__":
    main()
