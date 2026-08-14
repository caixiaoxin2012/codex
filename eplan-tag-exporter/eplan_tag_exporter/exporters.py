from __future__ import annotations

from pathlib import Path

import pandas as pd


def export_csv(detail: pd.DataFrame, output_path: Path) -> Path:
    """Export recognized PLC tags as UTF-8 BOM CSV for engineering tools/Excel."""
    path = output_path.with_suffix(".csv")
    detail.to_csv(path, index=False, encoding="utf-8-sig")
    return path


def export_tia_csv(detail: pd.DataFrame, output_path: Path) -> Path:
    """Export a simple Siemens TIA Portal-friendly tag table template."""
    path = output_path.with_name(f"{output_path.stem}_TIA.csv")
    names = detail.get("元件代号", pd.Series([""] * len(detail))).fillna("")
    comments = detail.get("说明", pd.Series([""] * len(detail))).fillna("")
    tia = pd.DataFrame(
        {
            "Name": names,
            "Path": [""] * len(detail),
            "Data Type": detail["类型"].map({"DI": "Bool", "DO": "Bool", "AI": "Int", "AO": "Int"}).fillna(""),
            "Logical Address": detail["标准地址"],
            "Comment": comments,
        }
    )
    tia.to_csv(path, index=False, encoding="utf-8-sig")
    return path
