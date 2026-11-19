<!-- 2026-11-17：一线通工具的本机HTTP与Codex MCP接入、验证和维护说明。 -->
# AI本机接口

## 日期、问题与范围

2026-11-17：用户希望同一台Windows电脑上的Codex直接操作一线通工具测试，确认采用
“本机控制接口＋MCP适配”，要求原协议、循环、激活和升级不受影响，源码接入阶段暂不编译、提交或发布。

GUI继续共用一个`ProtocolHandler`和`SerialManager(background_send=True)`。HTTP线程只
鉴权、解析和排队，Qt主线程统一读写界面及调度；写线程只接收原有独立字节快照。
不改任何协议编码、校验、流水号、激活算法、更新器或参考驱动，仅在右上角补充AI状态入口。

2026-11-19按用户要求仅调整AI连接和右上角状态：允许AI主动申请、工具内人工确认，
授权改为本次连接有效且不设分钟数。仍沿用本机HTTP＋MCP，不新增依赖；其余布局不变。
随后按用户要求保持V1.58.9重新打包，固定EXE及本轮ZIP均已包含这些改动。
用户已确认本轮功能正常并授权正式发布；此前未提交、未发布的阶段事实保留，正式结果见末节。

源码接入时保持1.58.8且未改EXE；随后用户确认打包V1.58.9本地测试版，固定EXE已含
AI接口，当时未改GitHub Releases。MCP SDK只安装在独立`.venv-mcp`中，主程序仍使用原
Python3.11.9/PyQt5依赖；不使用MCP源码入口绕过激活。

## 使用（V1.58.9）

1. 打开`dist/AD仪表一线通协议测试工具/AD仪表一线通协议测试工具.exe`，按原流程正常激活。
   主界面显示后只准备本机申请入口，不自动允许读取、连接串口或发送；不要同时运行另一实例。
2. 让Codex调用`one_line_request_connection`。工具弹出非模态确认，可选择“本次允许控制”、
   “仅允许只读”或“拒绝”，默认拒绝；关闭或Esc等同拒绝，重复申请不会堆叠弹窗。
3. Codex通过`one_line_connection_status`查询结果。批准后再查协议、串口、参数和当前帧；
   只读连接不能改参或发送。允许控制不自动执行测试，仍需用户明确COM口、协议和接线。
4. 本次授权不设五分钟或十五分钟到期。主动调用`one_line_close_connection`、在工具中断开
   或关闭软件后失效，不跨重启保存；新连接器不能继承旧连接器的授权。
5. 右上角机器人显示“AI申请中”“AI连接中”“AI测试中”；无近期活动时显示“AI已授权”，
   不把监听中或历史授权冒充持续网络连接。点击机器人可管理或断开本次连接。
6. 再让Codex选择协议、改参、连接明确COM口并发送。可随时在界面撤销授权或停止循环。
   如果发现异常，不应让AI通过反复重试发送来探测问题，应先查询任务和错误。

2026-11-17的旧V1.58.9恢复包仍需从“配置 / 诊断 → AI 本机接口…”手动开启和授权，
不包含主动申请和机器人提示；不要因版本号相同混用。当前固定入口已替换为2026-11-19新包。
连接器按发现文件能力协商，仍兼容旧包；MCP注册不变，只需重载连接器以发现新增工具。

独立连接器环境已在本机准备；其他开发环境可执行：

```powershell
python -B -m venv .venv-mcp
# Python3.11自带旧pip若长时间解析新依赖，只升级这个独立环境的安装器。
.\.venv-mcp\Scripts\python.exe -B -X utf8 -m pip install --upgrade pip
.\.venv-mcp\Scripts\python.exe -B -X utf8 -m pip install --only-binary=:all: --no-compile -r requirements-mcp-lock.txt
```

这些命令不安装到原PyQt5环境，不调用PyInstaller或C编译器；`.venv-mcp`是Codex连接器
需要长期使用的可再生运行环境，已忽略，不作为源码、备份或Release附件上传。

## Codex注册

