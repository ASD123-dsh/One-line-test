#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
串口通信管理模块

实现串口自动识别、连接管理、数据发送等功能
支持USB转TTL模块（如CH340）的自动识别
"""

import serial
import serial.tools.list_ports
import time
import threading
from datetime import datetime
from typing import List, Tuple, Optional, Callable
from PyQt5.QtCore import QObject, pyqtSignal, QTimer
from dataclasses import dataclass

@dataclass
class SerialPortInfo:
    """串口信息"""
    port: str           # 端口名（如COM3）
    description: str    # 描述信息
    hwid: str          # 硬件ID
    
    def __str__(self):
        return f"{self.port} ({self.description})"

class SerialManager(QObject):
    """串口管理器"""
    
    # 信号定义
    port_connected = pyqtSignal(str)        # 串口连接成功
    port_disconnected = pyqtSignal(str)     # 串口断开
    data_sent = pyqtSignal(list, str)       # 数据发送成功 (data, timestamp)
    send_error = pyqtSignal(str)            # 发送错误
    connection_error = pyqtSignal(str)      # 连接错误
    
    def __init__(self):
        super().__init__()
        self.serial_port: Optional[serial.Serial] = None
        self.is_connected = False
        self.send_timer = QTimer()
        self.send_timer.timeout.connect(self._send_cyclic_data)
        
        # 发送参数
        self.cyclic_data: Optional[List[int]] = None
        self.send_interval_ms = 1000
        self.tosc_us = 100
        
        # 性能优化相关
        self.send_count = 0  # 发送计数器
        self.ui_update_interval = 10  # 每10次发送更新一次UI
        self.last_frame_cache = None  # 缓存上次的帧数据格式化结果
        
    def scan_ports(self) -> List[SerialPortInfo]:
        """
        扫描可用串口
        
        Returns:
            可用串口列表
        """
        ports = []
        try:
            for port_info in serial.tools.list_ports.comports():
                port = SerialPortInfo(
                    port=port_info.device,
                    description=port_info.description,
                    hwid=port_info.hwid or ""
                )
                ports.append(port)
        except Exception as e:
            # 扫描串口失败，返回空列表
            pass
        
        return ports
    
    def connect_port(self, port_name: str, baud_rate: int = 9600) -> Tuple[bool, str]:
        """
        连接串口
        
        Args:
            port_name: 串口名称
            baud_rate: 波特率
            
        Returns:
            (success, error_message)
        """
        try:
            # 如果已连接，先断开
            if self.is_connected:
                self.disconnect_port()
            
            # 创建串口连接
            self.serial_port = serial.Serial(
                port=port_name,
                baudrate=baud_rate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=1.0,
                write_timeout=1.0
            )
            
            # 测试连接
            if self.serial_port.is_open:
                self.is_connected = True
                self.port_connected.emit(port_name)
                return True, ""
            else:
                return False, "串口打开失败"
                
        except serial.SerialException as e:
            error_msg = f"串口连接失败: {str(e)}"
            self.connection_error.emit(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"未知错误: {str(e)}"
            self.connection_error.emit(error_msg)
            return False, error_msg
    
    def disconnect_port(self) -> bool:
        """
        断开串口连接
        
        Returns:
            是否成功断开
        """
        try:
            # 停止循环发送
            self.stop_cyclic_send()
            
            if self.serial_port and self.serial_port.is_open:
                port_name = self.serial_port.port
                self.serial_port.close()
                self.is_connected = False
                self.port_disconnected.emit(port_name)
                return True
            
            self.is_connected = False
            return True
            
        except Exception as e:
            # 断开串口失败，返回False
            return False
    
    def send_single_frame(self, frame_data: List[int], skip_ui_update: bool = False) -> Tuple[bool, str]:
        """
        发送单帧数据
        
        Args:
            frame_data: 协议帧数据
            skip_ui_update: 是否跳过UI更新（用于高频发送优化）
            
        Returns:
            (success, error_message)
        """
        if not self.is_connected or not self.serial_port:
            return False, "串口未连接"
        
        expected_length = len(frame_data)
        if expected_length == 0:
            return False, "数据不能为空"
        
        try:
            # 转换为字节数组
            data_bytes = bytes(frame_data)
            
            # 发送数据
            bytes_written = self.serial_port.write(data_bytes)
            
            if bytes_written == expected_length:
                # 发送成功，使用异步方式处理空闲延迟
                idle_time_ms = (32 * self.tosc_us) / 1000.0
                
                # 使用QTimer异步处理空闲延迟，避免阻塞主线程
                if idle_time_ms > 0:
                    QTimer.singleShot(int(idle_time_ms), lambda: None)
                
                # 根据skip_ui_update参数决定是否发送UI更新信号
                if not skip_ui_update:
                    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                    self.data_sent.emit(frame_data, timestamp)
                
                return True, ""
            else:
                error_msg = (
                    f"数据发送不完整，期望{expected_length}字节，实际发送{bytes_written}字节"
                )
                if not skip_ui_update:
                    self.send_error.emit(error_msg)
                return False, error_msg
                
        except serial.SerialTimeoutException:
            error_msg = "串口发送超时"
            if not skip_ui_update:
                self.send_error.emit(error_msg)
            return False, error_msg
        except serial.SerialException as e:
            error_msg = f"串口发送失败: {str(e)}"
            if not skip_ui_update:
                self.send_error.emit(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"发送数据时发生未知错误: {str(e)}"
            if not skip_ui_update:
                self.send_error.emit(error_msg)
            return False, error_msg
    
    def start_cyclic_send(self, frame_data: List[int], interval_ms: int = 1000) -> Tuple[bool, str]:
        """
        开始循环发送数据
        
        Args:
            frame_data: 协议帧数据
            interval_ms: 发送间隔（毫秒）
            
        Returns:
            (success, error_message)
        """
        if not self.is_connected:
            return False, "串口未连接"
        
        if len(frame_data) == 0:
            return False, "数据不能为空"
        
        if not (500 <= interval_ms <= 5000):
            return False, "发送间隔必须在500ms-5000ms范围内"
        
        # 保存发送参数
        self.cyclic_data = frame_data.copy()
        self.send_interval_ms = interval_ms
        
        # 启动定时器
        self.send_timer.start(interval_ms)
        
        return True, ""
    
    def stop_cyclic_send(self):
        """停止循环发送"""
        self.send_timer.stop()
        self.cyclic_data = None
    
    def _send_cyclic_data(self):
        """定时器回调：发送循环数据"""
        if self.cyclic_data and self.is_connected:
            # 增加发送计数器
            self.send_count += 1
            
            # 根据发送频率决定是否更新UI
            # 对于高频发送（<200ms），每10次更新一次UI
            # 对于低频发送（>=200ms），每次都更新UI
            skip_ui = False
            if self.send_interval_ms < 200:
                skip_ui = (self.send_count % self.ui_update_interval) != 0
            
            # 发送数据
            success, error_msg = self.send_single_frame(self.cyclic_data, skip_ui_update=skip_ui)
            
            # 如果跳过了UI更新但需要显示错误，仍然发送错误信号
            if skip_ui and not success:
                self.send_error.emit(error_msg)
            
            # 每100次发送重置计数器，避免溢出
            if self.send_count >= 100:
                self.send_count = 0
            
            if not success:
                # 发送失败，停止循环发送
                self.stop_cyclic_send()
    
    def is_cyclic_sending(self) -> bool:
        """检查是否正在循环发送"""
        return self.send_timer.isActive()
    
    def set_tosc_value(self, tosc_us: int) -> bool:
        """
        设置Tosc值
        
        Args:
            tosc_us: Tosc值（微秒，32-320范围）
            
        Returns:
            是否设置成功
        """
        if 32 <= tosc_us <= 320:
            self.tosc_us = tosc_us
            return True
        return False
    
    def get_port_status(self) -> dict:
        """
        获取串口状态信息
        
        Returns:
            状态信息字典
        """
        status = {
            "connected": self.is_connected,
            "port_name": self.serial_port.port if self.serial_port else None,
            "baud_rate": self.serial_port.baudrate if self.serial_port else None,
            "cyclic_sending": self.is_cyclic_sending(),
            "send_interval_ms": self.send_interval_ms,
            "tosc_us": self.tosc_us
        }
        return status

class SerialPortDetector(QObject):
    """串口检测器 - 自动检测串口插拔"""
    
    ports_changed = pyqtSignal(list)  # 串口列表变化信号
    
    def __init__(self):
        super().__init__()
        self.last_ports = []
        self.detection_timer = QTimer()
        self.detection_timer.timeout.connect(self._check_ports)
        
    def start_detection(self, interval_ms: int = 2000):
        """开始串口检测"""
        self._check_ports()  # 立即检测一次
        self.detection_timer.start(interval_ms)
    
    def stop_detection(self):
        """停止串口检测"""
        self.detection_timer.stop()
    
    def _check_ports(self):
        """检查串口变化"""
        try:
            current_ports = []
            for port_info in serial.tools.list_ports.comports():
                port = SerialPortInfo(
                    port=port_info.device,
                    description=port_info.description,
                    hwid=port_info.hwid or ""
                )
                current_ports.append(port)
            
            # 检查是否有变化
            if len(current_ports) != len(self.last_ports) or \
               any(p1.port != p2.port for p1, p2 in zip(current_ports, self.last_ports)):
                self.last_ports = current_ports
                self.ports_changed.emit(current_ports)
                
        except Exception as e:
            # 检测串口变化失败，忽略此次检测
            pass
