from __future__ import annotations

from .ast import SourceRef
from .causal_chain import CausalChainAnalyzer
from .knowledge_graph import EngineeringKnowledgeGraph, GraphEntity, GraphRelation
from .project import BLOCK_PREFIX, ProjectResult


def enrich_with_causal_chains(
    graph: EngineeringKnowledgeGraph,
    project: ProjectResult,
) -> EngineeringKnowledgeGraph:
    """Add explicit completion-condition and abnormal-branch relations to the graph."""
    entities = list(graph.entities)
    relations = list(graph.relations)
    seen = {item.entity_id for item in entities}

    for block in project.blocks:
        block_id = f"{BLOCK_PREFIX.get(block.block_type, block.block_type)}:{_norm(block.name)}"
        machines = [
            item for item in graph.entities
            if item.kind == "STATE_MACHINE"
            and any(edge.source_id == block_id and edge.target_id == item.entity_id for edge in graph.relations)
        ]
        machine_by_selector = {_norm(item.name): item.entity_id for item in machines}

        for chain in CausalChainAnalyzer().analyze_block(block):
            machine_id = machine_by_selector.get(_norm(chain.selector))
            if not machine_id:
                continue
            source_state_id = f"STATE:{machine_id}:{_norm(chain.source_state)}"
            target_state_id = f"STATE:{machine_id}:{_norm(chain.target_state)}"

            if chain.completion_condition:
                condition_id = f"CONDITION:{source_state_id}:{chain.transition_line}"
                if condition_id not in seen:
                    seen.add(condition_id)
                    entities.append(
                        GraphEntity(
                            entity_id=condition_id,
                            kind="CONDITION",
                            name=chain.completion_condition,
                            source_refs=(SourceRef(block.source_file, chain.transition_line),),
                            metadata={"role": "completion_or_transition"},
                        )
                    )
                relations.append(
                    GraphRelation(
                        source_id=source_state_id,
                        target_id=condition_id,
                        relation="COMPLETES_WHEN",
                        source_ref=SourceRef(block.source_file, chain.transition_line),
                    )
                )
                relations.append(
                    GraphRelation(
                        source_id=condition_id,
                        target_id=target_state_id,
                        relation="ADVANCES_TO",
                        source_ref=SourceRef(block.source_file, chain.transition_line),
                    )
                )

            for alarm in chain.alarms:
                alarm_id = f"ALARM:{block_id}:{alarm.line_number}:{_norm(alarm.symbol)}"
                if alarm_id in seen:
                    relations.append(
                        GraphRelation(
                            source_id=source_state_id,
                            target_id=alarm_id,
                            relation="MAY_RAISE",
                            source_ref=SourceRef(block.source_file, alarm.line_number),
                            metadata={"category": alarm.category, "severity": alarm.severity},
                        )
                    )

    return EngineeringKnowledgeGraph(
        root=graph.root,
        entities=tuple(entities),
        relations=tuple(relations),
    )


def _norm(value: str) -> str:
    return value.strip().strip('"').lstrip("#").casefold()
