"""Unit tests for subcircuit template instantiation (FAZ 13)."""

from __future__ import annotations

import pytest

from kicad_mcp.server import create_server
from tests.conftest import call_tool_text


@pytest.mark.anyio
async def test_list_templates_returns_list() -> None:
    server = create_server()
    result = await call_tool_text(server, "sch_list_templates", {})
    assert "nrf52840" in result or "ws2812b" in result or "templates" in result.lower()


@pytest.mark.anyio
async def test_get_template_info_exists() -> None:
    server = create_server()
    result = await call_tool_text(
        server, "sch_get_template_info", {"template_name": "nrf52840_minimal"}
    )
    assert result is not None
    assert "nrf" in result.lower() or "not found" not in result.lower()


@pytest.mark.anyio
async def test_get_template_info_missing() -> None:
    server = create_server()
    result = await call_tool_text(
        server, "sch_get_template_info", {"template_name": "nonexistent_template_xyz"}
    )
    assert "not found" in result.lower() or "error" in result.lower()
