from __future__ import annotations

import re
from dataclasses import dataclass

DEVICE_TAG_RE = re.compile(
    r"(?<![A-Z0-9])(?:[-=+]?[A-Z]{1,4}\d{1,6}(?:[._/-][A-Z0-9]+)?)",
    re.IGNORECASE,
)

DEVICE_PREFIXES = {
    "SB": "按钮/开关",
    "SQ": "限位/接近开关",
    "B": "传感器",
    "YV": "电磁阀",
    "Y": "执行器",
    "KM": "接触器",
    "K": "继电器",
    "QF": "断路器",
    "FU": "熔断器",
    "M": "电机",
    "U": "变频器/驱动器",
    "G": "电源/电源模块",
    "H": "指示灯",
    "S": "开关/按钮",
    "X": "端子/接口",
}

GENERIC_WORDS = {
    "PLC", "INPUT", "OUTPUT", "DIGITAL", "ANALOG", "ADDRESS", "PAGE", "EPLAN",
}


@dataclass(frozen=True)
class AssociatedText:
    device_tag: str
    device_type: str
    description: str
    confidence: str


def _normalize_line(line: str) -> str:
    return " ".join(line.split()).strip()


def _tag_prefix(tag: str) -> str:
    clean = tag.lstrip("-=+").upper()
    match = re.match(r"[A-Z]+", clean)
    return match.group(0) if match else ""


def _extract_device_tags(text: str) -> list[str]:
    tags: list[str] = []
    for match in DEVICE_TAG_RE.finditer(text.upper()):
        tag = match.group(0).strip()
        prefix = _tag_prefix(tag)
        if tag in GENERIC_WORDS:
            continue
        if prefix in DEVICE_PREFIXES or (prefix and len(prefix) <= 3):
            if tag not in tags:
                tags.append(tag)
    return tags


def _clean_description(text: str, address: str, tags: list[str]) -> str:
    result = text
    result = re.sub(re.escape(address), " ", result, flags=re.IGNORECASE)
    for tag in tags:
        result = re.sub(re.escape(tag), " ", result, flags=re.IGNORECASE)
    result = re.sub(r"\s+", " ", result).strip(" -:;|,，。")
    return result[:240]


def associate_address(lines: list[str], line_index: int, address: str) -> AssociatedText:
    """Associate one PLC address with a nearby EPLAN device tag and description.

    Priority: same line, previous line, next line, then two-line neighborhood.
    """
    candidates: list[tuple[int, str, str]] = []
    for distance in (0, 1, 2):
        indexes = [line_index] if distance == 0 else [line_index - distance, line_index + distance]
        for idx in indexes:
            if 0 <= idx < len(lines):
                line = _normalize_line(lines[idx])
                if line:
                    candidates.append((distance, line, "same" if distance == 0 else "nearby"))

    chosen_tag = ""
    chosen_type = ""
    description_parts: list[str] = []
    confidence = "low"

    for distance, line, _ in candidates:
        tags = _extract_device_tags(line)
        if tags and not chosen_tag:
            chosen_tag = tags[0]
            chosen_type = DEVICE_PREFIXES.get(_tag_prefix(chosen_tag), "元件")
            confidence = "high" if distance == 0 else "medium"
        cleaned = _clean_description(line, address, tags)
        if cleaned and cleaned not in description_parts:
            description_parts.append(cleaned)
        if chosen_tag and description_parts and distance >= 1:
            break

    description = " | ".join(description_parts[:2])
    return AssociatedText(chosen_tag, chosen_type, description, confidence)
