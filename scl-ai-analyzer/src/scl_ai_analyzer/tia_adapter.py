from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from .project import ProjectAnalyzer, ProjectResult, SourceBlock


TIA_BLOCK_TAGS = {
    "SW.Blocks.FB": "FUNCTION_BLOCK",
    "SW.Blocks.FC": "FUNCTION",
    "SW.Blocks.OB": "ORGANIZATION_BLOCK",
    "SW.Blocks.DB": "DATA_BLOCK",
    "SW.Types.PlcStruct": "TYPE",
    "SW.Types.PlcEnum": "TYPE",
}

TEXT_EXTENSIONS = {".scl", ".awl", ".udt", ".db"}
XML_EXTENSIONS = {".xml"}


@dataclass(frozen=True)
class TIAExportItem:
    source_file: Path
    item_type: str
    name: str
    number: str | None = None
    programming_language: str | None = None
    source_text: str | None = None


@dataclass(frozen=True)
class TIAProjectResult:
    root: Path
    files: tuple[Path, ...]
    items: tuple[TIAExportItem, ...]
    scl_project: ProjectResult
    warnings: tuple[str, ...] = ()


class TIAExportAdapter:
    """Adapt exported TIA Portal XML/text files into the common SCL project model.

    The adapter intentionally does not open or modify .zap project archives. It works
    with files exported through TIA Portal/Openness or project libraries.
    """

    def __init__(self, project_analyzer: ProjectAnalyzer | None = None) -> None:
        self.project_analyzer = project_analyzer or ProjectAnalyzer()

    def scan(self, path: str | Path) -> TIAProjectResult:
        root = Path(path)
        if not root.exists():
            raise FileNotFoundError(f"TIA export path not found: {root}")

        files = self._collect_files(root)
        items: list[TIAExportItem] = []
        warnings: list[str] = []
        source_blocks: list[SourceBlock] = []
        scl_source_files: list[Path] = []

        for file_path in files:
            suffix = file_path.suffix.lower()
            try:
                if suffix in TEXT_EXTENSIONS:
                    text = file_path.read_text(encoding="utf-8-sig", errors="replace")
                    blocks = self.project_analyzer.split_blocks(text, file_path)
                    source_blocks.extend(blocks)
                    scl_source_files.append(file_path)
                    for block in blocks:
                        items.append(
                            TIAExportItem(
                                source_file=file_path,
                                item_type=block.block_type,
                                name=block.name,
                                source_text=block.text,
                            )
                        )
                elif suffix in XML_EXTENSIONS:
                    xml_items = self.parse_xml(file_path)
                    items.extend(xml_items)
                    for item in xml_items:
                        if not item.source_text:
                            continue
                        blocks = self.project_analyzer.split_blocks(
                            item.source_text, file_path
                        )
                        source_blocks.extend(blocks)
                        if blocks:
                            scl_source_files.append(file_path)
            except (OSError, ET.ParseError) as exc:
                warnings.append(f"{file_path}: {exc}")

        project_root = root if root.is_dir() else root.parent
        scl_project = ProjectResult(
            root=project_root,
            source_files=tuple(dict.fromkeys(scl_source_files)),
            blocks=tuple(source_blocks),
        )
        return TIAProjectResult(
            root=project_root,
            files=files,
            items=tuple(items),
            scl_project=scl_project,
            warnings=tuple(warnings),
        )

    def parse_xml(self, path: str | Path) -> tuple[TIAExportItem, ...]:
        file_path = Path(path)
        root = ET.parse(file_path).getroot()
        items: list[TIAExportItem] = []

        for element in root.iter():
            local_name = self._local_name(element.tag)
            item_type = TIA_BLOCK_TAGS.get(local_name)
            if item_type is None:
                continue

            name = self._find_attribute_text(element, "Name") or self._find_name(element)
            if not name:
                name = f"unnamed_{len(items) + 1}"

            number = self._find_attribute_text(element, "Number")
            language = self._find_attribute_text(element, "ProgrammingLanguage")
            source_text = self._extract_source_text(element)

            items.append(
                TIAExportItem(
                    source_file=file_path,
                    item_type=item_type,
                    name=name,
                    number=number,
                    programming_language=language,
                    source_text=source_text,
                )
            )

        return tuple(items)

    @staticmethod
    def _collect_files(root: Path) -> tuple[Path, ...]:
        if root.is_file():
            return (root,)
        accepted = TEXT_EXTENSIONS | XML_EXTENSIONS
        return tuple(
            sorted(
                path
                for path in root.rglob("*")
                if path.is_file() and path.suffix.lower() in accepted
            )
        )

    @classmethod
    def _find_attribute_text(cls, element: ET.Element, name: str) -> str | None:
        for child in element.iter():
            if cls._local_name(child.tag) != "Attribute":
                continue
            if child.attrib.get("Name", "").casefold() != name.casefold():
                continue
            value = "".join(child.itertext()).strip()
            if value:
                return value
        return None

    @classmethod
    def _find_name(cls, element: ET.Element) -> str | None:
        for child in element.iter():
            if cls._local_name(child.tag) == "Name":
                value = "".join(child.itertext()).strip()
                if value:
                    return value
        return None

    @classmethod
    def _extract_source_text(cls, element: ET.Element) -> str | None:
        candidates: list[str] = []
        for child in element.iter():
            local_name = cls._local_name(child.tag)
            if local_name in {"StructuredText", "Source", "Text", "Token"}:
                value = "".join(child.itertext()).strip()
                if value:
                    candidates.append(value)

        joined = "\n".join(dict.fromkeys(candidates)).strip()
        if not joined:
            return None

        if re.search(
            r"\b(FUNCTION_BLOCK|FUNCTION|ORGANIZATION_BLOCK|DATA_BLOCK)\b",
            joined,
            flags=re.IGNORECASE,
        ):
            return joined + ("\n" if not joined.endswith("\n") else "")
        return None

    @staticmethod
    def _local_name(tag: str) -> str:
        return tag.rsplit("}", 1)[-1]


