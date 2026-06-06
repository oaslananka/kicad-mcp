"""Unit tests for ERC rule severity tools (FAZ 5.2)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from kicad_mcp.server import create_server
from tests.conftest import call_tool_text


@pytest.mark.anyio
async def test_erc_list_rules_returns_all(tmp_path: Path) -> None:
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "demo.kicad_pro").write_text("{}", encoding="utf-8")
    (proj / "demo.kicad_pcb").write_text("", encoding="utf-8")
    (proj / "demo.kicad_sch").write_text("", encoding="utf-8")
    server = create_server()
    await call_tool_text(server, "kicad_set_project", {"project_dir": str(proj)})
    result = await call_tool_text(server, "erc_list_rules", {})
    payload = json.loads(result)
    assert payload["rules"]
    assert len(payload["rules"]) >= 10


@pytest.mark.anyio
async def test_erc_set_severity(tmp_path: Path) -> None:
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "demo.kicad_pro").write_text("{}", encoding="utf-8")
    (proj / "demo.kicad_pcb").write_text("", encoding="utf-8")
    (proj / "demo.kicad_sch").write_text("", encoding="utf-8")
    server = create_server()
    await call_tool_text(server, "kicad_set_project", {"project_dir": str(proj)})
    result = await call_tool_text(
        server, "erc_set_rule_severity", {"rule_name": "pin_not_connected", "severity": "warning"}
    )
    assert "warning" in result


@pytest.mark.anyio
async def test_erc_set_severity_invalid_rule(tmp_path: Path) -> None:
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "demo.kicad_pro").write_text("{}", encoding="utf-8")
    (proj / "demo.kicad_pcb").write_text("", encoding="utf-8")
    (proj / "demo.kicad_sch").write_text("", encoding="utf-8")
    server = create_server()
    await call_tool_text(server, "kicad_set_project", {"project_dir": str(proj)})
    result = await call_tool_text(
        server, "erc_set_rule_severity", {"rule_name": "bogus_rule", "severity": "error"}
    )
    assert "Unknown ERC rule" in result


@pytest.mark.anyio
async def test_erc_set_severity_invalid_level(tmp_path: Path) -> None:
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "demo.kicad_pro").write_text("{}", encoding="utf-8")
    (proj / "demo.kicad_pcb").write_text("", encoding="utf-8")
    (proj / "demo.kicad_sch").write_text("", encoding="utf-8")
    server = create_server()
    await call_tool_text(server, "kicad_set_project", {"project_dir": str(proj)})
    result = await call_tool_text(
        server, "erc_set_rule_severity", {"rule_name": "bus_conflict", "severity": "fatal"}
    )
    assert "Severity must be one of" in result


@pytest.mark.anyio
async def test_erc_reset_rules_all(tmp_path: Path) -> None:
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "demo.kicad_pro").write_text("{}", encoding="utf-8")
    (proj / "demo.kicad_pcb").write_text("", encoding="utf-8")
    (proj / "demo.kicad_sch").write_text("", encoding="utf-8")
    server = create_server()
    await call_tool_text(server, "kicad_set_project", {"project_dir": str(proj)})
    # Set a rule to ignore first
    await call_tool_text(
        server, "erc_set_rule_severity", {"rule_name": "pin_not_connected", "severity": "ignore"}
    )
    # Reset all
    await call_tool_text(server, "erc_reset_rules", {})
    # Verify via list
    result = await call_tool_text(server, "erc_list_rules", {})
    payload = json.loads(result)
    assert all(rule["severity"] == "error" for rule in payload["rules"])


@pytest.mark.anyio
async def test_erc_reset_rules_single(tmp_path: Path) -> None:
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "demo.kicad_pro").write_text("{}", encoding="utf-8")
    (proj / "demo.kicad_pcb").write_text("", encoding="utf-8")
    (proj / "demo.kicad_sch").write_text("", encoding="utf-8")
    server = create_server()
    await call_tool_text(server, "kicad_set_project", {"project_dir": str(proj)})
    await call_tool_text(server, "erc_reset_rules", {"rule_name": "label_conflict"})
    result = await call_tool_text(server, "erc_list_rules", {})
    payload = json.loads(result)
    for rule in payload["rules"]:
        if rule["name"] == "label_conflict":
            assert rule["severity"] == "error"
