from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .alarm_logic import AlarmLogicAnalyzer
from .ast import ProjectASTBuilder, SourceRef
from .device_logic import DeviceLogicAnalyzer
from .project import BLOCK_PREFIX, ProjectResult
from .state_machine import StateMachineAnalyzer


@dataclass(frozen=True)
class GraphEntity:
    entity_id: str
    kind: str
    name: str
    source_refs: tuple[SourceRef, ...] = ()
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class GraphRelation:
    source_id: str
    target_id: str
    relation: str
    source_ref: SourceRef | None = None
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class EngineeringKnowledgeGraph:
    root: Path
    entities: tuple[GraphEntity, ...]
    relations: tuple[GraphRelation, ...]

    def entity_map(self) -> dict[str, GraphEntity]:
        return {entity.entity_id: entity for entity in self.entities}

    def sources_for(self, entity_id: str) -> tuple[SourceRef, ...]:
        entity = self.entity_map().get(entity_id)
        return entity.source_refs if entity else ()

    def objects_at(self, file: str | Path, line: int) -> tuple[GraphEntity, ...]:
        file_name = Path(file).name.casefold()
        matches: list[GraphEntity] = []
        for entity in self.entities:
            if any(
                ref.file.name.casefold() == file_name and ref.line == line
                for ref in entity.source_refs
            ):
                matches.append(entity)
        return tuple(matches)

    def related(self, entity_id: str, relation: str | None = None) -> tuple[GraphEntity, ...]:
        entity_map = self.entity_map()
        targets: list[GraphEntity] = []
        for edge in self.relations:
            if edge.source_id != entity_id:
                continue
            if relation and edge.relation != relation:
                continue
            target = entity_map.get(edge.target_id)
            if target:
                targets.append(target)
        return tuple(targets)


class EngineeringKnowledgeGraphBuilder:
    """Merge parser, AST, state, device and alarm results into one traceable graph."""

    def build(self, project: ProjectResult) -> EngineeringKnowledgeGraph:
        entities: list[GraphEntity] = []
        relations: list[GraphRelation] = []
        seen_entities: set[str] = set()

        def add_entity(entity: GraphEntity) -> None:
            if entity.entity_id in seen_entities:
                return
            seen_entities.add(entity.entity_id)
            entities.append(entity)

        # Blocks, instances and cross-block calls come from the existing project AST.
        ast = ProjectASTBuilder().build(project)
        for node in ast.nodes:
            add_entity(
                GraphEntity(
                    entity_id=node.node_id,
                    kind=node.kind,
                    name=node.name,
                    source_refs=(node.source,),
                    metadata=dict(node.metadata),
                )
            )
        for edge in ast.edges:
            if edge.target_id.startswith("UNRESOLVED:"):
                add_entity(
                    GraphEntity(
                        entity_id=edge.target_id,
                        kind="UNRESOLVED",
                        name=edge.target_id.removeprefix("UNRESOLVED:"),
                        source_refs=(edge.source,),
                    )
                )
            relations.append(
                GraphRelation(
                    source_id=edge.source_id,
                    target_id=edge.target_id,
                    relation=edge.relation,
                    source_ref=edge.source,
                    metadata={"resolved": str(edge.resolved).lower()},
                )
            )

        device_analyzer = DeviceLogicAnalyzer()
        state_analyzer = StateMachineAnalyzer()
        alarm_analyzer = AlarmLogicAnalyzer()

        for block in project.blocks:
            block_id = self._block_id(block.block_type, block.name)

            # Device abstraction layer.
            for index, device in enumerate(device_analyzer.analyze_block(block), start=1):
                device_name = device.instance_name or block.name
                device_id = f"DEVICE:{block_id}:{self._norm(device_name)}:{device.device_type.casefold()}"
                refs = tuple(
                    SourceRef(block.source_file, evidence.line_number)
                    for evidence in device.evidence
                    if evidence.line_number
                ) or (SourceRef(block.source_file, 1),)
                add_entity(
                    GraphEntity(
                        entity_id=device_id,
                        kind="DEVICE",
                        name=device_name,
                        source_refs=refs,
                        metadata={
                            "device_type": device.device_type,
                            "confidence": device.confidence,
                            "fb_type": device.fb_type or "",
                        },
                    )
                )
                relations.append(
                    GraphRelation(
                        source_id=block_id,
                        target_id=device_id,
                        relation="REPRESENTS_DEVICE",
                        source_ref=refs[0],
                    )
                )
                if device.instance_name:
                    instance_id = f"INSTANCE:{block_id}:{self._norm(device.instance_name)}"
                    if instance_id in seen_entities:
                        relations.append(
                            GraphRelation(
                                source_id=instance_id,
                                target_id=device_id,
                                relation="MODELS_DEVICE",
                                source_ref=refs[0],
                            )
                        )

            # CASE-based state machines and transitions.
            for machine_index, machine in enumerate(state_analyzer.analyze(block.text), start=1):
                machine_id = f"STATE_MACHINE:{block_id}:{machine_index}:{self._norm(machine.selector)}"
                add_entity(
                    GraphEntity(
                        entity_id=machine_id,
                        kind="STATE_MACHINE",
                        name=machine.selector,
                        source_refs=(SourceRef(block.source_file, machine.start_line),),
                        metadata={"state_count": str(len(machine.states))},
                    )
                )
                relations.append(
                    GraphRelation(
                        source_id=block_id,
                        target_id=machine_id,
                        relation="HAS_STATE_MACHINE",
                        source_ref=SourceRef(block.source_file, machine.start_line),
                    )
                )

                state_ids: dict[str, str] = {}
                for state in machine.states:
                    state_id = f"STATE:{machine_id}:{self._norm(state)}"
                    state_ids[state] = state_id
                    add_entity(
                        GraphEntity(
                            entity_id=state_id,
                            kind="STATE",
                            name=state,
                            source_refs=(),
                            metadata={"selector": machine.selector},
                        )
                    )
                    relations.append(
                        GraphRelation(
                            source_id=machine_id,
                            target_id=state_id,
                            relation="HAS_STATE",
                        )
                    )

                for transition in machine.transitions:
                    source_state_id = state_ids.get(
                        transition.source,
                        f"STATE:{machine_id}:{self._norm(transition.source)}",
                    )
                    target_state_id = state_ids.get(
                        transition.target,
                        f"STATE:{machine_id}:{self._norm(transition.target)}",
                    )
                    if target_state_id not in seen_entities:
                        add_entity(
                            GraphEntity(
                                entity_id=target_state_id,
                                kind="STATE",
                                name=transition.target,
                                source_refs=(SourceRef(block.source_file, transition.line_number),),
                                metadata={"selector": machine.selector, "external_or_dynamic": "true"},
                            )
                        )
                    relations.append(
                        GraphRelation(
                            source_id=source_state_id,
                            target_id=target_state_id,
                            relation="TRANSITIONS_TO",
                            source_ref=SourceRef(block.source_file, transition.line_number),
                            metadata={"condition": transition.condition or ""},
                        )
                    )

            # Alarm/interlock findings are graph objects with exact line links.
            for finding in alarm_analyzer.analyze(block.text):
                alarm_id = f"ALARM:{block_id}:{finding.line_number}:{self._norm(finding.symbol)}"
                add_entity(
                    GraphEntity(
                        entity_id=alarm_id,
                        kind="ALARM",
                        name=finding.symbol,
                        source_refs=(SourceRef(block.source_file, finding.line_number),),
                        metadata={
                            "category": finding.category,
                            "severity": finding.severity,
                            "expression": finding.expression,
                        },
                    )
                )
                relations.append(
                    GraphRelation(
                        source_id=block_id,
                        target_id=alarm_id,
                        relation="HAS_ALARM",
                        source_ref=SourceRef(block.source_file, finding.line_number),
                    )
                )

        return EngineeringKnowledgeGraph(
            root=project.root,
            entities=tuple(entities),
            relations=tuple(relations),
        )

    @staticmethod
    def _norm(value: str) -> str:
        return value.strip().strip('"').lstrip("#").casefold()

    @classmethod
    def _block_id(cls, block_type: str, name: str) -> str:
        return f"{BLOCK_PREFIX.get(block_type, block_type)}:{cls._norm(name)}"


