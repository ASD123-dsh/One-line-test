# AD 仪表一线通协议测试工具

一个基于 Python、PyQt5 和 pyserial 的 PC 端协议测试工具，用于生成多种电动车仪表/BMS 协议帧，通过串口发送，并提供状态配置、场景预设、帧预览和发送记录。

## 主要功能

- **17 种协议**：协议元数据集中注册，可在界面中切换。
- **状态与运行数据配置**：支持状态位、电流、霍尔计数、SOC、电压档位及协议专用字段。
- **场景预设**：提供正常运行、能量回收和故障场景；具体字段以对应协议规格书为准。
- **发送方式**：支持单帧、循环发送和自定义包组循环。
- **发送监控**：显示十六进制帧、发送时间和发送结果。
- **帧输入校验**：统一校验帧长度、字节类型及 `0-255` 范围，避免非法自定义帧进入发送流程。

## 支持协议

当前注册表包含以下 17 种协议：

1. 瑞轮协议
2. FZ-sif 协议
3. 新日协议
4. 杭州安显协议
5. 常州新思维协议
6. 无锡一格 Y67 协议
7. 无锡台铃 Y34B 协议
8. 无锡台铃 Y34F 协议
9. 神州行协议
10. 雅迪协议
11. 优仪宝一线通协议
12. 精显一线通协议
13. 东威 GTXH 协议
14. 芯驰 BMS 协议
15. 绿源 BMS 一线通协议
16. 一线通--锂电池 BMS
17. 电池单线通讯协议

协议名称、帧长度、校验方式、发送方式、发送周期约束及帧生成入口统一维护在
`protocol/definitions.py`。新增协议时请按
[新增协议开发指南](docs/adding_protocol.md) 完成规格书核对、注册、实现和测试，不要继续在界面层堆叠协议分支。

## 安装

### 环境要求

- Windows 10/11
- Python 3.8 或更高版本
- 与目标设备电气特性匹配的串口转换/转码硬件

### 安装步骤

```powershell
git clone https://github.com/ASD123-dsh/One-line-test.git
cd One-line-test
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

运行时依赖包括：

- `PyQt5`：桌面界面
- `pyserial`：串口通信
- `rsa`：授权码相关功能

## 使用

```powershell
python main.py
```

基本流程：

1. 按目标规格书和硬件说明连接串口转换/转码设备，并确认电平、共地和信号方向。
2. 在界面中选择串口和波特率，然后连接。
3. 选择与目标仪表/BMS 一致的协议。
4. 选择场景或手动设置状态字段，核对当前帧预览。
5. 使用单帧、循环发送或包组循环发送。

> 当前协议注册表为兼容既有行为，17 种协议的主机侧 `send_mode` 均为
> `uart`。程序在这一契约下生成字节帧并写入串口；规格书中的单线脉宽、
> 位序、电压、电平和引脚要求，不能仅凭 Python 单元测试证明。不要在未确认
> 转码板、固件和实际接线的情况下，将普通 USB-TTL 串口直接视为目标单线总线。
> `Tosc` 也不会改变普通 UART 帧本身。

## 架构

```text
One-line-test/
├── main.py                         # 程序入口与全局异常记录
├── app_paths.py                    # 开发环境/打包环境资源路径
├── gui/
│   ├── main_window.py              # 主窗口和协议参数界面
│   ├── protocol_ui_registry.py     # 协议对应的切换、预设和状态读取入口
│   ├── frame_config_dialog.py      # 单帧配置
│   └── packet_sequence_dialog.py   # 包组配置及导入导出
├── protocol/
│   ├── definitions.py              # 不可变协议元数据注册表
│   ├── models.py                   # ProtocolConfig、StatusBits 数据模型
│   ├── frame_utils.py              # 帧长度和字节范围公共校验
│   └── protocol_handler.py         # 参数校验、帧编码、校验和、场景预设
├── serial_comm/
│   └── serial_manager.py           # 串口连接、单帧与循环发送
├── licensing/                      # 本地授权校验
├── tools/                          # 授权辅助工具
├── tests/                          # 单元测试和无界面 GUI 测试
├── docs/
│   └── adding_protocol.md          # 新增协议开发指南
├── PDF/                            # 本地协议规格书，默认不纳入 Git
└── 接码转码平台驱动源码/            # 转码平台相关 C 源码
```

核心职责如下：

- `definitions.py` 只描述协议元数据和分发入口，不实现字节编码。
- `models.py` 保存协议层与界面层共享的数据，不依赖 Qt 控件。
- `protocol_handler.py` 校验模型并生成帧；发送帧与预览帧统一通过注册表分发。
- `protocol_ui_registry.py` 维护协议到界面处理方法的映射，减少主窗口中的重复分支。
- `frame_utils.py` 为单帧配置、包组配置和串口发送提供同一套帧数据校验。
- `serial_manager.py` 负责传输，不解释协议字段。

## 规格书与验证

本地 `PDF/` 目录用于保存厂商协议规格书。该目录已在 `.gitignore` 中忽略，
因此从远程仓库克隆后不一定存在。实现或修改协议前，应先核对对应版本的规格书，
至少记录以下内容：

- 帧长度、固定字节和字段字节序
- 位定义、物理量单位、精度、符号和合法范围
- 校验算法及覆盖范围
- 序号/加密字段，以及预览是否允许消耗序号
- 发送周期、位序和波形要求

软件测试可验证帧编码、参数边界、校验和、注册表完整性及界面映射，但不能替代
转码固件编译、示波器波形检查和目标仪表/BMS 联调。

## 开发验证

在 PowerShell 中执行无界面单元测试：

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
python -m unittest discover -s tests -v
```

执行 Python 语法编译检查：

```powershell
python -m compileall -q main.py app_paths.py gui licensing protocol serial_comm tools tests
```

以上命令不等同于：

- 使用全志 Melis SDK/目标交叉编译器编译转码平台 C 驱动
- 在真实串口硬件上完成收发验证
- 在示波器/逻辑分析仪上验证单线时序
- 完成可执行文件打包

## 贡献

欢迎通过 Issue 或 Pull Request 修复问题、补充协议测试或增加新协议。涉及协议
字段的变更，请注明规格书名称和版本，并附边界用例或已脱敏的已知帧依据。

## 许可证

MIT License
