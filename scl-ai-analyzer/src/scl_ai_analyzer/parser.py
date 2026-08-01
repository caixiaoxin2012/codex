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

CALL_KEYWORDS = {"IF", "ELSIF", "CASE", "FOR", "WHILE", "REPEAT", "RETURN"}
BUILTIN_TYPES = {
    "BOOL", "BYTE", "WORD", "DWORD", "LWORD", "SINT", "USINT", "INT", "UINT",
    "DINT", "UDINT", "LINT", "ULINT", "REAL", "LREAL", "CHAR", "WCHAR",
    "STRING", "WSTRING", "TIME", "LTIME", "DATE", "TIME_OF_DAY", "TOD",
    "DATE_AND_TIME", "DT", "DTL", "S5TIME", "TIMER", "COUNTER", "ANY", "VARIANT",
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
class InstanceInfo:
    name: str
    fb_type: str
    section: str


@dataclass(frozen=True)
class CallInfo:
    target: str
    line_number: int
    call_kind: str = "Direct"
    fb_type: str | None = None


@dataclass(frozen=True)
class AnalysisResult:
    source_name: str
    block: BlockInfo = field(default_factory=BlockInfo)
    variables: tuple[Variable, ...] = ()
    instances: tuple[InstanceInfo, ...] = ()
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
        r'^\s*(?P<names>"?[A-Za-z_][\w]*"?(?:\s*,\s*"?[A-Za-z_][\w]*"?)*)\s*:\s*'
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
        name: re.compile(rf"\b{name}\b", re.IGNORECASE)
        for name in ("IF", "ELSIF", "CASE", "FOR", "WHILE", "REPEAT")
    }

    def parse_file(self, path: str | Path) -> AnalysisResult:
        file_path = Path(path)
        if not file_path.is_file():
            raise FileNotFoundError(f"SCL file not found: {file_path}")
        text = file_path.read_text(encoding="utf-8-sig", errors="replace")
        return self.parse_text(text, source_name=file_path.name)

    def parse_text(self, text: str, source_name: str = "inline.scl") -> AnalysisResult:
        cleaned = self._strip_comments(text)
        variables = tuple(self._parse_variables(text))
        instances = tuple(self._detect_instances(variables))
        return AnalysisResult(
            source_name=source_name,
            block=self._parse_block(cleaned),
            variables=variables,
            instances=instances,
            control_flow={name: len(pattern.findall(cleaned)) for name, pattern in self._flow_patterns.items()},
            calls=tuple(self._parse_calls(cleaned, instances)),
        )

    def _parse_variables(self, text: str) -> list[Variable]:
        variables: list[Variable] = []
        for section_match in self._section_pattern.finditer(self._strip_block_comments(text)):
            section = SECTION_NAMES[section_match.group("header").upper()]
            for raw_line in section_match.group("body").splitlines():
                if not raw_line.strip() or raw_line.strip().startswith("//"):
                    continue
                match = self._variable_pattern.match(raw_line)
                if not match:
                    continue
                for raw_name in match.group("names").split(","):
                    variables.append(
                        Variable(
                            section=section,
                            name=raw_name.strip().strip('"'),
                            data_type=match.group("type").strip(),
                            default=self._clean(match.group("default")),
                            comment=self._clean(match.group("comment")),
                        )
                    )
        return variables

    def _detect_instances(self, variables: tuple[Variable, ...]) -> list[InstanceInfo]:
        instances: list[InstanceInfo] = []
        for item in variables:
            normalized_type = self._normalize_identifier(item.data_type)
            if item.section not in {"Static", "Temp"}:
                continue
            if normalized_type in BUILTIN_TYPES or normalized_type.startswith("ARRAY"):
                continue
            instances.append(InstanceInfo(name=item.name, fb_type=item.data_type, section=item.section))
        return instances

    def _parse_block(self, text: str) -> BlockInfo:
        match = self._block_pattern.search(text)
        if not match:
            return BlockInfo()
        return BlockInfo(
            block_type=match.group("type").upper(),
            name=match.group("name").strip(),
            return_type=self._clean(match.group("return")),
        )

    def _parse_calls(self, text: str, instances: tuple[InstanceInfo, ...]) -> list[CallInfo]:
        instance_map = {self._normalize_identifier(item.name): item for item in instances}
        calls: list[CallInfo] = []
        for line_number, raw_line in enumerate(text.splitlines(), start=1):
            match = self._call_pattern.match(raw_line)
            if not match:
                continue
            target = match.group("target").strip()
            normalized = self._normalize_identifier(target)
            if normalized in CALL_KEYWORDS:
                continue
            instance = instance_map.get(normalized)
            calls.append(
                CallInfo(
                    target=target,
                    line_number=line_number,
                    call_kind="FB Instance" if instance else "Direct",
                    fb_type=instance.fb_type if instance else None,
                )
            )
        return calls

    @staticmethod
    def _normalize_identifier(value: str) -> str:
        return value.lstrip("#").strip().strip('"').upper()

    @staticmethod
    def _strip_block_comments(text: str) -> str:
        return re.sub(r"\(\*.*?\*\)", "", text, flags=re.DOTALL)

    @classmethod
    def _strip_comments(cls, text: str) -> str:
        return re.sub(r"//.*$", "", cls._strip_block_comments(text), flags=re.MULTILINE)

    @staticmethod
    def _clean(value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


def render_markdown(result: AnalysisResult) -> str:
    section_counts = Counter(item.section for item in result.variables)
    call_counts = Counter((item.target, item.call_kind, item.fb_type) for item in result.calls)
    lines = [
        f"# SCL 分析报告：{result.source_name}", "", "## 程序块概览", "",
        f"- **块类型：** {result.block.block_type or '未识别'}",
        f"- **块名称：** {result.block.name or '未识别'}",
        f"- **返回类型：** {result.block.return_type or '-'}",
        f"- **变量总数：** {len(result.variables)}",
        f"- **FB 实例数：** {len(result.instances)}",
        f"- **调用点数量：** {len(result.calls)}", "",
        "## FB 实例", "", "| 实例名 | FB 类型 | 区域 |", "|---|---|---|",
    ]
    if result.instances:
        for item in result.instances:
            lines.append(f"| {_escape(item.name)} | {_escape(item.fb_type)} | {item.section} |")
    else:
        lines.append("| - | - | 未识别到 FB 实例 |")

    lines.extend(["", "## 变量分区统计", "", "| 区域 | 数量 |", "|---|---:|"])
    for section in ("Input", "Output", "InOut", "Static", "Temp"):
        lines.append(f"| {section} | {section_counts.get(section, 0)} |")

    lines.extend(["", "## 控制结构统计", "", "| 结构 | 数量 |", "|---|---:|"])
    for name in ("IF", "ELSIF", "CASE", "FOR", "WHILE", "REPEAT"):
        lines.append(f"| {name} | {result.control_flow.get(name, 0)} |")

    lines.extend(["", "## 调用关系", "", "| 被调用对象 | 调用类型 | FB 类型 | 调用次数 | 行号 |", "|---|---|---|---:|---|"])
    if not result.calls:
        lines.append("| - | - | - | 0 | 未识别到直接调用 |")
    else:
        keys = dict.fromkeys((item.target, item.call_kind, item.fb_type) for item in result.calls)
        for target, call_kind, fb_type in keys:
            line_numbers = ", ".join(str(item.line_number) for item in result.calls if (item.target, item.call_kind, item.fb_type) == (target, call_kind, fb_type))
            lines.append(f"| {_escape(target)} | {call_kind} | {_escape(fb_type or '-')} | {call_counts[(target, call_kind, fb_type)]} | {line_numbers} |")

    lines.extend(["", "## 变量清单", "", "| 区域 | 变量名 | 数据类型 | 默认值 | 注释 |", "|---|---|---|---|---|"])
    if result.variables:
        for item in result.variables:
            lines.append(f"| {_escape(item.section)} | {_escape(item.name)} | {_escape(item.data_type)} | {_escape(item.default or '')} | {_escape(item.comment or '')} |")
    else:
        lines.append("| - | - | - | - | 未识别到变量声明 |")

    lines.extend(["", "## 复核说明", "", "本报告由规则解析器生成。FB 实例依据变量声明和调用名称进行匹配；复杂多实例、数组实例、动态调用和跨文件类型解析仍需 PLC 工程师人工复核。", ""])
    return "\n".join(lines)


def _escape(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")
