from scl_ai_analyzer.alarm_logic import AlarmLogicAnalyzer, render_alarm_markdown


SAMPLE = '''
FUNCTION_BLOCK "SafetyAndAlarm"
VAR_OUTPUT
    SafetyStop : Bool;
    MotorFault : Bool;
    AlarmHighTemp : Bool;
    DoorInterlock : Bool;
    WarningFilter : Bool;
END_VAR
BEGIN
    SafetyStop := EStop OR NOT SafetyOk;
    MotorFault := DriveError OR OverloadTrip;
    AlarmHighTemp := Temperature > 90.0;
    DoorInterlock := NOT DoorClosed;
    WarningFilter := FilterHours > 1000;
END_FUNCTION_BLOCK
'''


def test_classifies_alarm_and_interlock_logic() -> None:
    findings = AlarmLogicAnalyzer().analyze(SAMPLE)

    assert [item.category for item in findings] == [
        "SAFETY",
        "FAULT",
        "ALARM",
        "INTERLOCK",
        "WARNING",
    ]
    assert [item.severity for item in findings] == [
        "red",
        "red",
        "orange",
        "yellow",
        "blue",
    ]


def test_keeps_source_line_and_expression() -> None:
    findings = AlarmLogicAnalyzer().analyze(SAMPLE)
    alarm = next(item for item in findings if item.symbol == "AlarmHighTemp")

    assert alarm.line_number > 0
    assert "Temperature > 90.0" in alarm.expression


def test_comments_are_ignored() -> None:
    text = '''
    // FakeAlarm := TRUE;
    (* HiddenFault := TRUE; *)
    RealWarning := NeedService;
    '''
    findings = AlarmLogicAnalyzer().analyze(text)

    assert [item.symbol for item in findings] == ["RealWarning"]


def test_markdown_includes_color_levels() -> None:
    findings = AlarmLogicAnalyzer().analyze(SAMPLE)
    report = render_alarm_markdown("SafetyAndAlarm", findings)

    assert "SafetyAndAlarm" in report
    assert "red" in report
    assert "orange" in report
    assert "yellow" in report
    assert "blue" in report
