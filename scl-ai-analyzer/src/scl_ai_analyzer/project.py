from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .parser import AnalysisResult, SCLParser


BLOCK_ENDINGS = {
    "FUNCTION_BLOCK": "END_FUNCTION_BLOCK",
    "FUNCTION": "END_FUNCTION",
    "ORGANIZATION_BLOCK": "END_ORGANIZATION_BLOCK",
    "DATA_BLOCK": "END_DATA_BLOCK",
}

BLOCK_PREFIX = {
    "FUNCTION_BLOCK": "FB",
    "FUNCTION": "FC",
    "ORGANIZATION_BLOCK": "OB",
    "DATA_BLOCK": "DB",
}


@dataclass(frozen=True)
class SourceBlock:
    source_file: Path
    block_type: str
    name: str
    text: str
    analysis: AnalysisResult


@dataclass(frozen=True)
class ProjectResult:
    root: Path
    source_files: tuple[Path, ...]
    blocks: tuple[SourceBlock, ...]


class ProjectAnalyzer:
    """Scan exported SCL files, split blocks, and build a project-level index."""

    _header_pattern = re.compile(
        r'^\s*(?P<type>FUNCTION_BLOCK|FUNCTION|ORGANIZATION_BLOCK|DATA_BLOCK)\s+'
        r'"?(?P<name>[A-Za-z_][\w]*)"?',
        re.IGNORECASE | re.MULTILINE,
    )

    def __init__(self, parser: SCLParser | None = None) -> None:
        self.parser = parser or SCLParser()

    def scan(self, path: str | Path) -> ProjectResult:
        root = Path(path)
        if root.is_file():
            files = (root,)
            project_root = root.parent
        elif root.is_dir():
            files = tuple(sorted(root.rglob("*.scl")))
            project_root = root
        else:
            raise FileNotFoundError(f"Project path not found: {root}")

        blocks: list[SourceBlock] = []
        for file_path in files:
            text = file_path.read_text(encoding="utf-8-sig", errors="replace")
            blocks.extend(self.split_blocks(text, file_path))

        return ProjectResult(
            root=project_root,
            source_files=files,
            blocks=tuple(blocks),
        )

    def split_blocks(self, text: str, source_file: Path) -> list[SourceBlock]:
        matches = list(self._header_pattern.finditer(text))
        blocks: list[SourceBlock] = []

        for match in matches:
            block_type = match.group("type").upper()
            name = match.group("name")
            ending = BLOCK_ENDINGS[block_type]
            end_match = re.search(
                rf"\b{re.escape(ending)}\b",
                text[match.start():],
                flags=re.IGNORECASE,
            )
            if not end_match:
                continue

            end_index = match.start() + end_match.end()
            while end_index < len(text) and text[end_index] in ";\r\n":
                end_index += 1

            block_text = text[match.start():end_index].strip() + "\n"
            analysis = self.parser.parse_text(
                block_text,
                source_name=f"{source_file.name}:{name}",
            )
            blocks.append(
                SourceBlock(
                    source_file=source_file,
                    block_type=block_type,
                    name=name,
                    text=block_text,
                    analysis=analysis,
                )
            )

        return blocks

    @staticmethod
    def export_blocks(result: ProjectResult, output_dir: str | Path) -> tuple[Path, ...]:
        target = Path(output_dir)
        target.mkdir(parents=True, exist_ok=True)
        exported: list[Path] = []
        used_names: set[str] = set()

        for block in result.blocks:
            prefix = BLOCK_PREFIX.get(block.block_type, "BLOCK")
            safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", block.name).strip("_") or "unnamed"
            base_name = f"{prefix}_{safe_name}.scl"
            file_name = base_name
            index = 2
            while file_name.lower() in used_names:
                file_name = f"{prefix}_{safe_name}_{index}.scl"
                index += 1
            used_names.add(file_name.lower())

            output_path = target / file_name
            output_path.write_text(block.text, encoding="utf-8")
            exported.append(output_path)

        return tuple(exported)


