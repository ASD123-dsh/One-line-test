# 新增协议开发指南

本文说明如何在不改变既有公开入口的前提下，为项目增加一种仪表或 BMS 协议。
核心原则是：规格书先行、模型与传输解耦、注册表集中分发、预览无副作用、软件
验证与硬件验证分开记录。

## 1. 先整理规格书证据

开始编码前，从 `PDF/` 中确认规格书名称、版本和适用车型/设备，并整理一张协议
字段表。至少应包含：

| 项目 | 必须确认的内容 |
| --- | --- |
| 帧结构 | 总长度、帧头、固定字节、数据区、校验字节位置 |
| 位定义 | 每个状态位的字节位置、bit 位和有效电平 |
| 数值字段 | 单位、比例、字节序、有/无符号、偏移量、上下限 |
| 校验 | XOR、累加和或其他算法，以及参与计算的字节范围 |
| 序号/加密 | 初值、回绕范围、发送时递增规则、预览行为 |
| 传输约束 | 波特率、发送周期、位序、同步、脉宽和电气要求 |

不要只根据协议名称、相似厂商协议或一条样例帧推导缺失字段。规格书存在冲突时，
先保留证据并确认采用的版本；不要用静默截断或取模掩盖超范围输入。

`PDF/` 是本地参考目录，默认被 Git 忽略。测试注释或提交说明可记录规格书文件名、
版本及页码，但不要依赖其他开发者必然拥有该目录。

## 2. 注册协议元数据

在 `protocol/definitions.py` 中：

1. 新增唯一的协议名称常量。
2. 在 `PROTOCOL_DEFINITIONS` 中新增 `ProtocolDefinition`。
3. 明确 `frame_length`、`checksum_mode`、`send_mode` 和
   `generator_method`。
4. 按规格书填写 `min_send_interval_ms`、`max_send_interval_ms` 和
   `default_send_interval_ms`；需要每次切换都恢复默认周期时，再启用
   `reset_send_interval_on_switch`。
5. 只有发送与预览行为确实不同（例如发送会消耗序号）时，才设置
   `preview_generator_method`。
6. 只有规格书明确使用特殊 SOC 故障编码时，才设置 `soc_fault_value`。

示意：

```python
PROTOCOL_VENDOR_MODEL = "厂商型号协议"

PROTOCOL_DEFINITIONS = MappingProxyType({
    # ...既有协议...
    PROTOCOL_VENDOR_MODEL: ProtocolDefinition(
        name=PROTOCOL_VENDOR_MODEL,
        frame_length=12,
        checksum_mode="xor",
        send_mode="uart",
        generator_method="_generate_vendor_model_frame",
        preview_generator_method="_generate_vendor_model_frame_for_preview",
        min_send_interval_ms=500,
        max_send_interval_ms=5000,
        default_send_interval_ms=500,
    ),
})
```

上面的长度、校验和发送方式只是结构示意，不能直接复制为新协议参数。
`PROTOCOL_DEFINITIONS` 是不可变映射，`SUPPORTED_PROTOCOLS` 由其键顺序生成；
不要在运行期修改注册表，也不要另建一份协议名称清单。

当前注册表中的协议为兼容原功能都使用 `send_mode="uart"`。即使规格书描述了
单线脉宽，也不能在未核对转码硬件、固件接口和串口控制能力时擅自切换发送方式。

## 3. 扩展共享状态模型

在 `protocol/models.py` 的 `StatusBits` 中增加协议真正需要的输入字段：

- 多协议含义一致的字段优先复用通用字段。
- 仅一个协议使用的字段添加协议前缀，例如
  `vendor_model_temperature_c`。
- 默认值应能生成安全、合法、可解释的正常帧。
- 协议模型不能保存 `QCheckBox`、`QSpinBox` 等 Qt 控件。
- 不要删除或重命名已有字段，以免破坏现有调用者。

若一个概念在不同协议中的单位、符号或范围不同，应使用明确的协议专用字段，或在
编码方法中进行显式转换，不要依赖含义模糊的隐式复用。

## 4. 实现校验与帧生成

在 `protocol/protocol_handler.py` 中完成以下工作：

1. 在 `validate_status_bits()` 中增加协议专用参数校验。
2. 新增注册表所指向的帧生成方法。
3. 根据规格书逐字节赋值，并显式处理端序、比例和符号。
4. 复用已有 XOR/累加和等公共方法，但必须确认算法及覆盖范围一致。
5. 在 `get_byte_descriptions()` 中补充与实际帧长度一致的字节说明。
6. 为正常、能量回收、故障场景补充 `PresetScenarios` 工厂方法。

帧生成方法继续使用现有返回契约：

```python
(成功标志, 帧字节列表, 错误信息)
```

外部调用应继续通过 `generate_frame()` 和 `generate_frame_for_preview()`，
不要让界面直接调用私有协议编码方法。存在序号或加密状态时：

- 发送路径按规格书更新序号。
- 预览路径不得消耗下一次发送使用的序号。
- 回绕边界必须有单元测试。

当前未知协议名称为兼容旧调用会回退到默认协议。新增协议不能依赖该回退行为；
模型的 `protocol_name`、注册表键和界面选择项必须使用同一个协议常量。

## 5. 接入界面注册表

协议与主窗口方法的对应关系集中维护在 `gui/protocol_ui_registry.py`。为新协议增加
一个 `ProtocolUiSpec`，登记：

