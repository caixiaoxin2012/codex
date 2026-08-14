from __future__ import annotations

from dataclasses import dataclass

from .causal_chain import CausalChain, CausalChainAnalyzer
from .project import ProjectResult


@dataclass(frozen=True)
class FlowNarrative:
    block_name: str
    selector: str
    source_state: str
    target_state: str
    summary: str
    detail: str
    transition_line: int


class FlowNarrativeGenerator:
    """Convert traceable causal chains into concise Chinese engineering descriptions.

    The generator is deterministic: it only verbalizes facts already extracted from
    source code and does not invent process intent, safety meaning, or missing causes.
    """

    def generate_project(self, project: ProjectResult) -> tuple[FlowNarrative, ...]:
        return self.generate(CausalChainAnalyzer().analyze_project(project))

    def generate(self, chains: tuple[CausalChain, ...]) -> tuple[FlowNarrative, ...]:
        return tuple(self._describe(chain) for chain in chains)

    def _describe(self, chain: CausalChain) -> FlowNarrative:
        action_text = self._actions(chain)
        condition = chain.completion_condition or "无显式条件"
        alarm_text = self._alarms(chain)

        summary = (
            f"{chain.selector} 状态 {chain.source_state}：{action_text}；"
            f"当 {condition} 时转入状态 {chain.target_state}。"
        )
        detail_parts = [summary]
        if alarm_text:
            detail_parts.append(f"该状态代码段同时检测到 {alarm_text}。")
        detail_parts.append(f"状态跳转定位于第 {chain.transition_line} 行。")

        return FlowNarrative(
            block_name=chain.block_name,
            selector=chain.selector,
            source_state=chain.source_state,
            target_state=chain.target_state,
            summary=summary,
            detail="".join(detail_parts),
            transition_line=chain.transition_line,
        )

    @staticmethod
    def _actions(chain: CausalChain) -> str:
        parts: list[str] = []
        if chain.device_names:
            parts.append("操作设备 " + "、".join(chain.device_names))
        if chain.standard_blocks:
            parts.append("调用标准块 " + "、".join(chain.standard_blocks))
        assignments = [
            action.target for action in chain.actions
            if action.action_kind == "ASSIGNMENT"
        ]
        if assignments:
            parts.append("写入变量 " + "、".join(dict.fromkeys(assignments)))
        other_calls = [
            action.target for action in chain.actions
            if action.action_kind == "BLOCK_CALL"
        ]
        if other_calls:
            parts.append("调用 " + "、".join(dict.fromkeys(other_calls)))
        return "，".join(parts) if parts else "未识别到直接动作"

    @staticmethod
    def _alarms(chain: CausalChain) -> str:
        if not chain.alarms:
            return ""
        return "、".join(
            dict.fromkeys(f"{item.category} {item.symbol}" for item in chain.alarms)
        )


def render_flow_narratives_markdown(items: tuple[FlowNarrative, ...]) -> str:
    lines = ["## 自动流程说明", ""]
    if not items:
        lines.extend([
            "未生成流程说明：当前项目中没有可追溯的状态机因果链。",
            "",
        ])
        return "\n".join(lines)

    current_block: str | None = None
    for item in items:
        if item.block_name != current_block:
            current_block = item.block_name
            lines.extend([f"### {current_block}", ""])
        lines.append(
            f"- **{item.selector} / 状态 {item.source_state} → {item.target_state}：** {item.detail}"
        )
    lines.extend([
        "",
        "> 自动流程说明由可追溯代码关系确定性生成；未在代码中明确表达的工艺目的、设备安全含义和隐含因果不会自动补写。",
    ])
    return "\n".join(lines)
