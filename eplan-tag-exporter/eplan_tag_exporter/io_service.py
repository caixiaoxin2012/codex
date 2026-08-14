from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .__main__ import build_detail, export_tags
from .exporters import export_csv, export_tia_csv, export_tia_xlsx


@dataclass(frozen=True)
class ExportResult:
    files: tuple[Path, ...]
    row_count: int


def export_outputs(
    input_path: Path,
    output_base: Path,
    plc_vendor: str = "auto",
    formats: Iterable[str] = ("xlsx",),
) -> ExportResult:
    selected = {fmt.lower() for fmt in formats}
    if not selected:
        raise ValueError("至少选择一种输出格式。")

    detail, _ = build_detail(input_path, plc_vendor)
    output_base.parent.mkdir(parents=True, exist_ok=True)
    files: list[Path] = []

    if "xlsx" in selected:
        xlsx = output_base.with_suffix(".xlsx")
        export_tags(input_path, xlsx, plc_vendor=plc_vendor)
        files.append(xlsx)
    if "csv" in selected:
        files.append(export_csv(detail, output_base))
    if "tia_csv" in selected:
        files.append(export_tia_csv(detail, output_base, input_path))
    if "tia_xlsx" in selected:
        files.append(export_tia_xlsx(detail, output_base, input_path))

    unknown = selected - {"xlsx", "csv", "tia_csv", "tia_xlsx"}
    if unknown:
        raise ValueError(f"暂不支持的输出格式：{', '.join(sorted(unknown))}")

    return ExportResult(tuple(files), len(detail))