def render_tia_markdown(result: TIAProjectResult) -> str:
    counts: dict[str, int] = {}
    for item in result.items:
        counts[item.item_type] = counts.get(item.item_type, 0) + 1

    lines = [
        "# TIA Portal 导出分析报告",
        "",
        f"- **导出目录：** `{result.root}`",
        f"- **扫描文件：** {len(result.files)}",
        f"- **识别对象：** {len(result.items)}",
        f"- **可进入 SCL 解析器的程序块：** {len(result.scl_project.blocks)}",
        "",
        "## 对象统计",
        "",
        "| 对象类型 | 数量 |",
        "|---|---:|",
    ]
    for item_type in (
        "FUNCTION_BLOCK",
        "FUNCTION",
        "ORGANIZATION_BLOCK",
        "DATA_BLOCK",
        "TYPE",
    ):
        lines.append(f"| {item_type} | {counts.get(item_type, 0)} |")

    lines.extend(
        [
            "",
            "## 对象索引",
            "",
            "| 类型 | 名称 | 编号 | 语言 | 来源文件 | SCL 源码 |",
            "|---|---|---|---|---|---|",
        ]
    )
    for item in result.items:
        lines.append(
            f"| {item.item_type} | {item.name} | {item.number or '-'} "
            f"| {item.programming_language or '-'} | {item.source_file.name} "
            f"| {'是' if item.source_text else '否'} |"
        )

    if result.warnings:
        lines.extend(["", "## 警告", ""])
        lines.extend(f"- {warning}" for warning in result.warnings)

    lines.extend(
        [
            "",
            "## 限制",
            "",
            "XML 导出的结构会因 TIA Portal 版本、导出方式和对象类型而不同。当前版本优先提取对象元数据，并仅在 XML 中存在完整结构化文本时交给 SCL 解析器。",
            "",
        ]
    )
    return "\n".join(lines)
