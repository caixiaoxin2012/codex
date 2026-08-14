from pathlib import Path

from scl_ai_analyzer.project import ProjectAnalyzer
from scl_ai_analyzer.variable_xref import VariableCrossReferenceAnalyzer


def test_local_variable_scope_and_access(tmp_path: Path) -> None:
    (tmp_path / "a.scl").write_text(
        '''FUNCTION_BLOCK "FB_A"\nVAR\n    Ready : Bool;\nEND_VAR\n#Ready := FALSE;\nIF #Ready THEN\n    #Ready := TRUE;\nEND_IF;\nEND_FUNCTION_BLOCK\n''',
        encoding="utf-8",
    )
    (tmp_path / "b.scl").write_text(
        '''FUNCTION_BLOCK "FB_B"\nVAR\n    Ready : Bool;\nEND_VAR\n#Ready := TRUE;\nEND_FUNCTION_BLOCK\n''',
        encoding="utf-8",
    )

    project = ProjectAnalyzer().scan(tmp_path)
    analyzer = VariableCrossReferenceAnalyzer()
    index = analyzer.build(project)

    a = analyzer.lookup(project, "Ready", block_name="FB_A", cache=index)
    b = analyzer.lookup(project, "Ready", block_name="FB_B", cache=index)

    assert a is not None and a.scope == "FB_A"
    assert b is not None and b.scope == "FB_B"
    assert {ref.block_name for ref in a.all_references} == {"FB_A"}
    assert {ref.block_name for ref in b.all_references} == {"FB_B"}
    assert len(a.declarations) == 1
    assert len(a.reads) >= 1
    assert len(a.writes) >= 2


def test_global_dotted_symbol_crosses_blocks(tmp_path: Path) -> None:
    (tmp_path / "a.scl").write_text(
        '''FUNCTION "FC_A" : Void\n"DB_Process".Ready := TRUE;\nEND_FUNCTION\n''',
        encoding="utf-8",
    )
    (tmp_path / "b.scl").write_text(
        '''FUNCTION "FC_B" : Void\nIF "DB_Process".Ready THEN\nEND_IF;\nEND_FUNCTION\n''',
        encoding="utf-8",
    )

    project = ProjectAnalyzer().scan(tmp_path)
    analyzer = VariableCrossReferenceAnalyzer()
    index = analyzer.build(project)
    xref = analyzer.lookup(project, "DB_Process.Ready", block_name="FC_A", cache=index)

    assert xref is not None
    assert xref.scope == "PROJECT"
    assert {ref.block_name for ref in xref.all_references} == {"FC_A", "FC_B"}
    assert any(ref.access == "WRITE" for ref in xref.all_references)
    assert any(ref.access == "READ" for ref in xref.all_references)
