from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from .classifier import classify_address

ADDRESS_ALIASES = ("地址", "Address", "PLC地址", "变量地址")
NAME_ALIASES = ("名称", "Name", "Tag", "变量名")
DESCRIPTION_ALIASES = ("说明", "Description", "Comment", "注释")


def find_column(columns: list[str], requested: str | None, aliases: tuple[str, ...], required: bool) -> str | None:
    if requested:
        if requested not in columns:
            raise ValueError(f"找不到指定列：{requested}")
        return requested
    normalized = {str(column).strip().lower(): str(column) for column in columns}
    for alias in aliases:
        match = normalized.get(alias.lower())
        if match:
            return match
    if required:
        raise ValueError(f"找不到地址列，请使用 --address-column 指定。现有列：{', '.join(columns)}")
    return None


def read_table(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        try:
            return pd.read_csv(path, encoding="utf-8-sig")
        except UnicodeDecodeError:
            return pd.read_csv(path, encoding="gb18030")
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(path)
    raise ValueError("仅支持 CSV、XLSX、XLS 文件")


def export_tags(
    input_path: Path,
    output_path: Path,
    address_column: str | None = None,
    name_column: str | None = None,
    description_column: str | None = None,
) -> None:
    source = read_table(input_path)
    columns = [str(column) for column in source.columns]
    address_col = find_column(columns, address_column, ADDRESS_ALIASES, required=True)
    name_col = find_column(columns, name_column, NAME_ALIASES, required=False)
    description_col = find_column(columns, description_column, DESCRIPTION_ALIASES, required=False)

    rows: list[dict[str, object]] = []
    for _, row in source.iterrows():
        result = classify_address(row[address_col])
        rows.append(
            {
                "名称": row[name_col] if name_col else "",
                "原地址": row[address_col],
                "标准地址": result.normalized_address,
                "类型": result.io_type,
                "PLC品牌": result.vendor,
                "说明": row[description_col] if description_col else "",
            }
        )

    detail = pd.DataFrame(rows)
    summary = (
        detail.groupby(["PLC品牌", "类型"], dropna=False)
        .size()
        .reset_index(name="数量")
        .sort_values(["PLC品牌", "类型"])
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        detail.to_excel(writer, sheet_name="IO明细", index=False)
        summary.to_excel(writer, sheet_name="IO统计", index=False)
        source.to_excel(writer, sheet_name="原始数据", index=False)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="EPLAN / PLC 标签识别与 Excel 导出工具")
    parser.add_argument("input", type=Path, help="输入 CSV、XLSX 或 XLS 文件")
    parser.add_argument("-o", "--output", type=Path, default=Path("eplan_tags_output.xlsx"))
    parser.add_argument("--address-column")
    parser.add_argument("--name-column")
    parser.add_argument("--description-column")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        export_tags(
            args.input,
            args.output,
            args.address_column,
            args.name_column,
            args.description_column,
        )
    except (OSError, ValueError) as exc:
        print(f"错误：{exc}")
        return 1
    print(f"处理完成：{args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
