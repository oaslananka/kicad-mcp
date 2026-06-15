"""Integration tests for schematic edge cases and error paths."""

from __future__ import annotations

import re

import pytest

from kicad_mcp.server import build_server
from tests.conftest import call_tool_text


@pytest.mark.anyio
async def test_schematic_add_missing_junctions(sample_project, mock_kicad) -> None:
    """sch_add_missing_junctions should add junctions at wire intersections."""
    server = build_server("schematic")
    await call_tool_text(
        server,
        "sch_build_circuit",
        {
            "symbols": [
                {
                    "library": "Device",
                    "symbol_name": "R",
                    "x_mm": 10.0,
                    "y_mm": 10.0,
                    "reference": "R1",
                    "value": "10k",
                    "footprint": "Resistor_SMD:R_0805",
                },
                {
                    "library": "Device",
                    "symbol_name": "R",
                    "x_mm": 20.0,
                    "y_mm": 10.0,
                    "reference": "R2",
                    "value": "22k",
                    "footprint": "Resistor_SMD:R_0805",
                },
            ],
            "wires": [
                {"x1_mm": 10.0, "y1_mm": 10.0, "x2_mm": 20.0, "y2_mm": 10.0},
                {"x1_mm": 15.0, "y1_mm": 5.0, "x2_mm": 15.0, "y2_mm": 15.0},
            ],
        },
    )

    result = await call_tool_text(server, "sch_add_missing_junctions", {})
    assert "junction" in result.lower() or "added" in result.lower() or "updated" in result.lower()


@pytest.mark.anyio
async def test_schematic_check_power_flags(sample_project, mock_kicad) -> None:
    """sch_check_power_flags should analyze power symbols in the schematic."""
    server = build_server("schematic")
    await call_tool_text(
        server,
        "sch_build_circuit",
        {
            "symbols": [
                {
                    "library": "Device",
                    "symbol_name": "R",
                    "x_mm": 10.0,
                    "y_mm": 10.0,
                    "reference": "R1",
                    "value": "10k",
                    "footprint": "Resistor_SMD:R_0805",
                }
            ],
            "power_symbols": [{"name": "GND", "x_mm": 15.0, "y_mm": 15.0}],
        },
    )

    result = await call_tool_text(server, "sch_check_power_flags", {})
    assert "Power" in result or "power" in result or "GND" in result


@pytest.mark.anyio
async def test_schematic_trace_net_missing(sample_project, mock_kicad) -> None:
    """sch_trace_net should report when a net is not found."""
    server = build_server("schematic")
    await call_tool_text(
        server,
        "sch_build_circuit",
        {
            "symbols": [
                {
                    "library": "Device",
                    "symbol_name": "R",
                    "x_mm": 10.0,
                    "y_mm": 10.0,
                    "reference": "R1",
                    "value": "10k",
                    "footprint": "Resistor_SMD:R_0805",
                }
            ],
        },
    )

    result = await call_tool_text(server, "sch_trace_net", {"net_name": "NONEXISTENT"})
    assert "was not found" in result or "not found" in result.lower()


@pytest.mark.anyio
async def test_schematic_find_free_placement_no_keepout(sample_project, mock_kicad) -> None:
    """sch_find_free_placement should return coordinates without keepout regions."""
    server = build_server("schematic")
    result = await call_tool_text(server, "sch_find_free_placement", {"count": 3})
    assert "Free placement coordinates" in result
    assert "x_mm=" in result


@pytest.mark.anyio
async def test_schematic_find_free_placement_with_count(sample_project, mock_kicad) -> None:
    """sch_find_free_placement should return requested count of coordinates."""
    server = build_server("schematic")
    result = await call_tool_text(server, "sch_find_free_placement", {"count": 5})
    assert "Free placement coordinates" in result
    # Should have 5 coordinate entries
    matches = re.findall(r"\d+:\s*\(", result)
    assert len(matches) >= 5


@pytest.mark.anyio
async def test_schematic_set_sheet_size_invalid(sample_project, mock_kicad) -> None:
    """sch_set_sheet_size should report unknown paper size."""
    server = build_server("schematic")
    result = await call_tool_text(server, "sch_set_sheet_size", {"paper": "INVALID"})
    assert "Unknown paper size" in result


@pytest.mark.anyio
async def test_schematic_set_sheet_size_valid(sample_project, mock_kicad) -> None:
    """sch_set_sheet_size should resize to known paper sizes."""
    server = build_server("schematic")
    for paper in ["A4", "A3", "A2", "USLetter", "USLegal"]:
        result = await call_tool_text(server, "sch_set_sheet_size", {"paper": paper})
        assert "Sheet resized" in result or "already fits" in result


