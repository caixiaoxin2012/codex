# SCL AI Analyzer V0.11.1 - Windows EXE

V0.11.1 保留 Windows 独立 EXE 打包流程，并加入 Secure XML Input、PLC Code Review 与可选 AI 中文说明。目标产物：

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

仓库根目录的 `.github/workflows/build-scl-ai-analyzer-windows.yml` 会先运行测试，再在 Windows Runner 上构建 EXE，并上传名为 `SCL-AI-Analyzer-v0.11.1-Windows` 的 Actions Artifact。

也可以在 GitHub Actions 页面手动运行 `Build SCL AI Analyzer Windows EXE`。

## 当前说明

- 打包模式：PyInstaller one-file / windowed。
- 主界面：PySide6。
- 用户运行 EXE 时无需另外安装 Python。
- 第一次启动 one-file EXE 时，PyInstaller 会先解压运行时文件，因此启动速度可能比后续启动略慢。
- 当前 EXE 尚未加入商业代码签名证书；Windows SmartScreen 可能对未签名的新程序显示提醒。
- 发布前建议在 Windows 10/11 工程电脑上分别用真实 TIA/SCL 项目，尤其是 200 MB 以上 XML，做内存与耗时回归测试。