2026-11-17经用户确认，已在本机`C:\Users\hello\.codex\config.toml`注册`ad_oneline`。
注册不会开启一线通接口或授予写权限。实际STDIO入口如下，不包含会话令牌：

```powershell
codex mcp add ad_oneline -- "D:\work\Self_Made_Program\sifexe-Refactoring\.venv-mcp\Scripts\python.exe" -B -X utf8 "D:\work\Self_Made_Program\sifexe-Refactoring\tools\mcp_server.py" --connection-file "C:\Users\hello\AppData\Local\ad-meter-single-wire-tool\ai-control\connection.json"
```

也可在Codex MCP设置中新增STDIO服务器，填写同样的程序和参数。等效配置示例：

```toml
[mcp_servers.ad_oneline]
command = 'D:\work\Self_Made_Program\sifexe-Refactoring\.venv-mcp\Scripts\python.exe'
args = ['-B', '-X', 'utf8', 'D:\work\Self_Made_Program\sifexe-Refactoring\tools\mcp_server.py', '--connection-file', 'C:\Users\hello\AppData\Local\ad-meter-single-wire-tool\ai-control\connection.json']
startup_timeout_sec = 20
tool_timeout_sec = 90
enabled = true
```

保留Codex原有工具审批，不设置自动批准全部写工具；只增添`ad_oneline`，不替换其他服务器。
注册后需在客户端重新加载MCP/重新打开会话，以实际工具列表为准；本轮STDIO测试不是
“当前聊天已经自动获得新工具”的证明。现源码提供19个工具，需重载后以工具清单为准；
工程移动后需同步修改这条命令的绝对路径。
本机已显式指定发现文件路径，避免客户端环境没有提供正确用户目录；其他电脑需要按
实际用户目录调整参数，不把连接文件内容或令牌粘贴到聊天、配置或仓库。
`codex mcp get ad_oneline --json`已确认STDIO入口、20秒启动超时及90秒工具超时生效。
官方`mcp add`会重写整个MCP表的表示；本次将其省略的原默认字段及改写的数字类型恢复，
去除新条目后的全局配置与注册前摘要完全一致，项目配置未变。未放宽原工具审批。
撤回注册时只移除`mcp_servers.ad_oneline`表，保留所有原服务器、模型和账号配置；
未保存全局配置副本、Git授权或Codex账号令牌。

例：“先申请连接并等待我在工具内确认，再查询状态和当前帧；在我确认COM口后，选择星恒智能BMS，按10%、50%、100%
三个SOC各运行3秒、间隔1000ms，逐步返回实际写入数量和错误，不把仪表功能判为自动通过。”

## 工具与结果

| 工具 | 权限与职责 |
| --- | --- |
| `one_line_request_connection` | 只提出人工确认申请，不自行授予读取或操作权 |
| `one_line_connection_status` | 只查本连接申请的状态，不返回测试数据 |
| `one_line_close_connection` | 结束本次AI授权，停止自己的任务，不断开手动串口 |
| `one_line_status`、`one_line_protocols`、`one_line_ports`、`one_line_parameters` | 只读查询，不返回授权内容或串口hwid |
| `one_line_preview`、`one_line_results` | 只读预览和游标历史；预览不消耗流水号 |
| `one_line_select_protocol`、`one_line_configure`、`one_line_set_raw_frame` | 需本次控制授权；选择原注册协议、精确改参或设置原始帧 |
| `one_line_connect`、`one_line_disconnect` | 需本次控制授权，明确指定COM口；不抢占手动循环、不强关在途串口 |
| `one_line_send_once`、`one_line_start_cycle`、`one_line_start_sequence` | 需本次控制授权；真实发送，有界单帧/动态循环/固定包组 |
| `one_line_run_case` | 应用参数并运行一个有界步骤，连接器自动查询存活和完成；可多次调用做参数扫描 |
| `one_line_stop` | 即使撤销写权限仍可停止AI自己的任务；可用case_id防止停止另一任务 |

