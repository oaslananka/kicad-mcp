"""Unit tests for jobset tools (FAZ 2.1)."""

from __future__ import annotations

import pytest

from kicad_mcp.server import create_server
from tests.conftest import call_tool_text


@pytest.mark.anyio
async def test_jobset_list_templates() -> None:
    server = create_server()
    result = await call_tool_text(server, "jobset_list_templates", {})
    assert result is not None


@pytest.mark.anyio
async def test_jobset_export_missing_file() -> None:
    server = create_server()
    result = await call_tool_text(
        server,
        "jobset_export",
        {"output_name": "nonexistent"},
    )
    assert "PCB" in result or "jobset" in result.lower()
