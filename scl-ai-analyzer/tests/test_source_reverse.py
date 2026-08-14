from pathlib import Path

from scl_ai_analyzer.project import ProjectAnalyzer
from scl_ai_analyzer.source_reverse import ReverseSourceIndex


SOURCE = '''
FUNCTION_BLOCK AxisSequence
VAR
    Axis1 : FB_Axis;
    Step : INT;
    AlarmAxis : BOOL;
END_VAR
BEGIN
CASE Step OF
    10:
        Axis1();
        MC_Home();
        IF Axis1.Done THEN
            Step := 20;
        END_IF;
    20:
        AlarmAxis := Axis1.Error;
END_CASE;
END_FUNCTION_BLOCK
'''


def _block():
    analyzer = ProjectAnalyzer()
    blocks = analyzer.split_blocks(SOURCE, Path("AxisSequence.scl"))
    assert blocks
    return blocks[0]


def test_reverse_index_maps_variable_call_state_and_alarm():
    block = _block()
    index = ReverseSourceIndex().build(block)

    axis_call_line = next(
        line for line, links in index.items()
        if any(item.kind == "CALL" and item.name == "Axis1" for item in links)
    )
    kinds = {item.kind for item in index[axis_call_line]}
    assert "CALL" in kinds
    assert "VARIABLE" in kinds
    assert "STATE" in kinds

    alarm_line = next(
        line for line, links in index.items()
        if any(item.kind == "ALARM" and "AlarmAxis" in item.name for item in links)
    )
    alarm_kinds = {item.kind for item in index[alarm_line]}
    assert "ALARM" in alarm_kinds
    assert "VARIABLE" in alarm_kinds
    assert "STATE" in alarm_kinds


def test_reverse_index_maps_standard_block_and_transition():
    block = _block()
    index = ReverseSourceIndex().build(block)

    home_line = next(
        line for line, links in index.items()
        if any(item.kind == "STANDARD_BLOCK" and item.name == "MC_Home" for item in links)
    )
    assert any(item.kind == "STATE" for item in index[home_line])

    transition_line = next(
        line for line, links in index.items()
        if any(item.kind == "STATE_TRANSITION" for item in links)
    )
    kinds = {item.kind for item in index[transition_line]}
    assert "STATE_TRANSITION" in kinds
    assert "CAUSAL_CHAIN" in kinds
