from pathlib import Path

from scl_ai_analyzer.knowledge_graph import EngineeringKnowledgeGraphBuilder
from scl_ai_analyzer.project import ProjectAnalyzer


SAMPLE = '''
ORGANIZATION_BLOCK "Main"
BEGIN
    FB_Process();
END_ORGANIZATION_BLOCK

FUNCTION_BLOCK "FB_Process"
VAR
    Axis1 : FB_Axis;
END_VAR
BEGIN
    CASE Step OF
        0:
            IF Start THEN
                Step := 10;
            END_IF;
        10:
            IF Done THEN
                Step := 0;
            END_IF;
    END_CASE;

    #Axis1();
    FaultAxis := NOT AxisReady;
END_FUNCTION_BLOCK
'''


def build_graph():
    analyzer = ProjectAnalyzer()
    project = analyzer.scan if False else None
    blocks = analyzer.split_blocks(SAMPLE, Path("project.scl"))
    from scl_ai_analyzer.project import ProjectResult

    result = ProjectResult(
        root=Path("."),
        source_files=(Path("project.scl"),),
        blocks=tuple(blocks),
    )
    return EngineeringKnowledgeGraphBuilder().build(result)


def test_graph_contains_blocks_instances_states_and_alarm() -> None:
    graph = build_graph()
    kinds = {entity.kind for entity in graph.entities}

    assert "OB" in kinds
    assert "FB" in kinds
    assert "INSTANCE" in kinds
    assert "STATE_MACHINE" in kinds
    assert "STATE" in kinds
    assert "ALARM" in kinds


def test_graph_contains_engineering_relations() -> None:
    graph = build_graph()
    relations = {edge.relation for edge in graph.relations}

    assert "CALLS" in relations
    assert "DECLARES_INSTANCE" in relations
    assert "CALLS_INSTANCE" in relations
    assert "HAS_STATE_MACHINE" in relations
    assert "TRANSITIONS_TO" in relations
    assert "HAS_ALARM" in relations


def test_bidirectional_source_lookup() -> None:
    graph = build_graph()
    alarm = next(entity for entity in graph.entities if entity.kind == "ALARM")
    refs = graph.sources_for(alarm.entity_id)

    assert refs
    assert refs[0].file.name == "project.scl"
    assert refs[0].line is not None

    objects = graph.objects_at("project.scl", refs[0].line)
    assert any(item.entity_id == alarm.entity_id for item in objects)


def test_related_entities_can_be_queried() -> None:
    graph = build_graph()
    process = next(entity for entity in graph.entities if entity.kind == "FB" and entity.name == "FB_Process")

    alarms = graph.related(process.entity_id, "HAS_ALARM")
    machines = graph.related(process.entity_id, "HAS_STATE_MACHINE")

    assert alarms
    assert machines
