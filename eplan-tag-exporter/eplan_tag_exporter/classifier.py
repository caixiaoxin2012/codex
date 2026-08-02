from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Classification:
    vendor: str
    io_type: str
    normalized_address: str


def _clean(address: object) -> str:
    if address is None:
        return ""
    text = str(address).strip().upper()
    text = re.sub(r"^AT\s+", "", text)
    return re.sub(r"\s+", "", text)


def classify_address(address: object) -> Classification:
    value = _clean(address)
    if not value or value == "NAN":
        return Classification("Unknown", "Unknown", value)

    # IEC direct-address notation used by Beckhoff TwinCAT and CODESYS.
    if re.fullmatch(r"%IX\d+(?:\.\d+)?", value):
        return Classification("Beckhoff/CODESYS", "DI", value)
    if re.fullmatch(r"%QX\d+(?:\.\d+)?", value):
        return Classification("Beckhoff/CODESYS", "DO", value)
    if re.fullmatch(r"%I[WDL]\d+", value):
        return Classification("Beckhoff/CODESYS", "AI", value)
    if re.fullmatch(r"%Q[WDL]\d+", value):
        return Classification("Beckhoff/CODESYS", "AO", value)
    if re.fullmatch(r"%M[XWDL]\d+(?:\.\d+)?", value):
        return Classification("Beckhoff/CODESYS", "Memory", value)

    # Siemens absolute addressing.
    if re.fullmatch(r"DB\d+\.DB[XBWD]\d+(?:\.\d+)?", value):
        return Classification("Siemens", "DB", value)
    if re.fullmatch(r"I\d+\.\d+", value):
        return Classification("Siemens", "DI", value)
    if re.fullmatch(r"Q\d+\.\d+", value):
        return Classification("Siemens", "DO", value)
    if re.fullmatch(r"(?:PIW|AIW|IW|ID|IL)\d+", value):
        return Classification("Siemens", "AI", value)
    if re.fullmatch(r"(?:PQW|AQW|QW|QD|QL)\d+", value):
        return Classification("Siemens", "AO", value)
    if re.fullmatch(r"M\d+\.\d+", value):
        return Classification("Siemens", "Memory", value)
    if re.fullmatch(r"M[BWDL]?\d+", value):
        return Classification("Siemens", "Memory", value)

    # Mitsubishi device notation.
    if re.fullmatch(r"X[0-9A-F]+", value):
        return Classification("Mitsubishi", "DI", value)
    if re.fullmatch(r"Y[0-9A-F]+", value):
        return Classification("Mitsubishi", "DO", value)
    if re.fullmatch(r"(?:M|L|B)[0-9A-F]+", value):
        return Classification("Mitsubishi", "Memory", value)
    if re.fullmatch(r"(?:D|W|R|ZR)\d+", value):
        return Classification("Mitsubishi", "Data Register", value)

    return Classification("Unknown", "Unknown", value)