改参使用`StatusBits`的原字段名，先通过既有校验，再通过原UI绑定精确回读。不支持的
字段、控件不能精确表示的数值、越界和非有限值明确拒绝，恢复先前模型、控件和场景，
不静默截断。星恒字段的单位、步进和范围复用现有规格定义；其他参数以原协议校验及
预览结果为准。新协议注册后自动进入列表，新增模型和UI绑定仍遵守原开发指南。

- HTTP统一返回`ok`、`request_id`及`result`或稳定的`error.code`。MCP提供相同的结构化
  输出和只读/有副作用标记；标记不是授权，最终权限始终由GUI端检查。
- `send_once`返回`accepted`只说明后台受理；查询任务为`completed`及`written`事件后，
  才能说明实际调用串口write成功。硬件结果始终为`not_observed`，不是仪表、验密或波形通过。
- 普通循环每周期读取当前参数；已提交给驱动的帧不能撤回，新数据用于后续未提交快照。
  星恒20/31字节格式变化先停止旧循环；包组保持固定顺序和帧快照，不接受中途参数覆盖。
- 循环最多60000ms且不得短于发送间隔；本次连接授权无固定分钟数，不保存到磁盘；
  连续10秒没有已认证命令则停止AI任务。`run_case`自动轮询，直接使用`start_cycle`
  则应在10秒内持续查询状态。失联只停止自己的任务，不以保留会话授权冒充仍在连接。
- 未答复申请60秒后失效，拒绝或失效后全局冷却15秒防止重复弹窗；这是未批准申请的
  等待限制，不是对用户已允许连接设置时长。人工接管会停止AI并降回只读，不能抢占手动循环。
- `status.write_authorized`明确表示当前控制权；兼容字段`write_seconds_remaining`在本次
  允许控制时为`null`、无控制权时为`0`，不使用无限大或虚构剩余秒数。
- 停止时可先显示`stopping`，在途结果到达后再结束；停发后实际写出的最后一帧仍计入
  原任务。已完成任务不吸收后来手动单帧的结果，手动任务不被AI停止或改写。
- 近期256条写请求按请求ID防重复，相同ID不同参数拒绝；这是有界会话内防重，不是跨重启
  持久“恰好一次”保证。网络错误不自动重发，结果未知时用`results(request_id=...)`查询。
- HTTP线程和等待GUI的事件分别最多8份。未开始的请求超过2秒自动取消，不能在界面
  恢复后突然发帧；已开始的操作返回`processing`时应查询结果，不重复执行。
- 结构化历史最多2048条，单次读取最多256条，旧记录被截断时显式返回`truncated`。
  需要完整长测记录时应持续按游标收集，不能声称内存历史是永久日志。

## 安全、文件与退出

只监听`127.0.0.1`的系统分配端口，单一入口为`POST /v1/command`；认证用独立随机
会话令牌，严格检查Host、Origin、JSON、长度和命令白名单，不开放CORS、文件访问、
任意代码执行、激活码生成或升级控制。不开公网、不设防火墙规则、不访问Git授权。
JSON嵌套最多64层，指数溢出、NaN和Infinity在传输层即拒绝；Qt请求槽有最终异常边界，
防止畸形输入或未预期异常中止整个桌面程序。

发现文件位于`%LOCALAPPDATA%/ad-meter-single-wire-tool/ai-control/connection.json`，
只保存端点、会话标识及当前Windows用户DPAPI加密后的令牌，不保存明文令牌。
新发现记录另有能力列表，HTTP可选携带独立连接器标识；批准权限绑定本次连接器，只在内存保存。
连接器同用户解密后直连回环HTTP，不走系统代理、不跟随重定向，不将令牌返回给模型。
该保护不防当前Windows用户下的恶意进程或管理员，不应把它宣传为本机多租户隔离。

正常关闭只删除本次创建且内容未改的连接记录；同一发现文件不能被第二实例覆盖。
记录被改动、设为只读或占用时保留现场，关闭监听与原程序关闭/升级仍继续执行。
若程序被强杀，可能留下加密连接记录：先确认原工具和连接器已退出，检查该文件的软件
标识及PID，再手动移走这一份记录后重新开启；不要扫描删除用户目录或授权文件。

