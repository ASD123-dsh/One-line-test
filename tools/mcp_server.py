#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Codex的STDIO MCP连接器：仅转发本机白名单命令，不运行界面、不连接第二份串口。"""

import argparse
from pathlib import Path
import sys
import time
from typing import NotRequired, TypedDict

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai_control.client import LocalClient
from ai_control.transport import failure


class ToolResponse(TypedDict):
    """显式声明JSON结果，确保MCP同时提供结构化内容而非只有文本JSON。"""
    ok: bool
    request_id: NotRequired[str]
    result: NotRequired[dict[str, object]]
    error: NotRequired[dict[str, str]]


def create_server(connection_file=None):
    """MCP依赖只在连接器进程内加载，原PyQt5程序和源码回归不依赖该SDK。"""
    from mcp.server import MCPServer
    from mcp_types import ToolAnnotations
    from pydantic import StrictInt
    server = MCPServer("AD-OneLine", instructions="先申请本机连接并等待用户在工具弹窗内确认，本次授权不设分钟数。禁止自行授权、读私钥、激活或升级。明确端口和测试目标后才发送；发送受理不是完成，软件写入不代表仪表或单线时序通过。")
    client = LocalClient(connection_file)
    read_only = ToolAnnotations(read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False)
    mutating = ToolAnnotations(read_only_hint=False, destructive_hint=True, idempotent_hint=False, open_world_hint=True)
    safe_stop = ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=True, open_world_hint=False)

    def call(operation, arguments=None):
        """发现文件缺失时提示打开工具；连接申请也不能启动应用或自行开启权限。"""
        try:
            return client.call(operation, arguments)
        except (ValueError, OSError):
            return failure("CONNECTION_UNAVAILABLE", "请先打开支持连接申请的一线通工具；旧测试包需手动开启AI接口。收到申请后仍需用户在工具中确认，不能自行授权")

    @server.tool(annotations=safe_stop)
    def one_line_request_connection() -> ToolResponse:
        """请求工具弹出人工确认；不自行授予权限。返回pending后查询connection_status，拒绝或失效后不得反复弹窗。"""
        return call("request_connection")

    @server.tool(annotations=read_only)
    def one_line_connection_status() -> ToolResponse:
        """只查询本次连接申请结果（pending/approved/rejected/expired）；批准前不返回测试数据。"""
        return call("connection_status")

    @server.tool(annotations=safe_stop)
    def one_line_close_connection() -> ToolResponse:
        """结束本连接器的AI会话及授权，只停止AI自己的任务，不断开用户串口或干预手动循环。"""
        return call("close_connection")

    @server.tool(annotations=read_only)
    def one_line_status() -> ToolResponse:
        """只读：查询当前协议、串口、权限和最近任务；也用于十秒内的存活检查。"""
        return call("status")

    @server.tool(annotations=read_only)
    def one_line_protocols() -> ToolResponse:
        """只读：查询本工具支持的全部协议、帧长和发送间隔范围。"""
        return call("protocols")

    @server.tool(annotations=read_only)
    def one_line_ports() -> ToolResponse:
        """只读：列出当前本机串口名称和描述，不包含硬件序列号。"""
        return call("ports")

    @server.tool(annotations=read_only)
    def one_line_parameters() -> ToolResponse:
        """只读：查询当前协议参数字段、值和类型，设置前使用preview检查编码结果。"""
        return call("parameters")

    @server.tool(annotations=read_only)
    def one_line_preview(parameters: dict | None = None) -> ToolResponse:
        """只读：预览当前帧或指定参数效果，不改变UI、不消耗流水号、不发送。"""
        return call("preview", {"parameters": parameters or {}})

    @server.tool(annotations=mutating)
    def one_line_select_protocol(protocol: str, scenario_id: StrictInt = 0) -> ToolResponse:
        """需界面授权：选择协议及场景（0正常、1回收、2故障、3自定义），不自动发送。"""
        return call("select_protocol", {"protocol": protocol, "scenario_id": scenario_id})

    @server.tool(annotations=mutating)
    def one_line_configure(parameters: dict, interval_ms: StrictInt | None = None, tosc_us: StrictInt | None = None) -> ToolResponse:
        """需界面授权：修改数据自定义参数，普通循环下一快照生效；星恒类型变更先停止。"""
        values = {"parameters": parameters}
        if interval_ms is not None:
            values["interval_ms"] = interval_ms
        if tosc_us is not None:
            values["tosc_us"] = tosc_us
        return call("configure", values)

    @server.tool(annotations=mutating)
    def one_line_set_raw_frame(frame: list[StrictInt]) -> ToolResponse:
        """需界面授权：设置原始帧并切入全部自定义，保持用户给定字节及错误校验，不发送。"""
        return call("set_raw_frame", {"frame": frame})

    @server.tool(annotations=mutating)
    def one_line_connect(port: str, baud_rate: StrictInt = 9600) -> ToolResponse:
        """需界面授权：连接明确的Windows COM口，会操作真实硬件；不得擅自选择端口。"""
        return call("connect", {"port": port, "baud_rate": baud_rate})

    @server.tool(annotations=mutating)
    def one_line_disconnect() -> ToolResponse:
        """需界面授权：空闲后断开当前串口，不强制关闭在途写入。"""
        return call("disconnect")

    @server.tool(annotations=mutating)
    def one_line_send_once() -> ToolResponse:
        """需界面授权：实际提交一帧，返回受理编号；必须查询任务及written事件确认写入完成。"""
        return call("send_once")

    @server.tool(annotations=mutating)
    def one_line_start_cycle(duration_ms: StrictInt) -> ToolResponse:
        """需界面授权：启动最长60秒的动态循环；十秒内需查询状态，否则自动停发。"""
        return call("start_cycle", {"duration_ms": duration_ms})

    @server.tool(annotations=mutating)
    def one_line_start_sequence(frames: list[list[StrictInt]], duration_ms: StrictInt) -> ToolResponse:
        """需界面授权：启动1～256帧固定包组，有时长及存活限制；参数变化不覆盖固定包组。"""
        return call("start_sequence", {"frames": frames, "duration_ms": duration_ms})

    @server.tool(annotations=safe_stop)
    def one_line_stop(case_id: str | None = None) -> ToolResponse:
        """安全停止AI自己的测试，撤销操作权后仍可用；不能撤回已进入驱动的帧。"""
        return call("stop", {"case_id": case_id} if case_id else {})

    @server.tool(annotations=read_only)
    def one_line_results(after_id: StrictInt = 0, limit: StrictInt = 100, request_id: str | None = None) -> ToolResponse:
        """只读：按游标读取真实写入和错误，或查询最近写请求ID结果，历史截断会明确标记。"""
        return call("results", {"request_id": request_id} if request_id else {"after_id": after_id, "limit": limit})

    @server.tool(annotations=mutating)
    def one_line_run_case(parameters: dict, duration_ms: StrictInt, interval_ms: StrictInt | None = None) -> ToolResponse:
        """需界面授权：应用参数、运行有界循环并等待结束，自动查询存活；按步骤多次调用可做参数扫描。"""
        if type(duration_ms) is not int or not 10 <= duration_ms <= 60000:
            return failure("INVALID_ARGUMENT", "时长必须为10～60000毫秒")
        configured = one_line_configure(parameters, interval_ms)
        if not configured.get("ok"):
            return configured
        started = one_line_start_cycle(duration_ms)
        if not started.get("ok") or "id" not in started.get("result", {}):
            return started
        identifier = started["result"]["id"]
        deadline = time.monotonic() + duration_ms / 1000 + 5
        try:
            while time.monotonic() < deadline:
                time.sleep(0.2)
                status = one_line_status()
                if not status.get("ok"):
                    return status
                case = status["result"].get("case")
                if not case or case["id"] != identifier:
                    return failure("CASE_CHANGED", "任务已被用户或另一会话接管")
                if case["state"] not in {"running", "accepted", "stopping"}:
                    if case["state"] != "completed" or case["errors"] or not case["sent_frames"]:
                        return {"ok": False, "result": {"case": case, "hardware_result": "not_observed"},
                                "error": {"code": "CASE_NOT_COMPLETED", "message": "测试未完成有效写入，请检查任务状态和错误"}}
                    return {"ok": True, "result": {"case": case, "hardware_result": "not_observed"}}
            return failure("CASE_TIMEOUT", "等待完成超时，请查询在途写入状态")
        finally:
            # 只停止自己创建的任务，不能取消别的连接器刚启动的新任务。
            one_line_stop(identifier)

    return server


def main():
    """只运行STDIO服务，不修改Codex配置，不在启动时读取应用或Git凭据。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--connection-file", type=Path, help="可选：明确指定本机连接发现文件")
    args = parser.parse_args()
    try:
        server = create_server(args.connection_file)
    except ImportError:
        parser.exit(2, "请在独立环境安装requirements-mcp.txt；不要改动现有PyQt5环境。\n")
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
