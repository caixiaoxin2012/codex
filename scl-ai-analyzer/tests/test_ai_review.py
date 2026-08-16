from scl_ai_analyzer.ai_review import build_chinese_review_prompt, render_rule_based_chinese_summary
from scl_ai_analyzer.tag_checker import TagCheckReport, TagIssue


def test_ai_review_prompt_uses_structured_findings_only() -> None:
    report = TagCheckReport(
        checked_blocks=1,
        checked_variables=2,
        issues=(
            TagIssue(
                rule_id="UNUSED_VARIABLE",
                severity="warning",
                block_name="FB_Test",
                block_type="FUNCTION_BLOCK",
                variable="UnusedThing",
                section="Static",
                data_type="Bool",
                line_number=8,
                message="变量 UnusedThing 仅发现声明，未发现可追踪的读取或写入。",
                suggestion="确认是否已废弃。",
            ),
        ),
    )

    prompt = build_chinese_review_prompt(report)
    assert "PLC/SCL Code Review" in prompt
    assert "FB_Test" in prompt
    assert "UnusedThing" in prompt
    assert '"line": 8' in prompt
    assert "不要虚构源码" in prompt


def test_rule_based_summary_is_available_offline() -> None:
    report = TagCheckReport(issues=(), checked_blocks=2, checked_variables=10)
    text = render_rule_based_chinese_summary(report)
    assert "2 个程序块" in text
    assert "10 个变量声明" in text
