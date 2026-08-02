import pytest

from eplan_tag_exporter.classifier import classify_address


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
def test_classify_address(address: str, vendor: str, io_type: str) -> None:
    result = classify_address(address)
    assert result.vendor == vendor
    assert result.io_type == io_type


def test_unknown_address() -> None:
    result = classify_address("ABC123")
    assert result.vendor == "Unknown"
    assert result.io_type == "Unknown"
