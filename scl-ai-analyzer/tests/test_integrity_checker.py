from __future__ import annotations

import hashlib
from pathlib import Path

from scl_ai_analyzer.integrity_checker import IntegrityChecker
from scl_ai_analyzer.project import ProjectAnalyzer


def test_sha256_matches_hashlib(tmp_path: Path) -> None:
    path = tmp_path / "demo.scl"
    content = b"FUNCTION FC_Test : Bool\nBEGIN\nEND_FUNCTION\n"
    path.write_bytes(content)

    actual = IntegrityChecker(chunk_size=7).sha256_file(path)

    assert actual == hashlib.sha256(content).hexdigest()


def test_generates_manifest_and_sidecars_for_scl_and_xml(tmp_path: Path) -> None:
    scl = tmp_path / "A.scl"
    xml = tmp_path / "B.xml"
    scl.write_text("FUNCTION FC_A : Bool\nBEGIN\nEND_FUNCTION\n", encoding="utf-8")
    xml.write_text("<Document><Name>B</Name></Document>", encoding="utf-8")

    manifest = IntegrityChecker().generate_directory(tmp_path, recursive=False)

    assert manifest.manifest_path == tmp_path / "SHA256SUMS.txt"
    assert len(manifest.records) == 2
    assert (tmp_path / "A.scl.sha256").is_file()
    assert (tmp_path / "B.xml.sha256").is_file()
    text = manifest.manifest_path.read_text(encoding="utf-8")
    assert "A.scl" in text
    assert "B.xml" in text


def test_verify_manifest_detects_tampering(tmp_path: Path) -> None:
    path = tmp_path / "logic.scl"
    path.write_text("ORIGINAL", encoding="utf-8")
    checker = IntegrityChecker()
    manifest = checker.generate([path])

    before = checker.verify_manifest(manifest.manifest_path)
    assert len(before) == 1
    assert before[0].ok

    path.write_text("CHANGED", encoding="utf-8")
    after = checker.verify_manifest(manifest.manifest_path)
    assert after[0].status == "mismatch"
    assert not after[0].ok


def test_project_export_automatically_creates_sha256(tmp_path: Path) -> None:
    source = tmp_path / "source.scl"
    source.write_text(
        "FUNCTION FC_Demo : Bool\nBEGIN\nEND_FUNCTION\n",
        encoding="utf-8",
    )
    project = ProjectAnalyzer().scan(source)
    export_dir = tmp_path / "export"

    exported = ProjectAnalyzer.export_blocks(project, export_dir)

    assert len(exported) == 1
    assert exported[0].is_file()
    assert Path(str(exported[0]) + ".sha256").is_file()
    assert (export_dir / "SHA256SUMS.txt").is_file()
    results = IntegrityChecker().verify_manifest(export_dir / "SHA256SUMS.txt")
    assert results and all(item.ok for item in results)
