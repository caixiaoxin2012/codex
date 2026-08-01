from scl_ai_analyzer.parser import SCLParser, render_markdown

SAMPLE = '''
FUNCTION_BLOCK "MotorControl"
VAR_INPUT
    Start : Bool;
END_VAR
VAR
    Motor1, Motor2 : FB_Motor;
    AlarmManager : "FB Alarm";
    Step : Int := 0;
END_VAR
BEGIN
    #Motor1(Enable := Start);
    #Motor2(Enable := TRUE);
    FC_Reset();
    #AlarmManager(Trigger := TRUE);
END_FUNCTION_BLOCK
'''


def test_multi_instance_declarations() -> None:
    result = SCLParser().parse_text(SAMPLE)
    assert [item.name for item in result.instances] == ["Motor1", "Motor2", "AlarmManager"]
    assert [item.fb_type for item in result.instances] == ["FB_Motor", "FB_Motor", '"FB Alarm"']


def test_instance_calls_are_classified() -> None:
    result = SCLParser().parse_text(SAMPLE)
    assert [(item.target, item.call_kind, item.fb_type) for item in result.calls] == [
        ("#Motor1", "FB Instance", "FB_Motor"),
        ("#Motor2", "FB Instance", "FB_Motor"),
        ("FC_Reset", "Direct", None),
        ("#AlarmManager", "FB Instance", '"FB Alarm"'),
    ]


def test_builtin_static_is_not_instance() -> None:
    text = '''
    FUNCTION_BLOCK "Demo"
    VAR
        Step : Int;
        Axis : FB_Axis;
    END_VAR
    BEGIN
        #Axis();
    END_FUNCTION_BLOCK
    '''
    result = SCLParser().parse_text(text)
    assert [item.name for item in result.instances] == ["Axis"]
    assert result.calls[0].call_kind == "FB Instance"


def test_comments_and_keywords_are_ignored() -> None:
    text = '''
    FUNCTION "Demo" : Bool
    BEGIN
        // FakeCall();
        IF TRUE THEN
            RealCall();
        END_IF;
        (* HiddenCall(); *)
    END_FUNCTION
    '''
    result = SCLParser().parse_text(text)
    assert [item.target for item in result.calls] == ["RealCall"]


def test_markdown_contains_instance_summary() -> None:
    report = render_markdown(SCLParser().parse_text(SAMPLE, source_name="motor.scl"))
    assert "FB 实例" in report
    assert "Motor1" in report
    assert "FB_Motor" in report
    assert "FB Instance" in report
    assert "FC_Reset" in report
