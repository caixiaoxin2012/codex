from __future__ import annotations

import argparse
from pathlib import Path

from .parser import SCLParser, render_markdown
from .project import ProjectAnalyzer, render_project_markdown


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="scl-ai-analyzer",
        description="Analyze Siemens SCL files or exported project directories.",
    )
    parser.add_argument("input", type=Path, help="Path to a .scl file or project directory")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("scl_report.md"),
        help="Markdown report path",
    )
    parser.add_argument(
        "--export-dir",
        type=Path,
        help="Export each detected FB/FC/OB/DB as an individual .scl file",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.input.is_dir():
            project = ProjectAnalyzer().scan(args.input)
            report = render_project_markdown(project)
            exported = ()
            if args.export_dir:
                exported = ProjectAnalyzer.export_blocks(project, args.export_dir)
            summary = (
                f"{len(project.source_files)} source files, "
                f"{len(project.blocks)} blocks, {len(exported)} exported"
            )
        else:
            result = SCLParser().parse_file(args.input)
            report = render_markdown(result)
            block_label = result.block.name or "unknown block"
            summary = f"{block_label}, {len(result.variables)} variables"

        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report, encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise SystemExit(f"Analysis failed: {exc}") from exc

    print(f"Report generated: {args.output} ({summary})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
