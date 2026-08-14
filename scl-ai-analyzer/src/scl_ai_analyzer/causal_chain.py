from __future__ import annotations

import re
from dataclasses import dataclass

from .alarm_logic import AlarmFinding, AlarmLogicAnalyzer
from .project import ProjectResult, SourceBlock
from .state_actions import StateAction, StateActionAnalyzer
from .state_machine import StateMachineAnalyzer, StateTransition


@dataclass(frozen=True)
class CausalChain:
    block_name: str
    selector: str
    source_state: str
    actions: tuple[StateAction, ...]
    device_names: tuple[str, ...]
    standard_blocks: tuple[str, ...]
    completion_condition: str | None
    target_state: str
    transition_line: int
    alarms: tuple[AlarmFinding, ...] = ()


class CausalChainAnalyzer:
    """Build conservative state -> action -> device -> condition -> next-state chains.

    Alarm/interlock findings are attached only when their source line falls inside the
    same CASE state arm. This keeps the result traceable and avoids inventing process
    causality that is not present in the source code.
    """

    _case_pattern = re.compile(
        r"\bCASE\s+(?P<selector>[#A-Za-z_][\w\.]*)\s+OF(?P<body>.*?)\bEND_CASE\s*;?",
        re.IGNORECASE | re.DOTALL,
    )
    _state_header = re.compile(
        r"(?m)^\s*(?P<label>(?:-?\d+)|(?:[A-Za-z_][\w\.]*))(?:\s*,\s*(?:-?\d+|[A-Za-z_][\w\.]*))*\s*:\s*"
    )

    def analyze_project(self, project: ProjectResult) -> tuple[CausalChain, ...]:
        chains: list[CausalChain] = []
        for block in project.blocks:
            chains.extend(self.analyze_block(block))
        return tuple(chains)

    def analyze_block(self, block: SourceBlock) -> tuple[CausalChain, ...]:
        machines = StateMachineAnalyzer().analyze(block.text)
        actions = StateActionAnalyzer().analyze_block(block)
        alarms = AlarmLogicAnalyzer().analyze(block.text)
        ranges = self._state_ranges(block.text)
        result: list[CausalChain] = []

        for machine in machines:
            for transition in machine.transitions:
                state_actions = tuple(
                    item for item in actions
                    if self._norm(item.selector) == self._norm(machine.selector)
                    and self._norm(item.state) == self._norm(transition.source)
                )
                state_range = ranges.get((self._norm(machine.selector), self._norm(transition.source)))
                state_alarms: tuple[AlarmFinding, ...] = ()
                if state_range:
                    start_line, end_line = state_range
                    state_alarms = tuple(
                        finding for finding in alarms
                        if start_line <= finding.line_number <= end_line
                    )

                devices = tuple(dict.fromkeys(
                    item.device_name for item in state_actions if item.device_name
                ))
                standard_blocks = tuple(dict.fromkeys(
                    item.standard_block for item in state_actions if item.standard_block
                ))
                result.append(
                    CausalChain(
                        block_name=block.name,
                        selector=machine.selector,
                        source_state=transition.source,
                        actions=state_actions,
                        device_names=devices,
                        standard_blocks=standard_blocks,
                        completion_condition=transition.condition,
                        target_state=transition.target,
                        transition_line=transition.line_number,
                        alarms=state_alarms,
                    )
                )
        return tuple(result)

    def _state_ranges(self, text: str) -> dict[tuple[str, str], tuple[int, int]]:
        clean = self._strip_comments(text)
        ranges: dict[tuple[str, str], tuple[int, int]] = {}
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
                ranges[(self._norm(selector), self._norm(state))] = (
                    self._line_number(clean, start_offset),
                    self._line_number(clean, end_offset),
                )
        return ranges

    @staticmethod
    def _line_number(text: str, offset: int) -> int:
        return text.count("\n", 0, offset) + 1

    @staticmethod
    def _norm(value: str) -> str:
        return value.strip().strip('"').lstrip("#").casefold()

    @staticmethod
    def _strip_comments(text: str) -> str:
        text = re.sub(r"\(\*.*?\*\)", "", text, flags=re.DOTALL)
        return re.sub(r"//.*$", "", text, flags=re.MULTILINE)


def render_causal_chains_markdown(chains: tuple[CausalChain, ...]) -> str:
    lines = [
        "## 状态机工程因果链",
        "",
        "| 程序块 | 当前状态 | 动作 | 设备 | 标准块 | 完成/跳转条件 | 下一状态 | 报警/联锁 | 行号 |",
        "|---|---|---|---|---|---|---|---|---:|",
    ]
    if not chains:
        lines.append("| - | - | - | - | - | - | - | 未识别到因果链 | - |")
        return "\n".join(lines)

    for chain in chains:
        actions = "; ".join(f"{item.action_kind}:{item.target}" for item in chain.actions) or "-"
        devices = ", ".join(chain.device_names) or "-"
        standards = ", ".join(chain.standard_blocks) or "-"
        alarms = "; ".join(
            f"{item.category}:{item.symbol}" for item in chain.alarms
        ) or "-"
        lines.append(
            f"| {chain.block_name} | {chain.source_state} | {actions} | {devices} | {standards} "
            f"| {chain.completion_condition or '无条件'} | {chain.target_state} | {alarms} | {chain.transition_line} |"
        )
    lines.extend([
        "",
        "> 因果链只连接代码中可追溯的状态动作、跳转条件和同状态段报警/联锁；它是工程分析候选，不替代工艺与安全设计复核。",
    ])
    return "\n".join(lines)
