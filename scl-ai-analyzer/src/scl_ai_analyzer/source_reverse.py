from __future__ import annotations

import re
from dataclasses import dataclass

from .alarm_logic import AlarmLogicAnalyzer
from .causal_chain import CausalChainAnalyzer
from .device_logic import DeviceLogicAnalyzer
from .project import SourceBlock
from .standard_library import StandardLibraryAnalyzer
from .state_machine import StateMachineAnalyzer


@dataclass(frozen=True)
class ReverseLink:
    line_number: int
    kind: str
    name: str
    detail: str
    source_line: str


class ReverseSourceIndex:
    """Build a traceable source-line -> engineering-object index for one block."""

    _identifier = re.compile(r'#?"?[A-Za-z_][\w\.]*"?')
    _case_pattern = re.compile(
        r"\bCASE\s+(?P<selector>[#A-Za-z_][\w\.]*)\s+OF(?P<body>.*?)\bEND_CASE\s*;?",
        re.IGNORECASE | re.DOTALL,
    )
    _state_header = re.compile(
        r"(?m)^\s*(?P<label>(?:-?\d+)|(?:[A-Za-z_][\w\.]*))(?:\s*,\s*(?:-?\d+|[A-Za-z_][\w\.]*))*\s*:\s*"
    )

    def build(self, block: SourceBlock) -> dict[int, tuple[ReverseLink, ...]]:
        lines = block.text.splitlines()
        index: dict[int, list[ReverseLink]] = {}

        def add(line: int, kind: str, name: str, detail: str) -> None:
            if line < 1 or line > len(lines):
                return
            link = ReverseLink(line, kind, name, detail, lines[line - 1].strip())
            bucket = index.setdefault(line, [])
            key = (kind.casefold(), name.casefold(), detail.casefold())
            if not any((item.kind.casefold(), item.name.casefold(), item.detail.casefold()) == key for item in bucket):
                bucket.append(link)

        # Variable usages: declaration and reference occurrences are both useful to engineers.
        variables = {self._norm(item.name): item for item in block.analysis.variables}
        for line_number, raw_line in enumerate(lines, start=1):
            identifiers = {self._norm(value) for value in self._identifier.findall(raw_line)}
            for identifier in identifiers:
                variable = variables.get(identifier)
                if variable:
                    add(
                        line_number,
                        "VARIABLE",
                        variable.name,
                        f"{variable.section} / {variable.data_type}",
                    )

        for call in block.analysis.calls:
            add(
                call.line_number,
                "CALL",
                call.target,
                call.call_kind + (f" / {call.fb_type}" if call.fb_type else ""),
            )

        for finding in AlarmLogicAnalyzer().analyze(block.text):
            add(
                finding.line_number,
                "ALARM",
                finding.symbol,
                f"{finding.category} / {finding.severity} / {finding.expression}",
            )

        for use in StandardLibraryAnalyzer().analyze_block(block):
            add(
                use.line_number,
                "STANDARD_BLOCK",
                use.canonical_name,
                f"{use.family} / {use.purpose}",
            )

        for device in DeviceLogicAnalyzer().analyze_block(block):
            device_name = device.instance_name or device.block_name
            evidence_lines = {item.line_number for item in device.evidence if item.line_number}
            for line_number in evidence_lines:
                add(
                    line_number,
                    "DEVICE",
                    device_name,
                    f"{device.device_type} / confidence={device.confidence}",
                )

        for machine in StateMachineAnalyzer().analyze(block.text):
            add(machine.start_line, "STATE_MACHINE", machine.selector, f"states={len(machine.states)}")
            for transition in machine.transitions:
                add(
                    transition.line_number,
                    "STATE_TRANSITION",
                    f"{transition.source} -> {transition.target}",
                    transition.condition or "无条件",
                )

        # Also map every line inside a CASE state arm to the owning state.
        for selector, state, start_line, end_line in self._state_ranges(block.text):
            for line_number in range(start_line, end_line + 1):
                add(line_number, "STATE", state, f"selector={selector}")

        for chain in CausalChainAnalyzer().analyze_block(block):
            detail = (
                f"state {chain.source_state} -> {chain.target_state}; "
                f"condition={chain.completion_condition or '无条件'}"
            )
            add(chain.transition_line, "CAUSAL_CHAIN", chain.source_state, detail)
            for action in chain.actions:
                add(
                    action.line_number,
                    "CAUSAL_ACTION",
                    action.target,
                    f"state={chain.source_state}; kind={action.action_kind}",
                )

        return {line: tuple(items) for line, items in index.items()}

    def links_at(self, block: SourceBlock, line_number: int) -> tuple[ReverseLink, ...]:
        return self.build(block).get(line_number, ())

    def _state_ranges(self, text: str) -> tuple[tuple[str, str, int, int], ...]:
        clean = self._strip_comments_preserve_lines(text)
        ranges: list[tuple[str, str, int, int]] = []
        for case_match in self._case_pattern.finditer(clean):
            selector = case_match.group("selector")
            body = case_match.group("body")
            headers = list(self._state_header.finditer(body))
            for index, header in enumerate(headers):
                state = header.group("label").strip()
                start_offset = case_match.start("body") + header.start()
                end_offset = (
                    case_match.start("body") + headers[index + 1].start() - 1
                    if index + 1 < len(headers)
                    else case_match.start("body") + len(body)
                )
                ranges.append(
                    (
                        selector,
                        state,
                        self._line_number(clean, start_offset),
                        self._line_number(clean, end_offset),
                    )
                )
        return tuple(ranges)

    @staticmethod
    def _line_number(text: str, offset: int) -> int:
        return text.count("\n", 0, offset) + 1

    @staticmethod
    def _norm(value: str) -> str:
        return value.strip().strip('"').lstrip("#").casefold()

    @staticmethod
    def _strip_comments_preserve_lines(text: str) -> str:
        def block_replacer(match: re.Match[str]) -> str:
            value = match.group(0)
            return "".join("\n" if char == "\n" else " " for char in value)

        text = re.sub(r"\(\*.*?\*\)", block_replacer, text, flags=re.DOTALL)
        return re.sub(r"//.*$", lambda match: " " * len(match.group(0)), text, flags=re.MULTILINE)
