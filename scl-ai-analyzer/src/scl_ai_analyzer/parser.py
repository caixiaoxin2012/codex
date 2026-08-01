from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


SECTION_NAMES = {
    "VAR_INPUT": "Input",
    "VAR_OUTPUT": "Output",
    "VAR_IN_OUT": "InOut",
    "VAR_TEMP": "Temp",
    "VAR": "Static",
}


@dataclass(frozen=True)
class Variable:
    section: str
    name: str
    data_type: str
    default: str | None = None
    comment: str | None = None


class SCLParser:
    """Small, conservative parser for common Siemens SCL declarations."""

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

    def parse_file(self, path: str | Path) -> list[Variable]:
        file_path = Path(path)
        if not file_path.is_file():
            raise FileNotFoundError(f"SCL file not found: {file_path}")

        text = file_path.read_text(encoding="utf-8-sig", errors="replace")
        return self.parse_text(text)

    def parse_text(self, text: str) -> list[Variable]:
        variables: list[Variable] = []

        for section_match in self._section_pattern.finditer(text):
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

    @staticmethod
    def _clean(value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


def render_markdown(source_name: str, variables: list[Variable]) -> str:
    lines = [
        f"# SCL 分析报告：{source_name}",
        "",
        "## 变量清单",
        "",
        "| 区域 | 变量名 | 数据类型 | 默认值 | 注释 |",
        "|---|---|---|---|---|",
    ]

    if not variables:
        lines.append("| - | - | - | - | 未识别到变量声明 |")
    else:
        for item in variables:
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
            "本报告由规则解析器生成。关键逻辑和安全相关结论仍需 PLC 工程师人工复核。",
            "",
        ]
    )
    return "\n".join(lines)


def _escape(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")
