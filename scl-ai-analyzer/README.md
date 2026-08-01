# SCL AI Analyzer

SCL AI Analyzer 是一个面向 TIA Portal / SCL 工程的工业 AI 辅助工具。

## V0.1 目标

先跑通最小闭环：

1. 读取 `.scl` 文件；
2. 识别 `VAR_INPUT`、`VAR_OUTPUT`、`VAR_IN_OUT`、`VAR`、`VAR_TEMP` 变量区；
3. 提取变量名、类型、默认值与注释；
4. 生成 Markdown 工程报告。

## 暂不包含

- 自动修改 PLC 程序；
- 自动下载到 PLC；
- 替代人工安全审核；
- 复杂语法树与完整调用关系分析。

## 目录

```text
scl-ai-analyzer/
├── README.md
├── pyproject.toml
├── src/scl_ai_analyzer/
│   ├── __init__.py
│   ├── parser.py
│   └── cli.py
└── samples/
    └── motor_control.scl
```

## 运行

```bash
cd scl-ai-analyzer
python -m scl_ai_analyzer.cli samples/motor_control.scl -o report.md
```

## 下一阶段

- Network / Region 分块；
- IF / CASE / 状态机流程说明；
- FB / FC / OB 调用树；
- LLM 解释与来源片段引用；
- Word 报告导出。
