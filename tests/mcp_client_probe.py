#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""独立SDK进程的STDIO端到端探针，仅接受宿主测试创建的合成连接文件。"""

import argparse
import asyncio
import json
from pathlib import Path
import sys

from mcp import Client, StdioServerParameters


async def exercise(connection_file, server_path):
    """分别测试旧握手和当前协议，所有串口和授权均来自宿主的隔离假设备。"""
    summaries = []
    for mode in ("legacy", "auto"):
        parameters = StdioServerParameters(command=sys.executable, args=["-B", "-X", "utf8", str(server_path), "--connection-file", str(connection_file)])
        async with Client(parameters, mode=mode, read_timeout_seconds=20) as client:
            tools = (await client.list_tools()).tools
            assert len(tools) == 19
            names = {item.name for item in tools}
            assert "one_line_send_once" in names and "one_line_run_case" in names
            assert not any("grant" in name or "activation" in name or "update" in name for name in names)
            assert next(item for item in tools if item.name == "one_line_status").annotations.read_only_hint is True
            assert next(item for item in tools if item.name == "one_line_request_connection").annotations.read_only_hint is False

            async def call(name, arguments=None, ok=True):
                """只读取SDK结构化结果，失败时不显示连接文件或令牌。"""
                response = await client.call_tool(name, arguments or {})
                data = response.structured_content
                assert isinstance(data, dict), (name, response)
                assert data.get("ok") is ok, (name, data)
                return data.get("result") if ok else data["error"]

            assert (await call("one_line_status", ok=False))["code"] == "CONNECTION_REQUIRED"
            assert (await call("one_line_connection_status"))["state"] == "not_requested"
            pending = await call("one_line_request_connection")
            assert pending["state"] == "pending"
            print(json.dumps({"event": "awaiting_test_decision", "request_id": pending["request_id"]}), flush=True)
            for _ in range(100):
                connection = await call("one_line_connection_status")
                if connection["state"] == "approved":
                    break
                await asyncio.sleep(0.05)
            else:
                raise AssertionError("宿主测试未确认连接申请")
            assert connection["access"] == "read_only"
            assert (await call("one_line_send_once", ok=False))["code"] == "READ_ONLY"
            print(json.dumps({"event": "awaiting_test_grant"}), flush=True)
            for _ in range(100):
                status = await call("one_line_status")
                if status["write_authorized"]:
                    break
                await asyncio.sleep(0.05)
            else:
                raise AssertionError("宿主测试未授予合成设备权限")
            assert status["write_seconds_remaining"] is None
            assert len((await call("one_line_protocols"))["protocols"]) == 20
            await call("one_line_select_protocol", {"protocol": "星恒智能BMS", "scenario_id": 3})
            await call("one_line_configure", {"parameters": {"xingheng_message_id": 0x3A, "xingheng_soc_percent": 50.5}, "interval_ms": 10})
            preview = await call("one_line_preview")
            assert len(preview["bytes"]) == 31 and preview["bytes"][3] == 101, (mode, preview["bytes"])
            invalid = await client.call_tool("one_line_set_raw_frame", {"frame": [True] * 31})
            assert invalid.is_error
            assert (await call("one_line_preview"))["bytes"] == preview["bytes"]
            await call("one_line_connect", {"port": "COM9", "baud_rate": 115200})
            first = await call("one_line_send_once")
            assert first["state"] in {"accepted", "completed"}
            for _ in range(100):
                status = await call("one_line_status")
                if status["case"]["state"] == "completed":
                    break
                await asyncio.sleep(0.01)
            assert status["case"]["sent_frames"] == 1
            started = await call("one_line_start_cycle", {"duration_ms": 500})
            await asyncio.sleep(0.04)
            await call("one_line_configure", {"parameters": {"xingheng_soc_percent": 20.5}})
            await asyncio.sleep(0.04)
            await call("one_line_stop", {"case_id": started["id"]})
            for _ in range(100):
                status = await call("one_line_status")
                if not status["serial"]["cyclic_sending"] and status["case"]["state"] != "stopping":
                    break
                await asyncio.sleep(0.01)
            records = await call("one_line_results", {"after_id": 0, "limit": 256})
            frames = [item["frame"] for item in records["events"] if item["type"] == "written"]
            assert any(len(frame) == 31 and frame[3] == 41 for frame in frames)
            await call("one_line_configure", {"parameters": {"xingheng_message_id": 1}})
            public = (await call("one_line_preview"))["bytes"]
            assert len(public) == 20 and public[0] == 1
            await call("one_line_set_raw_frame", {"frame": [255] * 20})
            assert (await call("one_line_preview"))["bytes"] == [255] * 20
            case = await call("one_line_run_case", {"parameters": {"xingheng_soc_percent": 25}, "duration_ms": 80, "interval_ms": 10})
            assert case["case"]["state"] == "completed" and case["case"]["sent_frames"] > 0
            assert case["hardware_result"] == "not_observed"
            await call("one_line_disconnect")
            assert (await call("one_line_close_connection"))["state"] == "closed"
            assert (await call("one_line_status", ok=False))["code"] == "CONNECTION_REQUIRED"
            summaries.append({"mode": mode, "tools": len(tools), "protocols": 20, "run_case_frames": case["case"]["sent_frames"]})
    print(json.dumps({"event": "completed", "checks": summaries}), flush=True)


def main():
    """只由测试显式启动，不注册Codex、不读取真实授权、不写入客户配置。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--connection-file", type=Path, required=True)
    parser.add_argument("--server", type=Path, required=True)
    args = parser.parse_args()
    asyncio.run(exercise(args.connection_file, args.server))


if __name__ == "__main__":
    main()
