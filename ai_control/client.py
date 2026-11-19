#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MCP连接器使用的本机HTTP客户端；仅可申请人工确认，不自行授权或重试发帧。"""

from http.client import HTTPConnection
import json
import uuid

from ai_control.connection import read_descriptor, unprotect_token, validate_endpoint
from ai_control.transport import MAX_BODY_BYTES, MAX_RESPONSE_BYTES, strict_json


class LocalClient:
    """每次读取当前用户的加密会话，关闭或换会话后旧令牌自然失效。"""

    def __init__(self, connection_file=None):
        """每份连接器独立标识会话，不让新连接器继承另一次人工确认。"""
        self.connection_file = connection_file
        self.client_id = uuid.uuid4().hex

    def call(self, operation, arguments=None, request_id=None):
        """单次提交命令，区分受理和完成；网络错误不自动重复实际发送。"""
        descriptor = read_descriptor(self.connection_file)
        address = validate_endpoint(descriptor["endpoint"])
        token = unprotect_token(descriptor["protected_token"])
        identifier = request_id or uuid.uuid4().hex
        data = {"id": identifier, "operation": operation, "arguments": arguments if arguments is not None else {}}
        if "client_sessions" in descriptor.get("features", []):
            # 旧V1.58.9测试包不认识客户端字段；按发现能力协商，不重试任何写操作。
            data["client_id"] = self.client_id
        raw = json.dumps(data, ensure_ascii=False, allow_nan=False).encode("utf-8")
        if len(raw) > MAX_BODY_BYTES:
            raise ValueError("AI请求超过64KiB")
        connection = HTTPConnection("127.0.0.1", address.port, timeout=4.0)
        try:
            # HTTPConnection不读取系统代理，也不跟随重定向，令牌不会发到其他主机。
            connection.request("POST", "/v1/command", body=raw, headers={"Content-Type": "application/json", "Authorization": "Bearer " + token})
            response = connection.getresponse()
            data = response.read(MAX_RESPONSE_BYTES + 1)
            if len(data) > MAX_RESPONSE_BYTES:
                raise ValueError("AI接口响应过大")
            result = strict_json(data)
            if not isinstance(result, dict) or type(result.get("ok")) is not bool:
                raise ValueError("AI接口返回格式无效")
            return result
        except OSError:
            return {"ok": False, "request_id": identifier, "error": {"code": "CONNECTION_LOST",
                    "message": "本机连接中断，操作结果未知；不会自动重复发送，请查询状态或原请求ID结果"}}
        finally:
            connection.close()
