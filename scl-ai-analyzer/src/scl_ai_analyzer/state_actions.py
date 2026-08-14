from __future__ import annotations

import re
from dataclasses import dataclass

from .device_logic import DeviceLogicAnalyzer
from .project import ProjectResult, SourceBlock
from .standard_library import StandardLibraryAnalyzer


@dataclass(frozen=True)
class StateAction:
    block_name: str
    selector: str
    state: str
    action_kind: str
    target: str
    line_number: int
    device_name: str | None = None
    device_type: str | None = None
    standard_block: str | None = None
    standard_family: str | None = None


class StateActionAnalyzer:
    """Extract direct actions inside CASE state arms and link them to engineering objects."""

    _case_pattern = re.compile(
        r"\bCASE\s+(?P<selector>[#A-Za-z_][\w\.]*)\s+OF(?P<body>.*?)\bEND_CASE\s*;?",
        re.IGNORECASE | re.DOTALL,
    )
    _state_header = re.compile(
        r"(?m)^\s*(?P<label>(?:-?\d+)|(?:[A-Za-z_][\w\.]*))(?:\s*,\s*(?:-?\d+|[A-Za-z_][\w\.]*))*\s*:\s*"
    )
    _call_pattern = re.compile(
        r'^\s*(?P<target>(?:#?"[^"]+")|(?:#?[A-Za-z_][\w\.]*))\s*\(',
        re.IGNORECASE,
    )
    _assignment_pattern = re.compile(
        r'^\s*(?P<target>#?"?[A-Za-z_][\w\.]*"?)\s*:=\s*(?P<expr>[^;]+);',
        re.IGNORECASE,
    )

    def analyze_project(self, project: ProjectResult) -> tuple[StateAction, ...]:
        result: list[StateAction] = []
        for block in project.blocks:
            result.extend(self.analyze_block(block))
        return tuple(result)

    def analyze_block(self, block: SourceBlock) -> tuple[StateAction, ...]:
        clean = self._strip_comments(block.text)
        device_map = self._device_map(block)
        actions: list[StateAction] = []

        for case_match in self._case_pattern.finditer(clean):
            selector = case_match.group("selector")
            body = case_match.group("body")
            headers = list(self._state_header.finditer(body))
            for index, header in enumerate(headers):
                state = header.group("label").strip()
                start = header.end()
                end = headers[index + 1].start() if index + 1 < len(headers) else len(body)
                section = body[start:end]
                absolute_start = case_match.start("body") + start

                for local_line, raw_line in enumerate(section.splitlines(), start=0):
                    stripped = raw_line.strip()
                    if not stripped:
                        continue
                    offset = self._line_offset(section, local_line)
                    line_number = self._line_number(clean, absolute_start + offset)

                    call_match = self._call_pattern.match(raw_line)
                    if call_match:
                        target = call_match.group("target").strip()
                        normalized = self._norm(target)
                        device = device_map.get(normalized)
                        spec = StandardLibraryAnalyzer.lookup(target)
                        if device:
                            actions.append(
                                StateAction(
                                    block_name=block.name,
                                    selector=selector,
                                    state=state,
                                    action_kind="DEVICE_CALL",
                                    target=target,
                                    line_number=line_number,
                                    device_name=device[0],
                                    device_type=device[1],
                                )
                            )
                        elif spec:
                            actions.append(
                                StateAction(
                                    block_name=block.name,
                                    selector=selector,
                                    state=state,
                                    action_kind="STANDARD_BLOCK_CALL",
                                    target=target,
                                    line_number=line_number,
                                    standard_block=spec.name,
                                    standard_family=spec.family,
                                )
                            )
                        else:
                            actions.append(
                                StateAction(
                                    block_name=block.name,
                                    selector=selector,
                                    state=state,
                                    action_kind="BLOCK_CALL",
                                    target=target,
                                    line_number=line_number,
                                )
                            )
                        continue

                    assignment = self._assignment_pattern.match(raw_line)
                    if assignment:
                        target = assignment.group("target").strip()
                        # State-selector assignments represent transitions and are already modeled elsewhere.
                        if self._norm(target) == self._norm(selector):
                            continue
                        actions.append(
                            StateAction(
                                block_name=block.name,
                                selector=selector,
                                state=state,
                                action_kind="ASSIGNMENT",
                                target=target,
                                line_number=line_number,
                            )
                        )

        return tuple(actions)

    @staticmethod
    def _device_map(block: SourceBlock) -> dict[str, tuple[str, str]]:
        result: dict[str, tuple[str, str]] = {}
        for device in DeviceLogicAnalyzer().analyze_block(block):
            if not device.instance_name:
                continue
            result[StateActionAnalyzer._norm(device.instance_name)] = (
                device.instance_name,
                device.device_type,
            )
        return result

    @staticmethod
    def _line_offset(section: str, zero_based_line: int) -> int:
        if zero_based_line <= 0:
            return 0
        offset = 0
        for _ in range(zero_based_line):
            next_break = section.find("\n", offset)
            if next_break < 0:
                return len(section)
            offset = next_break + 1
        return offset

    @staticmethod
    def _line_number(text: str, offset: int) -> int:
        return text.count("\n", 0, offset) + 1

    @staticmethod
    def _norm(value: str) -> str:
        return value.strip().lstrip("#").strip('"').casefold()

    @staticmethod
    def _strip_comments(text: str) -> str:
        text = re.sub(r"\(\*.*?\*\)", "", text, flags=re.DOTALL)
        return re.sub(r"//.*$", "", text, flags=re.MULTILINE)


def render_state_actions_markdown(actions: tuple[StateAction, ...]) -> str:
    lines = [
        "## 状态机动作关联",
        "",
        "| 程序块 | 状态变量 | 状态 | 动作类型 | 目标 | 关联设备/标准块 | 行号 |",
        "|---|---|---|---|---|---|---:|",
    ]
    if not actions:
        lines.append("| - | - | - | - | - | 未识别到可关联动作 | - |")
        return "\n".join(lines)

    for item in actions:
        linked = "-"
        if item.device_name:
            linked = f"{item.device_name} ({item.device_type})"
        elif item.standard_block:
            linked = f"{item.standard_block} ({item.standard_family})"
        lines.append(
            f"| {item.block_name} | {item.selector} | {item.state} | {item.action_kind} | {item.target} | {linked} | {item.line_number} |"
        )
    return "\n".join(lines)
