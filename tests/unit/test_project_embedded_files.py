"""Unit tests for embedded file tools (FAZ 9)."""

from __future__ import annotations

import json

import pytest

from kicad_mcp.tools.embedded_files import _load_project_payload, _project_file


def test_load_project_payload_valid(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    proj_file = tmp_path / "test.kicad_pro"
    proj_file.write_text(json.dumps({"embedded_files": []}), encoding="utf-8")
    monkeypatch.setattr("kicad_mcp.tools.embedded_files._project_file", lambda: proj_file)
    payload = _load_project_payload()
    assert payload["embedded_files"] == []


def test_load_project_payload_rejects_bad_json(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    proj_file = tmp_path / "bad.kicad_pro"
    proj_file.write_text("{invalid", encoding="utf-8")
    monkeypatch.setattr("kicad_mcp.tools.embedded_files._project_file", lambda: proj_file)
    with pytest.raises(ValueError, match="valid JSON"):
        _load_project_payload()


def test_embed_rejects_large_file(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """A file > 1 MB should be rejected."""
    from kicad_mcp.tools.embedded_files import project_embed_file
    from kicad_mcp.config import get_config
    from kicad_mcp.path_safety import assert_within

    large = tmp_path / "large.bin"
    large.write_bytes(b"x" * 1_000_001)
    monkeypatch.setenv("KICAD_MCP_PROJECT_DIR", str(tmp_path))
    monkeypatch.setenv("KICAD_MCP_PROJECT_FILE", str(tmp_path / "test.kicad_pro"))
    (tmp_path / "test.kicad_pro").write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match="1 MB"):
        project_embed_file(source_path=str(large))
