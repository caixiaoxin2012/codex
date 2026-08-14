from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final


SUPPORTED_VENDORS: Final[tuple[str, ...]] = (
    "auto",
    "siemens",
    "mitsubishi",
    "beckhoff",
    "codesys",
)

VENDOR_DISPLAY_NAMES: Final[dict[str, str]] = {
    "auto": "Auto",
    "siemens": "Siemens",
    "mitsubishi": "Mitsubishi",
    "beckhoff": "Beckhoff",
    "codesys": "CODESYS",
}


@dataclass(frozen=True)
class Classification:
    vendor: str
    io_type: str
    normalized_address: str


def normalize_vendor(vendor: str | None) -> str:
    value = (vendor or "auto").strip().lower()
    aliases = {
        "自动": "auto",
        "西门子": "siemens",
        "三菱": "mitsubishi",
        "倍福": "beckhoff",
    }
    value = aliases.get(value, value)
    if value not in SUPPORTED_VENDORS:
        choices = ", ".join(SUPPORTED_VENDORS)
        raise ValueError(f"不支持的PLC品牌：{vendor}。可选值：{choices}")
    return value


def _clean(address: object) -> str:
    if address is None:
        return ""
    text = str(address).strip().upper()
    text = re.sub(r"^AT\s+", "", text)
    return re.sub(r"\s+", "", text)


def _unknown(value: str, vendor: str = "Unknown") -> Classification:
    return Classification(vendor, "Unknown", value)


def _classify_iec(value: str, vendor: str) -> Classification:
    if re.fullmatch(r"%IX\d+(?:\.\d+)?", value):
        return Classification(vendor, "DI", value)
    if re.fullmatch(r"%QX\d+(?:\.\d+)?", value):
        return Classification(vendor, "DO", value)
    if re.fullmatch(r"%I[WDL]\d+", value):
        return Classification(vendor, "AI", value)
    if re.fullmatch(r"%Q[WDL]\d+", value):
        return Classification(vendor, "AO", value)
    if re.fullmatch(r"%M[XWDL]\d+(?:\.\d+)?", value):
        return Classification(vendor, "Memory", value)
    return _unknown(value, vendor)


def _classify_siemens(value: str) -> Classification:
    vendor = "Siemens"
    if re.fullmatch(r"DB\d+\.DB[XBWD]\d+(?:\.\d+)?", value):
        return Classification(vendor, "DB", value)
    if re.fullmatch(r"I\d+\.\d+", value):
        return Classification(vendor, "DI", value)
    if re.fullmatch(r"Q\d+\.\d+", value):
        return Classification(vendor, "DO", value)
    if re.fullmatch(r"(?:PIW|AIW|IW|ID|IL)\d+", value):
        return Classification(vendor, "AI", value)
    if re.fullmatch(r"(?:PQW|AQW|QW|QD|QL)\d+", value):
        return Classification(vendor, "AO", value)
    if re.fullmatch(r"M\d+\.\d+", value) or re.fullmatch(r"M[BWDL]?\d+", value):
        return Classification(vendor, "Memory", value)
    return _unknown(value, vendor)


def _classify_mitsubishi(value: str) -> Classification:
    vendor = "Mitsubishi"
    if re.fullmatch(r"X[0-9A-F]+", value):
        return Classification(vendor, "DI", value)
    if re.fullmatch(r"Y[0-9A-F]+", value):
        return Classification(vendor, "DO", value)
    if re.fullmatch(r"(?:M|L|B)[0-9A-F]+", value):
        return Classification(vendor, "Memory", value)
    if re.fullmatch(r"(?:D|W|R|ZR)\d+", value):
        return Classification(vendor, "Data Register", value)
    return _unknown(value, vendor)


def classify_address(address: object, vendor: str | None = "auto") -> Classification:
    selected_vendor = normalize_vendor(vendor)
    value = _clean(address)
    if not value or value == "NAN":
        display_vendor = VENDOR_DISPLAY_NAMES.get(selected_vendor, "Unknown")
        return _unknown(value, display_vendor if selected_vendor != "auto" else "Unknown")

    if selected_vendor == "siemens":
        return _classify_siemens(value)
    if selected_vendor == "mitsubishi":
        return _classify_mitsubishi(value)
    if selected_vendor == "beckhoff":
        return _classify_iec(value, "Beckhoff")
    if selected_vendor == "codesys":
        return _classify_iec(value, "CODESYS")

    # 自动模式按特征明显程度排序；重叠地址（如 M100）默认按 Siemens 处理。
    iec_result = _classify_iec(value, "Beckhoff/CODESYS")
    if iec_result.io_type != "Unknown":
        return iec_result

    siemens_result = _classify_siemens(value)
    if siemens_result.io_type != "Unknown":
        return siemens_result

    mitsubishi_result = _classify_mitsubishi(value)
    if mitsubishi_result.io_type != "Unknown":
        return mitsubishi_result

    return _unknown(value)
