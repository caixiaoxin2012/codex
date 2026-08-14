from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class AlarmFinding:
    category: str
    severity: str
    symbol: str
    expression: str
    line_number: int
    evidence: str


class AlarmLogicAnalyzer:
    """Detect common alarm, fault, warning, interlock and safety logic conservatively."""

    _assignment = re.compile(
        r'(?P<symbol>#?"?[A-Za-z_][\w\.]*"?)\s*:=\s*(?P<expr>[^;]+);',
        re.IGNORECASE,
    )
    _if_line = re.compile(r"\bIF\s+(?P<cond>.*?)\s+THEN", re.IGNORECASE)

    CATEGORY_KEYWORDS = {
        "SAFETY": ("SAFETY", "ESTOP", "E_STOP", "EMERGENCY", "SAFE"),
        "INTERLOCK": ("INTERLOCK", "PERMISSIVE", "INHIBIT", "BLOCK"),
        "FAULT": ("FAULT", "ERROR", "TRIP"),
        "ALARM": ("ALARM", "ALM"),
        "WARNING": ("WARNING", "WARN"),
    }

    SEVERITY_BY_CATEGORY = {
        "SAFETY": "red",
        "FAULT": "red",
        "ALARM": "orange",
        "INTERLOCK": "yellow",
        "WARNING": "blue",
    }

    def analyze(self, text: str) -> tuple[AlarmFinding, ...]:
        clean = self._strip_comments(text)
        findings: list[AlarmFinding] = []
        lines = clean.splitlines()

        for line_number, raw_line in enumerate(lines, start=1):
            match = self._assignment.search(raw_line)
            if not match:
                continue
            symbol = match.group("symbol").strip()
            expr = " ".join(match.group("expr").split())
            category = self._classify(symbol, expr)
            if category is None:
                continue
            findings.append(
                AlarmFinding(
                    category=category,
                    severity=self.SEVERITY_BY_CATEGORY[category],
                    symbol=symbol,
                    expression=expr,
                    line_number=line_number,
                    evidence=raw_line.strip(),
                )
            )

        return tuple(findings)

    def _classify(self, symbol: str, expression: str) -> str | None:
        haystack = f"{symbol} {expression}".upper()
        for category in ("SAFETY", "FAULT", "ALARM", "INTERLOCK", "WARNING"):
            if any(keyword in haystack for keyword in self.CATEGORY_KEYWORDS[category]):
                return category
        return None

    @staticmethod
    def _strip_comments(text: str) -> str:
        text = re.sub(r"\(\*.*?\*\)", "", text, flags=re.DOTALL)
        return re.sub(r"//.*$", "", text, flags=re.MULTILINE)


def render_alarm_markdown(block_name: str, findings: tuple[AlarmFinding, ...]) -> str:
    lines = [f"### {block_name}", ""]
    if not findings:
        lines.append("未识别到典型报警、故障、联锁或安全赋值。")
        return "\n".join(lines)

    lines.extend(
        [
            "| 等级 | 类别 | 信号 | 条件/表达式 | 行号 |",
            "|---|---|---|---|---:|",
        ]
    )
    for item in findings:
        lines.append(
            f"| {item.severity} | {item.category} | {item.symbol} | {item.expression} | {item.line_number} |"
        )
    return "\n".join(lines)