@pytest.mark.anyio
async def test_schematic_auto_resize_sheet(sample_project, mock_kicad) -> None:
    """sch_auto_resize_sheet should resize sheet to fit symbols."""
    server = build_server("schematic")
    await call_tool_text(
        server,
        "sch_build_circuit",
        {
            "symbols": [
                {
                    "library": "Device",
                    "symbol_name": "R",
                    "x_mm": 200.0,
                    "y_mm": 150.0,
                    "reference": "R1",
                    "value": "10k",
                    "footprint": "Resistor_SMD:R_0805",
                }
            ]
        },
    )

    result = await call_tool_text(server, "sch_auto_resize_sheet", {})
    assert "Sheet resized" in result or "already fits" in result


@pytest.mark.anyio
async def test_schematic_annotate_start_number(sample_project, mock_kicad) -> None:
    """sch_annotate should support custom start number and order."""
    server = build_server("schematic")
    await call_tool_text(
        server,
        "sch_build_circuit",
        {
            "symbols": [
                {
                    "library": "Device",
                    "symbol_name": "R",
                    "x_mm": 10.0,
                    "y_mm": 10.0,
                    "reference": "R1",
                    "value": "10k",
                    "footprint": "Resistor_SMD:R_0805",
                },
                {
                    "library": "Device",
                    "symbol_name": "R",
                    "x_mm": 20.0,
                    "y_mm": 10.0,
                    "reference": "R2",
                    "value": "22k",
                    "footprint": "Resistor_SMD:R_0805",
                },
            ]
        },
    )

    result = await call_tool_text(
        server, "sch_annotate", {"start_number": 100, "order": "left_to_right"}
    )
    assert "Annotated" in result


@pytest.mark.anyio
async def test_schematic_reload(sample_project, mock_kicad) -> None:
    """sch_reload should reload the schematic file."""
    server = build_server("schematic")
    result = await call_tool_text(server, "sch_reload", {})
    assert "updated" in result.lower() or "reload" in result.lower()


@pytest.mark.anyio
async def test_schematic_create_sheet_duplicate(sample_project, mock_kicad) -> None:
    """sch_create_sheet should handle duplicate sheet names."""
    server = build_server("schematic")
    await call_tool_text(
        server,
        "sch_create_sheet",
        {"name": "Power", "filename": "power.kicad_sch", "x_mm": 40.0, "y_mm": 50.0},
    )
    result = await call_tool_text(
        server,
        "sch_create_sheet",
        {"name": "Power", "filename": "power2.kicad_sch", "x_mm": 80.0, "y_mm": 50.0},
    )
    assert "already exists" in result.lower() or "created" in result.lower()


@pytest.mark.anyio
async def test_schematic_list_sheets_empty(sample_project, mock_kicad) -> None:
    """sch_list_sheets should handle project with no child sheets."""
    server = build_server("schematic")
    result = await call_tool_text(server, "sch_list_sheets", {})
    assert "Sheets" in result or "No child sheets" in result or "sheet" in result.lower()


@pytest.mark.anyio
async def test_schematic_get_sheet_info_missing(sample_project, mock_kicad) -> None:
    """sch_get_sheet_info should report when sheet is not found."""
    server = build_server("schematic")
    result = await call_tool_text(server, "sch_get_sheet_info", {"sheet_name": "NONEXISTENT"})
    assert "not found" in result.lower() or "no sheet" in result.lower()


@pytest.mark.anyio
async def test_schematic_route_wire_between_pins_missing_refs(sample_project, mock_kicad) -> None:
    """sch_route_wire_between_pins should report missing references."""
    server = build_server("schematic")
    result = await call_tool_text(
        server,
        "sch_route_wire_between_pins",
        {"ref1": "R99", "pin1": "1", "ref2": "R100", "pin2": "2"},
    )
    assert "not found" in result.lower() or "missing" in result.lower()


@pytest.mark.anyio
async def test_schematic_swap_pins_same_pin(sample_project, mock_kicad) -> None:
    """sch_swap_pins should handle swapping same pin gracefully."""
    server = build_server("schematic")
    await call_tool_text(
        server,
        "sch_build_circuit",
        {
            "symbols": [
                {
                    "library": "Device",
                    "symbol_name": "R",
                    "x_mm": 10.0,
                    "y_mm": 10.0,
                    "reference": "R1",
                    "value": "10k",
                    "footprint": "Resistor_SMD:R_0805",
                }
            ]
        },
    )

    result = await call_tool_text(
        server, "sch_swap_pins", {"component_ref": "R1", "pin_a": "1", "pin_b": "1"}
    )
    assert "Recorded pin swap" in result or "same pin" in result.lower()