def render_knowledge_graph_markdown(graph: EngineeringKnowledgeGraph) -> str:
    counts: dict[str, int] = {}
    for entity in graph.entities:
        counts[entity.kind] = counts.get(entity.kind, 0) + 1

    lines = [
        "## 工程知识图谱",
        "",
        f"- **实体数量：** {len(graph.entities)}",
        f"- **关系数量：** {len(graph.relations)}",
        "",
        "| 实体类型 | 数量 |",
        "|---|---:|",
    ]
    for kind in ("OB", "FB", "FC", "DB", "INSTANCE", "DEVICE", "STATE_MACHINE", "STATE", "ALARM", "UNRESOLVED"):
        if counts.get(kind, 0):
            lines.append(f"| {kind} | {counts[kind]} |")

    relation_counts: dict[str, int] = {}
    for relation in graph.relations:
        relation_counts[relation.relation] = relation_counts.get(relation.relation, 0) + 1
    lines.extend(["", "### 关系统计", "", "| 关系 | 数量 |", "|---|---:|"])
    for relation, count in sorted(relation_counts.items()):
        lines.append(f"| {relation} | {count} |")

    lines.extend(
        [
            "",
            "### 双向定位索引",
            "",
            "| 工程对象 | 类型 | 代码位置 |",
            "|---|---|---|",
        ]
    )
    traceable = [entity for entity in graph.entities if entity.source_refs]
    if not traceable:
        lines.append("| - | - | 暂无可定位对象 |")
    else:
        for entity in traceable[:100]:
            locations = ", ".join(
                ref.file.name + (f":{ref.line}" if ref.line else "")
                for ref in entity.source_refs
            )
            lines.append(f"| {entity.name} | {entity.kind} | {locations} |")
        if len(traceable) > 100:
            lines.append(f"| … | … | 另有 {len(traceable) - 100} 个对象，报告中省略 |")

    lines.extend(
        [
            "",
            "> 双向定位数据可供后续 GUI 使用：工程对象可跳转到源代码位置，源代码行也可反查相关报警、设备、状态机或调用关系。",
        ]
    )
    return "\n".join(lines)
