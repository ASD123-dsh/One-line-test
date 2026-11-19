#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GUI线程内的受控AI命令协调器，共用现有协议、串口、定时器和状态界面。"""

from collections import OrderedDict, deque
from dataclasses import asdict, fields, replace
from datetime import datetime
import json
import math
import re
import secrets
import threading
import time
import uuid

from PyQt5.QtCore import QObject, QSignalBlocker, Qt, QTimer, pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import QAbstractButton, QAbstractSpinBox, QButtonGroup, QComboBox

from ai_control.catalog import CONNECTION_OPERATIONS, OPERATIONS, WRITE_OPERATIONS, READ_ONLY_FIELDS, parameter_schema, protocol_catalog
from ai_control.connection import ConnectionFile
from ai_control.transport import LocalServer, failure
from app_info import APP_VERSION
from app_settings import BAUD_RATES, MAX_PACKET_FRAMES
from gui.protocol_ui_registry import get_protocol_ui_spec
from gui.soft_theme import set_badge_tone
from protocol.definitions import PROTOCOL_DEFINITIONS, PROTOCOL_XINGHENG_BMS
from protocol.frame_utils import normalize_frame
from protocol.models import StatusBits

MAX_CASE_MS = 60000
CONTACT_TIMEOUT_SECONDS = 10.0
REQUEST_TIMEOUT_SECONDS = 60.0
REQUEST_COOLDOWN_SECONDS = 15.0


class ControlError(ValueError):
    """可向AI返回的业务拒绝，不弹出阻塞自动化请求的消息窗口。"""

    def __init__(self, code, message):
        """保存稳定错误码，不包含令牌、授权记录或堆栈。"""
        super().__init__(message)
        self.code = code


class _Invocation:
    """网络线程与GUI线程之间的一份有界请求，超时未开始时可安全取消。"""

    def __init__(self, data, session, permission_epoch=None):
        """独立持有请求及等待事件，不共享界面对象。"""
        self.data = data
        self.session = session
        self.permission_epoch = permission_epoch
        self.done = threading.Event()
        self.lock = threading.Lock()
        self.state = "queued"
        self.response = None