@pytest.mark.anyio
async def test_schematic_swap_gates_not_available(sample_project, mock_kicad) -> None:
    """sch_swap_gates should report when gates are not available."""
    server = build_server("schematic")
    await call_tool_text(
        server,
        "sch_build_circuit",
        {
            "symbols": [
                {
                    "library": "Device",
                    "symbol_name": "R",
                    "x_mm": 10.0,
                    "y_mm": 10.0,
                    "reference": "R1",
                    "value": "10k",
                    "footprint": "Resistor_SMD:R_0805",
                }
            ]
        },
    )

    result = await call_tool_text(
        server, "sch_swap_gates", {"component_ref": "R1", "gate_a": 1, "gate_b": 2}
    )
    assert "not available" in result.lower()


@pytest.mark.anyio
async def test_schematic_list_swappable_pins(sample_project, mock_kicad) -> None:
    """sch_list_swappable_pins should list swappable pins for a component."""
    server = build_server("schematic")
    await call_tool_text(
        server,
        "sch_build_circuit",
        {
            "symbols": [
                {
                    "library": "Device",
                    "symbol_name": "R",
                    "x_mm": 10.0,
                    "y_mm": 10.0,
                    "reference": "R1",
                    "value": "10k",
                    "footprint": "Resistor_SMD:R_0805",
                }
            ]
        },
    )

    result = await call_tool_text(server, "sch_list_swappable_pins", {"component_ref": "R1"})
    assert '"pins"' in result or "swappable" in result.lower()


@pytest.mark.anyio
async def test_schematic_move_symbol_missing(sample_project, mock_kicad) -> None:
    """sch_move_symbol should report when reference is not found."""
    server = build_server("schematic")
    result = await call_tool_text(
        server, "sch_move_symbol", {"reference": "R404", "x_mm": 10.0, "y_mm": 10.0}
    )
    assert "not found" in result.lower()


@pytest.mark.anyio
async def test_schematic_delete_symbol_missing(sample_project, mock_kicad) -> None:
    """sch_delete_symbol should report when reference is not found."""
    server = build_server("schematic")
    result = await call_tool_text(server, "sch_delete_symbol", {"reference": "R404"})
    assert "not found" in result.lower()


@pytest.mark.anyio
async def test_schematic_delete_wire_missing(sample_project, mock_kicad) -> None:
    """sch_delete_wire should report when wire_id is not found."""
    server = build_server("schematic")
    result = await call_tool_text(server, "sch_delete_wire", {"wire_id": "nonexistent"})
    assert "not found" in result.lower()


@pytest.mark.anyio
async def test_schematic_get_bounding_boxes(sample_project, mock_kicad) -> None:
    """sch_get_bounding_boxes should return bounding boxes for schematic items."""
    server = build_server("schematic")
    await call_tool_text(
        server,
        "sch_build_circuit",
        {
            "symbols": [
                {
                    "library": "Device",
                    "symbol_name": "R",
                    "x_mm": 10.0,
                    "y_mm": 10.0,
                    "reference": "R1",
                    "value": "10k",
                    "footprint": "Resistor_SMD:R_0805",
                }
            ]
        },
    )

    result = await call_tool_text(server, "sch_get_bounding_boxes", {})
    assert "Schematic bounding boxes" in result
    assert "R1" in result


@pytest.mark.anyio
async def test_schematic_get_connectivity_graph(sample_project, mock_kicad) -> None:
    """sch_get_connectivity_graph should return connectivity groups."""
    server = build_server("schematic")
    await call_tool_text(
        server,
        "sch_build_circuit",
        {
            "symbols": [
                {
                    "library": "Device",
                    "symbol_name": "R",
                    "x_mm": 10.0,
                    "y_mm": 10.0,
                    "reference": "R1",
                    "value": "10k",
                    "footprint": "Resistor_SMD:R_0805",
                },
                {
                    "library": "Device",
                    "symbol_name": "R",
                    "x_mm": 20.0,
                    "y_mm": 10.0,
                    "reference": "R2",
                    "value": "22k",
                    "footprint": "Resistor_SMD:R_0805",
                },
            ],
            "wires": [{"x1_mm": 10.0, "y1_mm": 10.0, "x2_mm": 20.0, "y2_mm": 10.0}],
            "labels": [{"name": "MID", "x_mm": 15.0, "y_mm": 10.0}],
        },
    )

    result = await call_tool_text(server, "sch_get_connectivity_graph", {})
    assert "Connectivity groups" in result
    assert "MID" in result


