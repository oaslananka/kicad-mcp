from __future__ import annotations

from pathlib import Path

SCHEMA_DIR = Path(__file__).resolve().parents[2] / "src-tauri" / "gen" / "schemas"

# Files Tauri's ACL generator always emits regardless of host OS.
REQUIRED_SCHEMA_FILES = {
    "acl-manifests.json",
    "capabilities.json",
}

# The per-host schema file Tauri emits is platform-specific (one of these), plus a
# "desktop-schema.json" meta. Asserting an exact, OS-locked set made this test pass
# only on Linux; it now validates the stable invariant across linux/macos/windows.
OPTIONAL_SCHEMA_FILES = {
    "desktop-schema.json",
    "linux-schema.json",
    "macos-schema.json",
    "windows-schema.json",
}

ALLOWED_SCHEMA_FILES = REQUIRED_SCHEMA_FILES | OPTIONAL_SCHEMA_FILES


def test_generated_tauri_schema_set_is_complete() -> None:
    schema_files = {path.name for path in SCHEMA_DIR.glob("*.json")}

    missing = REQUIRED_SCHEMA_FILES - schema_files
    assert not missing, f"missing required Tauri ACL schema files: {sorted(missing)}"

    unexpected = schema_files - ALLOWED_SCHEMA_FILES
    assert not unexpected, f"unexpected Tauri schema files: {sorted(unexpected)}"

    # At least one host/desktop schema must be present (the build did generate schemas).
    assert schema_files & OPTIONAL_SCHEMA_FILES, (
        "no host or desktop Tauri schema file was generated"
    )
