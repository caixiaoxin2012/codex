from pathlib import Path

from eplan_tag_exporter.gui import APP_VERSION, resource_path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_xilin_icons_are_present_and_valid() -> None:
    ico = PROJECT_ROOT / "assets" / "xilin-app-icon.ico"
    png = PROJECT_ROOT / "assets" / "xilin-app-icon.png"
    assert ico.read_bytes()[:4] == b"\x00\x00\x01\x00"
    assert int.from_bytes(ico.read_bytes()[4:6], "little") == 7
    assert png.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    assert resource_path("assets", "xilin-app-icon.ico") == ico


def test_versioned_builds_embed_xilin_icon() -> None:
    batch = (PROJECT_ROOT / "build_windows.bat").read_text(encoding="utf-8")
    workflow = (
        PROJECT_ROOT.parent / ".github" / "workflows" / "build-eplan-tag-exporter-windows.yml"
    ).read_text(encoding="utf-8")
    assert APP_VERSION == (PROJECT_ROOT / "VERSION").read_text(encoding="utf-8").strip()
    assert f"EPLAN-Tag-Exporter-v{APP_VERSION}" in batch
    assert f"EPLAN-Tag-Exporter-v{APP_VERSION}" in workflow
    assert "--icon assets\\xilin-app-icon.ico" in batch
    assert "--icon assets/xilin-app-icon.ico" in workflow