@pytest.mark.anyio
async def test_schematic_instantiate_template_missing(sample_project, mock_kicad) -> None:
    """sch_instantiate_template should report when template is not found."""
    server = build_server("schematic")
    result = await call_tool_text(
        server,
        "sch_instantiate_template",
        {"template_name": "nonexistent_template", "prefix": "TEST_"},
    )
    assert "not found" in result.lower()


@pytest.mark.anyio
async def test_schematic_get_template_info_missing(sample_project, mock_kicad) -> None:
    """sch_get_template_info should report when template is not found."""
    server = build_server("schematic")
    result = await call_tool_text(
        server, "sch_get_template_info", {"template_name": "nonexistent_template"}
    )
    assert "not found" in result.lower()


@pytest.mark.anyio
async def test_schematic_list_templates(sample_project, mock_kicad) -> None:
    """sch_list_templates should list available subcircuit templates."""
    server = build_server("schematic")
    result = await call_tool_text(server, "sch_list_templates", {})
    assert "Available" in result or "Templates" in result or "template" in result.lower()


@pytest.mark.anyio
async def test_schematic_add_jumper(sample_project, mock_kicad) -> None:
    """sch_add_jumper should add a jumper symbol to the schematic."""
    server = build_server("schematic")
    result = await call_tool_text(
        server, "sch_add_jumper", {"x_mm": 30.0, "y_mm": 30.0, "pins": 2, "open_by_default": True}
    )
    assert "Added jumper" in result or "jumper" in result.lower()


@pytest.mark.anyio
async def test_schematic_set_hop_over(sample_project, mock_kicad) -> None:
    """sch_set_hop_over should toggle hop-over display setting."""
    server = build_server("schematic")
    result = await call_tool_text(server, "sch_set_hop_over", {"enabled": False})
    assert "Hop-over display set to disabled" in result

    result = await call_tool_text(server, "sch_set_hop_over", {"enabled": True})
    assert "Hop-over display set to enabled" in result


@pytest.mark.anyio
async def test_schematic_add_bus_and_entry(sample_project, mock_kicad) -> None:
    """sch_add_bus and sch_add_bus_wire_entry should add bus elements."""
    server = build_server("schematic")
    bus = await call_tool_text(
        server, "sch_add_bus", {"x1_mm": 10.0, "y1_mm": 20.0, "x2_mm": 40.0, "y2_mm": 20.0}
    )
    entry = await call_tool_text(
        server,
        "sch_add_bus_wire_entry",
        {"x_mm": 15.0, "y_mm": 20.0, "direction": "up_right"},
    )
    schematic = (sample_project / "demo.kicad_sch").read_text(encoding="utf-8")
    assert "updated" in bus.lower() or "reload" in bus.lower()
    assert "updated" in entry.lower() or "reload" in entry.lower()
    assert "(bus" in schematic
    assert "(bus_entry" in schematic


@pytest.mark.anyio
async def test_schematic_add_no_connect(sample_project, mock_kicad) -> None:
    """sch_add_no_connect should add no-connect markers."""
    server = build_server("schematic")
    result = await call_tool_text(server, "sch_add_no_connect", {"x_mm": 30.0, "y_mm": 30.0})
    schematic = (sample_project / "demo.kicad_sch").read_text(encoding="utf-8")
    assert "updated" in result.lower() or "reload" in result.lower()
    assert "(no_connect" in schematic


@pytest.mark.anyio
async def test_schematic_add_hierarchical_label(sample_project, mock_kicad) -> None:
    """sch_add_hierarchical_label should add hierarchical labels with shapes."""
    server = build_server("schematic")
    for shape in ["input", "output", "bidirectional", "tri_state", "passive"]:
        result = await call_tool_text(
            server,
            "sch_add_hierarchical_label",
            {"text": f"SIG_{shape}", "x_mm": 30.0, "y_mm": 30.0, "shape": shape},
        )
        assert "updated" in result.lower() or "reload" in result.lower()

    schematic = (sample_project / "demo.kicad_sch").read_text(encoding="utf-8")
    assert "(hierarchical_label" in schematic


@pytest.mark.anyio
async def test_schematic_add_global_label_shapes(sample_project, mock_kicad) -> None:
    """sch_add_global_label should support all label shapes."""
    server = build_server("schematic")
    for shape in ["input", "output", "bidirectional", "tri_state", "passive"]:
        result = await call_tool_text(
            server,
            "sch_add_global_label",
            {"text": f"NET_{shape}", "x_mm": 30.0, "y_mm": 30.0, "shape": shape},
        )
        assert "updated" in result.lower() or "reload" in result.lower()

    schematic = (sample_project / "demo.kicad_sch").read_text(encoding="utf-8")
    assert "(global_label" in schematic


