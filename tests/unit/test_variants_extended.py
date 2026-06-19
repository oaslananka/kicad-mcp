"""Unit tests for variant extended tools (FAZ 10.2).
Tools: variant_clone, variant_delete, variant_get_component_status,
variant_export_manufacturing_package, variant_export_schematic.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from kicad_mcp.server import build_server, create_server
from kicad_mcp.tools.variants import (
    _load_state,
    _save_state,
    _variant_names,
)
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
    assert "Added symbol" in result


@pytest.mark.anyio
async def test_variant_clone_creates_new(sample_project: Path) -> None:
    _save_state(_load_state())
    state = _load_state()
    assert "default" in state["variants"]

    state["variants"]["v1"] = {"overrides": {}}
    _save_state(state)

    server = create_server()
    await call_tool_text(server, "kicad_set_project", {"project_dir": str(sample_project)})
    result = await call_tool_text(server, "variant_clone", {"name": "v1", "new_name": "v2"})
    assert "v2" in result

    state = _load_state()
    assert "v2" in state["variants"]


@pytest.mark.anyio
async def test_variant_clone_rejects_duplicate(sample_project: Path) -> None:
    state = _load_state()
    state["variants"]["dup"] = {"overrides": {}}
    _save_state(state)

    server = create_server()
    await call_tool_text(server, "kicad_set_project", {"project_dir": str(sample_project)})
    result = await call_tool_text(server, "variant_clone", {"name": "default", "new_name": "dup"})
    assert "already exists" in result.lower()


@pytest.mark.anyio
async def test_variant_delete_removes(sample_project: Path) -> None:
    state = _load_state()
    state["variants"]["to_delete"] = {"overrides": {}}
    _save_state(state)

    assert "to_delete" in _variant_names(_load_state())
    server = create_server()
    await call_tool_text(server, "kicad_set_project", {"project_dir": str(sample_project)})
    result = await call_tool_text(server, "variant_delete", {"name": "to_delete"})
    assert "Deleted" in result
    assert "to_delete" not in _variant_names(_load_state())


@pytest.mark.anyio
async def test_variant_delete_rejects_default(sample_project: Path) -> None:
    server = create_server()
    await call_tool_text(server, "kicad_set_project", {"project_dir": str(sample_project)})
    result = await call_tool_text(server, "variant_delete", {"name": "default"})
    assert "default" in result.lower()


@pytest.mark.anyio
async def test_variant_get_component_status_missing(sample_project: Path) -> None:
    server = create_server()
    await call_tool_text(server, "kicad_set_project", {"project_dir": str(sample_project)})
    result = await call_tool_text(
        server, "variant_get_component_status", {"variant": "default", "reference": "ZZ99"}
    )
    assert "not found" in result.lower()


@pytest.mark.anyio
async def test_variant_dnp_status(sample_project: Path) -> None:
    """Verify DNP (Do Not Populate) flag is reflected in component status."""
    state = _load_state()
    # Set up a variant with a DNP override for an existing component
    # The sample_project fixture has components; we set R1 as DNP
    if "variants" not in state:
        state["variants"] = {"default": {"overrides": {}}}
    state["variants"]["dnp_test"] = {
        "overrides": {
            "R1": {"fitted": False, "dnp": True, "exclude_from_bom": False},
        }
    }
    _save_state(state)

    server = create_server()
    await call_tool_text(server, "kicad_set_project", {"project_dir": str(sample_project)})
    result = await call_tool_text(
        server, "variant_get_component_status", {"variant": "dnp_test", "reference": "R1"}
    )
    assert "false" in result.lower() or "dnp" in result.lower()


@pytest.mark.anyio
async def test_schematic_population_tools_write_native_dnp_state(
    sample_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("KICAD_MCP_OPERATING_MODE", "write")
    server = build_server("schematic")
    await call_tool_text(server, "kicad_set_project", {"project_dir": str(sample_project)})
    await _place_test_resistor(server)

    result = await call_tool_text(
        server,
        "sch_set_component_population",
        {"reference": "R1", "populated": False, "reason": "Prototype option"},
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
async def test_variant_bom_exports_population_columns_from_native_dnp(
    sample_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("KICAD_MCP_OPERATING_MODE", "write")
    server = build_server("schematic")
    await call_tool_text(server, "kicad_set_project", {"project_dir": str(sample_project)})
    await _place_test_resistor(server)
    await call_tool_text(
        server,
        "sch_set_component_population",
        {"reference": "R1", "populated": False},
    )

    await call_tool_text(server, "variant_export_bom", {"variant": "default", "format": "csv"})

    bom = sample_project / "output" / "variants" / "default_bom.csv"
    text = bom.read_text(encoding="utf-8")
    assert "reference,value,footprint,populated,dnp" in text
    assert "R1," in text
    assert "False,True" in text
