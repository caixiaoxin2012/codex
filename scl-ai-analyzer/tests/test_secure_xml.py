from pathlib import Path

import pytest

from scl_ai_analyzer.secure_xml import (
    PLCXMLLoadError,
    SecurePLCXMLLoader,
    XMLNodePolicyError,
    XMLParseTimeoutError,
    XMLSecurityPolicy,
    XMLSizeLimitError,
)


def test_valid_xml_parses_and_reports_unknown_nodes(tmp_path: Path) -> None:
    path = tmp_path / "project.xml"
    path.write_text("<Document><CustomNode><Name>Demo</Name></CustomNode></Document>", encoding="utf-8")

    result = SecurePLCXMLLoader().load(path)

    assert result.root.tag == "Document"
    assert result.node_count == 3
    assert result.max_depth == 3
    assert any("CustomNode" in warning for warning in result.warnings)


def test_rejects_file_over_configured_size_limit(tmp_path: Path) -> None:
    path = tmp_path / "large.xml"
    path.write_text("<Document>1234567890</Document>", encoding="utf-8")
    policy = XMLSecurityPolicy(max_size_bytes=8)

    with pytest.raises(XMLSizeLimitError):
        SecurePLCXMLLoader(policy).load(path)


def test_rejects_dtd_or_entity_declarations(tmp_path: Path) -> None:
    path = tmp_path / "entity.xml"
    path.write_text(
        '<!DOCTYPE x [<!ENTITY a "boom">]><Document>&a;</Document>',
        encoding="utf-8",
    )

    with pytest.raises(XMLNodePolicyError):
        SecurePLCXMLLoader().load(path)


def test_strict_node_allow_list_rejects_unknown_tag(tmp_path: Path) -> None:
    path = tmp_path / "strict.xml"
    path.write_text("<Document><Unexpected /></Document>", encoding="utf-8")
    policy = XMLSecurityPolicy(
        allowed_local_names=frozenset({"Document"}),
        strict_allowed_nodes=True,
    )

    with pytest.raises(XMLNodePolicyError):
        SecurePLCXMLLoader(policy).load(path)


def test_zero_timeout_rejects_before_full_parse(tmp_path: Path) -> None:
    path = tmp_path / "timeout.xml"
    path.write_text("<Document><Name>Demo</Name></Document>", encoding="utf-8")
    policy = XMLSecurityPolicy(timeout_seconds=0)

    with pytest.raises(XMLParseTimeoutError):
        SecurePLCXMLLoader(policy).load(path)


def test_rejects_non_xml_extension(tmp_path: Path) -> None:
    path = tmp_path / "project.txt"
    path.write_text("<Document />", encoding="utf-8")

    with pytest.raises(PLCXMLLoadError):
        SecurePLCXMLLoader().load(path)
