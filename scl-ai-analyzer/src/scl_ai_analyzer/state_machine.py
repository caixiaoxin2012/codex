from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class StateTransition:
    source: str
    target: str
    condition: str | None
    line_number: int


@dataclass(frozen=True)
class StateMachine:
    selector: str
    states: tuple[str, ...]
    transitions: tuple[StateTransition, ...]
    start_line: int


class StateMachineAnalyzer:
    """Detect common SCL CASE-based state machines conservatively.

    V0.9 focuses on patterns such as `CASE Step OF` with state arms and assignments
    back to the same selector variable. Complex indirect transitions are left for
    later semantic analysis.
    """

    _case_pattern = re.compile(
        r"\bCASE\s+(?P<selector>[#A-Za-z_][\w\.]*)\s+OF(?P<body>.*?)\bEND_CASE\s*;?",
        re.IGNORECASE | re.DOTALL,
    )
    _state_header = re.compile(
        r"(?m)^\s*(?P<label>(?:-?\d+)|(?:[A-Za-z_][\w\.]*))(?:\s*,\s*(?:-?\d+|[A-Za-z_][\w\.]*))*\s*:\s*"
    )
    _if_transition = re.compile(
        r"\bIF\s+(?P<condition>.*?)\s+THEN(?P<body>.*?)\bEND_IF\s*;?",
        re.IGNORECASE | re.DOTALL,
    )

    def analyze(self, text: str) -> tuple[StateMachine, ...]:
        clean = self._strip_comments(text)
        machines: list[StateMachine] = []
        for case_match in self._case_pattern.finditer(clean):
            selector = case_match.group("selector")
            body = case_match.group("body")
            headers = list(self._state_header.finditer(body))
            states: list[str] = []
            transitions: list[StateTransition] = []

            for index, header in enumerate(headers):
                state = header.group("label").strip()
                states.append(state)
                section_start = header.end()
                section_end = headers[index + 1].start() if index + 1 < len(headers) else len(body)
                section = body[section_start:section_end]
                absolute_section_offset = case_match.start("body") + section_start

                transitions.extend(
                    self._extract_transitions(
                        text=clean,
                        section=section,
                        selector=selector,
                        source_state=state,
                        absolute_offset=absolute_section_offset,
                    )
                )

            machines.append(
                StateMachine(
                    selector=selector,
                    states=tuple(dict.fromkeys(states)),
                    transitions=tuple(transitions),
                    start_line=self._line_number(clean, case_match.start()),
                )
            )
        return tuple(machines)

    def _extract_transitions(
        self,
        *,
        text: str,
        section: str,
        selector: str,
        source_state: str,
        absolute_offset: int,
    ) -> list[StateTransition]:
        transitions: list[StateTransition] = []
        assignment = re.compile(
            rf"{re.escape(selector)}\s*:=\s*(?P<target>[^;]+)\s*;",
            re.IGNORECASE,
        )
        covered: list[tuple[int, int]] = []

        for if_match in self._if_transition.finditer(section):
            condition = " ".join(if_match.group("condition").split())
            if_body = if_match.group("body")
            for match in assignment.finditer(if_body):
                target = match.group("target").strip()
                local_pos = if_match.start("body") + match.start()
                transitions.append(
                    StateTransition(
                        source=source_state,
                        target=target,
                        condition=condition,
                        line_number=self._line_number(text, absolute_offset + local_pos),
                    )
                )
            covered.append((if_match.start(), if_match.end()))

        for match in assignment.finditer(section):
            if any(start <= match.start() < end for start, end in covered):
                continue
            transitions.append(
                StateTransition(
                    source=source_state,
                    target=match.group("target").strip(),
                    condition=None,
                    line_number=self._line_number(text, absolute_offset + match.start()),
                )
            )

        return transitions

    @staticmethod
    def _line_number(text: str, offset: int) -> int:
        return text.count("\n", 0, offset) + 1

    @staticmethod
    def _strip_comments(text: str) -> str:
        text = re.sub(r"\(\*.*?\*\)", "", text, flags=re.DOTALL)
        return re.sub(r"//.*$", "", text, flags=re.MULTILINE)


def render_state_machines_markdown(block_name: str, machines: tuple[StateMachine, ...]) -> str:
    lines = [f"### {block_name}", ""]
    if not machines:
        lines.append("未识别到 CASE 状态机。")
        return "\n".join(lines)

    for index, machine in enumerate(machines, start=1):
        lines.extend(
            [
                f"#### 状态机 {index}: `{machine.selector}`",
                "",
                f"- 状态数量：{len(machine.states)}",
                f"- 起始行：{machine.start_line}",
                f"- 状态：{', '.join(machine.states) if machine.states else '-'}",
                "",
                "| 当前状态 | 下一状态 | 条件 | 行号 |",
                "|---|---|---|---:|",
            ]
        )
        if machine.transitions:
            for transition in machine.transitions:
                lines.append(
                    f"| {transition.source} | {transition.target} | {transition.condition or '无条件'} | {transition.line_number} |"
                )
        else:
            lines.append("| - | - | 未识别到状态跳转 | - |")
        lines.append("")

    return "\n".join(lines)