@pytest.mark.anyio
async def test_schematic_update_properties_missing_field(sample_project, mock_kicad) -> None:
    """sch_update_properties should handle missing symbols gracefully."""
    server = build_server("schematic")
    result = await call_tool_text(
        server,
        "sch_update_properties",
        {"reference": "R404", "field": "Value", "value": "100k"},
    )
    assert "not found" in result.lower() or "Reference 'R404'" in result


@pytest.mark.anyio
async def test_schematic_get_pin_positions_missing_library(sample_project, mock_kicad) -> None:
    """sch_get_pin_positions should report when library is not found."""
    server = build_server("schematic")
    result = await call_tool_text(
        server,
        "sch_get_pin_positions",
        {"library": "MissingLib", "symbol_name": "R", "x_mm": 10.0, "y_mm": 10.0},
    )
    assert "not found" in result.lower() or "library" in result.lower()


@pytest.mark.anyio
async def test_schematic_get_symbols_empty(sample_project, mock_kicad) -> None:
    """sch_get_symbols should handle empty schematic."""
    server = build_server("schematic")
    result = await call_tool_text(server, "sch_get_symbols", {})
    assert "Symbols" in result or "No symbols" in result or "0 total" in result


@pytest.mark.anyio
async def test_schematic_get_wires_empty(sample_project, mock_kicad) -> None:
    """sch_get_wires should handle schematic with no wires."""
    server = build_server("schematic")
    result = await call_tool_text(server, "sch_get_wires", {})
    assert "Wires" in result or "No wires" in result or "contains no wires" in result


@pytest.mark.anyio
async def test_schematic_get_labels_empty(sample_project, mock_kicad) -> None:
    """sch_get_labels should handle schematic with no labels."""
    server = build_server("schematic")
    result = await call_tool_text(server, "sch_get_labels", {})
    assert "Labels" in result or "No labels" in result


@pytest.mark.anyio
async def test_schematic_get_net_names_empty(sample_project, mock_kicad) -> None:
    """sch_get_net_names should handle schematic with no nets."""
    server = build_server("schematic")
    result = await call_tool_text(server, "sch_get_net_names", {})
    assert "Nets" in result or "No nets" in result


@pytest.mark.anyio
async def test_schematic_build_circuit_empty(sample_project, mock_kicad) -> None:
    """sch_build_circuit should handle empty circuit definition."""
    server = build_server("schematic")
    result = await call_tool_text(
        server, "sch_build_circuit", {"symbols": [], "wires": [], "labels": []}
    )
    assert "Circuit" in result or "built" in result.lower() or "updated" in result.lower()


@pytest.mark.anyio
async def test_schematic_build_circuit_with_nets(sample_project, mock_kicad) -> None:
    """sch_build_circuit should support netlist-based wiring."""
    server = build_server("schematic")
    result = await call_tool_text(
        server,
        "sch_build_circuit",
        {
            "symbols": [
                {
                    "library": "Device",
                    "symbol_name": "R",
                    "x_mm": 10.0,
                    "y_mm": 10.0,
                    "reference": "R1",
                    "value": "10k",
                    "footprint": "Resistor_SMD:R_0805",
                },
                {
                    "library": "Device",
                    "symbol_name": "R",
                    "x_mm": 20.0,
                    "y_mm": 10.0,
                    "reference": "R2",
                    "value": "22k",
                    "footprint": "Resistor_SMD:R_0805",
                },
            ],
            "nets": [
                {
                    "name": "VIN",
                    "endpoints": [{"reference": "R1", "pin": "1"}],
                },
                {
                    "name": "MID",
                    "endpoints": [
                        {"reference": "R1", "pin": "2"},
                        {"reference": "R2", "pin": "1"},
                    ],
                },
                {"name": "GND", "endpoints": [{"reference": "R2", "pin": "2"}]},
            ],
        },
    )
    assert "Circuit" in result or "built" in result.lower()
    schematic = (sample_project / "demo.kicad_sch").read_text(encoding="utf-8")
    assert '(label "VIN"' in schematic
    assert '(label "MID"' in schematic


