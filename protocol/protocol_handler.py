#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
一线通协议V1.56处理模块

实现协议帧生成、校验和计算、Status位配置等核心功能
严格按照协议文档规范实现所有算法
"""

import struct
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

@dataclass
class ProtocolConfig:
    """协议配置参数"""
    # 固定参数（不可修改）
    DEVICE_CODE = 0x08          # DATA0 设备编码
    SEQ_CODE_L = 0x61           # DATA1 流水号低8位
    SEQ_CODE_H = 0x00           # 流水号高4位
    PLUS_CODE = 0x00            # 加密码（默认不加密）
    
    # 可配置参数
    tosc_us: int = 100          # Tosc值（32-320us，默认100us）
    baud_rate: int = 9600       # 串口波特率
    send_interval_ms: int = 1000 # 发送间隔（ms）

@dataclass
class StatusBits:
    """Status位参数定义"""
    # Status1 (DATA2低4位) - 通用字段
    distance_mode: bool = False     # D3: 运动里程模式
    speed_alarm: bool = False       # D2: 超速提示音
    p_gear_protect: bool = False    # D1: P档启动保护
    tcs_status: bool = False        # D0: TCS状态 (1=亮/0=灭)
    
    # 常州新思维协议专用字段 - Status1 (DATA2低4位)
    xinsiwei_reserved_d3: bool = False  # D3: 备用
    xinsiwei_reserved_d2: bool = False  # D2: 备用
    xinsiwei_reserved_d1: bool = False  # D1: 备用
    xinsiwei_reserved_d0: bool = False  # D0: 备用
    
    # Status2 (DATA3)
    hall_fault: bool = False        # D6: 霍尔故障
    throttle_fault: bool = False    # D5: 转把故障
    controller_fault: bool = False  # D4: 控制器故障
    under_voltage: bool = False     # D3: 欠压保护
    cruise: bool = False            # D2: 巡航
    assist: bool = False            # D1: 助力
    motor_phase_loss: bool = False  # D0: 电机缺相
    
    # Status3 (DATA4)
    gear_four: bool = False         # D7: 四档指示
    motor_running: bool = False     # D6: 电机运行状态 (1=运行/0=停止)
    brake: bool = False             # D5: 刹车
    controller_protect: bool = False # D4: 控制器保护
    regen_charging: bool = False    # D3: 滑行充电 (1=能量回收)
    anti_runaway: bool = False      # D2: 防飞车保护
    speed_mode: int = 0             # D1~D0: 三速模式 (0-3)
    
    # Status4 (DATA5)
    current_70_flag: bool = False   # D7: 70%电流标志
    one_key_enable: bool = False    # D6: 一键通启用
    ekk_enable: bool = False        # D5: EKK启用
    backup_power: bool = False      # D4: 备用电源
    over_current: bool = False      # D3: 过流保护
    stall_protect: bool = False     # D2: 堵转保护
    reverse: bool = False           # D1: 倒车
    speed_limit: bool = False       # D0: 限速 (1=限速/0=解除)
    
    # Status5 (DATA6) - 运行电流
    current_a: int = 0              # 运行电流（A），负电流高位为1
    
    # Status6~7 (DATA7~8) - 速度双字节
    speed_kmh: float = 0.0          # 速度（km/h），精度0.1
    
    # 常州新思维协议专用 - 霍尔计数速度
    xinsiwei_hall_count: int = 0    # 霍尔计数值（0-65535）
    
    # Status8 (DATA9) - 电池SOC
    soc_percent: int = 50           # 电池SOC (0-100%)，0xEE=故障
    soc_fault: bool = False         # SOC故障标志
    
    # Status9 (DATA10) - 系统电压
    voltage_36v: bool = False       # BIT0: 36V
    voltage_48v: bool = True        # BIT1: 48V (默认)
    voltage_60v: bool = False       # BIT2: 60V
    voltage_64v: bool = False       # BIT3: 64V
    voltage_72v: bool = False       # BIT4: 72V
    voltage_80v: bool = False       # BIT5: 80V
    voltage_84v: bool = False       # BIT6: 84V
    voltage_96v: bool = False       # BIT7: 96V
    
    # 常州新思维协议专用字段
    xinsiwei_protocol: bool = False # 标识是否使用常州新思维协议
    xinsiwei_sequence: int = 0      # 12位流水号（0-4095）

class ProtocolHandler:
    """一线通协议处理器"""
    
    def __init__(self):
        self.config = ProtocolConfig()
        self.status = StatusBits()
        # 常州新思维协议序号自动递增计数器
        self._xinsiwei_sequence_counter = 1  # 从1开始，符合协议文本示例（30 01, 30 02, 30 03, 30 04）
    
    def get_current_xinsiwei_sequence(self) -> int:
        """
        获取当前常州新思维协议序号（不递增）
        
        用于预览显示，不会改变内部计数器
        
        Returns:
            当前序号值
        """
        return self._xinsiwei_sequence_counter

    def get_next_xinsiwei_sequence(self) -> int:
        """
        获取下一个常州新思维协议序号并自动递增
        
        Returns:
            当前序号值（1-4095循环）
        """
        current_seq = self._xinsiwei_sequence_counter
        # 序号递增，范围1-4095循环（符合12位序号范围，但从1开始）
        self._xinsiwei_sequence_counter = (self._xinsiwei_sequence_counter % 4095) + 1
        return current_seq
    
    def reset_xinsiwei_sequence(self, start_value: int = 1):
        """
        重置常州新思维协议序号计数器
        
        Args:
            start_value: 起始序号值（默认为1）
        """
        if not (1 <= start_value <= 4095):
            raise ValueError("序号起始值必须在1-4095范围内")
        self._xinsiwei_sequence_counter = start_value
    
    def validate_status_bits(self, status: StatusBits) -> Tuple[bool, str]:
        """
        验证Status位参数是否符合协议规范
        
        Returns:
            (is_valid, error_message)
        """
        # 检查速度模式范围
        if not (0 <= status.speed_mode <= 3):
            return False, "速度模式必须在0-3范围内"
        
        # 检查电流范围（-128A到127A）
        if not (-128 <= status.current_a <= 127):
            return False, "运行电流必须在-128A到127A范围内"
        
        # 检查速度范围（0-6553.5 km/h）
        if not (0 <= status.speed_kmh <= 6553.5):
            return False, "速度必须在0-6553.5 km/h范围内"
        
        # 检查SOC范围
        if not status.soc_fault and not (0 <= status.soc_percent <= 100):
            return False, "SOC百分比必须在0-100范围内"
        
        # 检查系统电压（仅允许一个电压位为1）
        voltage_bits = [
            status.voltage_36v, status.voltage_48v, status.voltage_60v,
            status.voltage_64v, status.voltage_72v, status.voltage_80v,
            status.voltage_84v, status.voltage_96v
        ]
        if sum(voltage_bits) != 1:
            return False, "系统电压仅允许勾选1个电压位，符合协议1-52要求"
        
        return True, ""
    
    def xinsiwei_pluscode_encrypt(self, data_bytes: List[int]) -> int:
        """
        常州新思维协议8步PlusCode加密算法
        
        Args:
            data_bytes: 12字节数据 [DATA0-DATA11]
            
        Returns:
            加密后的PlusCode值 (0-255)
        """
        if len(data_bytes) != 12:
            raise ValueError("数据长度必须为12字节")
        
        # 初始化PlusCode为0
        plus_code = 0
        
        # 第1步：DATA0 XOR DATA6
        step1 = data_bytes[0] ^ data_bytes[6]
        plus_code ^= step1
        
        # 第2步：DATA1 XOR DATA7  
        step2 = data_bytes[1] ^ data_bytes[7]
        plus_code ^= step2
        
        # 第3步：DATA2 XOR DATA8
        step3 = data_bytes[2] ^ data_bytes[8]
        plus_code ^= step3
        
        # 第4步：DATA3 XOR DATA9
        step4 = data_bytes[3] ^ data_bytes[9]
        plus_code ^= step4
        
        # 第5步：DATA4 XOR DATA10
        step5 = data_bytes[4] ^ data_bytes[10]
        plus_code ^= step5
        
        # 第6步：DATA5 XOR DATA11
        step6 = data_bytes[5] ^ data_bytes[11]
        plus_code ^= step6
        
        # 第7步：前6步结果的累加和取低8位
        step7 = (step1 + step2 + step3 + step4 + step5 + step6) & 0xFF
        plus_code ^= step7
        
        # 第8步：所有DATA字节的累加和取低8位
        step8 = sum(data_bytes) & 0xFF
        plus_code ^= step8
        
        return plus_code & 0xFF
    

    
    def encode_status_bits(self, status: StatusBits) -> List[int]:
        """
        将Status位参数编码为协议数据字节
        
        Returns:
            [status1, status2, status3, status4, status5, status6, status7, status8, status9]
        """
        # Status1 (低4位)
        status1 = 0
        if status.distance_mode:
            status1 |= 0x08  # D3
        if status.speed_alarm:
            status1 |= 0x04  # D2
        if status.p_gear_protect:
            status1 |= 0x02  # D1
        if status.tcs_status:
            status1 |= 0x01  # D0
        
        # Status2
        status2 = 0
        if status.hall_fault:
            status2 |= 0x40  # D6
        if status.throttle_fault:
            status2 |= 0x20  # D5
        if status.controller_fault:
            status2 |= 0x10  # D4
        if status.under_voltage:
            status2 |= 0x08  # D3
        if status.cruise:
            status2 |= 0x04  # D2
        if status.assist:
            status2 |= 0x02  # D1
        if status.motor_phase_loss:
            status2 |= 0x01  # D0
        
        # Status3
        status3 = 0
        if status.gear_four:
            status3 |= 0x80  # D7
        if status.motor_running:
            status3 |= 0x40  # D6
        if status.brake:
            status3 |= 0x20  # D5
        if status.controller_protect:
            status3 |= 0x10  # D4
        if status.regen_charging:
            status3 |= 0x08  # D3
        if status.anti_runaway:
            status3 |= 0x04  # D2
        status3 |= (status.speed_mode & 0x03)  # D1~D0
        
        # Status4
        status4 = 0
        if status.current_70_flag:
            status4 |= 0x80  # D7
        if status.one_key_enable:
            status4 |= 0x40  # D6
        if status.ekk_enable:
            status4 |= 0x20  # D5
        if status.backup_power:
            status4 |= 0x10  # D4
        if status.over_current:
            status4 |= 0x08  # D3
        if status.stall_protect:
            status4 |= 0x04  # D2
        if status.reverse:
            status4 |= 0x02  # D1
        if status.speed_limit:
            status4 |= 0x01  # D0
        
        # Status5 - 运行电流（有符号字节）
        if status.current_a < 0:
            status5 = (256 + status.current_a) & 0xFF  # 负数补码表示
        else:
            status5 = status.current_a & 0xFF
        
        # Status6~7 - 速度（双字节，单位0.1km/h）
        speed_raw = int(status.speed_kmh * 10)
        status6 = (speed_raw >> 8) & 0xFF  # 高字节
        status7 = speed_raw & 0xFF         # 低字节
        
        # Status8 - 电池SOC
        if status.soc_fault:
            status8 = 0xEE  # 故障标志
        else:
            status8 = status.soc_percent & 0xFF
        
        # Status9 - 系统电压
        status9 = 0
        if status.voltage_36v:
            status9 |= 0x01  # BIT0
        if status.voltage_48v:
            status9 |= 0x02  # BIT1
        if status.voltage_60v:
            status9 |= 0x04  # BIT2
        if status.voltage_64v:
            status9 |= 0x08  # BIT3
        if status.voltage_72v:
            status9 |= 0x10  # BIT4
        if status.voltage_80v:
            status9 |= 0x20  # BIT5
        if status.voltage_84v:
            status9 |= 0x40  # BIT6
        if status.voltage_96v:
            status9 |= 0x80  # BIT7
        
        return [status1, status2, status3, status4, status5, status6, status7, status8, status9]
    
    def encode_xinsiwei_status_bits(self, status: StatusBits) -> List[int]:
        """
        将Status位参数编码为常州新思维协议数据字节
        
        Returns:
            [status1, status2, status3, status4, status5, status6, status7, status8, status9]
        """
        # Status1 (低4位) - 使用常州新思维协议的专用字段
        status1 = 0
        if status.xinsiwei_reserved_d3:
            status1 |= 0x08  # D3: 备用
        if status.xinsiwei_reserved_d2:
            status1 |= 0x04  # D2: 备用
        if status.xinsiwei_reserved_d1:
            status1 |= 0x02  # D1: 备用
        if status.xinsiwei_reserved_d0:
            status1 |= 0x01  # D0: 备用
        
        # Status2-4 使用通用字段（与标准协议相同）
        status2 = 0
        if status.hall_fault:
            status2 |= 0x40  # D6
        if status.throttle_fault:
            status2 |= 0x20  # D5
        if status.controller_fault:
            status2 |= 0x10  # D4
        if status.under_voltage:
            status2 |= 0x08  # D3
        if status.cruise:
            status2 |= 0x04  # D2
        if status.assist:
            status2 |= 0x02  # D1
        if status.motor_phase_loss:
            status2 |= 0x01  # D0
        
        status3 = 0
        if status.gear_four:
            status3 |= 0x80  # D7
        if status.motor_running:
            status3 |= 0x40  # D6
        if status.brake:
            status3 |= 0x20  # D5
        if status.controller_protect:
            status3 |= 0x10  # D4
        if status.regen_charging:
            status3 |= 0x08  # D3
        if status.anti_runaway:
            status3 |= 0x04  # D2
        status3 |= (status.speed_mode & 0x03)  # D1~D0
        
        status4 = 0
        if status.current_70_flag:
            status4 |= 0x80  # D7
        if status.one_key_enable:
            status4 |= 0x40  # D6
        if status.ekk_enable:
            status4 |= 0x20  # D5
        if status.backup_power:
            status4 |= 0x10  # D4
        if status.over_current:
            status4 |= 0x08  # D3
        if status.stall_protect:
            status4 |= 0x04  # D2
        if status.reverse:
            status4 |= 0x02  # D1
        if status.speed_limit:
            status4 |= 0x01  # D0
        
        # Status5 - 运行电流（与标准协议相同）
        if status.current_a < 0:
            status5 = (256 + status.current_a) & 0xFF
        else:
            status5 = status.current_a & 0xFF
        
        # Status6~7 - 霍尔计数（常州新思维协议特有）
        hall_count = status.xinsiwei_hall_count & 0xFFFF
        status6 = (hall_count >> 8) & 0xFF  # 高字节
        status7 = hall_count & 0xFF         # 低字节
        
        # Status8 - 电池SOC（与标准协议相同）
        if status.soc_fault:
            status8 = 0xEE
        else:
            status8 = status.soc_percent & 0xFF
        
        # Status9 - 系统电压（与标准协议相同）
        status9 = 0
        if status.voltage_36v:
            status9 |= 0x01
        if status.voltage_48v:
            status9 |= 0x02
        if status.voltage_60v:
            status9 |= 0x04
        if status.voltage_64v:
            status9 |= 0x08
        if status.voltage_72v:
            status9 |= 0x10
        if status.voltage_80v:
            status9 |= 0x20
        if status.voltage_84v:
            status9 |= 0x40
        if status.voltage_96v:
            status9 |= 0x80
        
        return [status1, status2, status3, status4, status5, status6, status7, status8, status9]
    

    
    def generate_xinsiwei_frame_for_preview(self, status: StatusBits) -> Tuple[bool, List[int], str]:
        """
        生成常州新思维协议的预览帧数据（不递增序号）
        
        此方法用于UI预览显示，使用当前序号值而不递增
        
        Returns:
            (success, frame_data, error_message)
        """
        # 创建状态副本，避免修改原始状态
        preview_status = StatusBits()
        
        # 复制所有状态字段
        for field_name in status.__dataclass_fields__:
            setattr(preview_status, field_name, getattr(status, field_name))
        
        # 使用当前序号（不递增）
        preview_status.xinsiwei_sequence = self.get_current_xinsiwei_sequence()
        
        # 确保使用常州新思维协议标识
        preview_status.xinsiwei_protocol = True
        
        # 调用原有的帧生成方法
        return self.generate_xinsiwei_frame(preview_status)
    
    def generate_frame(self, status: StatusBits) -> Tuple[bool, List[int], str]:
        """
        生成完整的协议帧数据（支持多协议路由）
        
        根据状态中的协议标识自动选择相应的帧生成方法：
        - 常州新思维协议：使用自动序号递增功能
        - 其他协议：使用原有的一线通协议
        
        Returns:
            (success, frame_data, error_message)
        """
        # 检查是否为常州新思维协议
        if hasattr(status, 'xinsiwei_protocol') and status.xinsiwei_protocol:
            # 使用常州新思维协议的自动序号功能
            return self.generate_xinsiwei_frame_with_auto_sequence(status)
        
        # 默认使用原有的一线通协议
        return self._generate_original_frame(status)
    
    def generate_frame_for_preview(self, status: StatusBits) -> Tuple[bool, List[int], str]:
        """
        生成完整的协议帧数据用于预览（不递增序号）
        
        根据状态中的协议标识自动选择相应的帧生成方法：
        - 常州新思维协议：使用预览专用方法（不递增序号）
        - 其他协议：使用原有的一线通协议（原本就不递增序号）
        
        Returns:
            (success, frame_data, error_message)
        """
        # 检查是否为常州新思维协议
        if hasattr(status, 'xinsiwei_protocol') and status.xinsiwei_protocol:
            # 使用常州新思维协议的预览方法（不递增序号）
            return self.generate_xinsiwei_frame_for_preview(status)
        
        # 默认使用原有的一线通协议（原本就不递增序号）
        return self._generate_original_frame(status)
    
    def _generate_original_frame(self, status: StatusBits) -> Tuple[bool, List[int], str]:
        """
        生成原有一线通协议的完整帧数据
        
        此方法保持原有协议的所有功能不变，确保兼容性
        
        Returns:
            (success, frame_data, error_message)
        """
        # 验证参数
        is_valid, error_msg = self.validate_status_bits(status)
        if not is_valid:
            return False, [], error_msg
        
        # 编码Status位
        status_bytes = self.encode_status_bits(status)
        
        # 构建帧数据
        frame = [0] * 12
        
        # DATA0 - 设备编码（固定）
        frame[0] = self.config.DEVICE_CODE
        
        # DATA1 - 流水号低8位（固定）
        frame[1] = self.config.SEQ_CODE_L
        
        # DATA2 - 流水号高4位 + Status1
        frame[2] = ((self.config.SEQ_CODE_H & 0x0F) << 4) + (status_bytes[0] & 0x0F)
        
        # DATA3~5 - Status2~4 + PlusCode
        frame[3] = (status_bytes[1] + self.config.PLUS_CODE) & 0xFF
        frame[4] = (status_bytes[2] + self.config.PLUS_CODE) & 0xFF
        frame[5] = (status_bytes[3] + self.config.PLUS_CODE) & 0xFF
        
        # DATA6 - Status5（不加密）
        frame[6] = status_bytes[4]
        
        # DATA7~10 - Status6~9 + PlusCode
        frame[7] = (status_bytes[5] + self.config.PLUS_CODE) & 0xFF
        frame[8] = (status_bytes[6] + self.config.PLUS_CODE) & 0xFF
        frame[9] = (status_bytes[7] + self.config.PLUS_CODE) & 0xFF
        frame[10] = (status_bytes[8] + self.config.PLUS_CODE) & 0xFF
        
        # DATA11 - 校验和（DATA0~DATA10的8位异或）
        checksum = 0
        for i in range(11):
            checksum ^= frame[i]
        frame[11] = checksum
        
        return True, frame, ""
    
    def generate_xinsiwei_frame_with_auto_sequence(self, status: StatusBits) -> Tuple[bool, List[int], str]:
        """
        生成常州新思维协议的完整帧数据（自动递增序号）
        
        此方法会自动使用内部序号计数器，每次调用时序号自动+1
        确保data0字段固定为0x30，保持原有协议格式不变
        
        Returns:
            (success, frame_data, error_message)
        """
        # 创建状态副本，避免修改原始状态
        auto_status = StatusBits()
        
        # 复制所有状态字段（保持原有设备编号处理逻辑）
        for field_name in status.__dataclass_fields__:
            setattr(auto_status, field_name, getattr(status, field_name))
        
        # 自动设置序号（使用内部计数器）
        auto_status.xinsiwei_sequence = self.get_next_xinsiwei_sequence()
        
        # 确保使用常州新思维协议标识
        auto_status.xinsiwei_protocol = True
        
        # 调用原有的帧生成方法（确保data0固定为0x30）
        return self.generate_xinsiwei_frame(auto_status)

    def generate_xinsiwei_frame(self, status: StatusBits) -> Tuple[bool, List[int], str]:
        """
        生成常州新思维协议的完整帧数据
        
        Returns:
            (success, frame_data, error_message)
        """
        # 验证参数
        is_valid, error_msg = self.validate_status_bits(status)
        if not is_valid:
            return False, [], error_msg
        
        # 验证常州新思维协议特有参数
        if not (0 <= status.xinsiwei_sequence <= 4095):
            return False, [], "常州新思维协议流水号必须在0-4095范围内"
        
        if not (0 <= status.xinsiwei_hall_count <= 65535):
            return False, [], "霍尔计数值必须在0-65535范围内"
        
        # 编码Status位（使用常州新思维协议专用编码）
        status_bytes = self.encode_xinsiwei_status_bits(status)
        
        # 构建帧数据
        frame = [0] * 12
        
        # DATA0 - 设备编码（常州新思维协议固定为0x30）
        frame[0] = 0x30
        
        # DATA1 - 流水号低8位
        frame[1] = status.xinsiwei_sequence & 0xFF
        
        # DATA2 - 流水号高4位 + Status1
        seq_high = (status.xinsiwei_sequence >> 8) & 0x0F
        frame[2] = (seq_high << 4) + (status_bytes[0] & 0x0F)
        
        # DATA3~10 - Status2~9（不加密，先构建原始数据）
        frame[3] = status_bytes[1]  # Status2
        frame[4] = status_bytes[2]  # Status3
        frame[5] = status_bytes[3]  # Status4
        frame[6] = status_bytes[4]  # Status5
        frame[7] = status_bytes[5]  # Status6
        frame[8] = status_bytes[6]  # Status7
        frame[9] = status_bytes[7]  # Status8
        frame[10] = status_bytes[8] # Status9
        
        # DATA11 - 校验和（DATA0~DATA10的8位异或）
        checksum = 0
        for i in range(11):
            checksum ^= frame[i]
        frame[11] = checksum
        
        # 应用8步PlusCode加密算法
        plus_code = self.xinsiwei_pluscode_encrypt(frame)
        
        # 将加密码应用到需要加密的字段（DATA3~5, DATA7~10）
        frame[3] = (frame[3] + plus_code) & 0xFF
        frame[4] = (frame[4] + plus_code) & 0xFF
        frame[5] = (frame[5] + plus_code) & 0xFF
        frame[7] = (frame[7] + plus_code) & 0xFF
        frame[8] = (frame[8] + plus_code) & 0xFF
        frame[9] = (frame[9] + plus_code) & 0xFF
        frame[10] = (frame[10] + plus_code) & 0xFF
        
        # 重新计算校验和（加密后）
        checksum = 0
        for i in range(11):
            checksum ^= frame[i]
        frame[11] = checksum
        
        return True, frame, ""
    

    
    def format_frame_display(self, frame: List[int]) -> str:
        """
        格式化帧数据用于显示
        
        Returns:
            格式化的十六进制字符串，包含字节含义说明
        """
        if len(frame) != 12:
            return "无效帧数据"
        
        display_lines = []
        display_lines.append("协议帧数据 (十六进制):")
        
        # 格式化每个字节
        hex_str = " ".join([f"{b:02X}" for b in frame])
        display_lines.append(hex_str)
        display_lines.append("")
        
        # 添加字节含义说明
        display_lines.append("字节含义:")
        display_lines.append(f"DATA0  = 0x{frame[0]:02X} (设备编码)")
        display_lines.append(f"DATA1  = 0x{frame[1]:02X} (流水号低8位)")
        display_lines.append(f"DATA2  = 0x{frame[2]:02X} (流水号高4位 + Status1)")
        display_lines.append(f"DATA3  = 0x{frame[3]:02X} (Status2 + 加密码)")
        display_lines.append(f"DATA4  = 0x{frame[4]:02X} (Status3 + 加密码)")
        display_lines.append(f"DATA5  = 0x{frame[5]:02X} (Status4 + 加密码)")
        display_lines.append(f"DATA6  = 0x{frame[6]:02X} (Status5 运行电流)")
        display_lines.append(f"DATA7  = 0x{frame[7]:02X} (Status6 速度高字节 + 加密码)")
        display_lines.append(f"DATA8  = 0x{frame[8]:02X} (Status7 速度低字节 + 加密码)")
        display_lines.append(f"DATA9  = 0x{frame[9]:02X} (Status8 电池SOC + 加密码)")
        display_lines.append(f"DATA10 = 0x{frame[10]:02X} (Status9 系统电压 + 加密码)")
        display_lines.append(f"DATA11 = 0x{frame[11]:02X} (校验和)")
        
        return "\n".join(display_lines)

# 预设测试场景
class PresetScenarios:
    """预设测试场景"""
    
    @staticmethod
    def normal_running() -> StatusBits:
        """正常运行场景"""
        status = StatusBits()
        status.voltage_48v = True           # 48V电压
        status.voltage_36v = False
        status.speed_kmh = 35.0             # 35.0km/h速度
        status.soc_percent = 80             # 80%电量
        status.motor_running = True         # 电机运行
        status.tcs_status = False           # TCS灭
        return status
    
    @staticmethod
    def changzhou_xinsiwei_normal_running() -> StatusBits:
        """常州新思维协议正常运行场景"""
        status = StatusBits()
        # 标识为常州新思维协议
        status.xinsiwei_protocol = True
        status.xinsiwei_sequence = 1234     # 12位流水号示例
        
        # 基本状态
        status.voltage_48v = True           # 48V电压
        status.voltage_36v = False
        status.xinsiwei_hall_count = 8500   # 霍尔计数值（对应约35km/h）
        status.soc_percent = 80             # 80%电量
        status.motor_running = True         # 电机运行
        status.current_a = 15               # 15A电流
        
        # 常州新思维协议专用字段
        status.xinsiwei_reserved_d0 = False # 备用位
        status.xinsiwei_reserved_d1 = False
        status.xinsiwei_reserved_d2 = False
        status.xinsiwei_reserved_d3 = False
        
        return status
    
    @staticmethod
    def changzhou_xinsiwei_energy_recovery() -> StatusBits:
        """常州新思维协议能量回收场景"""
        status = StatusBits()
        # 标识为常州新思维协议
        status.xinsiwei_protocol = True
        status.xinsiwei_sequence = 2468     # 12位流水号示例
        
        # 基本状态
        status.voltage_60v = True           # 60V电压
        status.voltage_48v = False
        status.xinsiwei_hall_count = 6800   # 霍尔计数值（对应约28km/h）
        status.soc_percent = 60             # 60%电量
        status.regen_charging = True        # 滑行充电
        status.current_a = -3               # -3A电流（回充）
        
        # 常州新思维协议专用字段
        status.xinsiwei_reserved_d0 = True  # 示例：某个备用位激活
        status.xinsiwei_reserved_d1 = False
        status.xinsiwei_reserved_d2 = False
        status.xinsiwei_reserved_d3 = False
        
        return status
    
    @staticmethod
    def changzhou_xinsiwei_fault_scenario() -> StatusBits:
        """常州新思维协议故障场景"""
        status = StatusBits()
        # 标识为常州新思维协议
        status.xinsiwei_protocol = True
        status.xinsiwei_sequence = 3691     # 12位流水号示例
        
        # 基本状态
        status.voltage_72v = True           # 72V电压
        status.voltage_48v = False
        status.xinsiwei_hall_count = 0      # 霍尔计数值为0（停止）
        status.soc_fault = True             # SOC故障
        status.throttle_fault = True        # 转把故障
        status.controller_fault = True      # 控制器故障
        status.under_voltage = True         # 欠压保护
        status.current_a = 0                # 0A电流
        
        # 常州新思维协议专用字段
        status.xinsiwei_reserved_d0 = True  # 故障指示
        status.xinsiwei_reserved_d1 = True
        status.xinsiwei_reserved_d2 = False
        status.xinsiwei_reserved_d3 = True
        
        return status
    
    @staticmethod
    def energy_recovery() -> StatusBits:
        """能量回收场景"""
        status = StatusBits()
        status.voltage_60v = True           # 60V电压
        status.voltage_48v = False
        status.speed_kmh = 28.5             # 28.5km/h速度
        status.soc_percent = 60             # 60%电量
        status.regen_charging = True        # 滑行充电
        status.tcs_status = True            # TCS亮
        status.current_a = -1               # -1A电流
        return status
    
    @staticmethod
    def fault_scenario() -> StatusBits:
        """故障场景"""
        status = StatusBits()
        status.voltage_72v = True           # 72V电压
        status.voltage_48v = False
        status.speed_kmh = 0.0              # 0km/h速度
        status.soc_fault = True             # SOC故障
        status.throttle_fault = True        # 转把故障
        status.p_gear_protect = True        # P档显示
        status.speed_limit = True           # 限速状态
        return status
    
    @staticmethod
    def xinri_normal_running() -> StatusBits:
        """新日协议正常运行场景"""
        status = StatusBits()
        status.voltage_48v = True           # 48V电压
        status.voltage_36v = False
        status.speed_kmh = 35.0             # 35.0km/h速度
        status.soc_percent = 80             # 80%电量
        status.motor_running = True         # 电机运行
        status.tcs_status = False           # TCS灭
        return status
    
    @staticmethod
    def xinri_energy_recovery() -> StatusBits:
        """新日协议能量回收场景"""
        status = StatusBits()
        status.voltage_48v = True           # 48V电压
        status.voltage_36v = False
        status.speed_kmh = 0.0              # 停车状态
        status.soc_percent = 85             # 85%电量（回收中）
        status.motor_running = False        # 电机停止
        status.regen_charging = True        # 能量回收
        status.brake = True                 # 刹车状态
        return status
    
    @staticmethod
    def xinri_fault_scenario() -> StatusBits:
        """新日协议故障场景"""
        status = StatusBits()
        status.voltage_48v = True           # 48V电压
        status.voltage_36v = False
        status.speed_kmh = 0.0              # 停车状态
        status.soc_percent = 15             # 15%低电量
        status.motor_running = False        # 电机停止
        status.hall_fault = True            # 霍尔故障
        status.controller_fault = True      # 控制器故障
        status.throttle_fault = True        # 转把故障
        status.under_voltage = True         # 欠压保护
        status.brake = True                 # 刹车状态
        status.p_gear_protect = True        # P档保护
        return status
    
    @staticmethod
    def hangzhou_anxian_normal_running() -> StatusBits:
        """杭州安显协议正常运行场景"""
        status = StatusBits()
        status.voltage_48v = True           # 48V电压
        status.voltage_36v = False
        status.speed_kmh = 30.0             # 30.0km/h速度
        status.soc_percent = 75             # 75%电量
        status.motor_running = True         # 电机运行
        status.tcs_status = False           # TCS灭
        status.assist = True                # 助力模式
        status.speed_mode = 2               # 二档模式
        return status
    
    @staticmethod
    def hangzhou_anxian_energy_recovery() -> StatusBits:
        """杭州安显协议能量回收场景"""
        status = StatusBits()
        status.voltage_60v = True           # 60V电压
        status.voltage_48v = False
        status.speed_kmh = 25.0             # 25.0km/h速度
        status.soc_percent = 90             # 90%电量（回收中）
        status.motor_running = True         # 电机运行
        status.regen_charging = True        # 能量回收
        status.current_a = -2               # -2A回收电流
        status.speed_mode = 1               # 一档模式
        return status
    
    @staticmethod
    def hangzhou_anxian_fault_scenario() -> StatusBits:
        """杭州安显协议故障场景"""
        status = StatusBits()
        status.voltage_48v = True           # 48V电压
        status.voltage_36v = False
        status.speed_kmh = 0.0              # 停车状态
        status.soc_percent = 20             # 20%低电量
        status.motor_running = False        # 电机停止
        status.controller_fault = True      # 控制器故障
        status.over_current = True          # 过流保护
        status.under_voltage = True         # 欠压保护
        status.speed_limit = True           # 限速状态
        status.p_gear_protect = True        # P档保护
        status.brake = True                 # 刹车状态
        return status