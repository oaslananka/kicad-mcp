from __future__ import annotations

from kicad_mcp.config import reset_config
from kicad_mcp.server import build_server
from kicad_mcp.tools.router import TOOL_CATEGORIES

AUTHORING_NAMES = {
    "sch_add_symbol",
    "sch_add_wire",
    "sch_add_label",
    "sch_add_no_connect",
    "sch_build_circuit",
    "sch_instantiate_template",
}


def test_authoring_names_are_declared_in_schematic_category() -> None:
    schematic_names = set(TOOL_CATEGORIES["schematic"]["tools"])
    assert AUTHORING_NAMES <= schematic_names


def test_authoring_names_are_discoverable_in_agent_full_write_mode(monkeypatch) -> None:
    monkeypatch.setenv("KICAD_MCP_OPERATING_MODE", "write")
    reset_config()
    server = build_server("agent_full")
    server.ensure_registered()
    discovered_names = {tool.name for tool in server.list_tools_sync()}
    assert AUTHORING_NAMES <= discovered_names