class AiController(QObject):
    """监听申请不等于允许读取或操作；所有授权只能由本机用户确认。"""

    requested = pyqtSignal(object)
    connection_requested = pyqtSignal(str)
    state_changed = pyqtSignal()

    def __init__(self, window, connection_file=None, clock=None):
        """挂接只读完成信号，不启动HTTP服务、不改串口或授权状态。"""
        super().__init__(window)
        self.window = window
        self.manager = window.serial_manager
        self.connection_file = ConnectionFile(connection_file)
        self.clock = clock or time.monotonic
        self.server = None
        self._session = None
        self._permission_epoch = uuid.uuid4().hex
        self.executing = False
        self._write_allowed = False
        self._approved = False
        self._owner_client = None
        self._last_owner_client = None
        self._connection_request = None
        self._last_decision = None
        self._next_request_at = 0.0
        self._client_seen = False
        self._state_stamp = None
        self._last_contact = 0.0
        self._next_license_check = 0.0
        self._case = None
        self._events = deque(maxlen=2048)
        self._event_id = 0
        self._cache = OrderedDict()
        self._invocation_slots = threading.BoundedSemaphore(8)
        self.requested.connect(self._execute, Qt.QueuedConnection)
        self.manager.write_completed.connect(self._on_write_completed)
        self.timer = QTimer(self)
        self.timer.setInterval(100)
        self.timer.timeout.connect(self._tick)

    def _activated(self):
        """沿用原激活服务，只检查有效性；不创建替代许可证或暴露授权数据。"""
        service = self.window.activation_service
        try:
            return service is not None and service.is_activated() is True
        except Exception:
            return False

    def listen_for_requests(self):
        """启动时仅接收授权申请，不开放测试数据、串口或发送控制。"""
        if self.server is not None:
            return
        if not self._activated():
            raise ValueError("请先通过原软件激活验证，再开启AI本机接口")
        token, session = secrets.token_urlsafe(32), uuid.uuid4().hex
        server = LocalServer(token, lambda data: self.invoke(data, session))
        try:
            self.connection_file.publish(server.endpoint, token, session)
            server.start()
        except Exception:
            server.close()
            self.connection_file.remove()
            raise
        self.server = server
        self._session = session
        self._cache.clear()
        self._approved = False
        self._write_allowed = False
        self._owner_client = None
        self._last_owner_client = None
        self._connection_request = None
        self._last_decision = None
        self._next_request_at = 0.0
        self._client_seen = False
        self._last_contact = self.clock()
        self._next_license_check = self.clock() + 1.0
        self.timer.start()
        self._event("request_listener_enabled")
        self._publish_state()

    def enable(self):
        """保留手动开启只读接口的入口；用户开启前仍只有申请权限。"""
        self.listen_for_requests()
        if not self._activated():
            raise ValueError("请先通过原软件激活验证，再开启AI本机接口")
        self._approved = True
        self._permission_epoch = uuid.uuid4().hex
        self._event("read_permission_granted")
        self._publish_state()

    def _check_grant(self):
        """授权前复核激活和手动任务，不能通过同意弹窗抢占手动循环。"""
        if self.server is None or not self._activated():
            raise ValueError("请先开启已激活工具的本机接口")
        if self.manager.is_cyclic_sending() and not self._owns_running():
            raise ValueError("请先停止手动循环，再授权AI控制")

    def grant_writes(self):
        """本次连接授权不设分钟数；关闭、撤销或人工接管后不自动恢复。"""
        self._check_grant()
        if self._connection_request is not None:
            self.resolve_connection(self._connection_request["id"], "control")
            return
        self._approved = True
        self._write_allowed = True
        self._permission_epoch = uuid.uuid4().hex
        self._last_contact = self.clock()
        self._event("write_permission_granted")
        self._publish_state()

    def revoke_writes(self):
        """撤销后停止本次AI任务，不停止用户自行启动的循环。"""
        self._write_allowed = False
        self._permission_epoch = uuid.uuid4().hex
        self._stop_owned("permission_revoked", "cancelled")
        self._publish_state()

    def close_connection(self):
        """用户主动断开本次AI会话；保留申请入口和手动串口，不清理其他数据。"""
        self._end_connection("connection_closed")

    def _end_connection(self, reason):
        """会话结束同时停本次任务，新的连接器必须重新申请并确认。"""
        self._write_allowed = False
        self._permission_epoch = uuid.uuid4().hex
        self._stop_owned(reason, "cancelled")
        if self._owner_client is not None:
            self._last_owner_client = self._owner_client
        self._owner_client = None
        self._approved = False
        self._client_seen = False
        if self._connection_request is not None:
            self._settle_request("rejected")
        elif self._last_decision is not None:
            self._last_decision["state"] = "closed"
        self._cache.clear()
        self._event(reason)
        self._publish_state()

    def shutdown(self):
        """关闭或升级时停止AI任务并清理本次连接记录，保留原程序的关闭流程。"""
        self._end_connection("service_closed")
        self.timer.stop()
        server, self.server = self.server, None
        self._session = None
        if server is not None:
            server.close()
        try:
            self.connection_file.remove()
        except (OSError, ValueError):
            # 记录只读或被替换时保留现场，不能让连接记录清理失败阻断原关闭/升级流程。
            self._event("connection_cleanup_warning", message="AI连接记录未清理，请按接入文档检查")
            self.window.status_bar.showMessage("AI连接记录未清理；接口已关闭，请按接入文档检查", 5000)
        self._publish_state()

    def manual_takeover(self, stop=True):
        """用户操作优先；切换按钮保留原循环状态，避免“停止”被误判成重新开始。"""
        if self.executing:
            return
        self._write_allowed = False
        self._permission_epoch = uuid.uuid4().hex
        if stop:
            self._stop_owned("manual_takeover", "cancelled")
        elif self._owns_running():
            self._case["stop_reason"] = "manual_takeover"
            self._case["final_state"] = "cancelled"
            self._case["state"] = "stopping" if self.manager.is_write_pending() else "cancelled"
        self._publish_state()

    def connection_state(self):
        """供本机界面显示逻辑会话；监听中或只有历史授权不冒充正在连接。"""
        pending = self._connection_request is not None
        recent = self._approved and self._client_seen and self.clock() - self._last_contact < CONTACT_TIMEOUT_SECONDS
        working = recent and bool(self._case and self._case["state"] in {"running", "accepted", "stopping"})
        state = ("pending" if pending else "working" if working else "connected" if recent
                 else "idle" if self._approved else "waiting" if self.server is not None else "disabled")
        return {"state": state, "write_authorized": self._write_allowed,
                "request_id": self._connection_request["id"] if pending else None}

    def _publish_state(self):
        """仅在显示状态变化时通知界面，避免每帧更新小图标或主界面布局。"""
        state = self.connection_state()
        stamp = tuple(state.items())
        if stamp != self._state_stamp:
            self._state_stamp = stamp
            self.state_changed.emit()

    def _settle_request(self, state):
        """完成一份申请并保留有限反馈，拒绝后冷却以免连续弹窗骚扰。"""
        request = self._connection_request
        if request is None:
            return
        self._last_decision = {**request, "state": state}
        self._connection_request = None
        self._next_request_at = self.clock() + (0 if state == "approved" else REQUEST_COOLDOWN_SECONDS)

    def _expire_request(self):
        """未操作的申请自动失效，过期弹窗不能在稍后意外赋予权限。"""
        if self._connection_request and self.clock() - self._connection_request["created"] >= REQUEST_TIMEOUT_SECONDS:
            self._settle_request("expired")
            self._publish_state()

    def resolve_connection(self, request_id, access):
        """仅由人工弹窗回调批准本次请求；网络命令没有批准或续权入口。"""
        self._expire_request()
        request = self._connection_request
        if request is None or request["id"] != request_id:
            return False
        if access not in {"control", "read_only", "reject"}:
            raise ValueError("连接授权选项无效")
        if access == "reject":
            self._settle_request("rejected")
        else:
            if not self._activated() or self.server is None:
                raise ValueError("请先通过原软件激活验证")
            if access == "control":
                self._check_grant()
            self._owner_client = request["client_id"]
            self._approved = True
            self._write_allowed = access == "control"
            self._permission_epoch = uuid.uuid4().hex
            self._client_seen = False
            self._cache.clear()
            self._settle_request("approved")
            self._last_decision["access"] = access
            self._event("connection_approved", access=access)
        self._publish_state()
        return True

    def _connection_identity(self, client_id):
        """申请使用独立随机标识；同用户令牌不等于另一个客户端已获用户同意。"""
        if not isinstance(client_id, str) or re.fullmatch(r"[0-9a-f]{32}", client_id) is None:
            raise ValueError("连接申请需要有效的本机客户端标识，请重新加载MCP连接器")

    def _connection_result(self, client_id):
        """未批准时只反馈申请进度，不泄露协议、串口、参数或测试结果。"""
        if self._approved and self._owner_client in (None, client_id):
            self._owner_client = client_id
            self._client_seen = True
            self._last_contact = self.clock()
            return {"state": "approved", "access": "control" if self._write_allowed else "read_only",
                    "authorization_scope": "current_connection", "write_authorized": self._write_allowed}
        if self._approved:
            return {"state": "busy", "message": "另一个本机AI会话已获允许，请在工具中先断开该连接"}
        for request in (self._connection_request, self._last_decision):
            if request is not None and request["client_id"] == client_id:
                return {"state": request["state"], "request_id": request["id"],
                        "retry_after_seconds": max(0, math.ceil(self._next_request_at - self.clock()))}
        return {"state": "not_requested"}

    def _op_request_connection(self, arguments, client_id):
        """AI只能提出申请；重复申请复用同一弹窗，绝不能自授读写权限。"""
        self._keys(arguments, ())
        self._connection_identity(client_id)
        if not self._activated():
            raise ControlError("NOT_ACTIVATED", "请先通过工具原有激活验证")
        self._expire_request()
        if self._approved or (self._connection_request and self._connection_request["client_id"] == client_id):
            return self._connection_result(client_id)
        if self._connection_request is not None:
            return {"state": "busy", "message": "工具正在等待另一份连接申请的人工确认"}
        if self.clock() < self._next_request_at:
            return {"state": "cooldown", "retry_after_seconds": math.ceil(self._next_request_at - self.clock())}
        request = {"id": uuid.uuid4().hex, "client_id": client_id, "state": "pending", "created": self.clock()}
        self._connection_request = request
        self._publish_state()
        # 弹窗在主线程异步展示，不让HTTP线程长时间等待人工操作。
        self.connection_requested.emit(request["id"])
        return {"state": "pending", "request_id": request["id"], "message": "请在一线通工具内确认本次连接申请"}

    def _op_connection_status(self, arguments, client_id):
        """只查询本连接器的申请状态；不是读取测试数据或延长控制授权。"""
        self._keys(arguments, ())
        self._connection_identity(client_id)
        self._expire_request()
        return self._connection_result(client_id)

    def _op_close_connection(self, arguments, client_id):
        """连接器可结束自己的AI会话，不断开用户串口或停止手动循环。"""
        self._keys(arguments, ())
        self._connection_identity(client_id)
        if self._approved and self._owner_client == client_id:
            self._end_connection("client_disconnected")
        elif self._connection_request is not None and self._connection_request["client_id"] == client_id:
            self._settle_request("cancelled")
        elif self._approved:
            raise ControlError("CONNECTION_IN_USE", "不能断开另一份本机AI会话")
        self._publish_state()
        return {"state": "closed"}

    def _check_connection(self, client_id, operation):
        """业务命令必须属于已批准会话，保留旧手动开启客户端的只读兼容。"""
        if operation != "stop" and not self._activated():
            self._end_connection("activation_invalid")
            raise ControlError("NOT_ACTIVATED", "软件激活已失效，AI连接已断开")
        if not self._approved:
            if operation == "stop" and client_id is not None and client_id == self._last_owner_client:
                return
            raise ControlError("CONNECTION_REQUIRED", "请先申请连接并在一线通工具内确认")
        if self._owner_client is not None and self._owner_client != client_id:
            raise ControlError("CONNECTION_IN_USE", "当前权限仅属于已确认的本机AI会话")
        if self._owner_client is None:
            self._owner_client = client_id
        self._client_seen = True
        self._last_contact = self.clock()

    def invoke(self, data, session=None):
        """HTTP线程通过排队信号调用主线程，超时未执行的命令不会稍后突然发帧。"""
        if not self._invocation_slots.acquire(blocking=False):
            return 503, failure("QUEUE_FULL", "已有八个请求等待界面处理，请稍后查询状态")
        invocation = _Invocation(data, self._session if session is None else session, self._permission_epoch)
        try:
            self.requested.emit(invocation)
        except RuntimeError:
            self._invocation_slots.release()
            return 503, failure("DISABLED", "界面已关闭，请重新打开工具")
        if invocation.done.wait(2.0):
            return invocation.response
        with invocation.lock:
            if invocation.state == "queued":
                invocation.state = "cancelled"
                return 503, failure("GUI_TIMEOUT", "界面正忙，未执行请求；请稍后查询状态")
            if invocation.response is not None:
                return invocation.response
        return 202, {"ok": True, "request_id": data["id"], "result": {"state": "processing", "note": "操作已开始；不要重复发送，请使用原请求ID查询结果"}}

    @pyqtSlot(object)
    def _execute(self, invocation):
        """仅此槽进入业务层，排队命令取消后不读取参数或操作串口。"""
        try:
            with invocation.lock:
                if invocation.state != "queued":
                    return
                invocation.state = "running"
            # 开关服务会更换会话；旧连接排队的请求不能借用新会话刚授予的操作权限。
            if invocation.session != self._session or self.server is None:
                response = (503, failure("SESSION_EXPIRED", "AI会话已关闭或更换，旧请求未执行"))
            elif (invocation.data.get("operation") in WRITE_OPERATIONS | {"stop", "close_connection"}
                  and invocation.permission_epoch != self._permission_epoch):
                # 修复撤权后重新同意时，旧Qt排队写命令可能借新授权执行的问题。
                response = (403, failure("SESSION_EXPIRED", "本次授权已撤销或更换，旧请求未执行"))
            else:
                try:
                    response = self.execute(invocation.data)
                except Exception:
                    # Qt槽的最终异常边界，避免畸形输入或未预期业务异常终止整个桌面进程。
                    response = (500, failure("INTERNAL_ERROR", "操作未正常完成，请在工具中检查状态"))
            with invocation.lock:
                invocation.response = response
                invocation.state = "done"
                invocation.done.set()
        finally:
            # 容量直到Qt取走排队事件才释放，不能在HTTP超时后继续堆积已取消事件。
            self._invocation_slots.release()

    def execute(self, data):
        """在GUI线程校验白名单和临时权限；近期相同写请求ID不会重复发帧。"""
        request_id, operation, arguments = data["id"], data["operation"], data["arguments"]
        client_id = data.get("client_id")
        try:
            fingerprint = json.dumps([client_id, operation, arguments], ensure_ascii=False, sort_keys=True, allow_nan=False)
        except (ValueError, TypeError, RecursionError, OverflowError):
            return 400, failure("INVALID_ARGUMENT", "参数不能包含非有限数值或过深嵌套")
        if self.executing:
            return 409, failure("BUSY", "另一个界面操作尚未完成")
        self.executing = True
        try:
            if self.server is None:
                raise ControlError("DISABLED", "AI接口未开启")
            if operation not in OPERATIONS:
                raise ControlError("UNKNOWN_OPERATION", "不支持此操作；激活、更新、文件或代码执行不在接口范围内")
            if client_id is not None:
                self._connection_identity(client_id)
            if operation in CONNECTION_OPERATIONS:
                result = getattr(self, "_op_" + operation)(arguments, client_id)
            else:
                if operation in WRITE_OPERATIONS and not self._activated():
                    self._end_connection("activation_invalid")
                    raise ControlError("NOT_ACTIVATED", "软件激活已失效，AI操作被拒绝")
                self._check_connection(client_id, operation)
                if request_id in self._cache:
                    old_fingerprint, response = self._cache[request_id]
                    return response if old_fingerprint == fingerprint else (409, failure("REQUEST_ID_REUSED", "请求ID已用于其他操作"))
                if operation in WRITE_OPERATIONS and not self._write_allowed:
                    raise ControlError("READ_ONLY", "请在工具中允许本次连接进行控制操作")
                result = getattr(self, "_op_" + operation)(arguments)
            response = (200, {"ok": True, "request_id": request_id, "result": result})
        except ControlError as exc:
            response = (403 if exc.code in {"READ_ONLY", "NOT_ACTIVATED", "CONNECTION_REQUIRED", "CONNECTION_IN_USE"} else 409, failure(exc.code, str(exc)))
        except (ValueError, TypeError, KeyError, OverflowError) as exc:
            response = (400, failure("INVALID_ARGUMENT", str(exc)))
        except Exception:
            response = (500, failure("INTERNAL_ERROR", "操作未正常完成，请在工具中检查状态"))
        finally:
            self.executing = False
            self._publish_state()
        if operation in WRITE_OPERATIONS or operation == "stop":
            self._cache[request_id] = (fingerprint, response)
            while len(self._cache) > 256:
                self._cache.popitem(last=False)
        return response

    def _keys(self, arguments, allowed, required=()):
        """禁止未知参数、路径注入和缺少必填项的请求进入业务层。"""
        if set(arguments) - set(allowed) or set(required) - set(arguments):
            raise ValueError("参数包含未知字段或缺少必填项")

    def _state(self):
        """读取与手动循环完全相同的当前帧状态。"""
        return self.window.get_current_status_from_ui() if self.window.custom_radio.isChecked() else self.window.current_status

    def _idle(self, allow_own_cycle=False):
        """不能抢占手动循环或在途单帧，也不向现有工作线程再堆叠任务。"""
        if self.manager.is_cyclic_sending():
            if not (allow_own_cycle and self._owns_running()):
                raise ControlError("BUSY", "已有循环正在发送，请先停止")
        elif self.manager.is_write_pending():
            raise ControlError("BUSY", "上一帧仍在写入，请先查询完成结果")

    def _owns_running(self):
        """以原发送代次识别本次AI任务，绝不停止后来启动的手动循环。"""
        return bool(self._case and self._case["state"] in {"running", "accepted"}
                    and self._case["generation"] == self.manager.get_send_generation())

    def _event(self, kind, **values):
        """结构化历史有固定容量，不包含认证头、授权文件或用户目录。"""
        self._event_id += 1
        self._events.append({"event_id": self._event_id, "type": kind,
                             "time": datetime.now().isoformat(timespec="milliseconds"), **values})

    def _op_status(self, arguments):
        """只读查询也用于存活检查；本次授权无固定倒计时且不会跨重启保存。"""
        self._keys(arguments, ())
        return {"version": APP_VERSION, "enabled": self.server is not None,
                "write_seconds_remaining": None if self._write_allowed else 0,
                "write_authorized": self._write_allowed, "authorization_scope": "current_connection",
                "protocol": self.window.current_protocol, "scenario_id": self.window.scenario_group.checkedId(),
                "serial": self.manager.get_port_status(), "case": self._public_case(),
                "hardware_result": "not_observed", "note": "写入完成不等于仪表接收、显示或单线物理时序通过"}

    def _op_protocols(self, arguments):
        """列出原注册表的全部协议及间隔边界。"""
        self._keys(arguments, ())
        return {"protocols": protocol_catalog()}

    def _op_ports(self, arguments):
        """只列出串口名称和描述，不返回硬件序列号或hwid。"""
        self._keys(arguments, ())
        return {"ports": [{"port": item.port, "description": item.description} for item in self.manager.scan_ports()]}

    def _op_parameters(self, arguments):
        """返回当前协议的模型字段，真实写入须通过校验及UI回读。"""
        self._keys(arguments, ())
        return parameter_schema(self.window.current_protocol, self._state())

    def _candidate(self, parameters):
        """先验证类型、有限值与既有协议规则，不静默截断输入或改变协议选择字段。"""
        if not isinstance(parameters, dict) or len(parameters) > 160:
            raise ValueError("parameters必须为有界字段对象")
        specs = {item.name: item.type for item in fields(StatusBits)}
        for name, value in parameters.items():
            if name not in specs or name in READ_ONLY_FIELDS:
                raise ValueError("参数字段不支持修改：" + name)
            expected = specs[name]
            valid = type(value) is bool if expected is bool else type(value) is int if expected is int else type(value) in (int, float)
            if not valid or (type(value) in (int, float) and (not -1e12 <= value <= 1e12 or not math.isfinite(value))):
                raise ValueError("参数类型或数值无效：" + name)
        state = replace(self._state(), **parameters)
        success, frame, error = self.window.generate_protocol_frame_for_preview(state)
        if not success:
            raise ValueError(error)
        return state, frame

    def _op_preview(self, arguments):
        """纯预览不消耗流水号，不改变UI参数，不接触串口。"""
        self._keys(arguments, ("parameters",))
        state, frame = self._candidate(arguments.get("parameters", {}))
        if self.window.frame_custom_radio.isChecked() and not arguments.get("parameters"):
            frame = list(self.window.custom_frame_data or [])
        return {"protocol": self.window.current_protocol, "bytes": frame,
                "hex": " ".join(f"{value:02X}" for value in frame),
                "descriptions": self.window.protocol_handler.get_byte_descriptions(self.window.current_protocol, state)}

    def _op_select_protocol(self, arguments):
        """复用原选择和预设入口，不自动连接或发送。"""
        self._keys(arguments, ("protocol", "scenario_id"), ("protocol",))
        protocol, scenario = arguments["protocol"], arguments.get("scenario_id", 0)
        if not isinstance(protocol, str) or protocol not in PROTOCOL_DEFINITIONS or type(scenario) is not int or not 0 <= scenario <= 3:
            raise ValueError("协议或场景无效；原始帧请用set_raw_frame")
        self._idle()
        self.window.protocol_combo.setCurrentText(protocol)
        self.window.scenario_group.button(scenario).setChecked(True)
        self.window.on_scenario_changed()
        return self._op_status({})

    def _op_configure(self, arguments):
        """动态参数沿用当前循环取帧路径，先完整校验，再原子更新UI。"""
        self._keys(arguments, ("parameters", "interval_ms", "tosc_us"))
        self._idle(allow_own_cycle=True)
        if self._owns_running() and self._case["kind"] == "sequence":
            raise ControlError("BUSY", "包组使用固定帧，请先停止包组再修改参数")
        state, _ = self._candidate(arguments.get("parameters", {}))
        definition = PROTOCOL_DEFINITIONS[self.window.current_protocol]
        interval = arguments.get("interval_ms", self.window.interval_spin.value())
        tosc = arguments.get("tosc_us", self.window.tosc_spin.value())
        if type(interval) is not int or not definition.min_send_interval_ms <= interval <= definition.max_send_interval_ms:
            raise ValueError("发送间隔不在当前协议允许范围内")
        if type(tosc) is not int or not 32 <= tosc <= 320:
            raise ValueError("Tosc必须在32～320微秒")
        old_state, old_scenario = self._state(), self.window.scenario_group.checkedId()
        old_ui = self.window.get_current_status_from_ui()
        old_model = self.window.current_status
        old_previous = self.window._previous_scenario_id
        old_tab = self.window.status_tabs.currentIndex()
        old_custom = self.window.custom_frame_data
        changed_format = state.xingheng_message_id != old_state.xingheng_message_id and self.window.current_protocol == PROTOCOL_XINGHENG_BMS
        if changed_format:
            self._stop_owned("format_changed", "cancelled")
        spec = get_protocol_ui_spec(self.window.current_protocol)
        try:
            self._apply_state(state, spec)
            actual = self.window.get_current_status_from_ui()
            for name, value in arguments.get("parameters", {}).items():
                if getattr(actual, name) != value:
                    raise ValueError("当前协议UI不能精确表示该参数，未应用：" + name)
        except Exception:
            # 失败时分别恢复实际控件与原预设模型；不能重载预设后悄悄改掉旧控件值。
            self._write_ui_state(old_ui, spec)
            self.window.current_status = old_model
            self.window.scenario_group.button(old_scenario).setChecked(True)
            self.window._previous_scenario_id = old_previous
            self.window.custom_frame_data = old_custom
            self.window.status_tabs.set_editable(old_scenario == 3)
            self.window.frame_config_btn.setEnabled(old_scenario == 4 and old_custom is not None)
            self.window.status_tabs.setCurrentIndex(old_tab)
            self.window._refresh_parameter_mode()
            self.window.update_current_frame_display()
            raise
        self.window.interval_spin.setValue(interval)
        self.window.tosc_spin.setValue(tosc)
        return {"parameters": asdict(self._state()), "preview": self._op_preview({}), "case": self._public_case()}

    def _apply_state(self, state, spec):
        """临时屏蔽旧参数控件的中间信号，避免半更新帧被预览或提交。"""
        self._write_ui_state(state, spec)
        self.window.custom_radio.setChecked(True)
        self.window.on_scenario_changed()

    def _write_ui_state(self, state, spec):
        """仅同步参数值，不重载预设、不改变模式，供正常应用和精确回退共同使用。"""
        # 只屏蔽输入信号；屏蔽QTabBar/QStackedWidget会让removeTab无法更新数量而卡住格式切换。
        inputs = (QAbstractButton, QAbstractSpinBox, QButtonGroup, QComboBox)
        blockers = [QSignalBlocker(item) for item in self.window.status_tabs.findChildren(QObject) if isinstance(item, inputs)]
        try:
            self.window.current_status = state
            getattr(self.window, spec.status_writer)()
        finally:
            blockers.clear()

    def _op_set_raw_frame(self, arguments):
        """仅校验既有帧长和字节范围；保留故意错误的帧头和校验，便于原始测试。"""
        self._keys(arguments, ("frame",), ("frame",))
        self._idle(allow_own_cycle=True)
        if self._owns_running() and self._case["kind"] == "sequence":
            raise ControlError("BUSY", "请先停止固定包组")
        length = self.window.protocol_handler.get_protocol_frame_length(self.window.current_protocol, self._state())
        frame = normalize_frame(arguments["frame"], expected_length=length)
        self.window.frame_custom_radio.setChecked(True)
        self.window.on_scenario_changed()
        self.window.on_custom_frame_changed(frame)
        return self._op_preview({})

    def _op_connect(self, arguments):
        """只连接明确选择的本机COM口，错误通过结构化结果返回，不阻塞弹窗。"""
        self._keys(arguments, ("port", "baud_rate"), ("port",))
        self._idle()
        port, baud = arguments["port"], arguments.get("baud_rate", int(self.window.baud_combo.currentText()))
        if not isinstance(port, str) or re.fullmatch(r"COM[1-9][0-9]{0,3}", port, re.IGNORECASE) is None:
            raise ValueError("请选择明确的Windows COM串口")
        if type(baud) is not int or baud not in BAUD_RATES:
            raise ValueError("波特率不受支持")
        if self.manager.is_connected:
            status = self.manager.get_port_status()
            if str(status["port_name"]).upper() == port.upper() and status["baud_rate"] == baud:
                return status
            raise ControlError("BUSY", "已有串口连接，请先明确断开")
        success, error = self.manager.connect_port(port, baud)
        if not success:
            raise ControlError("CONNECT_FAILED", error)
        self.window.baud_combo.setCurrentText(str(baud))
        index = self.window.port_combo.findData(port)
        if index < 0:
            self.window.port_combo.addItem(port, port)
            index = self.window.port_combo.findData(port)
        if index >= 0:
            self.window.port_combo.setCurrentIndex(index)
        return self.manager.get_port_status()

    def _op_disconnect(self, arguments):
        """空闲后才断开，不取消用户手动任务或释放仍在使用的串口。"""
        self._keys(arguments, ())
        self._idle()
        if not self.manager.disconnect_port():
            raise ControlError("BUSY", "串口仍在使用，请先停止并等待完成")
        return self.manager.get_port_status()

    def _begin_case(self, kind):
        """一份后台任务对应一个可查询编号，接收请求不直接标为写入成功。"""
        self._case = {"id": uuid.uuid4().hex, "kind": kind, "state": "accepted", "sent_frames": 0,
                      "errors": 0, "generation": self.manager.get_send_generation(), "stop_reason": "", "deadline": 0.0}
        return self._case

    def _public_case(self):
        """不暴露内部代次或用户数据，只返回有限的任务状态。"""
        return {key: value for key, value in self._case.items() if key not in {"generation", "deadline", "final_state"}} if self._case else None

    def _op_send_once(self, arguments):
        """校验连接和积压后再消耗原流水号，真实完成由后台结果信号确认。"""
        self._keys(arguments, ())
        self._idle()
        if not self.manager.is_connected:
            raise ControlError("NOT_CONNECTED", "串口未连接")
        frame = self.window._get_current_cyclic_frame()
        case = self._begin_case("single")
        success, error = self.manager.send_single_frame(frame, send_mode=self.window.protocol_handler.get_protocol_send_mode(self.window.current_protocol))
        if not success:
            case.update(state="failed", error=error)
            raise ControlError("SEND_REJECTED", error)
        return self._public_case()

    def _op_start_cycle(self, arguments):
        """有界循环沿用原frame_provider，每周期从当前界面读取最新配置。"""
        self._keys(arguments, ("duration_ms",), ("duration_ms",))
        return self._start_cycle(arguments["duration_ms"])

    def _op_start_sequence(self, arguments):
        """固定包组逐帧发送，不把动态参数悄悄写入已配置帧。"""
        self._keys(arguments, ("duration_ms", "frames"), ("duration_ms", "frames"))
        frames = arguments["frames"]
        if not isinstance(frames, list) or not 1 <= len(frames) <= MAX_PACKET_FRAMES:
            raise ValueError("包组必须为1～256帧")
        length = self.window.protocol_handler.get_protocol_frame_length(self.window.current_protocol, self._state())
        frames = [normalize_frame(frame, expected_length=length) for frame in frames]
        return self._start_cycle(arguments["duration_ms"], frames)

    def _start_cycle(self, duration, frames=None):
        """发送总时长、用户授权和连接存活均有限，AI断连不会留下无限循环。"""
        self._idle()
        interval = self.window.interval_spin.value()
        if type(duration) is not int or not interval <= duration <= MAX_CASE_MS:
            raise ValueError("测试时长必须不少于发送间隔且不超过60000毫秒")
        if not self.manager.is_connected:
            raise ControlError("NOT_CONNECTED", "串口未连接")
        definition = PROTOCOL_DEFINITIONS[self.window.current_protocol]
        options = {"send_mode": definition.send_mode, "min_interval_ms": definition.min_send_interval_ms, "max_interval_ms": definition.max_send_interval_ms}
        if frames is None:
            success, error = self.manager.start_cyclic_send(self._op_preview({})["bytes"], interval, frame_provider=self.window._get_current_cyclic_frame, **options)
        else:
            success, error = self.manager.start_cyclic_send_sequence(frames, interval, **options)
        if not success:
            raise ControlError("SEND_REJECTED", error)
        case = self._begin_case("sequence" if frames is not None else "cycle")
        case.update(state="running", deadline=self.clock() + duration / 1000.0)
        if frames is not None:
            if self.window.current_protocol == PROTOCOL_XINGHENG_BMS:
                self.window.store_xingheng_packet_frames(frames)
            else:
                self.window.packet_sequence_frames[self.window.current_protocol] = [frame.copy() for frame in frames]
        self.window.active_send_mode = "sequence" if frames is not None else "single"
        self.window.cyclic_send_btn.setText("循环发送" if frames is not None else "停止发送")
        self.window.packet_sequence_send_btn.setText("停止包组" if frames is not None else "包组循环")
        self.window.send_status.setText("AI 包组发送中" if frames is not None else "AI 循环发送中")
        set_badge_tone(self.window.send_status, "running")
        return self._public_case()

    def _op_stop(self, arguments):
        """只停止本次AI拥有的任务，撤销权限后仍可执行安全停止。"""
        self._keys(arguments, ("case_id",))
        if "case_id" in arguments and (not self._case or arguments["case_id"] != self._case["id"]):
            raise ControlError("CASE_CHANGED", "当前任务已变化，不停止另一个测试任务")
        self._stop_owned("requested", "cancelled")
        return {"case": self._public_case(), "write_pending": self.manager.is_write_pending()}

    def _stop_owned(self, reason, final_state):
        """停止后续提交，已经进入驱动的帧只能等待完成，不能承诺撤回。"""
        if not self._owns_running():
            return
        self._case.update(stop_reason=reason, final_state=final_state)
        self.manager.stop_cyclic_send()
        self.window._reset_send_action_buttons()
        self.window.send_status.setText("就绪")
        set_badge_tone(self.window.send_status, "muted")
        self._case["state"] = "stopping" if self.manager.is_write_pending() else final_state
        self._event("case_stopped", case_id=self._case["id"], reason=reason, state=self._case["state"])

    @pyqtSlot(dict)
    def _on_write_completed(self, result):
        """记录真实写入，包括停发时已在途的最后一帧，不将接受请求当作成功。"""
        case = self._case
        if not case or case["state"] not in {"accepted", "running", "stopping"} or result["generation"] != case["generation"]:
            return
        if result["success"]:
            case["sent_frames"] += 1
            self._event("written", case_id=case["id"], frame=list(result["frame"]), timestamp=result["timestamp"])
        elif not result["throttled"] and not result["cancelled"]:
            case["errors"] += 1
            self._event("write_failed", case_id=case["id"], message=result["error"])
        if case["state"] == "stopping":
            case["state"] = case.get("final_state", "cancelled")
        elif case["kind"] == "single":
            case["state"] = "completed" if result["success"] else "cancelled" if result["cancelled"] else "failed"
            if result["throttled"]:
                case["error"] = "串口缓冲积压，本次单帧未写入；不会自动重试"
        elif not result["success"] and not result["throttled"]:
            case["state"] = "failed"

    def _op_results(self, arguments):
        """按游标读取有界历史；丢弃旧记录时明确报告截断而不是返回虚假的完整记录。"""
        self._keys(arguments, ("after_id", "limit", "request_id"))
        if "request_id" in arguments:
            identifier = arguments["request_id"]
            if not isinstance(identifier, str) or identifier not in self._cache:
                raise ValueError("请求尚未完成或已超出最近256条写请求查询窗口")
            return {"response": self._cache[identifier][1][1]}
        after, limit = arguments.get("after_id", 0), arguments.get("limit", 100)
        if type(after) is not int or after < 0 or type(limit) is not int or not 1 <= limit <= 256:
            raise ValueError("历史游标无效或limit不在1～256")
        events = [dict(item) for item in self._events if item["event_id"] > after][:limit]
        return {"events": events, "next_id": events[-1]["event_id"] if events else after,
                "truncated": bool(self._events and after < self._events[0]["event_id"] - 1)}

    def _tick(self):
        """保留申请失效、激活和任务看门狗，不再对已允许的连接设置分钟数。"""
        now = self.clock()
        self._expire_request()
        if now >= self._next_license_check:
            self._next_license_check = now + 1.0
            if (self._approved or self._connection_request is not None) and not self._activated():
                self._end_connection("activation_invalid")
        if self._owns_running():
            if now - self._last_contact >= CONTACT_TIMEOUT_SECONDS:
                self._stop_owned("client_timeout", "cancelled")
            elif self._case["deadline"] and now >= self._case["deadline"]:
                self._stop_owned("duration_complete", "completed")
            elif self._case["kind"] != "single" and not self.manager.is_cyclic_sending():
                self._case.update(state="cancelled", stop_reason="stopped_in_ui")
        self._publish_state()
