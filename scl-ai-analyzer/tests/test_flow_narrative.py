from pathlib import Path

from scl_ai_analyzer.flow_narrative import FlowNarrativeGenerator
from scl_ai_analyzer.project import ProjectAnalyzer


def test_generates_traceable_chinese_flow_description():
    text = '''
FUNCTION_BLOCK "AxisSequence"
VAR
    Step : Int;
END_VAR
BEGIN
CASE Step OF
    10:
        MC_Home(Axis := Axis1, Execute := TRUE);
        IF Axis1.Homed THEN
            Step := 20;
        END_IF;
    20:
        Ready := TRUE;
        Step := 30;
END_CASE;
END_FUNCTION_BLOCK
'''
    analyzer = ProjectAnalyzer()
    blocks = analyzer.split_blocks(text, Path("axis.scl"))
    project = type("Project", (), {
        "root": Path("."),
        "source_files": (Path("axis.scl"),),
        "blocks": tuple(blocks),
    })()

    narratives = FlowNarrativeGenerator().generate_project(project)

    assert narratives
    first = narratives[0]
    assert first.source_state == "10"
    assert first.target_state == "20"
    assert "MC_Home" in first.detail
    assert "Axis1.Homed" in first.detail
    assert "状态 20" in first.detail


def test_does_not_invent_action_when_none_is_extracted():
    from scl_ai_analyzer.causal_chain import CausalChain

    chain = CausalChain(
        block_name="FB_Test",
        selector="Step",
        source_state="0",
        actions=(),
        device_names=(),
        standard_blocks=(),
        completion_condition=None,
        target_state="10",
        transition_line=5,
        alarms=(),
    )
    item = FlowNarrativeGenerator().generate((chain,))[0]
    assert "未识别到直接动作" in item.detail
    assert "无显式条件" in item.detail