## 改动文件、验证与待办

以下为最初接入和打包的历史记录；2026-11-19源码调整及重新打包见末两节，不覆盖旧包验证事实。

增量备份只包含本轮修改的七个原文件，位于本地忽略目录
`dist/历史归档/源码增量备份/ai-control-20261117.zip`；基线为
`46fe0ec76d8ac7ae9dd427830b6e15d16e5e64a2`，不做全工程或嵌套备份。

- 新增`ai_control/__init__.py`、`ai_control/catalog.py`、`ai_control/connection.py`、
  `ai_control/transport.py`、`ai_control/client.py`：发现、保护、传输和元数据组件。
- 新增`gui/ai_controller.py`、`gui/ai_control_dialog.py`：主线程命令及最小设置窗口。
- 新增`tools/mcp_server.py`、`requirements-mcp.txt`、`requirements-mcp-lock.txt`：独立SDK适配及锁定依赖。
- 新增`tests/test_ai_control.py`、`tests/test_ai_transport.py`、`tests/test_mcp_bridge.py`、
  `tests/mcp_client_probe.py`：假设备、HTTP、DPAPI和双协议真实STDIO回归。
- 修改`gui/main_window.py`、`gui/settings_panel.py`：延迟菜单入口、手动接管和退出收尾；
  默认无服务。修改`serial_comm/serial_manager.py`只增加完成快照信号和代次只读查询，
  不改变旧发送信号、返回契约或调度。
- 修改`tools/check_project.py`纳入新包语法/回归，修改`tests/test_update_dialog.py`保留全部
  旧菜单与升级断言并添加新菜单项；修改`.gitignore`排除独立环境，修改`README.md`及本记录。

统一验证：`python -B -X utf8 tools/check_project.py`。存在`.venv-mcp`时包含真实SDK
端到端；无可选环境时仅跳过该项，原激活、升级和其他回归仍运行。Windows DPAPI需要
正常当前用户上下文，隔离沙箱的拒绝访问不等同于程序或客户授权失败。

源码接入阶段验证：122个源码文件语法/冲突检查通过，全量470项回归通过（原432项及新增38项），
独立MCP环境`pip check`和差异格式检查通过。真实STDIO分别验证legacy及auto模式、16工具
发现、只读拒绝、合成授权、星恒实时/公有/原始帧、动态写入及有界步骤；新增小窗口的真实
离屏渲染没有裁切。未访问真实串口、客户授权或大模型，不代表硬件验收通过。

源码接入时114个受保护文件摘要与修改前完全一致，包括原协议、激活/升级代码、用户已有改动及
固定位置的EXE。七文件增量备份读回完整，SHA-256为
`fd33571aa47b7d2246d86a146fee5588e9aac40826f856c582fd4150ddd753f7`；Git HEAD仍为上述
基线，暂存区为空，版本仍为1.58.8；原环境仍为PyQt5 5.15.9、pyserial 3.5、rsa 4.9，
没有安装MCP。新增连接器另在本机全局Codex配置中，不纳入仓库或发行附件。

本轮临时工作目录`tmp/ai-control-20261117`用于摘要核验、设置窗口截图及合成连接探针，
核验结束且进程退出后清理其中脚本、截图、JSON及测试副本；不删除用户数据或未完成验收的
回退基线。保留独立`.venv-mcp`供连接器运行，保留七文件增量ZIP供用户验收后选择恢复；
清理的诊断与截图可通过本记录及正式测试重新生成，没有编译中间产物。

上述未编译、版本与EXE未变是源码接入阶段的历史事实；用户随后授权的本地打包见下节。
仍由用户验收真实仪表/转码平台，不以模拟测试代替真实硬件、输入法或跨版本安装验收。

## V1.58.9本地测试包

2026-11-17：用户要求打包测试Codex连接、AI接口与循环动态改参，明确确认本地V1.58.9，
不提交、不发布，打包后清理生成残留。本次只修改`app_info.py`、`README.md`、
`dist/README.md`及本记录，业务源码、协议、激活/升级、MCP入口和Codex配置均不再改动。
四文件原状态已保存在下述本地目录的`打包前变更文件.zip`，不做全工程或嵌套备份。

