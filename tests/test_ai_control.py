#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""本机AI协调回归；全部使用临时连接记录、模拟激活和假串口，不操作客户硬件。"""

from dataclasses import asdict
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import threading
import time
import unittest
from unittest.mock import Mock, patch
import uuid

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication, QMessageBox

from app_settings import SettingsStore
from gui.ai_controller import AiController
from gui.main_window import MainWindow
from protocol.definitions import PROTOCOL_DEFINITIONS, PROTOCOL_RUILUN, PROTOCOL_XINGHENG_BMS
from serial_comm.serial_manager import SerialManager, SerialPortDetector

_APP = QApplication.instance() or QApplication([])


class AiControlTests(unittest.TestCase):
    """覆盖权限、原发送路径、动态改参、手动接管及失联自动停发。"""

    def setUp(self):
        """独占临时记录且不扫描设备，模拟激活不生成或读取真实许可证。"""
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.modal_error = Mock()
        for target in (patch.object(SerialPortDetector, "start_detection"), patch.object(SerialManager, "scan_ports", return_value=[]),
                       patch.object(MainWindow, "refresh_recovery_notice"), patch("ai_control.connection.protect_token", return_value="synthetic-protected-data"),
                       patch("gui.main_window.QMessageBox.critical", self.modal_error)):
            target.start()
            self.addCleanup(target.stop)
        self.license = Mock()
        self.license.is_activated.return_value = True
        self.window = MainWindow(activation_service=self.license, settings_store=SettingsStore())
        self.window.history_update_timer.stop()
        self.addCleanup(self.window.close)
        self.controller = AiController(self.window, Path(self.temporary.name) / "connection.json")
        self.window.ai_controller = self.controller
        self.controller.connection_requested.connect(self.window._show_ai_connection_request)
        self.controller.state_changed.connect(self.window._refresh_ai_connection_badge)
        self.manager = self.window.serial_manager
        self.addCleanup(lambda: self.assertEqual(self.modal_error.call_count, 0, self.modal_error.call_args_list))

    def command(self, operation, arguments=None, identifier=None, ok=True, client_id=None):
        """从GUI线程执行与HTTP桥相同的命令，明确检查业务拒绝。"""
        data = {"id": identifier or uuid.uuid4().hex, "operation": operation, "arguments": arguments or {}}
        if client_id is not None:
            data["client_id"] = client_id
        status, response = self.controller.execute(data)
        self.assertEqual(response["ok"], ok, response)
        return response.get("result") if ok else response["error"]

    def enable(self, grant=True):
        """测试显式模拟用户开启，不通过任何网络接口授予权限。"""
        self.controller.enable()
        if grant:
            self.controller.grant_writes()

    def fake_port(self, writer=None):
        """记录实际交给后台write的不可变字节，连接信息全部为合成数据。"""
        self.written = []
        port = Mock()
        port.port, port.baudrate, port.out_waiting, port.is_open = "COM9", 115200, 0, True
        port.write.side_effect = writer or (lambda data: self.written.append(bytes(data)) or len(data))
        self.manager.serial_port, self.manager.is_connected = port, True
        self.window.on_port_connected("COM9")
        return port

    def pump(self, predicate, timeout=2.0):
        """运行真实Qt事件循环和后台结果处理，超时给出明确断言。"""
        until = time.monotonic() + timeout
        while not predicate() and time.monotonic() < until:
            QTest.qWait(5)
        self.assertTrue(predicate())

    def xingheng(self):
        """切换已注册的新协议，不通过控件猜测或复制编码逻辑。"""
        self.command("select_protocol", {"protocol": PROTOCOL_XINGHENG_BMS, "scenario_id": 3})

    def test_controller_is_disabled_and_menu_does_not_start_it(self):
        """默认没有HTTP端口、连接文件或自动写权限。"""
        self.assertIsNone(self.controller.server)
        self.assertFalse(self.controller.timer.isActive())
        self.assertFalse(self.controller.connection_file.path.exists())
        self.command("status", ok=False)
        with patch("gui.ai_control_dialog.QMessageBox.question", return_value=QMessageBox.No):
            self.window.show_ai_control_dialog()
            self.assertFalse(self.window.ai_control_dialog.isModal())
            self.window.ai_control_dialog.grant()
            self.assertIsNone(self.controller.server)
            self.window.ai_control_dialog.close()

    def test_no_activation_cannot_enable_or_send(self):
        """没有激活服务或激活过期时，不提供绕过原激活的后台入口。"""
        self.window.activation_service = None
        with self.assertRaises(ValueError):
            self.controller.enable()
        self.window.activation_service = self.license
        self.license.is_activated.return_value = False
        with self.assertRaises(ValueError):
            self.controller.enable()
        self.assertFalse(self.controller.connection_file.path.exists())

    def test_read_only_rejects_every_write_operation(self):
        """开启不等于授权，未知权限命令也不能提升为可写。"""
        self.enable(grant=False)
        for operation in ("select_protocol", "configure", "set_raw_frame", "connect", "disconnect", "send_once", "start_cycle", "start_sequence"):
            self.assertEqual(self.command(operation, ok=False)["code"], "READ_ONLY")
        for operation in ("grant_writes", "activate", "update", "exec", "read_file"):
            self.assertEqual(self.command(operation, ok=False)["code"], "UNKNOWN_OPERATION")
        self.assertFalse(self.manager.is_connected)

    def test_read_queries_do_not_consume_sequence_or_change_protocol(self):
        """参数和帧预览复用旧接口，纯查询不改变序号或当前场景。"""
        self.enable(grant=False)
        previous = dict(self.window.protocol_handler.__dict__)
        self.assertEqual(len(self.command("protocols")["protocols"]), 20)
        self.command("parameters")
        self.command("ports")
        for _ in range(3):
            self.command("preview")
            self.command("status")
        self.assertEqual(self.window.protocol_handler.__dict__, previous)
        self.assertEqual(self.window.current_protocol, PROTOCOL_RUILUN)

    def test_battery_parameter_discovery_does_not_mix_other_bms_fields(self):
        """集中字段查询避免把另一种BMS参数误导为当前可写数据。"""
        from protocol.definitions import PROTOCOL_BATTERY_SINGLE_WIRE, PROTOCOL_LISHEN_BMS
        self.enable()
        self.command("select_protocol", {"protocol": PROTOCOL_BATTERY_SINGLE_WIRE})
        self.assertEqual(set(self.command("parameters")["fields"]), {"soc_percent"})
        self.command("select_protocol", {"protocol": PROTOCOL_LISHEN_BMS})
        self.assertEqual(set(self.command("parameters")["fields"]), {"soc_percent", "lishen_total_voltage_v", "lishen_temperature_c"})

    def test_all_protocol_selection_and_preview_use_existing_registration(self):
        """全部20协议通过原UI注册入口切换，帧长仍按当前状态定义。"""
        self.enable()
        for protocol in PROTOCOL_DEFINITIONS:
            self.command("select_protocol", {"protocol": protocol, "scenario_id": 3})
            frame = self.command("preview")["bytes"]
            expected = self.window.protocol_handler.get_protocol_frame_length(protocol, self.window.current_status)
            self.assertEqual(len(frame), expected, protocol)
            self.assertEqual(self.window.protocol_combo.currentText(), protocol)
            self.command("parameters")

    def test_dynamic_xingheng_parameters_use_real_background_snapshots(self):
        """循环中SOC新值进入后续实际write，原始保护字段不被重算。"""
        self.enable()
        self.xingheng()
        self.command("configure", {"parameters": {"xingheng_soc_percent": 50.5}, "interval_ms": 10})
        self.fake_port()
        case = self.command("start_cycle", {"duration_ms": 500})
        self.pump(lambda: len(self.written) >= 1)
        self.assertEqual(self.written[0][3], 101)
        self.command("configure", {"parameters": {"xingheng_soc_percent": 20.5}})
        self.pump(lambda: any(frame[3] == 41 for frame in self.written))
        self.assertTrue(all(frame[13] == 0x4A and frame[27:30] == bytes([1, 0x2F, 0x9E]) for frame in self.written))
        self.command("stop", {"case_id": case["id"]})
        self.pump(lambda: not self.manager.is_write_pending())

    def test_format_change_stops_owned_cycle_and_updates_public_length(self):
        """星恒20/31字节切换保持原来的先停止语义。"""
        self.enable()
        self.xingheng()
        self.fake_port()
        self.command("configure", {"parameters": {}, "interval_ms": 10})
        self.command("start_cycle", {"duration_ms": 500})
        self.pump(lambda: bool(self.written))
        self.command("configure", {"parameters": {"xingheng_message_id": 1}})
        self.assertFalse(self.manager.is_cyclic_sending())
        self.assertEqual(len(self.command("preview")["bytes"]), 20)

    def test_raw_frame_is_not_repaired_and_acceptance_is_not_completion(self):
        """单帧先返回accepted，真实后台write完成后才出现written事件。"""
        self.enable()
        self.xingheng()
        self.command("set_raw_frame", {"frame": [255] * 31})
        self.fake_port()
        case = self.command("send_once")
        self.assertEqual(case["state"], "accepted")
        self.pump(lambda: self.controller._case["state"] == "completed")
        self.assertEqual(self.written, [bytes([255] * 31)])
        events = self.command("results")["events"]
        self.assertEqual(len([item for item in events if item["type"] == "written"]), 1)

    def test_recent_duplicate_id_cannot_submit_a_second_frame(self):
        """网络重放同一请求只返回原受理编号，不重复消耗序号或写串口。"""
        self.enable()
        self.fake_port()
        identifier = uuid.uuid4().hex
        first = self.command("send_once", identifier=identifier)
        second = self.command("send_once", identifier=identifier)
        self.assertEqual(first, second)
        error = self.command("stop", identifier=identifier, ok=False)
        self.assertEqual(error["code"], "REQUEST_ID_REUSED")
        self.pump(lambda: self.controller._case["state"] == "completed")
        self.assertEqual(len(self.written), 1)
        self.assertTrue(self.command("results", {"request_id": identifier})["response"]["ok"])

    def test_invalid_parameters_rollback_all_ui_values(self):
        """不支持的字段、非法范围和控件舍入都不能留下部分修改。"""
        self.enable()
        before = asdict(self.window.get_current_status_from_ui())
        before_model = asdict(self.window.current_status)
        before_scenario = self.window.scenario_group.checkedId()
        for parameters in ({"soc_percent": 101}, {"soc_percent": True}, {"soc_percent": "20"}, {"protocol_name": "x"}, {"xinchi_charge_mos": True, "soc_percent": 20}):
            self.command("configure", {"parameters": parameters}, ok=False)
            self.assertEqual(asdict(self.window.get_current_status_from_ui()), before)
            self.assertEqual(asdict(self.window.current_status), before_model)
            self.assertEqual(self.window.scenario_group.checkedId(), before_scenario)
        for interval in (True, 0, 9, 5001, 10.5):
            self.command("configure", {"parameters": {}, "interval_ms": interval}, ok=False)

    def test_sequence_order_is_fixed_and_parameters_do_not_override_it(self):
        """包组顺序与原实现一致，AI不能在运行中用参数覆盖固定帧列表。"""
        self.enable()
        self.fake_port()
        first = self.command("preview")["bytes"]
        second = first.copy()
        second[2] ^= 1
        self.command("configure", {"parameters": {}, "interval_ms": 10})
        self.command("start_sequence", {"frames": [first, second], "duration_ms": 500})
        self.pump(lambda: len(self.written) >= 4)
        self.assertEqual(self.written[:4], [bytes(first), bytes(second)] * 2)
        self.assertEqual(self.command("configure", {"parameters": {}}, ok=False)["code"], "BUSY")

    def test_manual_stop_button_does_not_restart_a_cycle(self):
        """用户按停止时撤销AI权，但不能因提前停了定时器而反转成启动。"""
        self.enable()
        self.fake_port()
        self.command("start_cycle", {"duration_ms": 1000})
        self.window.toggle_cyclic_send()
        self.assertFalse(self.manager.is_cyclic_sending())
        self.assertFalse(self.controller._write_allowed)

    def test_existing_manual_cycle_is_never_taken_over(self):
        """AI接口不得改变原手动循环的参数、发送或停止状态。"""
        self.enable()
        self.fake_port()
        self.window.toggle_cyclic_send()
        self.assertTrue(self.manager.is_cyclic_sending())
        with self.assertRaises(ValueError):
            self.controller.grant_writes()
        self.command("stop")
        self.assertTrue(self.manager.is_cyclic_sending())

    def test_manual_protocol_change_cancels_ai_without_switching_back(self):
        """原协议切换槽继续控制界面，后台不重建或改回旧协议。"""
        self.enable()
        self.fake_port()
        self.command("start_cycle", {"duration_ms": 1000})
        self.window.protocol_combo.setCurrentText(PROTOCOL_XINGHENG_BMS)
        QTest.qWait(20)
        self.assertEqual(self.window.current_protocol, PROTOCOL_XINGHENG_BMS)
        self.assertFalse(self.manager.is_cyclic_sending())
        self.assertFalse(self.controller._write_allowed)

    def test_lost_contact_stops_ai_jobs_but_does_not_set_a_permission_deadline(self):
        """失联看门狗仍生效；本次授权不因超过五分钟或更长空闲而自动到期。"""
        now = [100.0]
        self.controller.clock = lambda: now[0]
        self.enable()
        self.fake_port()
        self.command("start_cycle", {"duration_ms": 60000})
        now[0] += 11
        self.controller._tick()
        self.assertFalse(self.manager.is_cyclic_sending())
        self.assertEqual(self.controller._case["stop_reason"], "client_timeout")
        now[0] += 3600
        self.controller._tick()
        self.assertTrue(self.controller._write_allowed)
        self.assertIsNone(self.command("status")["write_seconds_remaining"])
        self.command("start_cycle", {"duration_ms": 60000})
        self.assertTrue(self.manager.is_cyclic_sending())
        self.command("stop")

    def test_duration_ends_and_failed_license_revokes_permission(self):
        """时长到达正常结束，激活失效立即拒绝之后的写入。"""
        self.enable()
        self.fake_port()
        self.command("configure", {"parameters": {}, "interval_ms": 10})
        self.command("start_cycle", {"duration_ms": 80})
        self.pump(lambda: self.controller._case["state"] == "completed")
        self.assertFalse(self.manager.is_cyclic_sending())
        self.license.is_activated.return_value = False
        self.assertEqual(self.command("send_once", ok=False)["code"], "NOT_ACTIVATED")

    def test_stopping_waits_for_the_actual_inflight_result(self):
        """已进入驱动的帧不能撤回，停止后的实际写入也必须计入本任务。"""
        entered, release = threading.Event(), threading.Event()
        def writer(data):
            """仅阻塞本测试的假串口，退出前始终释放。"""
            entered.set()
            release.wait(1)
            self.written.append(bytes(data))
            return len(data)
        self.addCleanup(release.set)
        self.enable()
        self.fake_port(writer)
        self.command("send_once")
        self.pump(entered.is_set)
        self.command("stop")
        self.assertEqual(self.controller._case["state"], "stopping")
        release.set()
        self.pump(lambda: self.controller._case["state"] == "cancelled")
        self.assertEqual(self.controller._case["sent_frames"], 1)

    def test_manual_single_write_is_not_attributed_to_old_ai_case(self):
        """同一底层代次里的后续手动单帧不污染已完成的AI测试记录。"""
        self.enable()
        self.fake_port()
        self.command("send_once")
        self.pump(lambda: self.controller._case["state"] == "completed")
        self.window.send_single_frame()
        self.pump(lambda: len(self.written) == 2 and not self.manager.is_write_pending())
        self.assertEqual(self.controller._case["sent_frames"], 1)

    def test_http_bridge_timeout_cancels_not_started_request(self):
        """GUI没有处理前超时的写请求在之后恢复事件循环时也不会发帧。"""
        self.enable()
        self.fake_port()
        results = []
        request = {"id": uuid.uuid4().hex, "operation": "send_once", "arguments": {}}
        thread = threading.Thread(target=lambda: results.append(self.controller.invoke(request)))
        thread.start()
        thread.join(2.5)
        self.assertFalse(thread.is_alive())
        self.assertEqual(results[0][0], 503)
        QTest.qWait(20)
        self.assertEqual(self.written, [])

    def test_gui_bridge_has_bounded_pending_requests(self):
        """界面繁忙时最多保留八份Qt事件，HTTP超时不能制造无限取消队列。"""
        self.enable()
        responses = []
        threads = [threading.Thread(target=lambda: responses.append(self.controller.invoke(
            {"id": uuid.uuid4().hex, "operation": "status", "arguments": {}}))) for _ in range(9)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(3)
        self.assertTrue(all(not thread.is_alive() for thread in threads))
        self.assertEqual(len(responses), 9)
        self.assertEqual(sum(response[1]["error"]["code"] == "QUEUE_FULL" for response in responses), 1)
        QTest.qWait(20)

    def test_results_are_bounded_and_report_truncation(self):
        """连续测试不无限增长内存，也不把被截断历史当作完整证据。"""
        self.enable()
        for _ in range(2050):
            self.controller._event("synthetic")
        result = self.command("results", {"after_id": 0, "limit": 5})
        self.assertTrue(result["truncated"])
        self.assertEqual(len(result["events"]), 5)
        self.command("results", {"limit": 257}, ok=False)

    def test_close_removes_only_current_connection_record(self):
        """关闭服务清理自有发现记录，不删除后来替换的未知文件。"""
        self.enable()
        path = self.controller.connection_file.path
        self.controller.shutdown()
        self.assertFalse(path.exists())
        self.controller.enable()
        path.write_text("foreign record", encoding="utf-8")
        self.controller.shutdown()
        self.assertEqual(path.read_text(encoding="utf-8"), "foreign record")

    def test_old_queued_session_cannot_use_new_permission(self):
        """重启服务后，旧连接排队的发帧请求不能借新授权执行。"""
        self.enable()
        self.fake_port()
        old_session = self.controller._session
        responses = []
        request = {"id": uuid.uuid4().hex, "operation": "send_once", "arguments": {}}
        thread = threading.Thread(target=lambda: responses.append(self.controller.invoke(request, old_session)))
        thread.start()
        self.controller.shutdown()
        self.controller.enable()
        self.controller.grant_writes()
        self.pump(lambda: bool(responses))
        thread.join(1)
        self.assertEqual(responses[0][1]["error"]["code"], "SESSION_EXPIRED")
        self.assertEqual(self.written, [])

    def test_stale_stop_cannot_cancel_new_case(self):
        """同步等待工具退出时只停止自己的编号，不干扰另一个测试。"""
        self.enable()
        self.fake_port()
        self.command("start_cycle", {"duration_ms": 1000})
        self.assertEqual(self.command("stop", {"case_id": uuid.uuid4().hex}, ok=False)["code"], "CASE_CHANGED")
        self.assertTrue(self.manager.is_cyclic_sending())

    def test_connection_failure_is_structured_without_modal_dialog(self):
        """AI连接失败不弹出阻塞窗口，手动连接的原提示路径保持不变。"""
        self.enable()
        with patch("serial_comm.serial_manager.serial.Serial", side_effect=OSError("synthetic connection failure")):
            error = self.command("connect", {"port": "COM9"}, ok=False)
        self.assertEqual(error["code"], "CONNECT_FAILED")
        self.assertEqual(self.modal_error.call_count, 0)
        self.window.on_connection_error("synthetic manual failure")
        self.modal_error.assert_called_once()
        self.modal_error.reset_mock()

    def test_busy_or_invalid_operations_do_not_consume_sequence(self):
        """忙、未连接和非法时长在生成真实帧前拒绝，预览序号不前进。"""
        self.enable()
        before = dict(self.window.protocol_handler.__dict__)
        self.command("send_once", ok=False)
        self.fake_port()
        for value in (True, -1, 0, 60001):
            self.command("start_cycle", {"duration_ms": value}, ok=False)
        self.assertEqual(self.window.protocol_handler.__dict__, before)
        self.assertEqual(self.written, [])

    def test_connection_cleanup_failure_does_not_block_close(self):
        """本机发现文件被占用时保留记录，原窗口关闭和串口清理仍能完成。"""
        self.enable()
        with patch.object(self.controller.connection_file, "remove", side_effect=PermissionError("synthetic busy file")):
            self.controller.shutdown()
        self.assertIsNone(self.controller.server)
        self.assertFalse(self.controller.timer.isActive())
        self.controller.connection_file.remove()

    def test_queued_slot_contains_unexpected_exceptions_and_releases_capacity(self):
        """异常不能从Qt槽逃逸中止应用，队列容量和后续合法请求都必须恢复。"""
        from gui.ai_controller import _Invocation
        self.enable()
        data = {"id": uuid.uuid4().hex, "operation": "status", "arguments": {}}
        self.assertTrue(self.controller._invocation_slots.acquire(blocking=False))
        invocation = _Invocation(data, self.controller._session, self.controller._permission_epoch)
        with patch.object(self.controller, "execute", side_effect=RuntimeError("synthetic unexpected failure")):
            self.controller._execute(invocation)
        self.assertTrue(invocation.done.is_set())
        self.assertEqual(invocation.response[0], 500)
        self.assertEqual(invocation.response[1]["error"]["code"], "INTERNAL_ERROR")
        self.assertNotIn("synthetic", str(invocation.response))
        self.command("status")
        self.assertEqual(self.command("configure", {"parameters": {"speed": float("inf")}}, ok=False)["code"], "INVALID_ARGUMENT")

    def request_connection(self, client_id=None):
        """测试客户端只能申请，批准动作始终模拟用户点击真实Qt按钮。"""
        client_id = client_id or uuid.uuid4().hex
        result = self.command("request_connection", client_id=client_id)
        self.assertEqual(result["state"], "pending")
        return client_id, result["request_id"]

    def approve_connection(self, read_only=False):
        """在隔离窗口模拟用户明确同意，不把批准入口作为MCP命令调用。"""
        client_id, request_id = self.request_connection()
        dialog = self.window.ai_connection_dialog
        (dialog.read_only_button if read_only else dialog.allow_button).click()
        self.assertIsNone(self.window.ai_connection_dialog)
        return client_id

    def test_startup_prepares_only_requests_and_does_not_read_or_control(self):
        """打开软件即可接收申请，但所有测试数据与串口操作仍须人工同意。"""
        self.window.prepare_ai_connection_requests()
        self.assertIsNotNone(self.controller.server)
        self.assertFalse(self.controller._approved)
        self.assertFalse(self.controller._write_allowed)
        self.assertTrue(self.window.ai_status_btn.isHidden())
        for operation in ("status", "ports", "protocols", "parameters", "preview", "results", "send_once"):
            self.assertEqual(self.command(operation, ok=False)["code"], "CONNECTION_REQUIRED")
        self.assertFalse(self.manager.is_connected)

    def test_connection_popup_is_non_modal_defaults_to_reject_and_never_self_grants(self):
        """重复申请只有一个提示，未点击前不能通过网络授予自己权限。"""
        self.controller.listen_for_requests()
        client_id, request_id = self.request_connection()
        dialog = self.window.ai_connection_dialog
        self.assertFalse(dialog.isModal())
        self.assertTrue(dialog.reject_button.isDefault())
        self.assertEqual(self.command("request_connection", client_id=client_id)["request_id"], request_id)
        self.assertIs(self.window.ai_connection_dialog, dialog)
        self.assertEqual(self.window.ai_status_btn.text(), "AI申请中")
        for operation in ("enable", "grant_writes", "resolve_connection"):
            self.assertEqual(self.command(operation, ok=False, client_id=client_id)["code"], "UNKNOWN_OPERATION")
        dialog.reject_button.click()
        self.assertEqual(self.command("connection_status", client_id=client_id)["state"], "rejected")
        self.assertFalse(self.controller._approved)
        self.assertFalse(self.controller._write_allowed)
        self.assertTrue(self.window.ai_status_btn.isHidden())

    def test_session_permission_requires_each_new_connector_to_be_confirmed(self):
        """本次允许只属于随机标识对应的连接器，不能被另一连接器继承。"""
        self.controller.listen_for_requests()
        client_id = self.approve_connection()
        status = self.command("status", client_id=client_id)
        self.assertTrue(status["write_authorized"])
        self.assertEqual(status["authorization_scope"], "current_connection")
        self.assertIsNone(status["write_seconds_remaining"])
        other = uuid.uuid4().hex
        for operation in ("status", "send_once", "close_connection"):
            self.assertEqual(self.command(operation, ok=False, client_id=other)["code"], "CONNECTION_IN_USE")
        result = self.command("connection_status", client_id=other)
        self.assertEqual(set(result), {"state", "message"})
        self.assertEqual(result["state"], "busy")
        self.assertFalse(self.manager.is_connected)

    def test_read_only_approval_can_query_but_cannot_send(self):
        """用户可单独选择只读，不因允许连接而隐式允许发送或自动提升权限。"""
        self.controller.listen_for_requests()
        client_id = self.approve_connection(read_only=True)
        self.assertEqual(self.command("connection_status", client_id=client_id)["access"], "read_only")
        self.command("preview", client_id=client_id)
        self.assertEqual(self.command("send_once", ok=False, client_id=client_id)["code"], "READ_ONLY")
        self.assertFalse(self.controller._write_allowed)

    def test_robot_badge_tracks_acknowledgement_activity_and_idle_not_listening(self):
        """提示区分申请、获准、实际连接和测试中，空闲不假装仍有活动连接。"""
        now = [100.0]
        self.controller.clock = lambda: now[0]
        self.controller.listen_for_requests()
        self.assertTrue(self.window.ai_status_btn.isHidden())
        client_id = self.approve_connection()
        self.assertEqual(self.window.ai_status_btn.text(), "AI已授权")
        self.command("connection_status", client_id=client_id)
        self.assertEqual(self.window.ai_status_btn.text(), "AI连接中")
        self.fake_port()
        self.command("start_cycle", {"duration_ms": 60000}, client_id=client_id)
        self.assertEqual(self.window.ai_status_btn.text(), "AI测试中")
        self.command("stop", client_id=client_id)
        self.pump(lambda: not self.manager.is_write_pending())
        now[0] += 11
        self.controller._tick()
        self.assertEqual(self.window.ai_status_btn.text(), "AI已授权")
        self.assertTrue(self.controller._write_allowed)
        self.window.ai_status_btn.click()
        self.assertIsNotNone(self.window.ai_control_dialog)
        self.assertNotIn("分钟", self.window.ai_control_dialog.grant_button.text())
        self.window.ai_control_dialog.revoke_button.click()
        self.assertTrue(self.window.ai_status_btn.isHidden())
        self.assertEqual(self.command("status", ok=False, client_id=client_id)["code"], "CONNECTION_REQUIRED")

    def test_denied_requests_are_cooled_down_even_if_the_client_changes_identity(self):
        """拒绝后的全局冷却避免不同请求ID或客户端标识持续触发弹窗。"""
        now = [100.0]
        self.controller.clock = lambda: now[0]
        self.controller.listen_for_requests()
        self.request_connection()
        self.window.ai_connection_dialog.reject()
        result = self.command("request_connection", client_id=uuid.uuid4().hex)
        self.assertEqual(result["state"], "cooldown")
        self.assertIsNone(self.window.ai_connection_dialog)
        now[0] += 16
        self.request_connection()
        self.window.ai_connection_dialog.reject()

    def test_expired_popup_cannot_grant_and_no_test_data_is_returned_before_approval(self):
        """只对未答复申请设有限等待；已获准连接没有五分钟到期机制。"""
        now = [100.0]
        self.controller.clock = lambda: now[0]
        self.controller.listen_for_requests()
        client_id, request_id = self.request_connection()
        pending = self.command("connection_status", client_id=client_id)
        self.assertNotIn("protocol", pending)
        self.assertNotIn("serial", pending)
        now[0] += 61
        self.controller._tick()
        self.assertIsNone(self.window.ai_connection_dialog)
        self.assertEqual(self.command("connection_status", client_id=client_id)["state"], "expired")
        self.assertFalse(self.controller.resolve_connection(request_id, "control"))
        self.assertFalse(self.controller._approved)

    def test_request_permission_cannot_take_over_a_manual_cycle(self):
        """人工点击同意时也先检查手动循环，可改选只读但不抢占手动测试。"""
        self.controller.listen_for_requests()
        self.fake_port()
        self.window.toggle_cyclic_send()
        client_id, request_id = self.request_connection()
        with self.assertRaises(ValueError):
            self.controller.resolve_connection(request_id, "control")
        self.assertFalse(self.controller._approved)
        self.assertTrue(self.manager.is_cyclic_sending())
        self.window.ai_connection_dialog.read_only_button.click()
        self.command("close_connection", client_id=client_id)
        self.assertTrue(self.manager.is_cyclic_sending())
        self.assertTrue(self.manager.is_connected)

    def test_other_connector_cannot_keep_owner_sending_after_lost_contact(self):
        """其他申请状态查询不计入已授权会话的心跳，失联仍会停发。"""
        now = [100.0]
        self.controller.clock = lambda: now[0]
        self.controller.listen_for_requests()
        client_id = self.approve_connection()
        self.fake_port()
        self.command("start_cycle", {"duration_ms": 60000}, client_id=client_id)
        now[0] += 11
        self.command("connection_status", client_id=uuid.uuid4().hex)
        self.controller._tick()
        self.assertFalse(self.manager.is_cyclic_sending())
        self.assertEqual(self.controller._case["stop_reason"], "client_timeout")

    def test_queued_write_cannot_borrow_renewed_session_permission(self):
        """保持同一个监听端口重授权时，旧Qt事件仍因授权代次不同被拒绝。"""
        self.controller.listen_for_requests()
        client_id = self.approve_connection()
        self.fake_port()
        responses = []
        data = {"id": uuid.uuid4().hex, "client_id": client_id, "operation": "send_once", "arguments": {}}
        thread = threading.Thread(target=lambda: responses.append(self.controller.invoke(data)))
        thread.start()
        time.sleep(0.02)
        self.command("close_connection", client_id=client_id)
        self.request_connection(client_id)
        self.window.ai_connection_dialog.allow_button.click()
        self.pump(lambda: bool(responses))
        thread.join(1)
        self.assertEqual(responses[0][1]["error"]["code"], "SESSION_EXPIRED")
        self.assertEqual(self.written, [])

    def test_permission_change_keeps_queued_read_safe_but_rejects_queued_write(self):
        """人工授权与只读轮询并发时不误报断连，旧排队写入仍不得借新权限发送。"""
        from gui.ai_controller import _Invocation
        self.enable(grant=False)
        self.fake_port()
        invocations = []
        for operation in ("status", "send_once"):
            data = {"id": uuid.uuid4().hex, "operation": operation, "arguments": {}}
            invocations.append(_Invocation(data, self.controller._session, self.controller._permission_epoch))
            self.assertTrue(self.controller._invocation_slots.acquire(blocking=False))
        self.controller.grant_writes()
        for invocation in invocations:
            self.controller._execute(invocation)
        self.assertTrue(invocations[0].response[1]["ok"])
        self.assertEqual(invocations[1].response[1]["error"]["code"], "SESSION_EXPIRED")
        self.assertEqual(self.written, [])

    def test_invalid_activation_closes_approved_and_pending_connections(self):
        """申请入口不能绕过激活，激活失效即撤权并关闭待确认弹窗。"""
        self.controller.listen_for_requests()
        client_id = self.approve_connection()
        self.license.is_activated.return_value = False
        self.assertEqual(self.command("status", ok=False, client_id=client_id)["code"], "NOT_ACTIVATED")
        self.assertFalse(self.controller._write_allowed)
        self.assertEqual(self.command("request_connection", ok=False, client_id=client_id)["code"], "NOT_ACTIVATED")
        self.license.is_activated.return_value = True
        self.request_connection(client_id)
        self.license.is_activated.return_value = False
        self.controller._next_license_check = 0
        self.controller._tick()
        self.assertIsNone(self.window.ai_connection_dialog)
        self.assertFalse(self.controller._approved)

    def test_listener_start_failure_is_nonfatal_and_close_removes_pending_popup(self):
        """发现记录冲突只提示，不阻断工具启动；关闭时不残留授权窗口。"""
        with patch.object(self.controller, "listen_for_requests", side_effect=ValueError("synthetic conflict")):
            self.window.prepare_ai_connection_requests()
        self.assertIsNone(self.controller.server)
        self.assertIn("AI连接申请入口未开启", self.window.status_bar.currentMessage())
        self.controller.listen_for_requests()
        self.request_connection()
        self.controller.shutdown()
        self.assertIsNone(self.window.ai_connection_dialog)
        self.assertTrue(self.window.ai_status_btn.isHidden())

    def test_new_listener_does_not_restore_previous_session_authorization(self):
        """关闭后重新开启监听不恢复已批准的只读或写权限。"""
        self.controller.listen_for_requests()
        client_id = self.approve_connection()
        self.controller.shutdown()
        self.controller.listen_for_requests()
        self.assertEqual(self.command("connection_status", client_id=client_id)["state"], "not_requested")
        self.assertEqual(self.command("status", ok=False, client_id=client_id)["code"], "CONNECTION_REQUIRED")
