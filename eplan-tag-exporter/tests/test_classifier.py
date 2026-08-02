import pytest

from eplan_tag_exporter.classifier import classify_address, normalize_vendor


@pytest.mark.parametrize(
    ("address", "vendor", "io_type"),
    [
        ("I0.0", "Siemens", "DI"),
        ("Q0.1", "Siemens", "DO"),
        ("PIW256", "Siemens", "AI"),
        ("AQW80", "Siemens", "AO"),
        ("DB100.DBX0.0", "Siemens", "DB"),
        ("X10", "Mitsubishi", "DI"),
        ("Y20", "Mitsubishi", "DO"),
        ("M100", "Siemens", "Memory"),
        ("D200", "Mitsubishi", "Data Register"),
        ("AT %IX0.0", "Beckhoff/CODESYS", "DI"),
        ("%QX0.0", "Beckhoff/CODESYS", "DO"),
        ("%IW0", "Beckhoff/CODESYS", "AI"),
        ("%QW0", "Beckhoff/CODESYS", "AO"),
    ],
)
def test_auto_classify_address(address: str, vendor: str, io_type: str) -> None:
    result = classify_address(address)
    assert result.vendor == vendor
    assert result.io_type == io_type


def test_manual_mitsubishi_resolves_m_address() -> None:
    result = classify_address("M100", "mitsubishi")
    assert result.vendor == "Mitsubishi"
    assert result.io_type == "Memory"


def test_manual_siemens_rejects_mitsubishi_device() -> None:
    result = classify_address("X10", "siemens")
    assert result.vendor == "Siemens"
    assert result.io_type == "Unknown"


def test_manual_iec_vendor_names_are_separate() -> None:
    assert classify_address("%IX0.0", "beckhoff").vendor == "Beckhoff"
    assert classify_address("%IX0.0", "codesys").vendor == "CODESYS"


def test_chinese_vendor_alias() -> None:
    assert normalize_vendor("三菱") == "mitsubishi"


def test_invalid_vendor() -> None:
    with pytest.raises(ValueError):
        normalize_vendor("omron")


def test_unknown_address() -> None:
    result = classify_address("ABC123")
    assert result.vendor == "Unknown"
    assert result.io_type == "Unknown"
