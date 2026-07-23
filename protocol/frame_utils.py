#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""协议帧数据的公共校验与标准化工具。"""

from typing import List, Optional


def validate_frame_length(frame_length: int, label: str = "帧长度") -> int:
    """校验帧长度并返回标准整数值。"""

    if isinstance(frame_length, bool) or not isinstance(frame_length, int):
        raise ValueError(f"{label}必须是正整数")
    if frame_length <= 0:
        raise ValueError(f"{label}必须是正整数")
    return frame_length


def normalize_frame(
    frame,
    *,
    expected_length: Optional[int] = None,
    allow_empty: bool = False,
    label: str = "帧数据",
) -> List[int]:
    """把帧标准化为独立列表，并严格校验字节类型、范围和长度。"""

    if expected_length is not None:
        expected_length = validate_frame_length(expected_length, "期望帧长度")

    if not isinstance(frame, (list, tuple, bytes, bytearray)):
        raise ValueError(f"{label}必须是字节序列")

    normalized: List[int] = []
    for index, value in enumerate(frame):
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"{label}第 {index + 1} 个值必须是 0-255 的整数")
        if not (0 <= value <= 0xFF):
            raise ValueError(f"{label}第 {index + 1} 个值必须是 0-255 的整数")
        normalized.append(value)

    if not normalized and not allow_empty:
        raise ValueError(f"{label}不能为空")
    if expected_length is not None and len(normalized) != expected_length:
        raise ValueError(
            f"{label}长度不匹配，期望 {expected_length} 字节，实际 {len(normalized)} 字节"
        )

    return normalized
