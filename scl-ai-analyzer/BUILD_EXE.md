# SCL AI Analyzer V0.11.3 - Windows EXE

V0.11.3 保留 Windows 独立 EXE 打包流程，并加入 Unified Secure Loader、Export Integrity / SHA-256、Secure XML Input、PLC Code Review 与可选 AI 中文说明。目标产物：

`dist/SCL_AI_Analyzer.exe`

## 本地一键构建

在 Windows 工程电脑上进入 `scl-ai-analyzer` 目录，双击：

`build_windows.bat`

脚本会自动：

1. 创建 `.venv-build` Python 虚拟环境。
2. 安装 PySide6、OpenAI SDK、PyInstaller 和当前项目。
3. 清理旧的 `build/` 与 `dist/`。
4. 使用 `packaging/SCL_AI_Analyzer.spec` 生成单文件 Windows GUI 程序。

构建完成后 EXE 位于：

`dist/SCL_AI_Analyzer.exe`

## Unified Secure Loader

V0.11.3 新增 `secure_loader.py`，统一 `.scl/.xml` 输入链路：

1. 验证扩展名、文件存在性和文件大小。
2. 流式计算 SHA-256。
3. 优先读取 `<filename>.sha256`，其次读取同目录 `SHA256SUMS.txt` 进行完整性校验。
4. SHA-256 不一致时立即拒绝，不进入 SCL/XML 解析器。
5. 无参考哈希时默认标记为 `computed_only` 并继续兼容解析；strict 模式可配置为无参考哈希直接拒绝。
6. 通过完整性检查后才进入 SCL 解析器或 Secure XML parser。

统一审计日志写入：

`%USERPROFILE%\.scl_ai_analyzer\logs\secure_loader.log`

日志包含来源、文件路径、文件类型、大小、SHA-256、哈希状态、参考哈希文件、哈希耗时、解析耗时、总耗时、异常类型和异常信息；不会记录完整 PLC 源码。

用户入口中，CLI 单 SCL、普通 SCL 项目、桌面项目分析以及 TIA 导出目录中的 `.scl/.xml` 都使用统一安全加载链路。`.awl/.udt/.db` 当前暂保留兼容读取路径。

## Export Integrity / SHA-256

V0.11.2 起提供 `integrity_checker.py`：

- 支持 `.scl` 与 `.xml` 文件 SHA-256。
- 哈希按 1 MB 数据块流式计算，不会为了算 SHA-256 把大型 XML 一次性读入内存。
- `ProjectAnalyzer.export_blocks()` 导出程序块后自动生成 `SHA256SUMS.txt`。
- 每个 `.scl/.xml` 文件可同时生成 `<filename>.sha256` sidecar。
- `SHA256SUMS.txt` 使用相对路径，导出目录整体复制到另一台工程电脑后仍可校验。
- `IntegrityChecker.verify_manifest()` 可识别 `ok / mismatch / missing / unsafe_path`。
- `IntegrityChecker.verify_sidecar()` 可对单文件 sidecar 做复核。
- V0.11.3 增加 sidecar/manifest 参考值查找，统一安全加载器可在解析前自动使用这些哈希。

示例导出目录：

```text
export/
  FB_Main.scl
  FB_Main.scl.sha256
  Project.xml
  Project.xml.sha256
  SHA256SUMS.txt
```

SHA-256 用于判断文件内容是否变化；它不是数字签名，也不能证明文件来自可信发布者。正式发布的软件本体仍建议使用代码签名证书。

## Secure XML Input

TIA XML 在进入解析器前先经过安全预检：

- XML 单文件硬上限：500 MB。
- 200 MB 以上记录大文件警告。
- 默认解析时间限制：60 秒（在 XML parser event 之间协作式检查）。
- 最大节点数量：2,000,000。
- 最大嵌套深度：128。
- 单节点最大属性数：128。
- 默认拒绝 `DOCTYPE` / `ENTITY` 声明，降低 XML 实体扩展攻击风险。
- 维护 TIA 常见节点允许列表；兼容模式下未知节点只告警，strict 模式可直接拒绝。
- 安全解析日志写入用户目录 `.scl_ai_analyzer/logs/xml_security.log`，采用滚动日志，不记录完整 PLC/XML 源码。
- 版本识别仅读取 XML 前 500 KB，不再为识别 TIA 版本把整个大型 XML 一次性读入内存。

注意：当前解析超时属于跨平台的协作式超时，而不是强制杀死解析进程。后续若需要处理不可信的第三方 XML，可进一步升级成隔离子进程硬超时。

## PLC Code Review 与 AI 中文说明

- 变量命名、缺失注释、重复变量、未使用变量四类规则检查完全离线运行。
- AI 中文说明只发送结构化规则检查结果，不发送完整 PLC 源码。
- 若要启用 OpenAI 中文说明，请在运行 EXE 前设置环境变量 `OPENAI_API_KEY`。
- 可通过 `SCL_AI_REVIEW_MODEL` 覆盖默认模型。
- 未配置 API Key 时，软件仍显示离线规则摘要，不影响项目解析和 Code Review。

## GitHub Actions 自动构建

仓库根目录的 `.github/workflows/build-scl-ai-analyzer-windows.yml` 会先运行测试，再在 Windows Runner 上构建 EXE，并上传名为 `SCL-AI-Analyzer-v0.11.3-Windows` 的 Actions Artifact。

也可以在 GitHub Actions 页面手动运行 `Build SCL AI Analyzer Windows EXE`。

## 当前说明

- 打包模式：PyInstaller one-file / windowed。
- 主界面：PySide6。
- 用户运行 EXE 时无需另外安装 Python。
- 第一次启动 one-file EXE 时，PyInstaller 会先解压运行时文件，因此启动速度可能比后续启动略慢。
- 当前 EXE 尚未加入商业代码签名证书；Windows SmartScreen 可能对未签名的新程序显示提醒。
- 发布前建议在 Windows 10/11 工程电脑上分别用真实 TIA/SCL 项目，尤其是 200 MB 以上 XML，做内存与耗时回归测试。