- 唯一最新程序：`dist/AD仪表一线通协议测试工具/`；完整EXE、专属运行库和清单须一起保留。
- 两个ZIP、两个SHA-256、`packaging-verification.json`和增量备份：
  `dist/历史归档/本地测试包/v1.58.9-ai-control-20261117/`，不是正式发行归档，不上传GitHub。
- 沿用Python3.11.9 x64、PyInstaller6.20.0及原Qt依赖；122个源码文件检查、470项全量回归通过。
- 两ZIP安全解压、189个程序文件/188项专属清单、82个主程序及8个更新器代码对象与当前源码一致，
  七项内嵌图标及所有图片资源与原件一致，没有打入私有激活生成器或独立MCP SDK。
- 直接从EXE的PYZ加载AI宿主、协议、GUI和串口代码，运行38项AI/HTTP/MCP模拟回归全部通过；
  外置连接器客户端按实际架构使用源码，两种MCP模式均发现16工具，覆盖只读拒绝、临时授权、
  星恒实时/公有/原始帧、有界步骤和循环动态SOC。未用业务源码补齐任何缺失的宿主模块。
- 候选与固定入口的真实EXE在空用户目录完成版本/路径/PID绑定的Qt就绪确认，稳定5秒后退出码0；
  更新器仅运行`--help`并返回0，未使用客户授权或执行安装，没有连接真实硬件或调用大模型。

旧189文件程序已与正式V1.58.8 managed ZIP逐文件一致；保留该原始ZIP供恢复，不长期
保留第二份旧版解压程序。本机Codex仍使用已经注册的独立连接器，无需改变主程序依赖；
重新加载MCP后，由用户在新EXE中手动开启接口及授权，再进行实际设备测试。
保护摘要、附件大小与SHA-256、固定入口和清理结果以本地`packaging-verification.json`为准。
本轮不创建提交、标签、Release或`release-publication.json`，待用户功能验收后另行授权发布。

收尾核验134个受保护文件摘要不变，34个既有Python缓存未重写，Git HEAD和空暂存区保持
原样。已清理`build/ai-package-20261117/`内591个临时生成文件（429,979,510字节），
包括诊断脚本、日志、双ZIP重复解压、模拟连接和旧版重复展开副本，并移除空build目录；
V1.58.8正式ZIP、四文件增量备份、当前固定程序、本地附件、MCP环境和用户数据均保留。
需要恢复旧程序时完整解压正式managed ZIP到新的独立目录，不能仅覆盖主EXE。

## AI主动申请与本次会话授权

2026-11-19：用户反馈手动开启接口较繁琐，希望AI发起连接申请、工具内确认，并在右上角
显示机器人状态；随后明确取消五分钟授权，改为本次允许期间有效。该阶段仅修改源码，
保持版本V1.58.9，不编译、不提交、不发布，也不修改本机Codex配置。

启动流程在原升级就绪通知之后准备“仅申请”监听；未批准只能申请、查申请结果或取消自己的
申请，不能读取协议、串口、参数或历史，也不能发送。确认弹窗非模态、默认拒绝，提供本次
控制和只读选项；关闭/Esc视为拒绝。只保留一份待答复申请，重复请求不堆叠弹窗，60秒未
答复失效，拒绝后冷却15秒。批准权限无固定倒计时，连接器随机标识只存在内存，另一连接器
不能借用授权；断开、撤销、关闭、重启或激活失效后不会自动恢复，人工接管降为只读。

机器人在申请/活动连接/测试时出现，空闲只显示已授权；点击可管理或断开，不把监听端口
当作AI已连接。保留60秒单次循环上限、失联10秒停本次任务、在途帧完成统计与手动优先。
排队写命令绑定授权代次，撤销后重新同意也不能借新权执行；只读轮询跨确认时不误报断连。
发现文件能力协商保留旧EXE的HTTP格式；新增3个MCP工具，原16个操作继续使用。

