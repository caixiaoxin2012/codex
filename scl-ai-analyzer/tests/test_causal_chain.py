from pathlib import Path

from scl_ai_analyzer.causal_chain import CausalChainAnalyzer
from scl_ai_analyzer.project import ProjectAnalyzer


def test_causal_chain_links_action_device_condition_next_state_and_alarm():
    text = '''
FUNCTION_BLOCK "AxisSequence"
VAR
    Axis1 : FB_Axis;
    AlarmAxis : BOOL;
END_VAR
BEGIN
CASE #Step OF
    10:
        #Axis1();
        AlarmAxis := #Axis1.Error;
        IF #Axis1.Done THEN
            #Step := 20;
        END_IF;
    20:
        #Axis1();
END_CASE;
END_FUNCTION_BLOCK
'''
    blocks = ProjectAnalyzer().split_blocks(text, Path("axis.scl"))
    chains = CausalChainAnalyzer().analyze_block(blocks[0])

    chain = next(item for item in chains if item.source_state == "10")
    assert chain.target_state == "20"
    assert chain.completion_condition == "#Axis1.Done"
    assert "Axis1" in chain.device_names
    assert any(item.symbol == "AlarmAxis" for item in chain.alarms)
    assert any(item.action_kind == "DEVICE_CALL" for item in chain.actions)
