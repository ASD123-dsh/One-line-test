# V1.57 更新器目录切换失败的本地修复

## 已确认的现场

2026-10-15，从 V1.57.0 检测并下载 V1.58.0 后，安装提示“安装失败，旧版本已恢复”。
检查发现完整 ZIP 的 SHA-256 与已发布附件一致，新版解压目录通过逐文件校验，
旧版正式目录也完整恢复到 V1.57.0。

失败位于旧目录备份成功后的“新版候选目录改名为正式目录”步骤。旧日志只保存了
概括错误，没有保留原始 Windows 错误，因此不能认定当时具体是哪个进程占用，
也不能据此认定是资源管理器或安全软件造成。

## 最小修改

- 只修改更新安装器，不修改协议帧、串口发送、授权逻辑和主窗口。
- Windows 错误码 5、32、33 对应的目录访问/占用错误，每次改名最多尝试 80 次，
  间隔 250ms，等待上限约 20 秒。备份、替换和回滚共用该逻辑。
- 其他错误立即停止，不自动删除或覆盖冲突目录，不结束其他用户进程。
- 保留原系统错误文本、失败阶段、Windows 错误码、重试次数、错误码序列、耗时、
  更新器工作目录和完整异常链，方便仍失败时继续准确定位。
- 本地只替换 V1.57 的 `_internal/updater.exe` 并刷新 `update-manifest.json`，
  主 EXE 及其版本号不变。完整修复 ZIP 位于 `dist/local-fixes/`，未上传 GitHub。

## 验证

- 183 项回归测试通过，覆盖临时占用、持续占用、回滚占用、备份占用、路径冲突和日志。
- 在 D 盘独占副本中使用真实 Win32 目录句柄制造占用：旧的 5 秒窗口不足；最终约
  20 秒窗口在重复测试中成功完成等待、替换、旧版备份、用户文件保留和新版重启。
- 持续占用不释放时，约 20 秒后恢复旧版，并保存真实 Windows 错误码和异常链。
- 临时占用测试使用实际 V1.57 主 EXE、修复后的独立更新器和已发布的完整 V1.58 包；
  新版重启后持续运行 5 秒。未对用户正式目录执行自动升级。
- 正式 V1.57 主 EXE 的 SHA-256 不变：
  `2adcf4576dc08f189cb65989c0f3f0fd6bea145c96b315484a5623a46c407ca5`。

这些验证证明修复覆盖受控占用场景，但不替代原现场的用户复测。如果仍失败，
应依据新 `handoff.json` 的 `winerror`、`stage`、`rename_errors` 和 `detail` 定位，
不应直接要求用户关闭安全软件或以管理员运行。

### 后续用户验证与正式版本

2026-10-15，用户确认使用本地修复更新器后，原路径的 V1.57 升级成功。
本修复纳入 V1.58.1 源码及完整发布包。以下“复测与发布边界”记录的是此前仅本地
修复阶段，不代表 V1.58.1 的正式发布状态。

## 复测与发布边界

重新启动原 `dist/AD仪表一线通协议测试工具/` 下的 V1.57.0，检测更新、下载后确认升级。
升级前导出需要保留的包组，并关闭同一安装目录的其他工具实例。

本次没有提交、推送、合并或修改 GitHub Releases，线上 V1.58.0 附件保持不变。
安装动作由当前版本自带更新器执行，因此先修复本地 V1.57 更新器才能覆盖此次升级。
升级至原线上 V1.58 后，其自带更新器仍来自原发布包；后续正式版本需要纳入本修复。

## 全部修改文件

- `updating/installer.py`
- `tests/test_updates.py`
- `docs/releasing.md`
- `docs/update-rename-fix-20261015.md`
- `dist/AD仪表一线通协议测试工具/_internal/updater.exe`
- `dist/AD仪表一线通协议测试工具/update-manifest.json`
- `dist/local-fixes/v1.57.0-updater-rename-fix-20261015/AD-OneLine-v1.57.0-windows-x64.zip`
- `dist/local-fixes/v1.57.0-updater-rename-fix-20261015/AD-OneLine-v1.57.0-windows-x64.zip.sha256`
- `dist/local-fixes/v1.57.0-updater-rename-fix-20261015/verification.json`
- `dist/local-fixes/v1.57.0-updater-rename-fix-20261015/修复与验证说明.md`

Windows 共享句柄机制参考：[Microsoft CreateFileW 文档](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew)。