本轮全部修改文件（21个）：

- 协调及启动：`main.py`、`gui/main_window.py`、`gui/ai_controller.py`。
- 确认和状态外观：`gui/ai_control_dialog.py`、`gui/ui_icons.py`、`gui/soft_theme.py`。
- 连接器与传输：`ai_control/catalog.py`、`ai_control/client.py`、`ai_control/connection.py`、
  `ai_control/transport.py`、`tools/mcp_server.py`。
- 回归：`tests/test_ai_control.py`、`tests/test_ai_transport.py`、`tests/test_mcp_bridge.py`、
  `tests/mcp_client_probe.py`、`tests/test_ui_icon_rendering.py`、`tests/test_update_dialog.py`、
  `tests/test_update_startup.py`；菜单及启动测试保留原更新/反馈/激活断言，只适配新增状态按钮
  与申请准备回调，并确认升级就绪回调仍先执行。
- 说明：`README.md`、`dist/README.md`、`docs/ai-control.md`。

修改前21文件已逐项校验保存于`dist/历史归档/源码增量备份/ai-connection-consent-20261119.zip`，
SHA-256为`abefbbc345ce18dd672baa190f11e9ffc21a10aeb450b206359f146cff1320e3`。
这是本轮增量回退基线，不包含全工程、运行环境、客户授权或私钥，待验收前保留。

`python -B -X utf8 tools/check_project.py`：122文件语法/冲突检查、487项全量回归通过；
官方SDK子进程覆盖legacy/auto两种MCP模式的19工具、申请确认、只读、允许控制、关闭，
以及星恒实时/公有/原始帧、动态SOC和有界步骤。命名管道测试在正常Windows用户上下文完成，
首次沙箱拒绝访问不作业务失败结论。Qt离屏检查加载系统原微软雅黑字体后，确认弹窗文字、
机器人配色和主工作区几何正常；不把离屏与假串口测试当作客户硬件、真实升级或EXE验收。

该源码阶段的EXE仍为2026-11-17测试包，SHA-256保持
`2b12f2127918c45fc236cbcfbafbd8cb4246b757ab1a29b1c327b88f8042c66a`；
Git HEAD仍为`46fe0ec76d8ac7ae9dd427830b6e15d16e5e64a2`，暂存区为空，原协议、激活、
更新器和串口调度源码本轮未改。现有34个Python缓存保留，使用`-B`未新增源码缓存。
已核对进程退出并清理`build/ai-consent-20261119/`内的探针及两张截图，共3文件、130599字节；
这些检查可由现有源码与模拟回归重新生成。不删旧测试包、历史归档、MCP环境、用户数据或
未知目录；当时新源码功能待用户另行要求打包及实机确认。

## V1.58.9连接申请重新打包

2026-11-19：用户明确要求保持V1.58.9，打包测试AI主动申请、本次授权及右上角机器人，
不提交、不发布。沿用原构建器、Python3.11.9 x64、PyInstaller6.20.0和原锁定依赖；
本轮仅更新`README.md`、`dist/README.md`及本记录，不再改业务源码、版本号或Codex配置。

- 唯一最新版仍为`dist/AD仪表一线通协议测试工具/`，完整保留EXE、专属运行库和清单。
- 两ZIP、两SHA-256、`packaging-verification.json`及三文档增量备份`打包前文档.zip`
  归集到`dist/历史归档/本地测试包/v1.58.9-ai-consent-20261119/`，不作为正式发行包上传。
- 122个Python文件检查、487项全量回归通过；两个ZIP安全解压和CRC通过，189个程序文件、
  188项清单、82个主程序及8个更新器项目代码对象与本轮源码一致，七项内嵌图标和全部图片一致。
- 直接加载本轮EXE内宿主代码运行63项AI/HTTP/MCP及图标模拟回归，全部通过且无跳过；
  外置客户端按原架构使用源码，两种MCP模式均覆盖19工具，包含本次授权和循环动态改参。
  真实控件离屏截图确认申请弹窗非模态、默认拒绝，机器人显示AI连接中且工作区几何不变。
