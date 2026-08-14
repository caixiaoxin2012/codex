from pathlib import Path

from scl_ai_analyzer.knowledge_graph import EngineeringKnowledgeGraphBuilder
from scl_ai_analyzer.project import ProjectAnalyzer, ProjectResult
from scl_ai_analyzer.standard_library import StandardLibraryAnalyzer
from scl_ai_analyzer.state_actions import StateActionAnalyzer


SAMPLE = '''
FUNCTION_BLOCK "AxisSequence"
VAR
    Servo : Servo;
END_VAR
BEGIN
    CASE Step OF
        0:
            #Servo(Enable := TRUE);
            MC_Power();
            IF Start THEN
                Step := 10;
            END_IF;
        10:
            MC_Home();
            Ready := TRUE;
            IF Homed THEN
                Step := 20;
            END_IF;
        20:
            MC_MoveAbsolute();
    END_CASE;
END_FUNCTION_BLOCK
'''


def build_project() -> ProjectResult:
    path = Path("AxisSequence.scl")
    blocks = ProjectAnalyzer().split_blocks(SAMPLE, path)
    return ProjectResult(root=Path("."), source_files=(path,), blocks=tuple(blocks))


def test_standard_library_recognizes_motion_blocks() -> None:
    uses = StandardLibraryAnalyzer().analyze_project(build_project())
    assert [item.canonical_name for item in uses] == [
        "MC_Power",
        "MC_Home",
        "MC_MoveAbsolute",
    ]
    assert all(item.family == "MotionControl" for item in uses)


def test_state_actions_link_device_and_standard_blocks() -> None:
    actions = StateActionAnalyzer().analyze_project(build_project())
    assert any(
        item.state == "0"
        and item.action_kind == "DEVICE_CALL"
        and item.device_name == "Servo"
        for item in actions
    )
    assert any(
        item.state == "10"
        and item.standard_block == "MC_Home"
        for item in actions
    )
    assert any(
        item.state == "10"
        and item.action_kind == "ASSIGNMENT"
        and item.target == "Ready"
        for item in actions
    )


def test_knowledge_graph_links_state_actions() -> None:
    graph = EngineeringKnowledgeGraphBuilder().build(build_project())
    kinds = {entity.kind for entity in graph.entities}
    relations = {edge.relation for edge in graph.relations}

    assert "STANDARD_BLOCK" in kinds
    assert "ACTION" in kinds
    assert "HAS_ACTION" in relations
    assert "ACTS_ON_DEVICE" in relations
    assert "USES_STANDARD_BLOCK" in relations
