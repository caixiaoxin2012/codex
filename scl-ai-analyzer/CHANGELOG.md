# Changelog

本项目从 V0.9.6 起，对每一次大的功能改动使用独立版本号和带版本号的 Git commit message 区分。

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