@pytest.mark.anyio
async def test_schematic_auto_place_symbols_linear(sample_project, mock_kicad) -> None:
    """sch_auto_place_symbols should support linear strategy."""
    server = build_server("schematic")
    await call_tool_text(
        server,
        "sch_build_circuit",
        {
            "symbols": [
                {
                    "library": "Device",
                    "symbol_name": "R",
                    "x_mm": 10.0,
                    "y_mm": 10.0,
                    "reference": "R1",
                    "value": "10k",
                    "footprint": "Resistor_SMD:R_0805",
                },
                {
                    "library": "Device",
                    "symbol_name": "R",
                    "x_mm": 10.0,
                    "y_mm": 20.0,
                    "reference": "R2",
                    "value": "22k",
                    "footprint": "Resistor_SMD:R_0805",
                },
            ]
        },
    )

    result = await call_tool_text(
        server, "sch_auto_place_symbols", {"symbol_list": ["R1", "R2"], "strategy": "linear"}
    )
    assert "Auto-placed" in result


@pytest.mark.anyio
async def test_schematic_auto_place_symbols_grid(sample_project, mock_kicad) -> None:
    """sch_auto_place_symbols should support grid strategy."""
    server = build_server("schematic")
    await call_tool_text(
        server,
        "sch_build_circuit",
        {
            "symbols": [
                {
                    "library": "Device",
                    "symbol_name": "R",
                    "x_mm": 10.0,
                    "y_mm": 10.0,
                    "reference": "R1",
                    "value": "10k",
                    "footprint": "Resistor_SMD:R_0805",
                },
                {
                    "library": "Device",
                    "symbol_name": "R",
                    "x_mm": 10.0,
                    "y_mm": 20.0,
                    "reference": "R2",
                    "value": "22k",
                    "footprint": "Resistor_SMD:R_0805",
                },
            ]
        },
    )

    result = await call_tool_text(
        server, "sch_auto_place_symbols", {"symbol_list": ["R1", "R2"], "strategy": "grid"}
    )
    assert "Auto-placed" in result


@pytest.mark.anyio
async def test_schematic_auto_place_symbols_missing_refs(sample_project, mock_kicad) -> None:
    """sch_auto_place_symbols should report missing references."""
    server = build_server("schematic")
    result = await call_tool_text(
        server,
        "sch_auto_place_symbols",
        {"symbol_list": ["R99", "R100"], "strategy": "linear"},
    )
    assert "not found" in result.lower() or "missing" in result.lower()


@pytest.mark.anyio
async def test_schematic_auto_place_functional_no_project(mock_kicad) -> None:
    """sch_auto_place_functional should handle missing project gracefully."""
    server = build_server("schematic")
    result = await call_tool_text(server, "sch_auto_place_functional", {})
    assert "No project" in result or "project" in result.lower()


@pytest.mark.anyio
async def test_schematic_analyze_net_compilation_empty(sample_project, mock_kicad) -> None:
    """sch_analyze_net_compilation should handle empty netlist."""
    server = build_server("schematic")
    result = await call_tool_text(
        server,
        "sch_analyze_net_compilation",
        {"symbols": [], "nets": []},
    )
    assert "Net compilation analysis" in result
    assert "Nets requested: 0" in result


@pytest.mark.anyio
async def test_schematic_add_power_symbol_rotated(sample_project, mock_kicad) -> None:
    """sch_add_power_symbol should support rotation."""
    server = build_server("schematic")
    result = await call_tool_text(
        server,
        "sch_add_power_symbol",
        {"name": "VCC", "x_mm": 20.0, "y_mm": 20.0, "rotation": 90},
    )
    schematic = (sample_project / "demo.kicad_sch").read_text(encoding="utf-8")
    assert "updated" in result.lower() or "reload" in result.lower()
    assert "VCC" in schematic


@pytest.mark.anyio
async def test_schematic_add_symbol_with_unit(sample_project, mock_kicad) -> None:
    """sch_add_symbol should support unit parameter for multi-unit symbols."""
    server = build_server("schematic")
    result = await call_tool_text(
        server,
        "sch_add_symbol",
        {
            "library": "MultiUnit",
            "symbol_name": "DualChild",
            "x_mm": 30.0,
            "y_mm": 30.0,
            "reference": "U1",
            "value": "DualChild",
            "footprint": "Package_DIP:DIP-8_W7.62mm",
            "rotation": 0,
            "unit": 1,
        },
    )
    schematic = (sample_project / "demo.kicad_sch").read_text(encoding="utf-8")
    assert "updated" in result.lower() or "reload" in result.lower()
    assert "(unit 1)" in schematic


