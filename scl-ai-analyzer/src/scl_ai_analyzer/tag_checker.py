from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

from .project import ProjectResult, SourceBlock
from .variable_xref import VariableCrossReferenceAnalyzer


RULE_NAMING = "TAG_NAMING"
RULE_MISSING_COMMENT = "MISSING_COMMENT"
RULE_DUPLICATE = "DUPLICATE_VARIABLE"
RULE_UNUSED = "UNUSED_VARIABLE"


@dataclass(frozen=True)
class TagDeclaration:
    name: str
    normalized_name: str
    section: str
    data_type: str
    line_number: int
    comment: str | None


@dataclass(frozen=True)
class TagIssue:
    rule_id: str
    severity: str
    block_name: str
    block_type: str
    variable: str
    section: str
    data_type: str
    line_number: int
    message: str
    suggestion: str
    evidence: str = ""


@dataclass(frozen=True)
class TagCheckReport:
    issues: tuple[TagIssue, ...]
    checked_blocks: int
    checked_variables: int

    def count(self, rule_id: str) -> int:
        return sum(1 for item in self.issues if item.rule_id == rule_id)

    @property
    def severity_counts(self) -> dict[str, int]:
        return dict(Counter(item.severity for item in self.issues))


class TagChecker:
    """Conservative PLC tag/code-review checks for exported SCL projects.

    V0.11.0 intentionally starts with four traceable checks:
    naming quality, missing comments, duplicate declarations and unused variables.
    Results are rule based and keep exact block/line context so an AI explanation can
    summarize them without becoming the source of truth.
    """

    _section_header = re.compile(
        r"^\s*(VAR_INPUT|VAR_OUTPUT|VAR_IN_OUT|VAR_TEMP|VAR)\b",
        re.IGNORECASE,
    )
    _declaration = re.compile(
        r'^\s*(?P<names>"?[A-Za-z_][\w]*"?(?:\s*,\s*"?[A-Za-z_][\w]*"?)*)\s*:\s*'
        r'(?P<type>[^;:=]+?(?:\[[^\]]+\])?)\s*'
        r'(?:\:=\s*(?P<default>[^;]+))?\s*;'
        r'(?:\s*//\s*(?P<comment>.*))?$',
        re.IGNORECASE,
    )
    _valid_name = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
    _generic_name = re.compile(
        r"^(?:tag|var|variable|temp|tmp|data|value|test|newtag|newvariable|unnamed|signal|flag)\d*$",
        re.IGNORECASE,
    )
    _section_names = {
        "VAR_INPUT": "Input",
        "VAR_OUTPUT": "Output",
        "VAR_IN_OUT": "InOut",
        "VAR_TEMP": "Temp",
        "VAR": "Static",
    }

    def __init__(self) -> None:
        self._xref = VariableCrossReferenceAnalyzer()

    def check_project(self, project: ProjectResult) -> TagCheckReport:
        xref_cache = self._xref.build(project)
        issues: list[TagIssue] = []
        checked_variables = 0

        for block in project.blocks:
            declarations = self._declarations(block)
            checked_variables += len(declarations)
            grouped: dict[str, list[TagDeclaration]] = {}
            for declaration in declarations:
                grouped.setdefault(declaration.normalized_name, []).append(declaration)
                issues.extend(self._check_naming(block, declaration))
                if not declaration.comment:
                    issues.append(
                        TagIssue(
                            rule_id=RULE_MISSING_COMMENT,
                            severity="warning",
                            block_name=block.name,
                            block_type=block.block_type,
                            variable=declaration.name,
                            section=declaration.section,
                            data_type=declaration.data_type,
                            line_number=declaration.line_number,
                            message=f"变量 {declaration.name} 缺少工程注释。",
                            suggestion="补充变量用途、单位、来源/去向或工艺含义，避免只重复变量名。",
                        )
                    )

            for items in grouped.values():
                if len(items) <= 1:
                    continue
                first = items[0]
                lines = ", ".join(f"L{item.line_number}" for item in items)
                issues.append(
                    TagIssue(
                        rule_id=RULE_DUPLICATE,
                        severity="error",
                        block_name=block.name,
                        block_type=block.block_type,
                        variable=first.name,
                        section=first.section,
                        data_type=first.data_type,
                        line_number=first.line_number,
                        message=f"变量 {first.name} 在同一程序块中重复声明 {len(items)} 次。",
                        suggestion="确认是否为误复制；保留唯一声明并更新所有引用。",
                        evidence=lines,
                    )
                )

            # Unused is evaluated once per scoped variable through the existing xref layer.
            for normalized, items in grouped.items():
                first = items[0]
                xref = self._xref.lookup(
                    project,
                    first.name,
                    block_name=block.name,
                    cache=xref_cache,
                )
                if xref is not None and (xref.reads or xref.writes):
                    continue
                issues.append(
                    TagIssue(
                        rule_id=RULE_UNUSED,
                        severity="warning",
                        block_name=block.name,
                        block_type=block.block_type,
                        variable=first.name,
                        section=first.section,
                        data_type=first.data_type,
                        line_number=first.line_number,
                        message=f"变量 {first.name} 仅发现声明，未发现可追踪的读取或写入。",
                        suggestion="确认是否已废弃；若确实不用则删除，否则检查动态/间接访问是否超出当前解析能力。",
                    )
                )

        issues.sort(
            key=lambda item: (
                self._severity_rank(item.severity),
                item.block_name.casefold(),
                item.line_number,
                item.rule_id,
            )
        )
        return TagCheckReport(
            issues=tuple(issues),
            checked_blocks=len(project.blocks),
            checked_variables=checked_variables,
        )

    def _check_naming(self, block: SourceBlock, item: TagDeclaration) -> list[TagIssue]:
        reasons: list[str] = []
        name = item.name
        if not self._valid_name.fullmatch(name):
            reasons.append("名称不符合基础字母/数字/下划线格式")
        if name.startswith("_") or name.endswith("_") or "__" in name:
            reasons.append("存在前导/尾随/连续下划线")
        if self._generic_name.fullmatch(name):
            reasons.append("名称过于通用或像自动生成占位名")
        if len(name) < 2 and not (item.section == "Temp" and name.casefold() in {"i", "j", "k", "n"}):
            reasons.append("名称过短，难以表达工程含义")

        if not reasons:
            return []
        return [
            TagIssue(
                rule_id=RULE_NAMING,
                severity="warning",
                block_name=block.name,
                block_type=block.block_type,
                variable=name,
                section=item.section,
                data_type=item.data_type,
                line_number=item.line_number,
                message=f"变量 {name} 命名需要复核：" + "；".join(reasons) + "。",
                suggestion="使用稳定、可读、能体现设备/动作/状态含义的工程名称；企业前缀规范可在后续版本配置化。",
            )
        ]

    def _declarations(self, block: SourceBlock) -> tuple[TagDeclaration, ...]:
        result: list[TagDeclaration] = []
        current_section: str | None = None
        pending_comment: str | None = None

        for line_number, raw_line in enumerate(block.text.splitlines(), start=1):
            stripped = raw_line.strip()
            header = self._section_header.match(raw_line)
            if header:
                current_section = self._section_names[header.group(1).upper()]
                pending_comment = None
                continue
            if current_section and re.match(r"^\s*END_VAR\b", raw_line, flags=re.IGNORECASE):
                current_section = None
                pending_comment = None
                continue
            if not current_section:
                continue
            if not stripped:
                pending_comment = None
                continue
            if stripped.startswith("//"):
                pending_comment = stripped[2:].strip() or None
                continue

            match = self._declaration.match(raw_line)
            if not match:
                continue
            inline_comment = (match.group("comment") or "").strip() or None
            comment = inline_comment or pending_comment
            data_type = match.group("type").strip()
            for raw_name in match.group("names").split(","):
                name = raw_name.strip().strip('"')
                result.append(
                    TagDeclaration(
                        name=name,
                        normalized_name=name.casefold(),
                        section=current_section,
                        data_type=data_type,
                        line_number=line_number,
                        comment=comment,
                    )
                )
            pending_comment = None

        return tuple(result)

    @staticmethod
    def _severity_rank(value: str) -> int:
        return {"error": 0, "warning": 1, "info": 2}.get(value.casefold(), 9)


