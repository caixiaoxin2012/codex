from __future__ import annotations

import argparse
from pathlib import Path

from .parser import SCLParser, render_markdown


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="scl-ai-analyzer",
        description="Parse a Siemens SCL file and generate a Markdown report.",
    )
    parser.add_argument("input", type=Path, help="Path to a .scl source file")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("scl_report.md"),
        help="Markdown report path",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        variables = SCLParser().parse_file(args.input)
        report = render_markdown(args.input.name, variables)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report, encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise SystemExit(f"Analysis failed: {exc}") from exc

    print(f"Report generated: {args.output} ({len(variables)} variables)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