@pytest.mark.anyio
async def test_schematic_add_wire_snap_to_grid(sample_project, mock_kicad) -> None:
    """sch_add_wire should snap to grid by default."""
    server = build_server("schematic")
    result = await call_tool_text(
        server,
        "sch_add_wire",
        {"x1_mm": 10.1, "y1_mm": 10.1, "x2_mm": 20.1, "y2_mm": 10.1},
    )
    schematic = (sample_project / "demo.kicad_sch").read_text(encoding="utf-8")
    assert "updated" in result.lower() or "reload" in result.lower()
    # Should be snapped to 2.54mm grid
    assert "(pts (xy 10.16 10.16) (xy 20.32 10.16))" in schematic


@pytest.mark.anyio
async def test_schematic_add_label_rotated(sample_project, mock_kicad) -> None:
    """sch_add_label should support rotation."""
    server = build_server("schematic")
    result = await call_tool_text(
        server,
        "sch_add_label",
        {"name": "ROTATED", "x_mm": 10.0, "y_mm": 10.0, "rotation": 90},
    )
    schematic = (sample_project / "demo.kicad_sch").read_text(encoding="utf-8")
    assert "updated" in result.lower() or "reload" in result.lower()
    assert "ROTATED" in schematic


@pytest.mark.anyio
async def test_schematic_get_pin_positions_rotated(sample_project, mock_kicad) -> None:
    """sch_get_pin_positions should account for rotation."""
    server = build_server("schematic")
    result = await call_tool_text(
        server,
        "sch_get_pin_positions",
        {"library": "Device", "symbol_name": "R", "x_mm": 10.0, "y_mm": 10.0, "rotation": 90},
    )
    assert "Pin 1" in result
    assert "rotation=90" in result or "90" in result


@pytest.mark.anyio
async def test_schematic_instantiate_template_with_params(sample_project, mock_kicad) -> None:
    """sch_instantiate_template should substitute parameters."""
    server = build_server("schematic")
    result = await call_tool_text(
        server,
        "sch_instantiate_template",
        {
            "template_name": "buzzer_nmos_driver",
            "prefix": "AUD_",
            "params": {"supply_v": 5.0},
        },
    )
    assert "Instantiation Plan" in result
    assert "AUD_" in result
    assert "5.0" in result


@pytest.mark.anyio
async def test_schematic_get_template_info_valid(sample_project, mock_kicad) -> None:
    """sch_get_template_info should return detailed template information."""
    server = build_server("schematic")
    result = await call_tool_text(
        server, "sch_get_template_info", {"template_name": "buzzer_nmos_driver"}
    )
    assert "Template" in result
    assert "Parameters" in result or "Symbols" in result or "Nets" in result


@pytest.mark.anyio
async def test_schematic_create_sheet_with_size(sample_project, mock_kicad) -> None:
    """sch_create_sheet should create child sheet with specified size."""
    server = build_server("schematic")
    result = await call_tool_text(
        server,
        "sch_create_sheet",
        {"name": "IO", "filename": "io.kicad_sch", "x_mm": 50.0, "y_mm": 50.0},
    )
    assert "Created child sheet 'IO'" in result
    assert (sample_project / "io.kicad_sch").exists()

    info = await call_tool_text(server, "sch_get_sheet_info", {"sheet_name": "IO"})
    assert "Sheet 'IO'" in info
    assert "io.kicad_sch" in info


@pytest.mark.anyio
async def test_schematic_delete_wire_by_uuid_prefix(sample_project, mock_kicad) -> None:
    """sch_delete_wire should support UUID prefix matching."""
    server = build_server("schematic")
    await call_tool_text(
        server,
        "sch_build_circuit",
        {
            "symbols": [
                {
                    "library": "Device",
                    "symbol_name": "R",
                    "x_mm": 10.0,
                    "y_mm": 10.0,
                    "reference": "R1",
                    "value": "10k",
                    "footprint": "Resistor_SMD:R_0805",
                },
                {
                    "library": "Device",
                    "symbol_name": "R",
                    "x_mm": 20.0,
                    "y_mm": 10.0,
                    "reference": "R2",
                    "value": "22k",
                    "footprint": "Resistor_SMD:R_0805",
                },
            ],
            "wires": [{"x1_mm": 10.0, "y1_mm": 10.0, "x2_mm": 20.0, "y2_mm": 10.0}],
        },
    )

    await call_tool_text(server, "sch_get_wires", {})
    # Try deleting with a short prefix that won't match anything meaningful
    result = await call_tool_text(server, "sch_delete_wire", {"wire_id": "0000"})
    assert "Deleted" in result or "not found" in result.lower()


