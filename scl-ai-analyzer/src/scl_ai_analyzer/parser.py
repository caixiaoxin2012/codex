from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path


SECTION_NAMES = {
    "VAR_INPUT": "Input",
    "VAR_OUTPUT": "Output",
    "VAR_IN_OUT": "InOut",
    "VAR_TEMP": "Temp",
    "VAR": "Static",
}

CALL_KEYWORDS = {
    "IF",
    "ELSIF",
    "CASE",
    "FOR",
    "WHILE",
    "REPEAT",
    "RETURN",
}


@dataclass(frozen=True)
class Variable:
    section: str
    name: str
    data_type: str
    default: str | None = None
    comment: str | None = None


@dataclass(frozen=True)
class BlockInfo:
    block_type: str | None = None
    name: str | None = None
    return_type: str | None = None


@dataclass(frozen=True)
class CallInfo:
    target: str
    line_number: int


@dataclass(frozen=True)
class AnalysisResult:
    source_name: str
    block: BlockInfo = field(default_factory=BlockInfo)
    variables: tuple[Variable, ...] = ()
    control_flow: dict[str, int] = field(default_factory=dict)
    calls: tuple[CallInfo, ...] = ()


class SCLParser:
    """Conservative parser for common Siemens SCL declarations and structure."""

    _section_pattern = re.compile(
        r"(?P<header>VAR_INPUT|VAR_OUTPUT|VAR_IN_OUT|VAR_TEMP|VAR)\b"
        r"(?P<body>.*?)END_VAR",
        re.IGNORECASE | re.DOTALL,
    )

    _variable_pattern = re.compile(
        r'^\s*"?(?P<name>[A-Za-z_][\w]*)"?\s*:\s*'
        r"(?P<type>[^;:=]+?(?:\[[^\]]+\])?)\s*"
        r"(?:\:=\s*(?P<default>[^;]+))?\s*;"
        r"(?:\s*//\s*(?P<comment>.*))?$",
        re.IGNORECASE,
    )

    _block_pattern = re.compile(
        r'^\s*(?P<type>FUNCTION_BLOCK|FUNCTION|ORGANIZATION_BLOCK|DATA_BLOCK)\s+'
        r'"?(?P<name>[A-Za-z_][\w]*)"?'
        r'(?:\s*:\s*(?P<return>[^\r\n]+?))?\s*$',
        re.IGNORECASE | re.MULTILINE,
    )

    _call_pattern = re.compile(
        r'^\s*(?P<target>(?:#?"[^"]+")|(?:#?[A-Za-z_][\w\.]*))\s*\(',
        re.IGNORECASE,
    )

    _flow_patterns = {
        "IF": re.compile(r"\bIF\b", re.IGNORECASE),
        "ELSIF": re.compile(r"\bELSIF\b", re.IGNORECASE),
        "CASE": re.compile(r"\bCASE\b", re.IGNORECASE),
        "FOR": re.compile(r"\bFOR\b", re.IGNORECASE),
        "WHILE": re.compile(r"\bWHILE\b", re.IGNORECASE),
        "REPEAT": re.compile(r"\bREPEAT\b", re.IGNORECASE),
    }

    def parse_file(self, path: str | Path) -> AnalysisResult:
        file_path = Path(path)
        if not file_path.is_file():
            raise FileNotFoundError(f"SCL file not found: {file_path}")

        text = file_path.read_text(encoding="utf-8-sig", errors="replace")
        return self.parse_text(text, source_name=file_path.name)

    def parse_text(self, text: str, source_name: str = "inline.scl") -> AnalysisResult:
        cleaned = self._strip_comments(text)
        block = self._parse_block(cleaned)
        variables = tuple(self._parse_variables(text))
        control_flow = {
            name: len(pattern.findall(cleaned))
            for name, pattern in self._flow_patterns.items()
        }
        calls = tuple(self._parse_calls(cleaned))
        return AnalysisResult(
            source_name=source_name,
            block=block,
            variables=variables,
            control_flow=control_flow,
            calls=calls,
        )

    def _parse_variables(self, text: str) -> list[Variable]:
        text_without_blocks = self._strip_block_comments(text)
        variables: list[Variable] = []
        for section_match in self._section_pattern.finditer(text_without_blocks):
            header = section_match.group("header").upper()
            section = SECTION_NAMES[header]
            body = section_match.group("body")

            for raw_line in body.splitlines():
                line = raw_line.strip()
                if not line or line.startswith("//"):
                    continue
                match = self._variable_pattern.match(raw_line)
                if not match:
                    continue
                variables.append(
                    Variable(
                        section=section,
                        name=match.group("name").strip(),
                        data_type=match.group("type").strip(),
                        default=self._clean(match.group("default")),
                        comment=self._clean(match.group("comment")),
                    )
                )
        return variables

    def _parse_block(self, text: str) -> BlockInfo:
        match = self._block_pattern.search(text)
        if not match:
            return BlockInfo()
        return BlockInfo(
            block_type=match.group("type").upper(),
            name=match.group("name").strip(),
            return_type=self._clean(match.group("return")),
        )

    def _parse_calls(self, text: str) -> list[CallInfo]:
        calls: list[CallInfo] = []
        for line_number, raw_line in enumerate(text.splitlines(), start=1):
            match = self._call_pattern.match(raw_line)
            if not match:
                continue
            target = match.group("target").strip()
            normalized = target.lstrip("#").strip('"').upper()
            if normalized in CALL_KEYWORDS:
                continue
            calls.append(CallInfo(target=target, line_number=line_number))
        return calls

    @staticmethod
    def _strip_block_comments(text: str) -> str:
        return re.sub(r"\(\*.*?\*\)", "", text, flags=re.DOTALL)

    @classmethod
    def _strip_comments(cls, text: str) -> str:
        without_blocks = cls._strip_block_comments(text)
        return re.sub(r"//.*$", "", without_blocks, flags=re.MULTILINE)

    @staticmethod
    def _clean(value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


def render_markdown(result: AnalysisResult) -> str:
    section_counts = Counter(item.section for item in result.variables)
    call_counts = Counter(item.target for item in result.calls)
    block_name = result.block.name or "未识别"
    block_type = result.block.block_type or "未识别"

    lines = [
        f"# SCL 分析报告：{result.source_name}",
        "",
        "## 程序块概览",
        "",
        f"- **块类型：** {block_type}",
        f"- **块名称：** {block_name}",
        f"- **返回类型：** {result.block.return_type or '-'}",
        f"- **变量总数：** {len(result.variables)}",
        f"- **调用点数量：** {len(result.calls)}",
        "",
        "## 变量分区统计",
        "",
        "| 区域 | 数量 |",
        "|---|---:|",
    ]

    for section in ("Input", "Output", "InOut", "Static", "Temp"):
        lines.append(f"| {section} | {section_counts.get(section, 0)} |")

    lines.extend(
        [
            "",
            "## 控制结构统计",
            "",
            "| 结构 | 数量 |",
            "|---|---:|",
        ]
    )
    for name in ("IF", "ELSIF", "CASE", "FOR", "WHILE", "REPEAT"):
        lines.append(f"| {name} | {result.control_flow.get(name, 0)} |")

    lines.extend(
        [
            "",
            "## 调用关系",
            "",
            "| 被调用对象 | 调用次数 | 行号 |",
            "|---|---:|---|",
        ]
    )
    if not result.calls:
        lines.append("| - | 0 | 未识别到直接调用 |")
    else:
        for target in dict.fromkeys(item.target for item in result.calls):
            line_numbers = ", ".join(
                str(item.line_number) for item in result.calls if item.target == target
            )
            lines.append(
                f"| {_escape(target)} | {call_counts[target]} | {line_numbers} |"
            )

    lines.extend(
        [
            "",
            "## 变量清单",
            "",
            "| 区域 | 变量名 | 数据类型 | 默认值 | 注释 |",
            "|---|---|---|---|---|",
        ]
    )

    if not result.variables:
        lines.append("| - | - | - | - | 未识别到变量声明 |")
    else:
        for item in result.variables:
            lines.append(
                "| {section} | {name} | {type} | {default} | {comment} |".format(
                    section=_escape(item.section),
                    name=_escape(item.name),
                    type=_escape(item.data_type),
                    default=_escape(item.default or ""),
                    comment=_escape(item.comment or ""),
                )
            )

    lines.extend(
        [
            "",
            "## 复核说明",
            "",
            "本报告由规则解析器生成。调用关系仅识别独立语句形式的直接调用；动态调用、复杂表达式和跨文件语义仍需 PLC 工程师人工复核。",
            "",
        ]
    )
    return "\n".join(lines)


def _escape(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")
