# Changelog

本项目从 V0.9.6 起，对每一次大的功能改动使用独立版本号和带版本号的 Git commit message 区分。

## V0.11.3 - Unified Secure Loader

- 新增 `secure_loader.py`，统一负责 `.scl/.xml` 文件的安全读取与解析入口。
- 固定处理顺序为：文件类型/大小检查 → SHA-256 计算与参考值校验 → 内容解析；哈希不一致时不会进入 SCL/XML 解析器。
- SHA-256 参考值优先读取 `<filename>.sha256` sidecar，其次读取同目录 `SHA256SUMS.txt`；也支持调用方显式传入 expected SHA-256。
- 无参考哈希时默认进入兼容模式：仍计算并记录 SHA-256，状态标记为 `computed_only`；`require_hash_reference=True` strict 模式可要求“无哈希不解析”。
- `SecureLoadResult` 保留来源、文件类型、大小、SHA-256、哈希状态、参考文件、哈希耗时、解析耗时、总耗时及安全警告。
- 新增滚动审计日志 `~/.scl_ai_analyzer/logs/secure_loader.log`；成功与失败均记录文件来源、路径、SHA-256（若已计算）、耗时、异常类型与异常信息，不记录完整 PLC 源码。
- 扩展 `integrity_checker.py`，新增 SHA-256 sidecar/manifest 参考值查找，并拒绝 sidecar 指向错误目标、manifest 路径越界或冲突记录。
- 新增 `secure_project.py`，普通 SCL 项目扫描统一经过 `SecureLoader`。
- `secure_tia_adapter.py` 升级：TIA 导出目录中的 `.scl/.xml` 统一经过 `SecureLoader`；`.awl/.udt/.db` 暂保留原兼容路径。
- CLI 单 SCL、CLI 项目模式以及桌面项目分析统一接入安全加载链路。
- 新增 `gui_v0113.py`，桌面版显示统一 SCL/XML 安全加载阶段。
- 新增 `tests/test_secure_loader.py`，覆盖 sidecar、manifest、篡改拒绝、无参考兼容模式、strict 模式、XML 安全解析、大小限制与审计日志。
- Windows EXE 入口、版本资源、构建脚本和 GitHub Actions Artifact 同步升级为 V0.11.3。

## V0.11.2 - Export Integrity / SHA-256

- 新增 `integrity_checker.py`，为导出的 `.scl/.xml` 文件生成 SHA-256。
- SHA-256 采用分块流式读取，默认每次 1 MB，不为大型 XML 一次性分配完整文件内存。
- `ProjectAnalyzer.export_blocks()` 导出 SCL 后自动生成统一 `SHA256SUMS.txt` 清单。
- 每个受支持文件同时生成 `<filename>.sha256` sidecar，便于单文件交付时独立校验。
- 清单使用相对路径，整个导出目录复制到其他工程电脑后仍可复核。
- 导出目录若同时包含 `.xml`，会与 `.scl` 一起纳入统一 SHA-256 清单。
- 新增 `verify_manifest()`，可识别 `ok / mismatch / missing / unsafe_path`。
- 新增 `verify_sidecar()`，支持单文件 SHA-256 sidecar 校验。
- 清单验证阻止路径逃逸到清单目录之外，避免恶意 manifest 引用任意本地文件。
- 新增 `tests/test_integrity_checker.py`，覆盖已知摘要、SCL/XML 清单、篡改检测和自动导出哈希。
- 桌面版、Windows EXE 版本资源与 GitHub Actions Artifact 同步升级为 V0.11.2。
- SHA-256 用于判断文件内容是否被修改，不等同于数字签名或可信发布者身份认证。

## V0.11.1 - Secure XML Input

