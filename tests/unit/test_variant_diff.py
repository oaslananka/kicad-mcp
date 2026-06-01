from __future__ import annotations

import json
from pathlib import Path

import pytest

from kicad_mcp.server import create_server
from kicad_mcp.tools.schematic import place_symbol_block
from tests.conftest import call_tool_text

pytestmark = pytest.mark.mcp_mode("write")


def _write_variant_schematic(sample_project) -> None:
    schematic = sample_project / "demo.kicad_sch"
    schematic.write_text(
        (
            "(kicad_sch\n"
            "\t(version 20250316)\n"
            '\t(generator "pytest")\n'
            '\t(uuid "00000000-0000-0000-0000-000000000000")\n'
            '\t(paper "A4")\n'
            "\t(lib_symbols)\n"
            f"{place_symbol_block('Device:R', 20.0, 20.0, 'R1', '10k', 'Resistor_SMD:R_0805')}\n"
            f"{place_symbol_block('Device:R', 35.0, 20.0, 'R2', '1k', 'Resistor_SMD:R_1206')}\n"
            "\t(sheet_instances\n"
            '\t\t(path "/" (page "1"))\n'
            "\t)\n"
            "\t(embedded_fonts no)\n"
            ")\n"
        ),
        encoding="utf-8",
    )


@pytest.mark.anyio
async def test_variant_tools_create_diff_and_export(sample_project) -> None:
    _write_variant_schematic(sample_project)
    server = create_server()

    await call_tool_text(server, "kicad_set_project", {"project_dir": str(sample_project)})
    await call_tool_text(server, "variant_create", {"name": "lite"})
    await call_tool_text(
        server,
        "variant_set_component_override",
        {"variant": "lite", "reference": "R2", "enabled": False},
    )
    await call_tool_text(server, "variant_set_active", {"name": "lite"})

    listing = json.loads(await call_tool_text(server, "variant_list", {}))
    assert listing["active_variant"] == "lite"
    assert {item["name"] for item in listing["variants"]} == {"default", "lite"}

    diff = json.loads(
        await call_tool_text(
            server,
            "variant_diff_bom",
            {"variant_a": "default", "variant_b": "lite"},
        )
    )
    assert diff["removed"][0]["reference"] == "R2"

    exported = await call_tool_text(server, "variant_export_bom", {"variant": "lite"})
    assert "lite_bom.csv" in exported

    project_payload = json.loads((sample_project / "demo.kicad_pro").read_text(encoding="utf-8"))
    assert project_payload["variants"]["active_variant"] == "lite"
    assert "lite" in project_payload["variants"]["variants"]
    assert not Path(sample_project / ".kicad-mcp" / "variants.json").exists()


@pytest.mark.anyio
async def test_variant_tools_cover_error_paths_and_json_export(sample_project) -> None:
    _write_variant_schematic(sample_project)
    server = create_server()

    await call_tool_text(server, "kicad_set_project", {"project_dir": str(sample_project)})
    await call_tool_text(server, "variant_create", {"name": "lite"})

    empty_error = await call_tool_text(server, "variant_create", {"name": "   "})
    duplicate_error = await call_tool_text(server, "variant_create", {"name": "lite"})
    missing_ref_error = await call_tool_text(
        server,
        "variant_set_component_override",
        {"variant": "lite", "reference": "U99", "enabled": False},
    )

    assert "must not be empty" in empty_error
    assert "already exists" in duplicate_error
    assert "was not found in the active schematic" in missing_ref_error

    await call_tool_text(
        server,
        "variant_set_component_override",
        {
            "variant": "lite",
            "reference": "R1",
            "enabled": True,
            "value": "22k",
            "footprint": "Resistor_SMD:R_0603",
        },
    )
    diff = json.loads(
        await call_tool_text(
            server,
            "variant_diff_bom",
            {"variant_a": "default", "variant_b": "lite"},
        )
    )
    exported = await call_tool_text(
        server,
        "variant_export_bom",
        {"variant": "lite", "format": "json"},
    )

    assert diff["changed"][0]["reference"] == "R1"
    assert "lite_bom.json" in exported
    exported_payload = json.loads(
        (sample_project / "output" / "variants" / "lite_bom.json").read_text(encoding="utf-8")
    )
    assert exported_payload[0]["footprint"] == "Resistor_SMD:R_0603"

    format_error = await call_tool_text(
        server,
        "variant_export_bom",
        {"variant": "lite", "format": "xlsx"},
    )
    assert "Only csv and json" in format_error