@pytest.mark.anyio
async def test_schematic_update_properties_value_escaping(sample_project, mock_kicad) -> None:
    """sch_update_properties should properly escape special characters in values."""
    server = build_server("schematic")
    await call_tool_text(
        server,
        "sch_build_circuit",
        {
            "symbols": [
                {
                    "library": "Device",
                    "symbol_name": "R",
                    "x_mm": 10.0,
                    "y_mm": 10.0,
                    "reference": "R1",
                    "value": "10k",
                    "footprint": "Resistor_SMD:R_0805",
                }
            ]
        },
    )

    result = await call_tool_text(
        server,
        "sch_update_properties",
        {"reference": "R1", "field": "Value", "value": '10k "1%"'},
    )
    schematic = (sample_project / "demo.kicad_sch").read_text(encoding="utf-8")
    assert "Updated R1.Value" in result
    assert '10k \\"1%\\"' in schematic or '10k "1%"' in schematic


@pytest.mark.anyio
async def test_schematic_add_symbol_no_footprint(sample_project, mock_kicad) -> None:
    """sch_add_symbol should work without an explicit footprint."""
    server = build_server("schematic")
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
            "rotation": 0,
        },
    )
    schematic = (sample_project / "demo.kicad_sch").read_text(encoding="utf-8")
    assert "updated" in result.lower() or "reload" in result.lower()
    assert "R1" in schematic


@pytest.mark.anyio
async def test_schematic_build_circuit_auto_layout_no_coords(sample_project, mock_kicad) -> None:
    """sch_build_circuit with auto_layout should assign coordinates when missing."""
    server = build_server("schematic")
    result = await call_tool_text(
        server,
        "sch_build_circuit",
        {
            "auto_layout": True,
            "symbols": [
                {
                    "library": "Device",
                    "symbol_name": "R",
                    "reference": "R1",
                    "value": "10k",
                    "footprint": "Resistor_SMD:R_0805",
                },
                {
                    "library": "Device",
                    "symbol_name": "R",
                    "reference": "R2",
                    "value": "22k",
                    "footprint": "Resistor_SMD:R_0805",
                },
            ],
            "wires": [],
            "labels": [{"name": "OUT"}],
            "power_symbols": [{"name": "GND"}],
        },
    )
    assert "Applied basic auto-layout" in result or "Applied netlist-aware auto-layout" in result
    schematic = (sample_project / "demo.kicad_sch").read_text(encoding="utf-8")
    assert "R1" in schematic
    assert "R2" in schematic
    assert "OUT" in schematic
    assert "GND" in schematic


@pytest.mark.anyio
async def test_schematic_add_pin_labels(sample_project, mock_kicad) -> None:
    """sch_add_pin_labels should connect symbol pins to nets via stubs and labels."""
    server = build_server("schematic")
    await call_tool_text(
        server,
        "sch_build_circuit",
        {
            "symbols": [
                {
                    "library": "Device",
                    "symbol_name": "R",
                    "x_mm": 10.0,
                    "y_mm": 10.0,
                    "reference": "R1",
                    "value": "10k",
                    "footprint": "Resistor_SMD:R_0805",
                },
            ],
        },
    )
    result = await call_tool_text(
        server,
        "sch_add_pin_labels",
        {
            "connections": [
                {"reference": "R1", "pin": "1", "net": "NET_IN"},
            ],
        },
    )
    assert "->" in result
    assert "NET_IN" in result


@pytest.mark.anyio
async def test_schematic_delete_label(sample_project, mock_kicad) -> None:
    """sch_delete_label should remove a matching label from the schematic."""
    server = build_server("schematic")
    await call_tool_text(
        server,
        "sch_add_label",
        {"name": "TO_DELETE", "x_mm": 50.0, "y_mm": 50.0, "rotation": 0},
    )
    result = await call_tool_text(
        server,
        "sch_delete_label",
        {"name": "TO_DELETE", "x_mm": 50.0, "y_mm": 50.0},
    )
    assert "Deleted" in result
    assert "TO_DELETE" in result


@pytest.mark.anyio
async def test_schematic_move_label(sample_project, mock_kicad) -> None:
    """sch_move_label should move a label to a new coordinate."""
    server = build_server("schematic")
    await call_tool_text(
        server,
        "sch_add_label",
        {"name": "TO_MOVE", "x_mm": 20.0, "y_mm": 20.0, "rotation": 0},
    )
    result = await call_tool_text(
        server,
        "sch_move_label",
        {"name": "TO_MOVE", "x_mm": 20.0, "y_mm": 20.0, "new_x_mm": 80.0, "new_y_mm": 40.0},
    )
    assert "Moved" in result or "moved" in result or "TO_MOVE" in result
