# Changelog

本项目从 V0.9.6 起，对每一次大的功能改动使用独立版本号和带版本号的 Git commit message 区分。

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