- 候选和固定EXE均在隔离空用户目录完成实际Qt就绪握手，稳定5秒后正常退出；
  独立更新器`--help`返回0，未执行安装、连接真实串口、读取客户授权或调用大模型。

固定EXE的SHA-256为`1a192fa93b82a73ae0269fee96b30d1955a31930e90852a3286d64d4d839872a`。
替换前189个旧程序文件与2026-11-17的V1.58.9 managed ZIP逐文件一致，原ZIP完整保留供恢复；
V1.58.8正式包、源码阶段21文件增量备份、MCP环境、私有激活工具和用户数据不删。
172个受保护文件及34个既有Python缓存保持摘要不变，Git HEAD和空暂存区不变。
本轮临时目录`build/ai-consent-package-20261119/`仅用于校验、模拟与旧程序暂存，
进程退出后已清理其中586个生成文件（430,174,035字节），包括探针、截图、重复解压和旧版展开副本；
构建器的独占中间目录也已自动清理，附件摘要及最终状态见本地验证JSON。
这些检查不代替客户仪表、真实输入法、波形或实际跨版本升级验收，功能仍由用户实测确认。

## V1.58.9正式发布

2026-11-19：用户确认本轮测试正常，并同意提交、合并main和发布V1.58.9。直接沿用连接申请
重新打包阶段的两个ZIP及校验文件，不重编译、不升版，不改协议、激活或升级算法。发布说明
只保留三条一句话概括，详细证据继续维护在本记录；三类AI连接管理接口共计19项MCP工具。

本次提交白名单共31个文件：

- 入口与依赖：`.gitignore`、`app_info.py`、`main.py`、`requirements-mcp.txt`、`requirements-mcp-lock.txt`。
- AI组件：`ai_control/__init__.py`、`ai_control/catalog.py`、`ai_control/client.py`、
  `ai_control/connection.py`、`ai_control/transport.py`、`tools/mcp_server.py`。
- 界面与完成结果：`gui/main_window.py`、`gui/settings_panel.py`、`gui/soft_theme.py`、`gui/ui_icons.py`、
  `gui/ai_control_dialog.py`、`gui/ai_controller.py`、`serial_comm/serial_manager.py`。
- 检查与回归：`tools/check_project.py`、`tests/test_ai_control.py`、`tests/test_ai_transport.py`、
  `tests/test_mcp_bridge.py`、`tests/mcp_client_probe.py`、`tests/test_ui_icon_rendering.py`、
  `tests/test_update_dialog.py`、`tests/test_update_startup.py`。
- 文档：`README.md`、`dist/README.md`、`docs/ai-control.md`、`docs/releasing.md`、`docs/releases/v1.58.9.md`。

本轮四文档修改前状态保存在本地测试包目录的`发布前文档变更.zip`；既有AGENTS.md变更、
历史回退记录、dist历史二进制变更、两个私有激活工具及用户数据不纳入提交或清理。
发布前122文件检查和487项回归再次通过；两个验收ZIP、189文件清单及主程序82个、
更新器8个项目代码对象与待发布源码一致，保持原包摘要。打包阶段的63项冻结模拟回归及
实际EXE启动结果保留原记录，不改写为本轮新增的硬件或安装测试。

PR及main的CI通过、标签指向合并提交、正式Latest与四附件匿名实际下载核验后，按
`docs/releasing.md`执行既有归档脚本；正式归档必须包含两ZIP、两SHA-256、发布说明、
原打包验证和真实`release-publication.json`，以其中的合并、公开和下载证据为准。
只清理本轮独占生成目录与已完整归档的重复副本，不删除旧恢复包或尚未完成的用户测试。
原本地打包记录中的`published=false`是当时事实，正式状态另记，不追写伪造成功。

接口依据：[Codex MCP配置](https://developers.openai.com/codex/mcp)、
[官方Python SDK](https://py.sdk.modelcontextprotocol.io/)、
[MCP工具与用户控制](https://modelcontextprotocol.io/specification/latest/server/tools)。
