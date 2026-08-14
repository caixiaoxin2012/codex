# SCL AI Analyzer V0.10.5 - Windows EXE

V0.10.5 增加 Windows 独立 EXE 打包流程。目标产物：

`dist/SCL_AI_Analyzer.exe`

## 本地一键构建

在 Windows 工程电脑上进入 `scl-ai-analyzer` 目录，双击：

`build_windows.bat`

脚本会自动：

1. 创建 `.venv-build` Python 虚拟环境。
2. 安装 PySide6、PyInstaller 和当前项目。
3. 清理旧的 `build/` 与 `dist/`。
4. 使用 `packaging/SCL_AI_Analyzer.spec` 生成单文件 Windows GUI 程序。

构建完成后 EXE 位于：

`dist/SCL_AI_Analyzer.exe`

## GitHub Actions 自动构建

仓库根目录的 `.github/workflows/build-scl-ai-analyzer-windows.yml` 会在 Windows Runner 上构建 EXE，并上传名为 `SCL-AI-Analyzer-v0.10.5-Windows` 的 Actions Artifact。

也可以在 GitHub Actions 页面手动运行 `Build SCL AI Analyzer Windows EXE`。

## 当前说明

- 打包模式：PyInstaller one-file / windowed。
- 主界面：PySide6。
- 用户运行 EXE 时无需另外安装 Python。
- 第一次启动 one-file EXE 时，PyInstaller 会先解压运行时文件，因此启动速度可能比后续启动略慢。
- 当前 EXE 尚未加入商业代码签名证书；Windows SmartScreen 可能对未签名的新程序显示提醒。
- 发布前建议在 Windows 10/11 工程电脑上分别做真实 TIA/SCL 项目回归测试。
