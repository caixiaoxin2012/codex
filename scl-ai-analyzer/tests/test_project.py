from pathlib import Path

from scl_ai_analyzer.project import ProjectAnalyzer, render_project_markdown


MULTI_BLOCK = '''
FUNCTION_BLOCK "MotorControl"
VAR
    Motor : FB_Motor;
END_VAR
BEGIN
    #Motor();
END_FUNCTION_BLOCK

FUNCTION "ResetAll" : Bool
BEGIN
    ResetAll := TRUE;
END_FUNCTION

ORGANIZATION_BLOCK "MainCycle"
BEGIN
    "MotorControl"();
END_ORGANIZATION_BLOCK
'''


def test_split_multiple_blocks() -> None:
    analyzer = ProjectAnalyzer()
    blocks = analyzer.split_blocks(MULTI_BLOCK, Path("project.scl"))

    assert [(item.block_type, item.name) for item in blocks] == [
        ("FUNCTION_BLOCK", "MotorControl"),
        ("FUNCTION", "ResetAll"),
        ("ORGANIZATION_BLOCK", "MainCycle"),
    ]
    assert blocks[0].analysis.instances[0].name == "Motor"


def test_scan_directory_and_export(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "all_blocks.scl").write_text(MULTI_BLOCK, encoding="utf-8")

    analyzer = ProjectAnalyzer()
    result = analyzer.scan(source_dir)
    output_dir = tmp_path / "generated"
    exported = analyzer.export_blocks(result, output_dir)

    assert len(result.source_files) == 1
    assert len(result.blocks) == 3
    assert {path.name for path in exported} == {
        "FB_MotorControl.scl",
        "FC_ResetAll.scl",
        "OB_MainCycle.scl",
    }
    assert all(path.read_text(encoding="utf-8").strip() for path in exported)


def test_project_report_contains_index(tmp_path: Path) -> None:
    source = tmp_path / "project.scl"
    source.write_text(MULTI_BLOCK, encoding="utf-8")
    result = ProjectAnalyzer().scan(source)
    report = render_project_markdown(result)

    assert "SCL 项目分析报告" in report
    assert "MotorControl" in report
    assert "ResetAll" in report
    assert "MainCycle" in report
    assert "| FB | 1 |" in report
    assert "| FC | 1 |" in report
    assert "| OB | 1 |" in report
