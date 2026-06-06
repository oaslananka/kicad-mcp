"""Unit tests for embedded file tools (FAZ 9).
Tools: project_list_embedded_files, project_extract_embedded_file,
project_remove_embedded_file.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from kicad_mcp.server import create_server
from kicad_mcp.tools.embedded_files import _load_project_payload
from tests.conftest import call_tool_text


@pytest.mark.anyio
async def test_load_project_payload_valid(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    proj_file = tmp_path / "test.kicad_pro"
    proj_file.write_text(json.dumps({"embedded_files": []}), encoding="utf-8")
    monkeypatch.setattr("kicad_mcp.tools.embedded_files._project_file", lambda: proj_file)
    payload = _load_project_payload()
    assert payload["embedded_files"] == []


@pytest.mark.anyio
async def test_load_project_payload_rejects_bad_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    proj_file = tmp_path / "bad.kicad_pro"
    proj_file.write_text("{invalid", encoding="utf-8")
    monkeypatch.setattr("kicad_mcp.tools.embedded_files._project_file", lambda: proj_file)
    with pytest.raises(ValueError, match="valid JSON"):
        _load_project_payload()


@pytest.mark.anyio
async def test_embed_rejects_large_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A file > 1 MB should be rejected."""
    large = tmp_path / "large.bin"
    large.write_bytes(b"x" * 1_000_001)
    (tmp_path / "test.kicad_pro").write_text("{}", encoding="utf-8")
    (tmp_path / "test.kicad_pcb").write_text("", encoding="utf-8")
    (tmp_path / "test.kicad_sch").write_text("", encoding="utf-8")

    server = create_server()
    await call_tool_text(server, "kicad_set_project", {"project_dir": str(tmp_path)})
    result = await call_tool_text(server, "project_embed_file", {"source_path": str(large)})
    assert "too large" in result.lower() or "1 mb" in result.lower()
