from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from .secure_xml import SecurePLCXMLLoader
from .tia_adapter import (
    TIA_BLOCK_TAGS,
    TIAExportAdapter as BaseTIAExportAdapter,
    TIAExportItem,
    TIAProjectResult,
)


class TIAExportAdapter(BaseTIAExportAdapter):
    """TIA adapter variant that routes every XML file through SecurePLCXMLLoader."""

    def __init__(self, *args, xml_loader: SecurePLCXMLLoader | None = None, **kwargs) -> None:
        super().__init__(*args, **kwargs)
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
