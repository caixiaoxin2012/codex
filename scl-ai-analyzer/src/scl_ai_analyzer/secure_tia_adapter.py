from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from .project import ProjectResult, SourceBlock
from .secure_loader import SecureLoader
from .secure_xml import SecurePLCXMLLoader
from .tia_adapter import (
    SUPPORTED_TIA_VERSIONS,
    TEXT_EXTENSIONS,
    XML_EXTENSIONS,
    TIA_BLOCK_TAGS,
    TIAExportAdapter as BaseTIAExportAdapter,
    TIAExportItem,
    TIAProjectResult,
    TIAVersionDetector,
    VersionDetection,
)


class StreamingTIAVersionDetector(TIAVersionDetector):
    """Detect TIA version without loading an entire large XML file into memory."""

    def detect(self, root: Path, files: tuple[Path, ...]) -> VersionDetection:
        evidence_by_version: dict[str, list[tuple[int, str]]] = {
            version: [] for version in SUPPORTED_TIA_VERSIONS
        }

        for file_path in files:
            self._collect_from_text(
                file_path.name,
                f"文件名：{file_path.name}",
                evidence_by_version,
                base_score=1,
            )
            if file_path.suffix.lower() != ".xml":
                continue
            try:
                with file_path.open("rb") as stream:
                    prefix = stream.read(500_000)
                text = prefix.decode("utf-8-sig", errors="replace")
            except OSError:
                continue
            self._collect_from_text(
                text,
                f"XML：{file_path.name}",
                evidence_by_version,
                base_score=2,
            )

        ranked: list[tuple[int, str, list[tuple[int, str]]]] = []
        for version, entries in evidence_by_version.items():
            if entries:
                ranked.append((sum(score for score, _ in entries), version, entries))
        ranked.sort(reverse=True)

        if not ranked:
            return VersionDetection(
                version=None,
                confidence="unknown",
                evidence=("未发现 V16-V21 版本元数据，使用通用兼容模式",),
            )

        best_score, best_version, entries = ranked[0]
        second_score = ranked[1][0] if len(ranked) > 1 else 0
        if best_score >= 5 and best_score >= second_score + 2:
            confidence = "high"
        elif best_score >= 3 and best_score > second_score:
            confidence = "medium"
        else:
            confidence = "low"

        return VersionDetection(
            version=best_version,
            confidence=confidence,
            evidence=tuple(dict.fromkeys(text for _, text in entries)),
        )


class TIAExportAdapter(BaseTIAExportAdapter):
    """TIA adapter whose `.scl/.xml` reads pass through SecureLoader.

    Legacy `.awl/.udt/.db` text inputs keep their existing compatibility path for
    now; V0.11.3 specifically unifies the SCL/XML security boundary.
    """

    def __init__(
        self,
        project_analyzer=None,
        version_detector: TIAVersionDetector | None = None,
        *,
        secure_loader: SecureLoader | None = None,
        xml_loader: SecurePLCXMLLoader | None = None,
    ) -> None:
        super().__init__(
            project_analyzer=project_analyzer,
            version_detector=version_detector or StreamingTIAVersionDetector(),
        )
        if secure_loader is not None and xml_loader is not None:
            raise ValueError("secure_loader 与 xml_loader 不能同时指定")
        self.secure_loader = secure_loader or SecureLoader(xml_loader=xml_loader)
        # Backward-compatible attribute for callers/tests that inspect the XML loader.
        self.xml_loader = self.secure_loader.xml_loader
        self._security_warnings: list[str] = []

    def scan(self, path: str | Path) -> TIAProjectResult:
        root = Path(path)
        if not root.exists():
            raise FileNotFoundError(f"TIA export path not found: {root}")

        self._security_warnings = []
        files = self._collect_files(root)
        version = self.version_detector.detect(root, files)
        items: list[TIAExportItem] = []
        warnings: list[str] = []
        source_blocks: list[SourceBlock] = []
        scl_source_files: list[Path] = []

        for file_path in files:
            suffix = file_path.suffix.lower()
            try:
                if suffix in TEXT_EXTENSIONS:
                    if suffix == ".scl":
                        loaded = self.secure_loader.load(
                            file_path,
                            source=f"tia_export_scl:{root}",
                        )
                        text = loaded.text or ""
                        self._security_warnings.extend(
                            f"{file_path.name}: {warning}" for warning in loaded.warnings
                        )
                    else:
                        text = file_path.read_text(
                            encoding="utf-8-sig",
                            errors="replace",
                        )
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
                            item.source_text,
                            file_path,
                        )
                        source_blocks.extend(blocks)
                        if blocks:
                            scl_source_files.append(file_path)
            except (OSError, ET.ParseError, ValueError) as exc:
                warnings.append(f"{file_path}: {exc}")

        project_root = root if root.is_dir() else root.parent
        scl_project = ProjectResult(
            root=project_root,
            source_files=tuple(dict.fromkeys(scl_source_files)),
            blocks=tuple(source_blocks),
        )
        merged_warnings = tuple(
            dict.fromkeys(tuple(warnings) + tuple(self._security_warnings))
        )
        return TIAProjectResult(
            root=project_root,
            files=files,
            items=tuple(items),
            scl_project=scl_project,
            version=version,
            warnings=merged_warnings,
        )

    def parse_xml(self, path: str | Path) -> tuple[TIAExportItem, ...]:
        file_path = Path(path)
        loaded = self.secure_loader.load(
            file_path,
            source="tia_export_xml",
        )
        secure = loaded.xml_result
        if secure is None:
            raise ValueError(f"XML 安全加载未返回解析结果：{file_path}")
        self._security_warnings.extend(
            f"{file_path.name}: {warning}" for warning in loaded.warnings
        )

        items: list[TIAExportItem] = []
        for element in secure.root.iter():
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
