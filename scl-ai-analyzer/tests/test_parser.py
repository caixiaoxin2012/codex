from scl_ai_analyzer.parser import SCLParser, render_markdown


SAMPLE = '''
FUNCTION_BLOCK "MotorControl"
VAR_INPUT
    Start : Bool; // 启动命令
    Speed : Real := 50.0;
END_VAR
VAR_OUTPUT
    Running : Bool;
END_VAR
VAR
    Step : Int := 0;
END_VAR
BEGIN
    IF Start THEN
        Running := TRUE;
    ELSIF Speed <= 0.0 THEN
        Running := FALSE;
    END_IF;

    CASE Step OF
        0: Step := 1;
        1: Step := 2;
    END_CASE;
END_FUNCTION_BLOCK
'''


def test_parse_block_and_variables() -> None:
    result = SCLParser().parse_text(SAMPLE, source_name="motor.scl")

    assert result.block.block_type == "FUNCTION_BLOCK"
    assert result.block.name == "MotorControl"
    assert len(result.variables) == 4
    assert result.variables[0].section == "Input"
    assert result.variables[0].name == "Start"
    assert result.variables[0].comment == "启动命令"
    assert result.variables[1].default == "50.0"
    assert result.variables[3].section == "Static"


def test_count_control_flow() -> None:
    result = SCLParser().parse_text(SAMPLE)

    assert result.control_flow["IF"] == 1
    assert result.control_flow["ELSIF"] == 1
    assert result.control_flow["CASE"] == 1
    assert result.control_flow["FOR"] == 0


def test_markdown_contains_engineering_summary() -> None:
    result = SCLParser().parse_text(SAMPLE, source_name="motor.scl")
    report = render_markdown(result)

    assert "# SCL 分析报告：motor.scl" in report
    assert "FUNCTION_BLOCK" in report
    assert "MotorControl" in report
    assert "变量分区统计" in report
    assert "控制结构统计" in report
    assert "启动命令" in report


def test_block_comments_are_ignored() -> None:
    text = '''
    (* FUNCTION_BLOCK Fake\nVAR_INPUT\nBad : Bool;\nEND_VAR *)
    FUNCTION "RealFunction" : Bool
    VAR_INPUT
        Enable : Bool;
    END_VAR
    BEGIN
        RealFunction := Enable;
    END_FUNCTION
    '''
    result = SCLParser().parse_text(text)

    assert result.block.name == "RealFunction"
    assert result.block.return_type == "Bool"
    assert [item.name for item in result.variables] == ["Enable"]
