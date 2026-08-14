from __future__ import annotations

from dataclasses import dataclass

from .project import ProjectResult, SourceBlock


@dataclass(frozen=True)
class StandardBlockSpec:
    name: str
    family: str
    purpose: str
    interface_roles: tuple[str, ...] = ()


@dataclass(frozen=True)
class StandardBlockUse:
    owner_block: str
    called_name: str
    canonical_name: str
    family: str
    purpose: str
    interface_roles: tuple[str, ...]
    line_number: int


# Conservative catalog: it describes engineering intent, not a complete Siemens API contract.
STANDARD_BLOCKS: dict[str, StandardBlockSpec] = {
    "MC_POWER": StandardBlockSpec(
        "MC_Power", "MotionControl", "Enable or disable axis power/technology-object readiness.",
        ("Axis", "Enable", "Status", "Busy", "Error", "ErrorID"),
    ),
    "MC_HOME": StandardBlockSpec(
        "MC_Home", "MotionControl", "Reference/home a motion axis.",
        ("Axis", "Execute", "Position", "Done", "Busy", "Error", "ErrorID"),
    ),
    "MC_MOVEABSOLUTE": StandardBlockSpec(
        "MC_MoveAbsolute", "MotionControl", "Command an axis to an absolute position.",
        ("Axis", "Execute", "Position", "Velocity", "Done", "Busy", "Active", "Error", "ErrorID"),
    ),
    "MC_MOVERELATIVE": StandardBlockSpec(
        "MC_MoveRelative", "MotionControl", "Command an axis by a relative distance.",
        ("Axis", "Execute", "Distance", "Velocity", "Done", "Busy", "Active", "Error", "ErrorID"),
    ),
    "MC_MOVEVELOCITY": StandardBlockSpec(
        "MC_MoveVelocity", "MotionControl", "Command continuous axis motion at a target velocity.",
        ("Axis", "Execute", "Velocity", "InVelocity", "Busy", "Active", "Error", "ErrorID"),
    ),
    "MC_STOP": StandardBlockSpec(
        "MC_Stop", "MotionControl", "Stop a motion axis using a controlled stop command.",
        ("Axis", "Execute", "Done", "Busy", "Error", "ErrorID"),
    ),
    "MC_HALT": StandardBlockSpec(
        "MC_Halt", "MotionControl", "Halt an axis while allowing later motion commands.",
        ("Axis", "Execute", "Done", "Busy", "Error", "ErrorID"),
    ),
    "MC_RESET": StandardBlockSpec(
        "MC_Reset", "MotionControl", "Acknowledge/reset motion technology-object errors.",
        ("Axis", "Execute", "Done", "Busy", "Error", "ErrorID"),
    ),
    "PID_COMPACT": StandardBlockSpec(
        "PID_Compact", "PID", "Closed-loop PID controller for common process-control applications.",
        ("Setpoint", "Input", "Output", "Manual", "State", "Error"),
    ),
    "PID_3STEP": StandardBlockSpec(
        "PID_3Step", "PID", "Three-step controller for motorized actuators/valves.",
        ("Setpoint", "Input", "Open", "Close", "State", "Error"),
    ),
    "TON": StandardBlockSpec(
        "TON", "IEC_Timer", "On-delay timer.", ("IN", "PT", "Q", "ET"),
    ),
    "TOF": StandardBlockSpec(
        "TOF", "IEC_Timer", "Off-delay timer.", ("IN", "PT", "Q", "ET"),
    ),
    "TP": StandardBlockSpec(
        "TP", "IEC_Timer", "Pulse timer.", ("IN", "PT", "Q", "ET"),
    ),
    "CTU": StandardBlockSpec(
        "CTU", "IEC_Counter", "Count-up counter.", ("CU", "R", "PV", "Q", "CV"),
    ),
    "CTD": StandardBlockSpec(
        "CTD", "IEC_Counter", "Count-down counter.", ("CD", "LD", "PV", "Q", "CV"),
    ),
}


class StandardLibraryAnalyzer:
    """Resolve known standard blocks while keeping the catalog easy to extend."""

    def analyze_project(self, project: ProjectResult) -> tuple[StandardBlockUse, ...]:
        uses: list[StandardBlockUse] = []
        for block in project.blocks:
            uses.extend(self.analyze_block(block))
        return tuple(uses)

    def analyze_block(self, block: SourceBlock) -> tuple[StandardBlockUse, ...]:
        uses: list[StandardBlockUse] = []
        for call in block.analysis.calls:
            spec = self.lookup(call.target)
            if spec is None:
                continue
            uses.append(
                StandardBlockUse(
                    owner_block=block.name,
                    called_name=call.target,
                    canonical_name=spec.name,
                    family=spec.family,
                    purpose=spec.purpose,
                    interface_roles=spec.interface_roles,
                    line_number=call.line_number,
                )
            )
        return tuple(uses)

    @staticmethod
    def lookup(name: str) -> StandardBlockSpec | None:
        normalized = name.lstrip("#").strip().strip('"').upper()
        return STANDARD_BLOCKS.get(normalized)


def render_standard_library_markdown(uses: tuple[StandardBlockUse, ...]) -> str:
    lines = [
        "## 标准功能库解析",
        "",
        "| 所在块 | 标准块 | 家族 | 功能 | 常见接口角色 | 行号 |",
        "|---|---|---|---|---|---:|",
    ]
    if not uses:
        lines.append("| - | - | - | - | - | 未识别到已登记标准块 |")
        return "\n".join(lines)

    for item in uses:
        roles = ", ".join(item.interface_roles) if item.interface_roles else "-"
        lines.append(
            f"| {item.owner_block} | {item.canonical_name} | {item.family} | {item.purpose} | {roles} | {item.line_number} |"
        )
    lines.extend(
        [
            "",
            "> 标准块说明是工程语义摘要，不替代对应 TIA Portal 版本的 Siemens 官方接口文档；具体参数必须结合实际版本和块接口复核。",
        ]
    )
    return "\n".join(lines)