- 新增 `secure_xml.py`，为 PLC/TIA XML 输入增加独立安全预检层。
- XML 单文件硬上限调整为 **500 MB**；200 MB 以上记录大文件警告。
- 增加解析时间限制、最大节点数量、最大嵌套深度和单节点属性数量限制。
- 默认拒绝 `DOCTYPE` / `ENTITY` 声明，降低 XML 实体扩展类攻击风险。
- 增加 TIA 常见 XML 节点允许列表；默认兼容模式下未知节点只告警，strict 模式可直接拒绝未知节点。
- 新增滚动安全日志 `~/.scl_ai_analyzer/logs/xml_security.log`，记录解析成功、拒绝原因和异常，不记录完整 PLC/XML 源码。
- 新增 `secure_tia_adapter.py`，桌面版和 CLI 的 TIA XML 统一经过安全加载器。
- 大型 XML 的 TIA 版本识别改为只流式读取前 500 KB，不再使用 `read_text()` 载入整个文件。
- 桌面版升级为 `gui_v0111.py`，XML 安全提示会进入底部解析日志。
- 新增 `tests/test_secure_xml.py` 与 `tests/test_secure_tia_adapter.py`。
- Windows EXE、版本资源、构建脚本和 GitHub Actions Artifact 同步升级为 V0.11.1。
- 当前超时采用跨平台协作式检查；后续可进一步升级为隔离子进程硬超时，适合处理完全不可信的第三方 XML。

## V0.11.0 - PLC Code Review

- 新增 `tag_checker.py`，把 SCL AI Analyzer 从程序解析扩展到 PLC Code Review。
- 第一版规则检查覆盖四类问题：变量命名、缺失注释、重复变量、未使用变量。
- 每条检查结果保留 `rule_id`、严重度、程序块、变量、区域、数据类型、源码行、问题说明和整改建议。
- 重复变量按同一程序块作用域判断；未使用变量复用现有变量交叉引用层，基于可追踪静态读写关系判断。
- 命名检查采用保守基础规则，重点识别占位/通用名称、异常下划线和过短名称，不强行绑定某一家企业前缀规范。
- 缺失注释支持同行 `//` 注释和声明前一行 `//` 工程注释。
- 新增 `ai_review.py`，只把结构化规则检查结果交给 AI 生成中文审查说明，不发送完整 PLC 源码。
- AI 中文说明默认使用 OpenAI Responses API；规则检查和离线规则摘要不依赖网络。
- 桌面版新增 “PLC Code Review” 页签，展示规则问题、整改建议和中文审查说明。
- 双击 Code Review 问题可跳转到对应程序块源码行。
- 新增 `tests/test_tag_checker.py` 与 `tests/test_ai_review.py`。
- Windows EXE 构建加入 AI 可选依赖，并在 GitHub Actions 中先运行测试再打包。
- `scl-ai-analyzer-gui` 和 Windows EXE 入口切换到 V0.11.0。

## V0.10.5 - Windows Standalone EXE Packaging

- 新增 `gui_v0105.py`，桌面窗口版本升级为 V0.10.5。
- 新增 `desktop_entry.py`，作为 PyInstaller 稳定桌面入口。
- 新增 `packaging/SCL_AI_Analyzer.spec`，使用 PyInstaller one-file/windowed 模式生成 `SCL_AI_Analyzer.exe`。
- 新增 Windows EXE 版本资源 `packaging/version_info.txt`。
- 新增 `build_windows.bat`，Windows 工程电脑可一键创建构建环境并输出 EXE。
- 新增 `BUILD_EXE.md`，说明本地打包、自动构建和发布注意事项。
- 新增 GitHub Actions 工作流 `.github/workflows/build-scl-ai-analyzer-windows.yml`，在 `windows-latest` 自动构建并上传 EXE Artifact。
- `pyproject.toml` 新增 `packaging` 可选依赖并加入 PyInstaller，GUI 启动入口切换到 V0.10.5。
- 当前 EXE 未配置商业代码签名证书；正式对外发布前建议补充签名并在 Windows 10/11 工程电脑做回归测试。

## V0.10.4 - Project-wide Block Call Cross Reference

- 新增 `call_xref.py`，建立 FB/FC/OB/DB 全项目调用块交叉引用。
- FB 实例调用通过实例声明解析到实际 FB 类型；直接 FC/块调用按块名解析。
- 未能解析的调用明确保留为 `unresolved`，不自动猜测目标块。
- 每个程序块同时提供 Incoming / Outgoing 调用点，并保留调用者、实例、调用类型、文件、源码行和原始源码。
- 调用点关联现有源码反向索引，可显示调用发生时所属 CASE 状态及相关工程对象。
- 新增从 OB 出发的调用路径还原，可展示 `OB → 上层 FB/FC → 当前块` 的完整调用链。
- 桌面版新增“调用块交叉引用”页签；选择程序块后自动显示调用路径与 IN/OUT 调用点。
- 双击调用交叉引用结果可跨程序块跳转到实际调用源码位置。
- 新增 `tests/test_call_xref.py`，覆盖 FB 实例解析、OB 根调用路径和 unresolved 调用保留。
- `scl-ai-analyzer-gui` 启动入口切换到 V0.10.4 桌面实现。

