#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""星恒 A1.3.3 已确认的公有/31字节实时格式，不包含加密算法或硬件波形。"""

from dataclasses import dataclass
from decimal import Decimal
from types import MappingProxyType

from .frame_utils import normalize_frame

XINGHENG_PUBLIC = 0x01
XINGHENG_REALTIME = 0x3A
XINGHENG_FRAME_LENGTHS = MappingProxyType({XINGHENG_PUBLIC: 20, XINGHENG_REALTIME: 31})


@dataclass(frozen=True)
class XinghengField:
    """共享物理量范围和精度，界面与校验使用同一份定义。"""

    name: str
    label: str
    minimum: float
    maximum: float
    step: float = 1
    hexadecimal: bool = False


XINGHENG_COMMON_FIELDS = (
    XinghengField("soc_percent", "SOC (%)", 0, 100, 0.5),
    XinghengField("voltage_v", "总电压 (V)", 0, 1000, 0.1),
    XinghengField("current_a", "工作电流 (A)", -500, 500, 0.1),
    XinghengField("max_temperature_c", "最高温度 (℃)", -40, 150),
    XinghengField("min_temperature_c", "最低温度 (℃)", -40, 150),
    XinghengField("mos_temperature_c", "MOS温度 (℃)", -40, 150),
    XinghengField("fault_code", "故障码", 0, 255, hexadecimal=True),
    XinghengField("work_state", "工作状态", 0, 2),
)
XINGHENG_PUBLIC_FIELDS = (
    XinghengField("manufacturer", "厂商代码", 0, 254, hexadecimal=True),
    XinghengField("model", "电池型号", 0, 15),
    XinghengField("material", "电芯材料", 0, 15),
    XinghengField("rated_voltage_v", "额定电压 (V)", 0, 1000, 0.1),
    XinghengField("rated_capacity_ah", "额定容量 (Ah)", 0, 1000, 0.1),
)
XINGHENG_REALTIME_FIELDS = (
    XinghengField("response_device", "请求应答设备", 0, 3),
    XinghengField("cycle_count", "循环次数", 0, 60000),
    XinghengField("max_cell_mv", "最高单体 (mV)", 0, 10000),
    XinghengField("min_cell_mv", "最低单体 (mV)", 0, 10000),
    XinghengField("max_cell_index", "最高单体位置", 1, 25),
    XinghengField("min_cell_index", "最低单体位置", 1, 25),
    # 8位、0.1A/bit，FF为无效；不能将文档含混的“250”误作250A后截断。
    XinghengField("regen_current_a", "允许回馈电流 (A)", 0, 25.4, 0.1),
    XinghengField("charge_voltage_v", "请求充电电压 (V)", 0, 1000, 0.1),
    XinghengField("charge_current_a", "请求充电电流 (A)", 0, 25.4, 0.1),
    XinghengField("charge_state", "充电状态", 0, 4),
)
XINGHENG_VERSION_FIELD = XinghengField("version", "协议版本", 0, 0xEE, hexadecimal=True)
XINGHENG_RAW_FIELDS = (
    XinghengField("bms_status_raw", "BMS状态 (原始)", 0, 255, hexadecimal=True),
    XinghengField("key_raw", "key (原始)", 1, 255, hexadecimal=True),
    XinghengField("result0_raw", "结果字节0 (原始)", 0, 255, hexadecimal=True),
    XinghengField("result1_raw", "结果字节1 (原始)", 0, 255, hexadecimal=True),
)


def xingheng_frame_length(message_id):
    """仅接受已确认的两种格式；布尔值不能借整数相等关系冒充01报文。"""
    if type(message_id) is not int or message_id not in XINGHENG_FRAME_LENGTHS:
        raise ValueError("星恒报文类型必须为 0x01 或 0x3A")
    return XINGHENG_FRAME_LENGTHS[message_id]


def xingheng_fields(message_id):
    """返回当前格式参与编码的字段，不验证另一个报文未使用的参数。"""
    xingheng_frame_length(message_id)
    extra = XINGHENG_PUBLIC_FIELDS if message_id == XINGHENG_PUBLIC else XINGHENG_REALTIME_FIELDS + XINGHENG_RAW_FIELDS
    return (XINGHENG_VERSION_FIELD,) + XINGHENG_COMMON_FIELDS + extra


def xingheng_wire_value(value, resolution=1, offset=0):
    """对已校验物理量使用十进制精确换算，避免浮点误差和无意舍入。"""
    return int((Decimal(str(value)) - Decimal(str(offset))) / Decimal(str(resolution)))


def normalize_xingheng_test_frame(frame, message_id=None):
    """原始测试只校验字节和已支持长度，保留用户故意设置的帧头、len或错误校验。"""
    normalized = normalize_frame(frame, label="星恒测试帧")
    allowed = (xingheng_frame_length(message_id),) if message_id is not None else tuple(XINGHENG_FRAME_LENGTHS.values())
    if len(normalized) not in allowed:
        raise ValueError("星恒测试帧长度必须匹配20字节公有或31字节实时格式")
    return normalized


def xingheng_byte_descriptions(message_id=XINGHENG_REALTIME):
    """逐字节说明按当前报文返回副本，不把原始保护字段解释成已解密状态。"""
    xingheng_frame_length(message_id)
    if message_id == XINGHENG_PUBLIC:
        return [
            "公有报文ID (固定0x01)", "协议版本 (默认0x13)", "电池厂商代码 (0x01星恒)",
            "电池型号", "电芯材料", "额定电压低字节 (0.1V)", "额定电压高字节",
            "额定容量低字节 (0.1Ah)", "额定容量高字节", "SOC (0.5%/bit；FF无效)",
            "工作电压低字节 (0.1V)", "工作电压高字节", "工作电流低字节 (0.1A，偏移-500A)",
            "工作电流高字节", "最高温度 (偏移-40℃)", "最低温度 (偏移-40℃)",
            "MOS温度 (偏移-40℃)", "故障码 (含报警/预警)", "工作状态 (0放电/1充电/2回馈)",
            "前19字节累加和低8位",
        ]
    return [
        "实时报文ID (固定0x3A)", "协议版本 (客户参考0x13)", "数据长度len (固定0x1B，不含头及校验)",
        "SOC (0.5%/bit；C8=100%；FF无效)", "工作电压低字节 (0.1V)", "工作电压高字节",
        "工作电流低字节 (0.1A，偏移-500A)", "工作电流高字节", "最高温度 (偏移-40℃)",
        "最低温度 (偏移-40℃)", "MOS温度 (偏移-40℃)", "故障码 (含报警/预警)",
        "工作状态D0-2／请求应答设备D5-7", "BMS状态原始字节 (不加密、不解码)",
        "循环次数低字节", "循环次数高字节", "最高单体电压低字节 (mV)", "最高单体电压高字节",
        "最低单体电压低字节 (mV)", "最低单体电压高字节", "最高单体位置", "最低单体位置",
        "允许回馈电流 (0.1A/bit)", "请求充电电压低字节 (0.1V)", "请求充电电压高字节",
        "请求充电电流 (0.1A/bit；FA=25A)", "充电状态", "key原始字节 (不自动改变)",
        "加密结果原始字节0 (不计算)", "加密结果原始字节1 (不计算)", "前30字节累加和低8位",
    ]
