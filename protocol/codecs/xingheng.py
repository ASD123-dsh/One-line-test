#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""星恒智能BMS公有与客户31字节实时帧编码；保护字段仅原样透传。"""

from ..xingheng import XINGHENG_PUBLIC, xingheng_wire_value


class XinghengBmsCodec:
    """构造测试数据，不实现加密、互认、串口或单线物理时序。"""

    def _generate_xingheng_bms_frame(self, status):
        """按当前类型编码并求和，禁止套用旧BMS的SOC、电流和温度比例。"""
        valid, error = self.validate_status_bits(status)
        if not valid:
            return False, [], error
        if status.xingheng_message_id == XINGHENG_PUBLIC:
            frame = self._xingheng_public_payload(status)
        else:
            frame = self._xingheng_realtime_payload(status)
        frame.append(self._sum_checksum(frame))
        return True, frame, ""

    def _xingheng_measurements(self, status):
        """共有测量值按Intel低字节先发，零电流编码为0x1388而非0。"""
        voltage = xingheng_wire_value(status.xingheng_voltage_v, 0.1)
        current = xingheng_wire_value(status.xingheng_current_a, 0.1, -500)
        return [
            xingheng_wire_value(status.xingheng_soc_percent, 0.5),
            voltage & 255, voltage >> 8, current & 255, current >> 8,
            status.xingheng_max_temperature_c + 40,
            status.xingheng_min_temperature_c + 40,
            status.xingheng_mos_temperature_c + 40, status.xingheng_fault_code,
        ]

    def _xingheng_public_payload(self, status):
        """生成20字节公有帧的前19字节，不附加私有len或任何加密字段。"""
        voltage = xingheng_wire_value(status.xingheng_rated_voltage_v, 0.1)
        capacity = xingheng_wire_value(status.xingheng_rated_capacity_ah, 0.1)
        return [
            XINGHENG_PUBLIC, status.xingheng_version, status.xingheng_manufacturer,
            status.xingheng_model, status.xingheng_material,
            voltage & 255, voltage >> 8, capacity & 255, capacity >> 8,
        ] + self._xingheng_measurements(status) + [status.xingheng_work_state]

    def _xingheng_realtime_payload(self, status):
        """保持客户截图的3A 13 1B布局；原始状态、key和结果不随SOC重新计算。"""
        frame = [0x3A, status.xingheng_version, 0x1B] + self._xingheng_measurements(status)
        frame.extend([
            status.xingheng_work_state | (status.xingheng_response_device << 5),
            status.xingheng_bms_status_raw,
        ])
        for value in (status.xingheng_cycle_count, status.xingheng_max_cell_mv, status.xingheng_min_cell_mv):
            frame.extend([value & 255, value >> 8])
        charge_voltage = xingheng_wire_value(status.xingheng_charge_voltage_v, 0.1)
        frame.extend([
            status.xingheng_max_cell_index, status.xingheng_min_cell_index,
            xingheng_wire_value(status.xingheng_regen_current_a, 0.1),
            charge_voltage & 255, charge_voltage >> 8,
            xingheng_wire_value(status.xingheng_charge_current_a, 0.1),
            status.xingheng_charge_state, status.xingheng_key_raw,
            status.xingheng_result0_raw, status.xingheng_result1_raw,
        ])
        return frame