## V0.10.3 - Project-wide Variable Cross Reference

- 新增 `variable_xref.py`，建立变量全项目交叉引用索引。
- 区分变量 `DECLARE / READ / WRITE`，并保留程序块、文件、源码行和原始代码。
- 局部变量按 FB/FC/OB/DB 作用域隔离，避免不同程序块中同名 `#Ready` 被错误合并。
- DB/全局成员变量按项目级汇总，支持 `DB_Process.Ready` 和 `"DB_Process".Ready` 形式。
- 每条变量引用携带同一源码位置关联的状态机、报警、设备、调用和因果链对象。
- 桌面版新增“变量交叉引用”页签；点击源码变量时自动显示其声明、读取和写入位置。
- 双击交叉引用结果可跨 FB/FC/OB/DB 切换程序块并跳转到对应源码行。
- 新增 `tests/test_variable_xref.py`，覆盖局部变量作用域和全局 DB 成员跨块引用。
- `scl-ai-analyzer-gui` 启动入口切换到 V0.10.3 桌面实现。

## V0.10.2 - Reverse Source Navigation

- 新增 `source_reverse.py`，建立源码行到工程对象的反向索引。
- 点击源码任意行，可反查变量、调用对象、报警/联锁、设备、状态机、标准块和因果链。
- CASE 状态区间内的源码行会关联到所属状态，而不仅是状态跳转行。
- 新增桌面“反向关联”页签，显示当前块、源码位置、源码内容及关联对象。
- 源码行变化时，右侧调用关系、状态机、设备、报警联锁、标准块、因果链表格同步选择对应行。
- 保留 V0.10.1 的“分析结果 -> 源码”跳转，形成真正双向导航。
- 新增 `tests/test_source_reverse.py`。
- `scl-ai-analyzer-gui` 启动入口切换到 V0.10.2 桌面实现。

## V0.10.1 - Per-block Analysis and Source Navigation

- 右侧“调用关系、状态机、设备、报警联锁、标准块、因果链”由占位文本升级为当前 FB/FC/OB/DB 的真实分析结果。
- 分析结果使用表格展示，并保留可追溯源码行号。
- 双击分析结果可自动切换到“源码”页并定位对应代码行。
- 项目树选择程序块时同步选中中间程序块列表。
- 完成分析后自动显示第一个程序块，减少空白界面。
- 调用关系也纳入源码跳转体系，为后续工程知识图谱反向导航打基础。

## V0.10.0 - Windows Desktop GUI

- 新增 `src/scl_ai_analyzer/gui.py`，采用 PySide6 构建 Windows 优先桌面界面。
- 桌面布局包含：顶部导入/分析/导出工具栏、左侧项目树、中间 FB/FC/OB/DB 列表、右侧分析页签、底部解析日志与进度条。
- 分析任务运行在 `QThread` 后台线程中，避免大型项目解析时阻塞界面。
- 支持导入 TIA/SCL 项目目录并自动调用现有解析核心。
- 当前块可查看概览、变量、调用关系和源码。
- 预留状态机、设备、报警联锁、标准块、因果链等详细页签。
- 新增 `scl-ai-analyzer-gui` 启动命令。
- `PySide6` 作为 `gui` 可选依赖，保留原有 CLI 使用方式。

## V0.9.6 - Automatic Flow Narrative Generator

- 新增 `flow_narrative.py`。
- 将状态机工程因果链自动转换为中文工程流程说明。
- 流程说明覆盖：当前状态、动作、设备、标准块、完成/跳转条件、下一状态、报警/联锁和源码行号。
- 采用确定性生成，不自动补写代码中不存在的工艺意图或安全结论。
- 新增 `tests/test_flow_narrative.py`。

## V0.9.5 - Engineering Causal Chain

- 串联状态、动作、设备、标准块、完成条件、下一状态和报警/联锁。
- 知识图谱增加因果关系。

## V0.9.4 - Standard Library and State Actions

- 新增标准功能库解析。
- 新增状态机动作与设备对象关联。

## V0.9.3 - Bidirectional Mapping and Knowledge Graph

- 新增工程知识图谱。
- 新增工程对象与源代码双向定位。
