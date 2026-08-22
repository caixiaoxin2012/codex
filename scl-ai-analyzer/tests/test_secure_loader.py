from __future__ import annotations

import io
import logging
from pathlib import Path

import pytest

from scl_ai_analyzer.integrity_checker import IntegrityChecker
from scl_ai_analyzer.secure_loader import (
    SecureLoader,
    SecureLoaderHashMismatchError,
    SecureLoaderHashReferenceMissingError,
    SecureLoaderPolicy,
    SecureLoaderSizeError,
)


def _memory_logger() -> tuple[logging.Logger, io.StringIO]:
    stream = io.StringIO()
    logger = logging.Logger("secure-loader-test")
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler(stream)
    logger.addHandler(handler)
    return logger, stream


def test_scl_sidecar_is_verified_before_parse_and_audited(tmp_path: Path) -> None:
    path = tmp_path / "demo.scl"
    path.write_text(
        "FUNCTION FC_Demo : Bool\nBEGIN\n    FC_Demo := TRUE;\nEND_FUNCTION\n",
        encoding="utf-8",
    )
    IntegrityChecker().generate([path])
    logger, stream = _memory_logger()

    result = SecureLoader(logger=logger).load(path, source="uploaded_project")

    assert result.hash_status == "verified_sidecar"
    assert result.integrity_verified
    assert result.scl_analysis is not None
    assert result.scl_analysis.block.name == "FC_Demo"
    assert result.sha256 in stream.getvalue()
    assert "source=uploaded_project" in stream.getvalue()
    assert "parse_seconds=" in stream.getvalue()


def test_manifest_is_used_when_sidecar_is_absent(tmp_path: Path) -> None:
    path = tmp_path / "logic.scl"
    path.write_text(
        "FUNCTION FC_Logic : Bool\nBEGIN\nEND_FUNCTION\n",
        encoding="utf-8",
    )
    IntegrityChecker().generate([path], write_sidecars=False)

    result = SecureLoader().load(path, source="manifest_only")

    assert result.hash_status == "verified_manifest"
    assert result.hash_reference == tmp_path / "SHA256SUMS.txt"


def test_hash_mismatch_rejects_malformed_xml_before_xml_parse(tmp_path: Path) -> None:
    path = tmp_path / "project.xml"
    path.write_text("<Document />", encoding="utf-8")
    IntegrityChecker().generate([path])
    # If parsing happened first this would be an XML parse error. The expected
    # behavior is a SHA-256 mismatch before the parser sees the malformed content.
    path.write_text("<Document>", encoding="utf-8")

    with pytest.raises(SecureLoaderHashMismatchError):
        SecureLoader().load(path, source="tampered_export")


def test_no_hash_reference_is_computed_only_in_compatibility_mode(tmp_path: Path) -> None:
    path = tmp_path / "raw.scl"
    path.write_text(
        "FUNCTION FC_Raw : Bool\nBEGIN\nEND_FUNCTION\n",
        encoding="utf-8",
    )

    result = SecureLoader().load(path, source="raw_user_file")

    assert result.hash_status == "computed_only"
    assert len(result.sha256) == 64
    assert any("未找到" in warning for warning in result.warnings)


def test_strict_mode_requires_hash_reference(tmp_path: Path) -> None:
    path = tmp_path / "strict.scl"
    path.write_text(
        "FUNCTION FC_Strict : Bool\nBEGIN\nEND_FUNCTION\n",
        encoding="utf-8",
    )
    loader = SecureLoader(policy=SecureLoaderPolicy(require_hash_reference=True))

    with pytest.raises(SecureLoaderHashReferenceMissingError):
        loader.load(path, source="strict_import")


def test_xml_is_hash_verified_then_securely_parsed(tmp_path: Path) -> None:
    path = tmp_path / "tia.xml"
    path.write_text("<Document><Name>Demo</Name></Document>", encoding="utf-8")
    IntegrityChecker().generate([path])

    result = SecureLoader().load(path, source="tia_export")

    assert result.hash_status == "verified_sidecar"
    assert result.xml_result is not None
    assert result.xml_result.root.tag == "Document"
    assert result.parse_seconds >= 0
    assert result.total_seconds >= result.parse_seconds


def test_size_limit_is_checked_before_hashing(tmp_path: Path) -> None:
    path = tmp_path / "large.scl"
    path.write_text("1234567890", encoding="utf-8")
    loader = SecureLoader(
        policy=SecureLoaderPolicy(max_size_bytes=8, warn_size_bytes=4)
    )

    with pytest.raises(SecureLoaderSizeError):
        loader.load(path, source="oversize")
