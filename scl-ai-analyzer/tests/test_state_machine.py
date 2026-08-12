from scl_ai_analyzer.state_machine import StateMachineAnalyzer


SAMPLE = '''
FUNCTION_BLOCK "Sequence"
VAR
    Step : Int := 0;
END_VAR
BEGIN
    CASE Step OF
        0:
            IF Start THEN
                Step := 10;
            END_IF;
        10:
            IF Done THEN
                Step := 20;
            END_IF;
        20:
            Step := 0;
    END_CASE;
END_FUNCTION_BLOCK
'''


def test_detect_case_state_machine() -> None:
    machines = StateMachineAnalyzer().analyze(SAMPLE)
    assert len(machines) == 1
    machine = machines[0]
    assert machine.selector == "Step"
    assert machine.states == ("0", "10", "20")
    assert [(t.source, t.target, t.condition) for t in machine.transitions] == [
        ("0", "10", "Start"),
        ("10", "20", "Done"),
        ("20", "0", None),
    ]
    assert all(t.line_number > 0 for t in machine.transitions)


def test_comments_do_not_create_states() -> None:
    text = '''
    // CASE Fake OF
    CASE #State OF
        1:
            (* #State := 99; *)
            #State := 2;
        2:
            #State := 1;
    END_CASE;
    '''
    machine = StateMachineAnalyzer().analyze(text)[0]
    assert machine.selector == "#State"
    assert machine.states == ("1", "2")
    assert [t.target for t in machine.transitions] == ["2", "1"]
