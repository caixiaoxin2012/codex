from __future__ import annotations

import json
import os
from dataclasses import dataclass

from .tag_checker import TagCheckReport


class AIReviewUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class AIReviewResult:
    text: str
    provider: str
    model: str
    prompt: str


def build_chinese_review_prompt(report: TagCheckReport) -> str:
    findings = [
        {
            "rule_id": item.rule_id,
            "severity": item.severity,
            "block": item.block_name,
            "block_type": item.block_type,
            "variable": item.variable,
            "section": item.section,
            "data_type": item.data_type,
            "line": item.line_number,
            "message": item.message,
            "suggestion": item.suggestion,
            "evidence": item.evidence,
        }
        for item in report.issues
    ]
    payload = {
        "checked_blocks": report.checked_blocks,
        "checked_variables": report.checked_variables,
        "issue_count": len(report.issues),
        "findings": findings,
    }
    return (
        "你是一名严谨的 PLC/SCL Code Review 助手。\n"
        "请只根据下面的规则检查结果生成中文工程说明，不要虚构源码、工艺逻辑或安全结论。\n"
        "要求：\n"
        "1. 先给出总体结论和风险优先级；\n"
        "2. 按重复变量、未使用变量、缺失注释、命名问题分组说明；\n"
        "3. 对 error 优先处理，对 warning 给出可执行整改建议；\n"
        "4. 每个重要问题尽量引用程序块、变量和行号；\n"
        "5. 明确指出静态分析限制，例如 HMI/OPC/动态访问可能造成未使用变量误报；\n"
        "6. 不要声称规则检查未提供的事实。\n\n"
        "结构化检查结果：\n"
        + json.dumps(payload, ensure_ascii=False, indent=2)
    )


def render_rule_based_chinese_summary(report: TagCheckReport) -> str:
    if not report.issues:
        return (
            f"本次检查覆盖 {report.checked_blocks} 个程序块、{report.checked_variables} 个变量声明。"
            "当前四类规则未发现问题。仍建议对 HMI/OPC 外部绑定、动态访问和安全相关变量进行人工复核。"
        )

    errors = sum(1 for item in report.issues if item.severity == "error")
    warnings = sum(1 for item in report.issues if item.severity == "warning")
    lines = [
        f"本次检查覆盖 {report.checked_blocks} 个程序块、{report.checked_variables} 个变量声明，共发现 {len(report.issues)} 个问题，"
        f"其中 error {errors} 个、warning {warnings} 个。",
        "建议优先处理重复声明，再清理未使用变量，随后补齐注释并统一命名。",
    ]
    if errors:
        lines.append("存在 error 级问题，建议在继续功能扩展前先完成复核和整改。")
    lines.append("未使用变量属于静态分析候选；HMI/OPC、外部映射或动态访问场景可能需要人工排除误报。")
    return "\n".join(lines)


class OpenAIChineseReviewGenerator:
    """Generate a Chinese review from structured findings only.

    The full PLC source is intentionally not sent. The SDK reads OPENAI_API_KEY from
    the environment by default. SCL_AI_REVIEW_MODEL can override the default model.
    """

    def __init__(self, model: str | None = None) -> None:
        self.model = model or os.getenv("SCL_AI_REVIEW_MODEL", "gpt-5.6")

    def generate(self, report: TagCheckReport) -> AIReviewResult:
        prompt = build_chinese_review_prompt(report)
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise AIReviewUnavailable(
                "未安装 openai Python SDK。请安装项目的 ai 可选依赖后再使用 AI 中文说明。"
            ) from exc

        if not os.getenv("OPENAI_API_KEY"):
            raise AIReviewUnavailable(
                "未检测到 OPENAI_API_KEY。规则检查仍可离线使用；配置 API Key 后可生成 AI 中文说明。"
            )

        try:
            client = OpenAI()
            response = client.responses.create(model=self.model, input=prompt)
            text = (response.output_text or "").strip()
        except Exception as exc:  # Provider/network boundary: surface a concise error to GUI.
            raise AIReviewUnavailable(f"AI 中文说明生成失败：{exc}") from exc

        if not text:
            raise AIReviewUnavailable("AI 返回了空的中文说明。")
        return AIReviewResult(
            text=text,
            provider="OpenAI",
            model=self.model,
            prompt=prompt,
        )