def render_project_markdown(result: ProjectResult) -> str:
    from .alarm_logic import AlarmLogicAnalyzer, render_alarm_markdown
    from .ast import ProjectASTBuilder, render_ast_markdown
    from .device_logic import DeviceLogicAnalyzer, render_devices_markdown
    from .knowledge_graph import EngineeringKnowledgeGraphBuilder, render_knowledge_graph_markdown
    from .state_machine import StateMachineAnalyzer, render_state_machines_markdown

    counts: dict[str, int] = {key: 0 for key in BLOCK_PREFIX}
    for block in result.blocks:
        counts[block.block_type] = counts.get(block.block_type, 0) + 1

    lines = [
        "# SCL 项目分析报告",
        "",
        f"- **项目目录：** `{result.root}`",
        f"- **SCL 源文件：** {len(result.source_files)}",
        f"- **识别程序块：** {len(result.blocks)}",
        "",
        "## 程序块统计",
        "",
        "| 类型 | 数量 |",
        "|---|---:|",
        f"| FB | {counts.get('FUNCTION_BLOCK', 0)} |",
        f"| FC | {counts.get('FUNCTION', 0)} |",
        f"| OB | {counts.get('ORGANIZATION_BLOCK', 0)} |",
        f"| DB | {counts.get('DATA_BLOCK', 0)} |",
        "",
        "## 程序块索引",
        "",
        "| 类型 | 名称 | 来源文件 | 变量 | FB 实例 | 调用点 |",
        "|---|---|---|---:|---:|---:|",
    ]

    for block in result.blocks:
        analysis = block.analysis
        lines.append(
            f"| {BLOCK_PREFIX.get(block.block_type, block.block_type)} "
            f"| {block.name} | {block.source_file.name} "
            f"| {len(analysis.variables)} | {len(analysis.instances)} | {len(analysis.calls)} |"
        )

    ast = ProjectASTBuilder().build(result)
    lines.extend(["", render_ast_markdown(ast), ""])

    graph = EngineeringKnowledgeGraphBuilder().build(result)
    lines.extend([render_knowledge_graph_markdown(graph), ""])

    devices = DeviceLogicAnalyzer().analyze_project(result)
    lines.extend([render_devices_markdown(devices), ""])

    state_analyzer = StateMachineAnalyzer()
    state_sections: list[str] = []
    for block in result.blocks:
        machines = state_analyzer.analyze(block.text)
        if machines:
            state_sections.append(render_state_machines_markdown(block.name, machines))

    lines.extend(["## 状态机分析", ""])
    if state_sections:
        for section in state_sections:
            lines.extend([section, ""])
    else:
        lines.extend(["未识别到典型 `CASE <state> OF` 状态机。", ""])

    alarm_analyzer = AlarmLogicAnalyzer()
    alarm_sections: list[str] = []
    alarm_count = 0
    for block in result.blocks:
        findings = alarm_analyzer.analyze(block.text)
        if findings:
            alarm_count += len(findings)
            alarm_sections.append(render_alarm_markdown(block.name, findings))

    lines.extend(["## 报警与联锁分析", "", f"- **识别条目：** {alarm_count}", ""])
    if alarm_sections:
        for section in alarm_sections:
            lines.extend([section, ""])
    else:
        lines.extend(["未识别到典型 Alarm/Fault/Warning/Interlock/Safety 赋值。", ""])

    lines.extend(
        [
            "## 颜色分级说明",
            "",
            "- **red**：Safety / Fault / Error / Trip 候选，需优先人工复核。",
            "- **orange**：Alarm 候选。",
            "- **yellow**：Interlock / Permissive / Inhibit 候选。",
            "- **blue**：Warning 候选。",
            "",
            "## 说明",
            "",
            "本功能面向从 TIA Portal 或项目库导出的 SCL 文本。它不会直接修改 `.zap16` 工程；自动生成的是独立、可审查的 `.scl` 文件。V0.9.3 增加统一工程知识图谱与双向定位索引；工程对象与代码行可互相追溯。状态机识别目前聚焦 CASE 型顺控；设备与报警分类均为规则级候选，不等同于安全认证结论，关键联锁和安全逻辑必须由 PLC 工程师人工复核。",
            "",
        ]
    )
    return "\n".join(lines)
