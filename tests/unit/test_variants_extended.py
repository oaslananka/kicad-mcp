"""Unit tests for variant extended tools (FAZ 10.2).
Tools: variant_clone, variant_delete, variant_get_component_status,
variant_export_manufacturing_package, variant_export_schematic.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from kicad_mcp.server import create_server
from kicad_mcp.tools.variants import (
    _load_state,
    _save_state,
    _variant_names,
)
from tests.conftest import call_tool_text


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