- `switch_handler`：初始化该协议状态并创建/复用配置界面
- `preset_loader`：把当前场景预设加载到界面
- `status_reader`：从界面读取并返回 `StatusBits`

示意：

```python
PROTOCOL_UI_SPECS = MappingProxyType({
    # ...既有协议...
    PROTOCOL_VENDOR_MODEL: ProtocolUiSpec(
        switch_handler="switch_to_vendor_model_protocol",
        preset_loader="load_vendor_model_preset_scenario",
        status_reader="get_vendor_model_status_from_ui",
    ),
})
```

优先复用通用状态页，并根据规格书调整标签、范围和禁用的保留位。只有字段布局差异
明显时才创建专用页面。无论采用哪种方式，都要保证：

- UI 注册表键与 `PROTOCOL_DEFINITIONS` 完全一致。
- 切换协议后状态模型、帧长度、字节说明和包组长度同步更新。
- 切换协议时停止旧协议的循环发送，避免继续发送旧帧。
- 保留位不可编辑，界面中不展示规格书未定义的“伪功能”。
- 信号只连接一次，重建页签时释放旧控件。

如果仓库中的 `ProtocolUiSpec` 字段名后续调整，应以该文件当前定义为准，但仍应
维持“切换、场景加载、状态读取”三个职责的集中映射。

## 6. 统一校验自定义帧

协议固定帧长度来自 `ProtocolDefinition.frame_length`。单帧配置、包组导入和串口
发送应复用 `protocol/frame_utils.py`：

- `validate_frame_length()`：拒绝布尔值、非整数和非正长度。
- `normalize_frame()`：接受列表、元组、`bytes` 或 `bytearray`，输出独立整数列表。
- 每个字节必须是非布尔整数且在 `0-255` 范围内。
- 固定长度协议必须传入 `expected_length` 校验。

不要在各对话框或发送路径中再写一套不同的字节校验规则。

## 7. 添加测试

至少覆盖以下测试类型：

### 注册表一致性

- 新协议存在于 `PROTOCOL_DEFINITIONS` 和 `SUPPORTED_PROTOCOLS`。
- `generator_method`、可选预览方法在 `ProtocolHandler` 中真实存在。
- UI 注册表与协议注册表键集合一致。
- 帧长度、校验模式和发送方式查询结果正确。
- 发送间隔的最小值、最大值、默认值和切换复位策略正确。

### 编码正确性

- 根据规格书样例或已确认抓包编写已知向量测试。
- 每个固定字节、状态位、字节序和物理量比例均有断言。
- 校验字节使用独立计算验证，不只与实现自身比较。
- `get_byte_descriptions()` 数量与帧长度一致。

### 边界与异常

- 数值最小值、最大值和越界值。
- 有符号字段的正值、零值和负值。
- 非整数、布尔值、非法 SOC/电压组合及长度不匹配。
- 序号初值、连续发送、预览不递增和回绕。
- 自定义帧中间位置出现非法字节时也必须整体拒绝。

### 界面行为

- 切换到新协议后使用了正确的配置页和字段标签。
- 正常/能量回收/故障场景能得到预期 `StatusBits`。
- UI 输入生成的帧与协议层直接生成结果一致。
- 协议切换会停止正在进行的循环发送。

## 8. 执行软件验证

PowerShell 无界面单元测试：

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
python -m unittest discover -s tests -v
```

Python 语法编译检查：

```powershell
python -m compileall -q main.py app_paths.py gui licensing protocol serial_comm tools tests
```

如果只修改一个协议，可先运行对应测试模块，再执行完整测试。例如：

```powershell
python -m unittest tests.test_protocol_handler -v
```

测试失败时不要通过放宽校验、删除断言或把异常帧静默转换为零值来“修绿”。

## 9. 完成硬件验证

软件测试通过后，还需要在目标硬件链路上记录：

1. 实际使用的 PC 串口、转码板型号、转码固件版本和接线。
2. 串口波特率、帧间隔及转码固件接收到的完整字节。
3. 单线侧电压、电平、位序、同步和每种码元的脉宽。
4. 示波器/逻辑分析仪抓取的帧与规格书字段对应关系。
5. 目标仪表/BMS 对正常、边界和故障场景的实际响应。

`unittest` 和 `compileall` 只能证明 Python 软件层结果；它们不能证明：

- 转码平台 C 驱动已在全志 Melis SDK 和目标老编译器中通过编译
- UART 字节已经被正确转换为目标单线波形
- 实际电气连接满足目标设备要求
- 真实仪表/BMS 已正确解析和显示

## 10. 合入前检查清单

- [ ] 协议名称、版本和规格书依据已记录
- [ ] `definitions.py` 中元数据完整且生成方法存在
- [ ] `models.py` 字段含义、单位和默认值明确
- [ ] 参数越界不会被静默截断或取模
- [ ] 发送预览不会意外消耗序号
- [ ] 三类场景及字节说明已补充
- [ ] UI 注册表和协议注册表键集合一致
- [ ] 自定义帧使用 `frame_utils.py` 校验
- [ ] 已知向量、边界、异常和 UI 测试已通过
- [ ] 全量单元测试与 Python 语法编译检查已通过
- [ ] Melis C 驱动编译状态与真实硬件验证状态已分别记录
