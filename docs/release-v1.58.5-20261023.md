<!-- 2026-10-23：V1.58.5 正式发布范围、验收包校验与归档约定，不改写原打包阶段记录。 -->
# V1.58.5 发布与归档记录

## 用户确认与范围

2026-10-23 用户确认图标、黑角和 50ms 发送记录测试正常，授权将 V1.58.5 提交、
合并 main、发布 GitHub Releases，并要求更新说明每项一句、成功后归档和清理。
本次不重新编译，不修改验收后的源码和 EXE；只补充本次发布说明及导航。

累计功能为双栏工作区、协议搜索、只读帧表格、变化高亮、发送历史表格、参数页独立
滚动与只读提示，最终配色为经典灰绿。小图标使用适配按钮背景的颜色，状态标签
取消原生基线叠绘形成的黑角；后台快速发送逐帧保留真实完成时间，界面仍批量刷新。

协议帧头、编码和校验不变；原同步串口契约、显式限频参数、单任务积压保护、包组
顺序、动态参数和异常停止保留。更新器和授权模块未改。软件写入时间不代表硬件
单线物理层时序；本次没有重新执行真实串口或完整跨版本升级验收。

## 发布前的实际核验

- `python -X utf8 -B tools/check_project.py`：103 个 Python 文件静态检查、375 项回归通过。
- 当前 110 个源码/资源摘要与最终打包记录逐一一致；未调用编译器或 PyInstaller。
- 固定程序目录 189 个文件通过原更新清单校验，其中 188 个文件由专属清单管理。
- 两个 ZIP 逐项检查路径、重复项、文件类型、CRC 和清单摘要，均为 189 个文件。
- managed ZIP 与固定目录逐文件一致；两个校验文件内容与原始 ZIP 匹配。
- GitHub 当前账号为仓库所有者，远端 main 与本地发布起点一致；发布前没有 v1.58.5 标签或 Release。

唯一正常使用程序为 `dist/AD仪表一线通协议测试工具/AD仪表一线通协议测试工具.exe`，
大小 3,763,807 字节，SHA-256：
`e67f417d0aa93c001b3d5b5e3b4b895deeb5d0406068e23615dc020f2be83321`。
必须连同 `_ad_oneline_internal/` 和 `ad-oneline-update-manifest.json` 分发。

## 原始验收附件

| 附件 | 字节数 | SHA-256 |
| --- | ---: | --- |
| `AD-OneLine-v1.58.5-windows-x64-managed.zip` | 49,613,490 | `325aae974b1d58f7e26f873da981cb2a840747f9762e3b94fa355f335dd11814` |
| `AD-OneLine-v1.58.5-windows-x64.zip` | 49,610,134 | `0debd42a49d8273df402e9feac9aacb4d35b4bf8f5fdbedf318e8a9960cee233` |
| `AD-OneLine-v1.58.5-windows-x64-managed.zip.sha256` | 110 | `0a9c2dbb2902b2e470a07d04f2d7cdbecc26f1df5cbbeada609d0b196ee0ed90` |
| `AD-OneLine-v1.58.5-windows-x64.zip.sha256` | 102 | `933141ea9b24e08a2a3bf328c9111deeb88ba770b0f6cdf721bcc1caccb0897a` |

分发优先 managed 主包；旧命名 ZIP 仅供旧独占目录客户端迁移，不用于混放安装。
附件直接复用 `v1.58.5-icons-history-20261022` 最终包，不使用其他同版本阶段备份。

## 提交、线上核验与归档

以 `codex/release-v1.58.5` 分支提交相关源码、资源、测试和文档，审阅及 CI 通过后合并
main。标签 `v1.58.5` 指向合并提交，Release 使用 [简短更新说明](releases/v1.58.5.md)。

发布收尾要求公开稳定版、Latest、版本标签与 main 合并提交一致，四附件状态、大小、
GitHub 摘要以及实际下载摘要均匹配。真实 PR、提交、CI、发布地址与时间另存
`dist/历史归档/正式发行版/v1.58.5/release-publication.json`，不能用本记录代替线上核验。

使用 `python -B tools/archive_release.py` 按 [发布步骤](releasing.md) 执行 `--prune-source`。
正式目录须包含两个 ZIP、两个校验文件、真实发布记录、发布说明及原打包记录，共七个
文件。打包记录中的本地验收状态保留历史原值，不将其改写为正式发布状态。

## 备份、清理与恢复

补充发布文档前已逐文件保存 139 个源码、资源和说明到
`dist/历史归档/发布前源码-v1.58.5-20261023.zip`，SHA-256：
`2e556f19fe1ad8f6a6d1ea734b9a746fce274ee8f57e1c3dbf60f0721a063754`。
该备份不含程序二进制、PDF、私钥、授权和用户数据，不覆盖此前备份。

发布成功并完整归档后，只移除本次 `build/release-v1.58.5-20261023/` 核验脚本、
下载副本和临时记录，以及已迁入正式归档的最终本地包副本和空目录。
历史发行版、各阶段恢复 ZIP、截图、旧升级验收入口和必要输入缓存均保留。
临时核验可按源码及正式记录重跑；程序恢复从正式 ZIP 解压至新的独立目录，
不要覆盖运行中的程序。旧 tracked `dist` 二进制变动不纳入本次源码提交或重置。

## 本次全部源码与文档修改文件

- 规则与导航：`AGENTS.md`、`README.md`、`app_info.py`、`docs/releasing.md`。
- 主界面：`gui/main_window.py`、`gui/frame_preview.py`、`gui/protocol_selector.py`、
  `gui/protocol_tabs.py`、`gui/send_history.py`、`gui/soft_theme.py`、`gui/ui_icons.py`。
- 参数页布局：`gui/protocol_pages/common_forms.py`、`gui/protocol_pages/lishen.py`。
- 后台记录：`serial_comm/serial_manager.py`。
- 图标资源：`img/ui/check.svg`、`img/ui/chevron-down.svg`、`img/ui/chevron-up.svg`、`img/ui/radio.svg`。
- 回归：`tests/test_background_serial.py`、`tests/test_lishen_protocol.py`、
  `tests/test_classic_palette.py`、`tests/test_reference_ui.py`、`tests/test_soft_ui.py`、
  `tests/test_ui_icon_rendering.py`。
- 既有界面阶段记录：`docs/ui-soft-glass-20261022.md`、`docs/ui-reference-alignment-20261022.md`、
  `docs/ui-navy-palette-20261022.md`、`docs/ui-classic-palette-20261022.md`、
  `docs/ui-classic-palette-verification-20261022.json`、`docs/ui-icons-history-20261022.md`。
- 发布记录：`docs/releases/v1.58.5.md`、`docs/release-v1.58.5-20261023.md`。

开发侧另同步 `dist/README.md` 到正式归档位置，不提交生成程序文件；发布后归档附件
及核验记录均为生成归档，最终清理结果随本次交付说明提供。
