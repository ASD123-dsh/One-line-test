#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""回环HTTP安全与MCP本机客户端回归；只使用本测试创建的短期监听和合成令牌。"""

from http.client import HTTPConnection
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import uuid

from ai_control.client import LocalClient
from ai_control.connection import ConnectionFile, protect_token, read_descriptor, unprotect_token, validate_endpoint
from ai_control.transport import LocalServer, strict_json


class LocalTransportTests(unittest.TestCase):
    """拒绝浏览器跨域、Host伪造、无认证、重复JSON和无界输入。"""

    def setUp(self):
        """测试分配自己的回环端口，不访问客户串口或其他网络地址。"""
        self.dispatched = []
        self.token = "synthetic-token-for-local-test-only-1234"
        def dispatch(data):
            """只保存合成请求，不调用任何真实业务。"""
            self.dispatched.append(data)
            return 200, {"ok": True, "result": {"operation": data["operation"]}}
        self.server = LocalServer(self.token, dispatch)
        self.server.start()
        self.addCleanup(self.server.close)

    def request(self, raw=None, headers=None, path="/v1/command", method="POST"):
        """保留精确HTTP头，便于验证重复头与错误Host。"""
        body = raw if raw is not None else json.dumps({"id": uuid.uuid4().hex, "operation": "status", "arguments": {}}).encode()
        connection = HTTPConnection("127.0.0.1", self.server.server.server_port, timeout=2)
        try:
            values = {"Content-Type": "application/json", "Authorization": "Bearer " + self.token, **(headers or {})}
            connection.request(method, path, body=body, headers=values)
            response = connection.getresponse()
            return response.status, json.loads(response.read())
        finally:
            connection.close()

    def test_loopback_binding_and_authenticated_request(self):
        """只在127.0.0.1监听，合法请求不返回认证内容。"""
        self.assertEqual(self.server.server.server_address[0], "127.0.0.1")
        status, data = self.request()
        self.assertEqual(status, 200)
        self.assertEqual(len(self.dispatched), 1)
        self.assertNotIn(self.token, json.dumps(data))

    def test_authentication_host_and_origin_are_all_required(self):
        """恶意网页、其他主机名和错误认证均不能进入主线程分发。"""
        for headers, expected in (({"Authorization": "Bearer wrong"}, 401), ({"Authorization": "é"}, 401),
                                  ({"Host": "evil.example"}, 403), ({"Origin": "http://evil.example"}, 403),
                                  ({"Origin": "null"}, 403)):
            self.assertEqual(self.request(headers=headers)[0], expected)
        self.assertEqual(self.dispatched, [])

    def test_path_method_and_body_limits(self):
        """没有调试网页、文件读取或无限输入入口。"""
        self.assertEqual(self.request(path="/../keys")[0], 404)
        self.assertEqual(self.request(method="GET")[0], 405)
        self.assertEqual(self.request(headers={"Content-Type": "text/plain"})[0], 400)
        self.assertEqual(self.request(headers={"Content-Length": "999999999999999999999999999"})[0], 413)
        self.assertEqual(self.request(headers={"Transfer-Encoding": "chunked"})[0], 400)
        self.assertEqual(self.dispatched, [])

    def test_malformed_json_and_unbounded_nesting_are_rejected(self):
        """重复字段、非有限值、未知顶层字段及过深JSON不进入控制器。"""
        for raw in (b'{"id":"x","id":"y"}', b'{"x":NaN}', b'{"x":1e400}',
                    b'[' * 80 + b'0' + b']' * 80, b'[' * 1200 + b']' * 1200,
                    json.dumps({"id": uuid.uuid4().hex, "operation": "status", "arguments": {}, "extra": 1}).encode()):
            self.assertEqual(self.request(raw=raw)[0], 400)
        self.assertEqual(self.dispatched, [])

    def test_strict_json_rejects_repeated_and_non_finite_values(self):
        """客户端和服务器使用同样的严格JSON解释。"""
        for raw in (b'{"x":1,"x":2}', b'{"x":Infinity}', b'{"x":NaN}',
                    b'{"x":1e400}', b'{"x":-1e400}', b'[' * 80 + b'0' + b']' * 80):
            with self.assertRaises(ValueError):
                strict_json(raw)

    def test_client_uses_local_connection_without_proxy_or_token_output(self):
        """连接器只直接连回环地址，不跟随系统代理，也不输出令牌。"""
        with TemporaryDirectory() as directory:
            path = Path(directory) / "connection.json"
            with patch("ai_control.connection.protect_token", return_value="synthetic-protected-data"):
                descriptor = ConnectionFile(path)
                descriptor.publish(self.server.endpoint, self.token, uuid.uuid4().hex)
            self.assertNotIn(self.token, path.read_text(encoding="utf-8"))
            with patch("ai_control.client.unprotect_token", return_value=self.token), patch.dict(os.environ, {"HTTP_PROXY": "http://example.invalid:9", "HTTPS_PROXY": "http://example.invalid:9"}):
                client = LocalClient(path)
                result = client.call("status")
            self.assertTrue(result["ok"])
            self.assertEqual(self.dispatched[0]["client_id"], client.client_id)
            self.assertNotEqual(client.client_id, LocalClient(path).client_id)
            self.assertNotIn(self.token, json.dumps(result))
            descriptor.remove()

    def test_client_keeps_legacy_packet_shape_for_existing_manual_test_exe(self):
        """能力协商保留旧EXE的严格消息格式，不因更新MCP源码破坏旧测试包。"""
        with TemporaryDirectory() as directory, patch("ai_control.connection.protect_token", return_value="test-only"):
            path = Path(directory) / "connection.json"
            descriptor = ConnectionFile(path)
            descriptor.publish(self.server.endpoint, self.token, uuid.uuid4().hex)
            data = json.loads(path.read_text(encoding="utf-8"))
            data.pop("features")
            path.write_text(json.dumps(data), encoding="utf-8")
            with patch("ai_control.client.unprotect_token", return_value=self.token):
                self.assertTrue(LocalClient(path).call("status")["ok"])
            self.assertEqual(set(self.dispatched[-1]), {"id", "operation", "arguments"})

    def test_session_metadata_rejects_malformed_ids_before_dispatch(self):
        """只允许可选的严格随机标识，不放宽旧顶层字段或JSON白名单。"""
        for client_id in (None, True, "", "../connection", "a" * 33, "A" * 32):
            raw = json.dumps({"id": uuid.uuid4().hex, "operation": "request_connection", "arguments": {}, "client_id": client_id}).encode()
            self.assertEqual(self.request(raw=raw)[0], 400)
        self.assertEqual(self.dispatched, [])

    def test_descriptor_is_exclusive_and_unknown_changes_are_preserved(self):
        """其他实例不能覆盖记录，关闭后只清理自己的原始文件。"""
        with TemporaryDirectory() as directory, patch("ai_control.connection.protect_token", return_value="test-only"):
            path = Path(directory) / "connection.json"
            first, other = ConnectionFile(path), ConnectionFile(path)
            first.publish(self.server.endpoint, self.token, uuid.uuid4().hex)
            with self.assertRaises(ValueError):
                other.publish(self.server.endpoint, self.token, uuid.uuid4().hex)
            self.assertEqual(read_descriptor(path)["endpoint"], self.server.endpoint)
            path.write_text("foreign file", encoding="utf-8")
            first.remove()
            self.assertEqual(path.read_text(encoding="utf-8"), "foreign file")

    def test_unsafe_endpoints_are_never_used(self):
        """发现文件也被视为不可信输入，不能把会话令牌转发到其他网站。"""
        for endpoint in ("https://127.0.0.1:1234/v1/command", "http://localhost:1234/v1/command", "http://evil.example:1234/v1/command",
                         "http://u:p@127.0.0.1:1234/v1/command", "http://127.0.0.1:1234/other", "http://127.0.0.1:1234/v1/command?q=x"):
            with self.assertRaises(ValueError):
                validate_endpoint(endpoint)
