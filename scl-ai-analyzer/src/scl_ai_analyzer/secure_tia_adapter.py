from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from .secure_xml import SecurePLCXMLLoader
from .tia_adapter import (
    SUPPORTED_TIA_VERSIONS,
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
    """TIA adapter variant that routes every XML file through SecurePLCXMLLoader."""

    def __init__(
        self,
        project_analyzer=None,
        version_detector: TIAVersionDetector | None = None,
        *,
        xml_loader: SecurePLCXMLLoader | None = None,
    ) -> None:
        super().__init__(
            project_analyzer=project_analyzer,
            version_detector=version_detector or StreamingTIAVersionDetector(),
        )
        self.xml_loader = xml_loader or SecurePLCXMLLoader()
        self._security_warnings: list[str] = []

    def scan(self, path: str | Path) -> TIAProjectResult:
        self._security_warnings = []
        result = super().scan(path)
        if not self._security_warnings:
            return result
        merged = tuple(dict.fromkeys(result.warnings + tuple(self._security_warnings)))
        return replace(result, warnings=merged)

    def parse_xml(self, path: str | Path) -> tuple[TIAExportItem, ...]:
        file_path = Path(path)
        secure = self.xml_loader.load(file_path)
        self._security_warnings.extend(
            f"{file_path.name}: {warning}" for warning in secure.warnings
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
