#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""应用日志和脱敏诊断导出，只包含显式白名单，不打包客户目录或授权文件。"""

import json
import logging
from logging.handlers import RotatingFileHandler
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

from app_info import APP_VERSION
from app_paths import user_data_directory

LOGGER = logging.getLogger("ad_oneline")


def configure_logging():
    """按需建立滚动日志，路径不可写时不阻止软件启动。"""
    if LOGGER.handlers:
        return
    LOGGER.setLevel(logging.INFO)
    try:
        root = user_data_directory() / "logs"
        root.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(root / "application.log", maxBytes=512 * 1024, backupCount=2, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        LOGGER.addHandler(handler)
    except OSError:
        LOGGER.addHandler(logging.NullHandler())


def diagnostic_report(protocol_name, port_status, recovery_notice=""):
    """仅导出协议、参数、计数和恢复状态，不导出串口身份、用户路径或原始日志。"""
    permitted = ("is_connected", "baud_rate", "cyclic_sending", "cyclic_frame_count", "send_interval_ms", "tosc_us")
    counters = ("sent_frames", "deferred_ticks", "backpressure_events", "errors", "queue_bytes", "write_ms", "actual_interval_ms")
    statistics = port_status.get("statistics", {})
    return {
        "schema": 1, "app_version": APP_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "python": ".".join(map(str, sys.version_info[:3])), "system": platform.system(),
        "protocol": protocol_name,
        "serial": {key: port_status.get(key) for key in permitted},
        "statistics": {key: statistics.get(key) for key in counters},
        "incomplete_update_detected": bool(recovery_notice),
        "note": "周期为软件写入调用间隔，不代表转码板单线侧的实测波形周期。",
    }


def export_diagnostics(path, protocol_name, port_status, recovery_notice=""):
    """导出用户指定的单个 JSON，不遍历安装目录或复制运行日志。"""
    raw = json.dumps(diagnostic_report(protocol_name, port_status, recovery_notice), ensure_ascii=False, indent=2)
    with Path(path).open("w", encoding="utf-8") as output:
        output.write(raw)
