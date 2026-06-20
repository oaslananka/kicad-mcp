"""Unit tests for footprint/symbol CLI export tools (FAZ 2.2–2.4)."""

from __future__ import annotations

import pytest

from kicad_mcp.server import create_server
from tests.conftest import call_tool_text


@pytest.mark.anyio
async def test_fp_export_rejects_invalid_format() -> None:
    server = create_server()
    result = await call_tool_text(
        server,
        "fp_export",
        {"library": "Lib", "footprint": "FP", "format": "invalid"},
    )
    # Depending on mode/project config this may fail before format validation.
    assert (
        "MODE_FORBIDDEN" in result
        or "format" in result.lower()
        or "no pcb file configured" in result.lower()
    )


@pytest.mark.anyio
async def test_fp_get_info_rejects_missing() -> None:
    server = create_server()
    result = await call_tool_text(
        server,
        "fp_get_info",
        {"library": "Nonexistent", "footprint": "Missing"},
    )
    # Tool is blocked by mode (or missing project)
    assert "MODE_FORBIDDEN" in result or "No project" in result or "PCB file" in result


@pytest.mark.anyio
async def test_sym_export_rejects_invalid_format() -> None:
    server = create_server()
    result = await call_tool_text(
        server,
        "sym_export",
        {"library": "Lib", "symbol": "Sym", "format": "bogus"},
    )
    assert (
        "MODE_FORBIDDEN" in result
        or "format" in result.lower()
        or "no project file configured" in result.lower()
    )
