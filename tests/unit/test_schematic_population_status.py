"""Tests for native Populate/DNP reporting (issue #186, slice 6).

`sch_set_dnp` already toggles KiCad's native ``(dnp ...)`` flag; these tests
cover the read side added on top of it — recording a DNP reason, reporting
population status via `sch_get_population_status`, and surfacing the
populated/dnp columns in variant BOM exports.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from kicad_mcp.server import build_server
from tests.conftest import call_tool_text


async def _place_test_resistor(server: object) -> None:
    result = await call_tool_text(
        server,
        "sch_add_symbol",
        {
            "library": "Device",
            "symbol_name": "R",
            "x_mm": 10.0,
            "y_mm": 10.0,
            "reference": "R1",
            "value": "10k",
            "footprint": "Resistor_SMD:R_0805",
            "rotation": 0,
        },
    )
    assert "placed" in result.lower() or "added symbol" in result.lower()


@pytest.mark.anyio
async def test_set_dnp_reason_is_reported_by_population_status(
    sample_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("KICAD_MCP_OPERATING_MODE", "write")
    server = build_server("schematic")
    await call_tool_text(server, "kicad_set_project", {"project_dir": str(sample_project)})
    await _place_test_resistor(server)

    result = await call_tool_text(
        server,
        "sch_set_dnp",
        {"reference": "R1", "enabled": True, "reason": "Prototype option"},
    )
    status = json.loads(
        await call_tool_text(server, "sch_get_population_status", {"reference": "R1"})
    )

    assert "DNP" in result
    assert status["count"] == 1
    component = status["components"][0]
    assert component["reference"] == "R1"
    assert component["populated"] is False
    assert component["dnp"] is True
    assert component["reason"] == "Prototype option"
    assert "(dnp yes)" in (sample_project / "demo.kicad_sch").read_text(encoding="utf-8")


@pytest.mark.anyio
async def test_population_status_defaults_to_populated(
    sample_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("KICAD_MCP_OPERATING_MODE", "write")
    server = build_server("schematic")
    await call_tool_text(server, "kicad_set_project", {"project_dir": str(sample_project)})
    await _place_test_resistor(server)

    status = json.loads(await call_tool_text(server, "sch_get_population_status", {}))

    assert status["count"] == 1
    component = status["components"][0]
    assert component["reference"] == "R1"
    assert component["populated"] is True
    assert component["dnp"] is False
    assert component["reason"] == ""


@pytest.mark.anyio
async def test_get_population_status_unknown_reference_raises(
    sample_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("KICAD_MCP_OPERATING_MODE", "write")
    server = build_server("schematic")
    await call_tool_text(server, "kicad_set_project", {"project_dir": str(sample_project)})
    await _place_test_resistor(server)

    result = await call_tool_text(server, "sch_get_population_status", {"reference": "R99"})
    assert "was not found" in result


@pytest.mark.anyio
async def test_variant_bom_exports_population_columns(
    sample_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("KICAD_MCP_OPERATING_MODE", "write")
    server = build_server("schematic")
    await call_tool_text(server, "kicad_set_project", {"project_dir": str(sample_project)})
    await _place_test_resistor(server)
    await call_tool_text(server, "sch_set_dnp", {"reference": "R1", "enabled": True})

    message = await call_tool_text(
        server, "variant_export_bom", {"variant": "default", "format": "csv"}
    )

    bom = Path(message.split("exported to", 1)[1].split("(", 1)[0].strip())
    text = bom.read_text(encoding="utf-8")
    assert "reference,value,footprint,populated,dnp" in text
    assert "R1," in text
    assert "False,True" in text
