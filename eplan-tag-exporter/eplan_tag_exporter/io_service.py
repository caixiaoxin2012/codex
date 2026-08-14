from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd

from .__main__ import export_tags, read_table
from .classifier import classify_address, normalize_vendor
from .exporters import export_csv, export_tia_csv


@dataclass(frozen=True)
class ExportResult:
    files: tuple[Path, ...]
    row_count: int


def build_detail(input_path: Path, plc_vendor: str = "auto") -> pd.DataFrame:
    vendor = normalize_vendor(plc_vendor)
    source = read_table(input_path, vendor)

    if input_path.suffix.lower() == ".pdf":
        rows = []
        for _, row in source.iterrows():
            result = classify_address(row["地址"], vendor)
            rows.append(
                {
                    "页码": row.get("页码", ""),
                    "名称": "",
                    "原地址": row["地址"],
                    "标准地址": result.normalized_address,
                    "类型": result.io_type,
                    "PLC品牌": result.vendor,
                    "说明/所在行": row.get("原始行", ""),
                }
            )
        return pd.DataFrame(rows)

    address_candidates = ["地址", "Address", "PLC地址", "变量地址"]
    columns = {str(c).strip().lower(): str(c) for c in source.columns}
    address_col = next((columns[x.lower()] for x in address_candidates if x.lower() in columns), None)
    if not address_col:
        raise ValueError("输入表格中找不到地址列。")

    name_col = next((columns[x.lower()] for x in ["名称", "Name", "Tag", "变量名"] if x.lower() in columns), None)
    desc_col = next((columns[x.lower()] for x in ["说明", "Description", "Comment", "注释"] if x.lower() in columns), None)

    rows = []
    for _, row in source.iterrows():
        result = classify_address(row[address_col], vendor)
        rows.append(
            {
                "页码": row.get("页码", ""),
                "名称": row[name_col] if name_col else "",
                "原地址": row[address_col],
                "标准地址": result.normalized_address,
                "类型": result.io_type,
                "PLC品牌": result.vendor,
                "说明/所在行": row[desc_col] if desc_col else "",
            }
        )
    return pd.DataFrame(rows)


def export_outputs(
    input_path: Path,
    output_base: Path,
    plc_vendor: str = "auto",
    formats: Iterable[str] = ("xlsx",),
) -> ExportResult:
    selected = {fmt.lower() for fmt in formats}
    if not selected:
        raise ValueError("至少选择一种输出格式。")

    detail = build_detail(input_path, plc_vendor)
    output_base.parent.mkdir(parents=True, exist_ok=True)
    files: list[Path] = []

    if "xlsx" in selected:
        xlsx = output_base.with_suffix(".xlsx")
        export_tags(input_path, xlsx, plc_vendor=plc_vendor)
        files.append(xlsx)
    if "csv" in selected:
        files.append(export_csv(detail, output_base))
    if "tia_csv" in selected:
        files.append(export_tia_csv(detail, output_base))

    unknown = selected - {"xlsx", "csv", "tia_csv"}
    if unknown:
        raise ValueError(f"暂不支持的输出格式：{', '.join(sorted(unknown))}")

    return ExportResult(tuple(files), len(detail))
