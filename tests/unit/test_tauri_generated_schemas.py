from __future__ import annotations

from pathlib import Path

SCHEMA_DIR = Path(__file__).resolve().parents[2] / "src-tauri" / "gen" / "schemas"
EXPECTED_SCHEMA_FILES = {
    "acl-manifests.json",
    "capabilities.json",
    "desktop-schema.json",
    "linux-schema.json",
    "windows-schema.json",
}


def test_generated_tauri_schema_set_is_complete() -> None:
    schema_files = {path.name for path in SCHEMA_DIR.glob("*.json")}
    assert schema_files == EXPECTED_SCHEMA_FILES
