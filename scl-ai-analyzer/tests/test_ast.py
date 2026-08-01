from pathlib import Path

from scl_ai_analyzer.ast import ProjectASTBuilder, render_ast_markdown
from scl_ai_analyzer.project import ProjectAnalyzer, ProjectResult


SOURCE = '''
ORGANIZATION_BLOCK "Main"
BEGIN
    MotorControl();
    MissingFC();
END_ORGANIZATION_BLOCK

FUNCTION_BLOCK "MotorControl"
VAR
    Drive : FB_Drive;
END_VAR
BEGIN
    #Drive();
    ResetAll();
END_FUNCTION_BLOCK

FUNCTION_BLOCK "FB_Drive"
BEGIN
END_FUNCTION_BLOCK

FUNCTION "ResetAll" : Bool
BEGIN
    ResetAll := TRUE;
END_FUNCTION
'''


def build_project() -> ProjectResult:
    source_file = Path("project.scl")
    blocks = ProjectAnalyzer().split_blocks(SOURCE, source_file)
    return ProjectResult(root=Path("."), source_files=(source_file,), blocks=tuple(blocks))


def test_builds_cross_file_symbols_and_edges() -> None:
    ast = ProjectASTBuilder().build(build_project())

    kinds = {(node.kind, node.name) for node in ast.nodes}
    assert ("OB", "Main") in kinds
    assert ("FB", "MotorControl") in kinds
    assert ("FC", "ResetAll") in kinds
    assert ("INSTANCE", "Drive") in kinds

    relations = {edge.relation for edge in ast.edges}
    assert "CALLS" in relations
    assert "CALLS_INSTANCE" in relations
    assert "INSTANCE_OF" in relations


def test_reports_unresolved_calls() -> None:
    ast = ProjectASTBuilder().build(build_project())

    assert any(item.code == "UNRESOLVED_CALL" for item in ast.diagnostics)
    assert any(not edge.resolved for edge in ast.edges)


def test_renders_ob_rooted_tree() -> None:
    report = render_ast_markdown(ProjectASTBuilder().build(build_project()))

    assert "项目树状结构" in report
    assert "OB `Main`" in report
    assert "FB `MotorControl`" in report
    assert "unresolved `missingfc`" in report
