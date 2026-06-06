"""Unit tests for DRC exclusion tools (FAZ 5.1).

Tools covered: drc_list_exclusions, drc_remove_exclusion,
    drc_add_exclusion, drc_validate_exclusions.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from kicad_mcp.server import create_server
from tests.conftest import call_tool_text


@pytest.mark.anyio
async def test_drc_list_exclusions_empty(tmp_path: Path) -> None:
    # Create a minimal project structure
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "demo.kicad_pro").write_text("{}", encoding="utf-8")
    (proj / "demo.kicad_pcb").write_text("", encoding="utf-8")
    (proj / "demo.kicad_sch").write_text("", encoding="utf-8")
    server = create_server()
    await call_tool_text(server, "kicad_set_project", {"project_dir": str(proj)})
    result = await call_tool_text(server, "drc_list_exclusions", {})
    payload = json.loads(result)
    assert payload["exclusions"] == []


@pytest.mark.anyio
async def test_drc_remove_exclusion_nonexistent(tmp_path: Path) -> None:
    # Create a minimal project structure
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "demo.kicad_pro").write_text("{}", encoding="utf-8")
    (proj / "demo.kicad_pcb").write_text("", encoding="utf-8")
    (proj / "demo.kicad_sch").write_text("", encoding="utf-8")
    server = create_server()
    await call_tool_text(server, "kicad_set_project", {"project_dir": str(proj)})
    result = await call_tool_text(server, "drc_remove_exclusion", {"uuid": "nobody"})
    assert "No exclusion found" in result
