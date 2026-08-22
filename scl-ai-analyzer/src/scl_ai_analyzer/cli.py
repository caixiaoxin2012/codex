from __future__ import annotations

import argparse
from pathlib import Path

from .parser import render_markdown
from .project import ProjectAnalyzer, render_project_markdown
from .secure_loader import SecureLoader
from .secure_project import SecureProjectAnalyzer
from .secure_tia_adapter import TIAExportAdapter
from .tag_checker import TagChecker, render_tag_check_markdown
from .tia_adapter import render_tia_markdown


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="scl-ai-analyzer",
        description="Analyze Siemens SCL files, exported projects, and TIA XML exports.",
    )
    parser.add_argument("input", type=Path, help="SCL file or exported project directory")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("scl_report.md"),
        help="Markdown report path",
    )
    parser.add_argument(
        "--mode",
        choices=("auto", "single", "project", "tia"),
        default="auto",
        help="Analysis mode; auto chooses from the input type",
    )
    parser.add_argument(
        "--export-dir",
        type=Path,
        help="Export detected FB/FC/OB/DB blocks as individual .scl files",
    )
    parser.add_argument(
        "--code-review",
        action="store_true",
        help="Append PLC variable-quality Code Review checks to project/TIA reports",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        mode = _resolve_mode(args.input, args.mode)
        review_project = None

        if mode == "single":
            loaded = SecureLoader().load(args.input, source="cli_single_scl")
            result = loaded.scl_analysis
            if result is None:
                raise ValueError(f"SCL 安全加载未返回解析结果：{args.input}")
            report = render_markdown(result)
            summary = (
                f"{result.block.name or 'unknown block'}, {len(result.variables)} variables, "
                f"sha256={loaded.sha256[:12]}…, {loaded.hash_status}"
            )
        elif mode == "project":
            project = SecureProjectAnalyzer().scan(args.input)
            review_project = project
            report = render_project_markdown(project)
            exported = ()
            if args.export_dir:
                exported = ProjectAnalyzer.export_blocks(project, args.export_dir)
            summary = (
                f"{len(project.source_files)} source files, "
                f"{len(project.blocks)} blocks, {len(exported)} exported"
            )
        else:
            tia_result = TIAExportAdapter().scan(args.input)
            review_project = tia_result.scl_project
            report = render_tia_markdown(tia_result)
            exported = ()
            if args.export_dir:
                exported = ProjectAnalyzer.export_blocks(
                    tia_result.scl_project, args.export_dir
                )
            summary = (
                f"{len(tia_result.items)} TIA objects, "
                f"{len(tia_result.scl_project.blocks)} parsed SCL blocks, "
                f"{len(exported)} exported"
            )

        if args.code_review and review_project is not None:
            tag_report = TagChecker().check_project(review_project)
            report = report.rstrip() + "\n\n" + render_tag_check_markdown(tag_report) + "\n"

        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report, encoding="utf-8")
    except (OSError, UnicodeError, ValueError) as exc:
        raise SystemExit(f"Analysis failed: {exc}") from exc

    print(f"Report generated: {args.output} ({summary})")
    return 0


def _resolve_mode(path: Path, requested: str) -> str:
    if requested != "auto":
        return requested
    if path.is_file() and path.suffix.lower() == ".scl":
        return "single"
    if path.is_file() and path.suffix.lower() == ".xml":
        return "tia"
    if path.is_dir() and any(path.rglob("*.xml")):
        return "tia"
    return "project"


if __name__ == "__main__":
    raise SystemExit(main())
