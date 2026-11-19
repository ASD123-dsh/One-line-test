#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""只监听回环地址的有界HTTP传输，不直接访问Qt控件或串口。"""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hmac
import json
import math
import re
import socket
import threading

MAX_BODY_BYTES = 64 * 1024
MAX_RESPONSE_BYTES = 1024 * 1024


def failure(code, message):
    """统一错误格式，不向调用者暴露异常堆栈或本机敏感路径。"""
    return {"ok": False, "error": {"code": code, "message": message}}


def strict_json(raw):
    """拒绝重复字段、NaN和无穷值，避免Python宽松JSON解释产生歧义。"""
    def pairs(items):
        """一个对象内的字段只能出现一次。"""
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("重复JSON字段")
            result[key] = value
        return result

    def invalid_constant(value):
        """非标准JSON数值必须由参数校验明确拒绝。"""
        raise ValueError("JSON不能包含非有限数值")

    def finite_float(value):
        """拒绝1e400这类标准JSON指数溢出，不能让无穷值穿透到Qt请求槽。"""
        number = float(value)
        if not math.isfinite(number):
            raise ValueError("JSON不能包含非有限数值")
        return number

    data = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs,
                      parse_constant=invalid_constant, parse_float=finite_float)
    pending = [(data, 0)]
    while pending:
        item, depth = pending.pop()
        if depth > 64:
            raise ValueError("JSON嵌套过深")
        if isinstance(item, dict):
            pending.extend((value, depth + 1) for value in item.values())
        elif isinstance(item, list):
            pending.extend((value, depth + 1) for value in item)
    return data


class _BoundedServer(ThreadingHTTPServer):
    """最多八个短请求，慢连接不能创建无界线程，也不阻塞界面。"""

    daemon_threads = True
    block_on_close = False
    allow_reuse_address = False

    def __init__(self, token, dispatch):
        """固定绑定IPv4回环和系统分配端口，不接受外部监听配置。"""
        self.token = token
        self.dispatch = dispatch
        self.slots = threading.BoundedSemaphore(8)
        super().__init__(("127.0.0.1", 0), _Handler)

    def get_request(self):
        """所有连接都有有限读写超时，不无限等待未完成请求。"""
        request, address = super().get_request()
        request.settimeout(2.0)
        return request, address

    def process_request(self, request, client_address):
        """并发达到上限时关闭新连接，不累积等待队列。"""
        if not self.slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self.slots.release()
            raise

    def process_request_thread(self, request, client_address):
        """请求结束后释放容量，包含对端中断和参数错误路径。"""
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.slots.release()

    def handle_error(self, request, client_address):
        """不记录HTTP请求或认证头，断开的客户端不污染应用日志。"""


class _Handler(BaseHTTPRequestHandler):
    """单一JSON入口，禁止浏览器跨域调用、Host伪造和HTTP请求转发。"""

    protocol_version = "HTTP/1.0"
    server_version = "AD-OneLine-Control"
    sys_version = ""

    def log_message(self, format, *args):
        """关闭默认访问日志，令牌、参数和客户路径不进入终端。"""

    def _respond(self, status, data):
        """响应大小有界且不缓存；连接中断不会影响主程序。"""
        if not getattr(self, "_body_consumed", False):
            # Windows在未消费请求体时关闭连接可能丢失错误响应；只做一次有界、短超时排空。
            previous_timeout = self.connection.gettimeout()
            try:
                self.connection.settimeout(0.02)
                self.rfile.read1(MAX_BODY_BYTES)
            except OSError:
                pass
            finally:
                self.connection.settimeout(previous_timeout)
        raw = json.dumps(data, ensure_ascii=False, allow_nan=False).encode("utf-8")
        if len(raw) > MAX_RESPONSE_BYTES:
            status, raw = 500, json.dumps(failure("RESPONSE_TOO_LARGE", "结果过大，请减少读取条数")).encode()
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(raw)
        except (OSError, socket.timeout):
            pass

    def do_GET(self):
        """只提供POST接口，不暴露网页或调试目录。"""
        self._respond(405, failure("METHOD_NOT_ALLOWED", "仅支持本机JSON命令"))

    def do_POST(self):
        """传输线程只负责鉴权和消息格式，业务通过受控桥提交到GUI线程。"""
        if self.path != "/v1/command":
            self._respond(404, failure("NOT_FOUND", "接口不存在"))
            return
        if (self.client_address[0] != "127.0.0.1" or self.headers.get_all("Origin")
                or self.headers.get_all("Host") != [f"127.0.0.1:{self.server.server_port}"]):
            self._respond(403, failure("LOCAL_ONLY", "仅允许受信任的本机客户端"))
            return
        authorization = self.headers.get_all("Authorization")
        if (not self.server.token or not authorization or len(authorization) != 1
                or not hmac.compare_digest(authorization[0].encode("utf-8"), ("Bearer " + self.server.token).encode("ascii"))):
            self._respond(401, failure("UNAUTHORIZED", "AI连接认证失败"))
            return
        if self.headers.get_all("Transfer-Encoding") or self.headers.get("Content-Type", "").lower() != "application/json":
            self._respond(400, failure("INVALID_REQUEST", "仅支持有长度的JSON请求"))
            return
        lengths = self.headers.get_all("Content-Length") or []
        if len(lengths) != 1 or len(lengths[0]) > 6 or not lengths[0].isascii() or not lengths[0].isdigit() or not 0 < int(lengths[0]) <= MAX_BODY_BYTES:
            self._respond(413, failure("INVALID_LENGTH", "请求大小必须为1～65536字节"))
            return
        try:
            raw = self.rfile.read(int(lengths[0]))
            self._body_consumed = True
            if len(raw) != int(lengths[0]):
                raise ValueError("请求不完整")
            data = strict_json(raw)
            if (not isinstance(data, dict) or set(data) not in ({"id", "operation", "arguments"}, {"id", "client_id", "operation", "arguments"})
                    or not isinstance(data["id"], str) or re.fullmatch(r"[0-9a-f]{32}", data["id"]) is None
                    or ("client_id" in data and (not isinstance(data["client_id"], str) or re.fullmatch(r"[0-9a-f]{32}", data["client_id"]) is None))
                    or not isinstance(data["operation"], str) or len(data["operation"]) > 40
                    or not isinstance(data["arguments"], dict)):
                raise ValueError("请求结构无效")
        except (ValueError, UnicodeError, RecursionError, OSError):
            self._respond(400, failure("INVALID_REQUEST", "请求格式或JSON参数无效"))
            return
        try:
            status, response = self.server.dispatch(data)
        except Exception:
            status, response = 500, failure("INTERNAL_ERROR", "本机控制请求失败，请查看工具状态")
        self._respond(status, response)


class LocalServer:
    """可显式开启和关闭的传输层，不自动随应用或导入启动。"""

    def __init__(self, token, dispatch):
        """创建回环监听，不暴露公网端口或依赖Web框架。"""
        self.server = _BoundedServer(token, dispatch)
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.1}, daemon=True, name="AD-OneLine-LocalAPI")

    @property
    def endpoint(self):
        """返回唯一允许的本机会话入口。"""
        return f"http://127.0.0.1:{self.server.server_port}/v1/command"

    def start(self):
        """只启动一次后台收包线程，不读取界面。"""
        self.thread.start()

    def close(self):
        """停止接受新连接，不等待仍在主线程等待中的HTTP工作线程。"""
        if self.thread.is_alive():
            self.server.shutdown()
            self.thread.join(timeout=1.0)
        self.server.server_close()
        self.server.token = ""
