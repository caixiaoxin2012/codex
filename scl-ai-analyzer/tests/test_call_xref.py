from pathlib import Path

from scl_ai_analyzer.call_xref import BlockCallCrossReferenceAnalyzer
from scl_ai_analyzer.project import ProjectAnalyzer


def test_resolves_fb_instance_and_ob_root_path(tmp_path: Path) -> None:
    source = tmp_path / "project.scl"
    source.write_text(
        '''
ORGANIZATION_BLOCK OB1
BEGIN
    Main();
END_ORGANIZATION_BLOCK

FUNCTION_BLOCK Main
VAR
    Axis1 : FB_Axis;
END_VAR
BEGIN
    CASE Step OF
        10:
            Axis1();
            IF Done THEN
                Step := 20;
            END_IF;
    END_CASE;
END_FUNCTION_BLOCK

FUNCTION_BLOCK FB_Axis
BEGIN
END_FUNCTION_BLOCK
''',
        encoding="utf-8",
    )

    project = ProjectAnalyzer().scan(tmp_path)
    index = BlockCallCrossReferenceAnalyzer().build(project)

    main = index["main"]
    assert any(ref.caller_block == "OB1" for ref in main.incoming)
    assert any(ref.resolved_block == "FB_Axis" for ref in main.outgoing)

    axis = index["fb_axis"]
    incoming = next(ref for ref in axis.incoming if ref.caller_block == "Main")
    assert incoming.instance_name == "Axis1"
    assert incoming.state == "10"
    assert ("OB1", "Main", "FB_Axis") in axis.root_paths


def test_keeps_unresolved_calls_explicit(tmp_path: Path) -> None:
    source = tmp_path / "unresolved.scl"
    source.write_text(
        '''
FUNCTION FC_Test : Bool
BEGIN
    UnknownHelper();
END_FUNCTION
''',
        encoding="utf-8",
    )

    project = ProjectAnalyzer().scan(tmp_path)
    xref = BlockCallCrossReferenceAnalyzer().build(project)["fc_test"]
    assert len(xref.outgoing) == 1
    assert xref.outgoing[0].target_name == "UnknownHelper"
    assert xref.outgoing[0].resolved_block is None
