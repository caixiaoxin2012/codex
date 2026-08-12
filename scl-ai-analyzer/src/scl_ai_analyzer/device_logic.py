from __future__ import annotations

import re
from dataclasses import dataclass

from .project import ProjectResult, SourceBlock


@dataclass(frozen=True)
class DeviceEvidence:
    kind: str
    value: str
    line_number: int | None = None


@dataclass(frozen=True)
class DeviceObject:
    block_name: str
    instance_name: str | None
    device_type: str
    fb_type: str | None
    confidence: str
    evidence: tuple[DeviceEvidence, ...]


DEVICE_PATTERNS: dict[str, tuple[re.Pattern[str], ...]] = {
    "ServoAxis": (
        re.compile(r"\b(axis|servo|motion|drive)\b", re.IGNORECASE),
        re.compile(r"\bMC_(Power|Home|MoveAbsolute|MoveRelative|MoveVelocity|Stop|Halt|Reset)\b", re.IGNORECASE),
    ),
    "Motor": (
        re.compile(r"\b(motor|mtr|conveyor|fan|blower)\b", re.IGNORECASE),
    ),
    "Cylinder": (
        re.compile(r"\b(cylinder|cyl|pneumatic|aircyl)\b", re.IGNORECASE),
    ),
    "Valve": (
        re.compile(r"\b(valve|vlv|solenoid)\b", re.IGNORECASE),
    ),
    "Pump": (
        re.compile(r"\b(pump|pmp)\b", re.IGNORECASE),
    ),
}

STANDARD_BLOCK_FAMILIES: dict[str, str] = {
    "MC_POWER": "MotionControl",
    "MC_HOME": "MotionControl",
    "MC_MOVEABSOLUTE": "MotionControl",
    "MC_MOVERELATIVE": "MotionControl",
    "MC_MOVEVELOCITY": "MotionControl",
    "MC_STOP": "MotionControl",
    "MC_HALT": "MotionControl",
    "MC_RESET": "MotionControl",
    "PID_COMPACT": "PID",
    "PID_3STEP": "PID",
    "CTRL_PID": "PID",
}


class DeviceLogicAnalyzer:
    """Heuristic industrial-device recognition with explicit evidence.

    This layer does not claim semantic certainty. It combines FB instance names/types
    with known standard-block calls and reports confidence so engineers can review it.
    """

    def analyze_project(self, project: ProjectResult) -> tuple[DeviceObject, ...]:
        devices: list[DeviceObject] = []
        for block in project.blocks:
            devices.extend(self.analyze_block(block))
        return tuple(devices)

    def analyze_block(self, block: SourceBlock) -> tuple[DeviceObject, ...]:
        call_evidence = self._standard_call_evidence(block)
        devices: list[DeviceObject] = []

        for instance in block.analysis.instances:
            haystack = f"{instance.name} {instance.fb_type}"
            scores: dict[str, list[DeviceEvidence]] = {}
            for device_type, patterns in DEVICE_PATTERNS.items():
                for pattern in patterns:
                    match = pattern.search(haystack)
                    if match:
                        scores.setdefault(device_type, []).append(
                            DeviceEvidence(kind="instance", value=match.group(0))
                        )

            if call_evidence:
                motion = [item for item in call_evidence if item.kind == "MotionControl"]
                if motion and self._looks_axis_like(haystack):
                    scores.setdefault("ServoAxis", []).extend(motion)

            if not scores:
                continue

            device_type, evidence = max(scores.items(), key=lambda item: len(item[1]))
            confidence = self._confidence(evidence)
            devices.append(
                DeviceObject(
                    block_name=block.name,
                    instance_name=instance.name,
                    device_type=device_type,
                    fb_type=instance.fb_type,
                    confidence=confidence,
                    evidence=tuple(evidence),
                )
            )

        # A block may directly represent a device even without an FB instance.
        block_scores: dict[str, list[DeviceEvidence]] = {}
        for device_type, patterns in DEVICE_PATTERNS.items():
            for pattern in patterns:
                match = pattern.search(block.name)
                if match:
                    block_scores.setdefault(device_type, []).append(
                        DeviceEvidence(kind="block_name", value=match.group(0))
                    )
        if call_evidence and any(item.kind == "MotionControl" for item in call_evidence):
            block_scores.setdefault("ServoAxis", []).extend(
                item for item in call_evidence if item.kind == "MotionControl"
            )

        if block_scores:
            device_type, evidence = max(block_scores.items(), key=lambda item: len(item[1]))
            devices.append(
                DeviceObject(
                    block_name=block.name,
                    instance_name=None,
                    device_type=device_type,
                    fb_type=None,
                    confidence=self._confidence(evidence),
                    evidence=tuple(evidence),
                )
            )

        return tuple(self._deduplicate(devices))

    @staticmethod
    def _looks_axis_like(value: str) -> bool:
        return bool(re.search(r"axis|servo|motion|drive", value, flags=re.IGNORECASE))

    @staticmethod
    def _standard_call_evidence(block: SourceBlock) -> list[DeviceEvidence]:
        evidence: list[DeviceEvidence] = []
        for call in block.analysis.calls:
            normalized = call.target.lstrip("#").strip('"').upper()
            family = STANDARD_BLOCK_FAMILIES.get(normalized)
            if family:
                evidence.append(
                    DeviceEvidence(kind=family, value=call.target, line_number=call.line_number)
                )
        return evidence

    @staticmethod
    def _confidence(evidence: list[DeviceEvidence]) -> str:
        kinds = {item.kind for item in evidence}
        if "MotionControl" in kinds and len(evidence) >= 2:
            return "high"
        if len(evidence) >= 2:
            return "medium"
        return "low"

    @staticmethod
    def _deduplicate(items: list[DeviceObject]) -> list[DeviceObject]:
        seen: set[tuple[str, str | None, str]] = set()
        result: list[DeviceObject] = []
        for item in items:
            key = (item.block_name.casefold(), item.instance_name.casefold() if item.instance_name else None, item.device_type)
            if key in seen:
                continue
            seen.add(key)
            result.append(item)
        return result


def render_devices_markdown(devices: tuple[DeviceObject, ...]) -> str:
    lines = [
        "## 设备逻辑识别",
        "",
        "| 所在块 | 实例 | 设备类型 | FB 类型 | 置信度 | 识别依据 |",
        "|---|---|---|---|---|---|",
    ]
    if not devices:
        lines.append("| - | - | - | - | - | 未识别到典型设备对象 |")
        return "\n".join(lines)

    for item in devices:
        evidence = "; ".join(
            f"{entry.kind}:{entry.value}" + (f"@L{entry.line_number}" if entry.line_number else "")
            for entry in item.evidence
        )
        lines.append(
            f"| {item.block_name} | {item.instance_name or '-'} | {item.device_type} "
            f"| {item.fb_type or '-'} | {item.confidence} | {evidence} |"
        )
    lines.extend(
        [
            "",
            "> 设备类型为规则推断结果，必须结合工艺命名、硬件组态和现场设计人工复核。",
        ]
    )
    return "\n".join(lines)
