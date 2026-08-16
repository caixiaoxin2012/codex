from pathlib import Path

from scl_ai_analyzer.project import ProjectAnalyzer
from scl_ai_analyzer.tag_checker import (
    RULE_DUPLICATE,
    RULE_MISSING_COMMENT,
    RULE_NAMING,
    RULE_UNUSED,
    TagChecker,
)


def test_tag_checker_detects_first_four_review_categories(tmp_path: Path) -> None:
    source = tmp_path / "review.scl"
    source.write_text(
        '''
FUNCTION_BLOCK FB_Review
VAR_INPUT
    Start : Bool; // Cycle start
    Tag1 : Bool;
END_VAR
VAR
    MotorReady : Bool; // Motor ready state
    MotorReady : Bool; // Accidental duplicate
    UnusedThing : Bool; // Reserved but currently unused
END_VAR
BEGIN
    IF Start THEN
        MotorReady := TRUE;
    END_IF;
END_FUNCTION_BLOCK
'''.lstrip(),
        encoding="utf-8",
    )

    project = ProjectAnalyzer().scan(tmp_path)
    report = TagChecker().check_project(project)
    rules = {item.rule_id for item in report.issues}

    assert RULE_NAMING in rules
    assert RULE_MISSING_COMMENT in rules
    assert RULE_DUPLICATE in rules
    assert RULE_UNUSED in rules
    assert any(item.variable == "Tag1" and item.rule_id == RULE_MISSING_COMMENT for item in report.issues)
    assert any(item.variable == "MotorReady" and item.rule_id == RULE_DUPLICATE for item in report.issues)
    assert any(item.variable == "UnusedThing" and item.rule_id == RULE_UNUSED for item in report.issues)


def test_preceding_comment_counts_as_engineering_comment(tmp_path: Path) -> None:
    source = tmp_path / "commented.scl"
    source.write_text(
        '''
FUNCTION_BLOCK FB_Commented
VAR_INPUT
    // Start command from HMI
    StartCmd : Bool;
END_VAR
BEGIN
    IF StartCmd THEN
        ;
    END_IF;
END_FUNCTION_BLOCK
'''.lstrip(),
        encoding="utf-8",
    )

    project = ProjectAnalyzer().scan(tmp_path)
    report = TagChecker().check_project(project)

    assert not any(
        item.variable == "StartCmd" and item.rule_id == RULE_MISSING_COMMENT
        for item in report.issues
    )
    assert not any(
        item.variable == "StartCmd" and item.rule_id == RULE_UNUSED
        for item in report.issues
    )
