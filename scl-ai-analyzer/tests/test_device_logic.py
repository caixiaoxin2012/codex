from pathlib import Path

from scl_ai_analyzer.device_logic import DeviceLogicAnalyzer, render_devices_markdown
from scl_ai_analyzer.project import ProjectAnalyzer, ProjectResult


SOURCE = '''
FUNCTION_BLOCK "AxisControl"
VAR
    Axis1 : FB_Axis;
    Motor1 : FB_Motor;
    ClampCyl : FB_Cylinder;
END_VAR
BEGIN
    MC_Power();
    MC_Home();
    #Axis1();
    #Motor1();
    #ClampCyl();
END_FUNCTION_BLOCK
'''


def _project() -> ProjectResult:
    block = ProjectAnalyzer().split_blocks(SOURCE, Path("devices.scl"))[0]
    return ProjectResult(
        root=Path("."),
        source_files=(Path("devices.scl"),),
        blocks=(block,),
    )


def test_recognizes_axis_motor_and_cylinder() -> None:
    devices = DeviceLogicAnalyzer().analyze_project(_project())
    kinds = {(item.instance_name, item.device_type) for item in devices}

    assert ("Axis1", "ServoAxis") in kinds
    assert ("Motor1", "Motor") in kinds
    assert ("ClampCyl", "Cylinder") in kinds


def test_motion_calls_raise_axis_confidence() -> None:
    devices = DeviceLogicAnalyzer().analyze_project(_project())
    axis = next(item for item in devices if item.instance_name == "Axis1")

    assert axis.confidence in {"medium", "high"}
    assert any(item.kind == "MotionControl" for item in axis.evidence)


def test_report_includes_evidence() -> None:
    report = render_devices_markdown(DeviceLogicAnalyzer().analyze_project(_project()))

    assert "设备逻辑识别" in report
    assert "ServoAxis" in report
    assert "MC_Power" in report
    assert "Motor" in report
