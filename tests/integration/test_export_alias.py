"""Deprecated export alias behavior (work order P1-T1, ADR-0003)."""

from __future__ import annotations

import pytest

from kicad_mcp.server import build_server
from kicad_mcp.tools.aliases import ALIASES
from tests.conftest import call_tool_text


def test_export_3d_step_recorded_as_alias() -> None:
    server = build_server("minimal")
    server.ensure_registered()
    registered = {tool.name for tool in server._tool_manager.list_tools()}
    assert "export_3d_step" in registered
    assert "export_step" in registered
    assert ALIASES.get("export_3d_step") == "export_step"


@pytest.mark.anyio
async def test_export_3d_step_delegates_to_export_step(sample_project) -> None:
    server = build_server("minimal")
    await call_tool_text(server, "kicad_set_project", {"project_dir": str(sample_project)})
    alias_out = await call_tool_text(server, "export_3d_step", {})
    canonical_out = await call_tool_text(server, "export_step", {})
    assert alias_out == canonical_out
