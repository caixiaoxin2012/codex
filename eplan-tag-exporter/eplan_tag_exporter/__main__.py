from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd
from pypdf import PdfReader

from .classifier import SUPPORTED_VENDORS, classify_address, normalize_vendor
from .pdf_association import associate_address

ADDRESS_ALIASES = ("地址", "Address", "PLC地址", "变量地址")
NAME_ALIASES = ("名称", "Name", "Tag", "变量名")
DESCRIPTION_ALIASES = ("说明", "Description", "Comment", "注释")

PDF_ADDRESS_TOKEN = re.compile(
    r"(?<![A-Z0-9_%])(?:"
    r"DB\d+\.DB[XBWD]\d+(?:\.\d+)?|"
    r"(?:PIW|PQW|AIW|AQW|IW|QW|ID|QD|IL|QL)\d+|"
    r"[IQM]\d+\.\d+|M[BWDL]?\d+|"
    r"[XY][0-9A-F]+|(?:D|W|R|ZR|L|B)\d+|"
    r"%[IQM][XWDL]\d+(?:\.\d+)?"
    r")(?![A-Z0-9_])",
    re.IGNORECASE,
)


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


def read_pdf(path: Path, plc_vendor: str) -> pd.DataFrame:
    reader = PdfReader(str(path))
    rows: list[dict[str, object]] = []
    extracted_chars = 0

    for page_number, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        extracted_chars += len(text.strip())
        lines = [" ".join(line.split()) for line in text.splitlines()]

        for line_index, clean_line in enumerate(lines):
            if not clean_line:
                continue
            for match in PDF_ADDRESS_TOKEN.finditer(clean_line):
                address = match.group(0).upper()
                result = classify_address(address, plc_vendor)
                if result.io_type == "Unknown":
                    continue
                associated = associate_address(lines, line_index, address)
                rows.append(
                    {
                        "页码": page_number,
                        "地址": address,
                        "元件代号": associated.device_tag,
                        "元件类型": associated.device_type,
                        "说明": associated.description,
                        "关联置信度": associated.confidence,
                        "原始行": clean_line,
                    }
                )

    if extracted_chars == 0:
        raise ValueError(
            "PDF 中没有可提取文字，可能是扫描版图纸。当前版本先支持可搜索文字型 PDF，"
            "扫描版将在下一步加入 OCR/图像识别。"
        )
    if not rows:
        raise ValueError("PDF 已读取，但没有识别到 PLC 地址。请检查 PLC 品牌选择或图纸地址格式。")

    return pd.DataFrame(rows).drop_duplicates(
        subset=["页码", "地址", "元件代号", "原始行"]
    ).reset_index(drop=True)


def read_table(path: Path, plc_vendor: str = "auto") -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return read_pdf(path, plc_vendor)
    if suffix == ".csv":
        try:
            return pd.read_csv(path, encoding="utf-8-sig")
        except UnicodeDecodeError:
            return pd.read_csv(path, encoding="gb18030")
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(path)
    raise ValueError("仅支持 PDF、CSV、XLSX、XLS 文件")


def build_detail(input_path: Path, plc_vendor: str = "auto") -> tuple[pd.DataFrame, pd.DataFrame]:
    selected_vendor = normalize_vendor(plc_vendor)
    source = read_table(input_path, selected_vendor)
    columns = [str(column) for column in source.columns]

    if input_path.suffix.lower() == ".pdf":
        address_col = "地址"
        name_col = "元件代号"
        description_col = "说明"
    else:
        address_col = find_column(columns, None, ADDRESS_ALIASES, required=True)
        name_col = find_column(columns, None, NAME_ALIASES, required=False)
        description_col = find_column(columns, None, DESCRIPTION_ALIASES, required=False)

    rows: list[dict[str, object]] = []
    for _, row in source.iterrows():
        result = classify_address(row[address_col], selected_vendor)
        rows.append(
            {
                "页码": row.get("页码", ""),
                "元件代号": row[name_col] if name_col else "",
                "元件类型": row.get("元件类型", ""),
                "原地址": row[address_col],
                "标准地址": result.normalized_address,
                "类型": result.io_type,
                "PLC品牌": result.vendor,
                "说明": row[description_col] if description_col else "",
                "关联置信度": row.get("关联置信度", ""),
                "原始行": row.get("原始行", ""),
            }
        )

    return pd.DataFrame(rows), source


def export_tags(
    input_path: Path,
    output_path: Path,
    address_column: str | None = None,
    name_column: str | None = None,
    description_column: str | None = None,
    plc_vendor: str = "auto",
) -> None:
    detail, source = build_detail(input_path, plc_vendor)
    summary = (
        detail.groupby(["PLC品牌", "类型"], dropna=False)
        .size()
        .reset_index(name="数量")
        .sort_values(["PLC品牌", "类型"])
    )
    device_summary = (
        detail[detail["元件代号"].astype(str).str.len() > 0]
        .groupby(["元件类型"], dropna=False)
        .size()
        .reset_index(name="数量")
        .sort_values("数量", ascending=False)
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        detail.to_excel(writer, sheet_name="IO明细", index=False)
        summary.to_excel(writer, sheet_name="IO统计", index=False)
        device_summary.to_excel(writer, sheet_name="元件统计", index=False)
        source.to_excel(writer, sheet_name="PDF识别原始数据" if input_path.suffix.lower() == ".pdf" else "原始数据", index=False)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="EPLAN PDF / PLC 标签识别与 Excel 表格导出工具")
    parser.add_argument("input", type=Path, help="输入 PDF、CSV、XLSX 或 XLS 文件")
    parser.add_argument("-o", "--output", type=Path, default=Path("eplan_tags_output.xlsx"))
    parser.add_argument(
        "--plc-vendor",
        default="auto",
        choices=SUPPORTED_VENDORS,
        help="PLC品牌：auto、siemens、mitsubishi、beckhoff、codesys（默认 auto）",
    )
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
            args.plc_vendor,
        )
    except (OSError, ValueError) as exc:
        print(f"错误：{exc}")
        return 1
    print(f"处理完成：{args.output}（PLC品牌：{args.plc_vendor}）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