def render_tag_check_markdown(report: TagCheckReport) -> str:
    counts = {
        RULE_NAMING: report.count(RULE_NAMING),
        RULE_MISSING_COMMENT: report.count(RULE_MISSING_COMMENT),
        RULE_DUPLICATE: report.count(RULE_DUPLICATE),
        RULE_UNUSED: report.count(RULE_UNUSED),
    }
    lines = [
        "## PLC Code Review：变量质量检查",
        "",
        f"- **检查程序块：** {report.checked_blocks}",
        f"- **检查变量声明：** {report.checked_variables}",
        f"- **发现问题：** {len(report.issues)}",
        "",
        "| 检查项 | 数量 |",
        "|---|---:|",
        f"| 变量命名 | {counts[RULE_NAMING]} |",
        f"| 缺失注释 | {counts[RULE_MISSING_COMMENT]} |",
        f"| 重复变量 | {counts[RULE_DUPLICATE]} |",
        f"| 未使用变量 | {counts[RULE_UNUSED]} |",
        "",
        "| 严重度 | 规则 | 程序块 | 变量 | 区域 | 行号 | 问题 | 建议 |",
        "|---|---|---|---|---|---:|---|---|",
    ]
    if not report.issues:
        lines.append("| - | - | - | - | - | - | 当前四类规则未发现问题 | - |")
    else:
        for item in report.issues:
            lines.append(
                f"| {item.severity} | {item.rule_id} | {_escape(item.block_name)} | {_escape(item.variable)} "
                f"| {item.section} | {item.line_number} | {_escape(item.message)} | {_escape(item.suggestion)} |"
            )
    lines.extend(
        [
            "",
            "> 未使用变量基于当前可追踪的静态读写关系判断；反射、动态访问、外部 HMI/OPC 绑定等场景需人工复核。",
        ]
    )
    return "\n".join(lines)


def _escape(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")
