"""Unit tests for validation/quality gate tools (FAZ 5)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from kicad_mcp.server import create_server
from tests.conftest import call_tool_text


def _create_project(tmp_path: Path) -> Path:
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "demo.kicad_pro").write_text("{}", encoding="utf-8")
    (proj / "demo.kicad_pcb").write_text("", encoding="utf-8")
    (proj / "demo.kicad_sch").write_text("", encoding="utf-8")
    return proj


@pytest.mark.anyio
async def test_erc_list_rules_returns_expected(tmp_path: Path) -> None:
    proj = _create_project(tmp_path)
    server = create_server()
    await call_tool_text(server, "kicad_set_project", {"project_dir": str(proj)})
    result = await call_tool_text(server, "erc_list_rules", {})
    assert "power_pin_not_driven" in result
    assert "duplicate_reference" in result


@pytest.mark.anyio
async def test_erc_severity_defaults(tmp_path: Path) -> None:
    proj = _create_project(tmp_path)
    # Write a custom severity file before calling erc_list_rules
    sev_dir = proj / ".kicad-mcp"
    sev_dir.mkdir(parents=True, exist_ok=True)
    custom = {"power_pin_not_driven": "warning", "pin_not_connected": "ignore"}
    (sev_dir / "erc_severity.json").write_text(json.dumps(custom, indent=2), encoding="utf-8")
    server = create_server()
    await call_tool_text(server, "kicad_set_project", {"project_dir": str(proj)})
    result = await call_tool_text(server, "erc_list_rules", {})
    # The result should reflect our custom severity for at least one rule
    assert "warning" in result or "ignore" in result
