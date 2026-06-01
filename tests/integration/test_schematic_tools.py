from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from kicad_mcp.config import get_config
from kicad_mcp.server import build_server
from kicad_mcp.tools.schematic import parse_schematic_file
from tests.conftest import call_tool_text


@pytest.mark.anyio
async def test_schematic_add_label(sample_project, mock_kicad) -> None:
    server = build_server("schematic")
    text = await call_tool_text(
        server,
        "sch_add_label",
        {"name": "NET_A", "x_mm": 10.0, "y_mm": 10.0, "rotation": 0},
    )
    assert "updated" in text.lower() or "reload" in text.lower()
    labels = await call_tool_text(server, "sch_get_labels", {})
    assert "NET_A" in labels


@pytest.mark.anyio
async def test_schematic_string_values_are_escaped(sample_project, mock_kicad) -> None:
    server = build_server("schematic")

    await call_tool_text(
        server,
        "sch_add_label",
        {"name": 'NET(1)"A\\B', "x_mm": 10.0, "y_mm": 10.0, "rotation": 0},
    )

    schematic = (sample_project / "demo.kicad_sch").read_text(encoding="utf-8")
    labels = await call_tool_text(server, "sch_get_labels", {})
    assert '"NET(1)\\"A\\\\B"' in schematic
    assert 'NET(1)"A\\B' in labels


@pytest.mark.anyio
async def test_schematic_misc_file_tools_cover_buses_labels_jumper_and_project_flags(
    sample_project,
    mock_kicad,
) -> None:
    server = build_server("schematic")

    bus = await call_tool_text(
        server,
        "sch_add_bus",
        {"x1_mm": 10.0, "y1_mm": 20.0, "x2_mm": 40.0, "y2_mm": 20.0},
    )
    entry = await call_tool_text(
        server,
        "sch_add_bus_wire_entry",
        {"x_mm": 15.0, "y_mm": 20.0, "direction": "down_right"},
    )
    no_connect = await call_tool_text(
        server,
        "sch_add_no_connect",
        {"x_mm": 30.0, "y_mm": 30.0},
    )
    global_label = await call_tool_text(
        server,
        "sch_add_global_label",
        {"text": "USB_DP", "x_mm": 50.0, "y_mm": 20.0, "shape": "output"},
    )
    hierarchical = await call_tool_text(
        server,
        "sch_add_hierarchical_label",
        {"text": "SENSE", "x_mm": 55.0, "y_mm": 25.0, "shape": "input"},
    )
    jumper = await call_tool_text(
        server,
        "sch_add_jumper",
        {"x_mm": 70.0, "y_mm": 35.0, "pins": 3, "open_by_default": False},
    )
    hop = await call_tool_text(server, "sch_set_hop_over", {"enabled": True})
    labels = await call_tool_text(server, "sch_get_labels", {})
    nets = await call_tool_text(server, "sch_get_net_names", {})
    wires = await call_tool_text(server, "sch_get_wires", {})

    schematic = (sample_project / "demo.kicad_sch").read_text(encoding="utf-8")
    project_payload = (sample_project / "demo.kicad_pro").read_text(encoding="utf-8")

    assert "updated" in bus.lower()
    assert "updated" in entry.lower()
    assert "updated" in no_connect.lower()
    assert "updated" in global_label.lower()
    assert "updated" in hierarchical.lower()
    assert "Added jumper" in jumper
    assert "Hop-over display set to enabled" in hop
    assert "(bus" in schematic
    assert "(bus_entry" in schematic
    assert "(no_connect" in schematic
    assert '(global_label "USB_DP"' in schematic
    assert '(hierarchical_label "SENSE"' in schematic
    assert '"hop_over_display": true' in project_payload
    assert "USB_DP" in labels and "SENSE" in labels
    assert "- USB_DP" in nets and "- SENSE" in nets
    assert "Wires" in wires or "contains no wires" in wires


@pytest.mark.anyio
async def test_power_symbol_reference_is_hidden_and_value_offset(
    sample_project,
    mock_kicad,
) -> None:
    server = build_server("schematic")

    result = await call_tool_text(
        server,
        "sch_add_power_symbol",
        {"name": "GND", "x_mm": 20.0, "y_mm": 30.0, "rotation": 0},
    )

    schematic = (sample_project / "demo.kicad_sch").read_text(encoding="utf-8")
    assert "updated" in result.lower() or "reload" in result.lower()
    assert "Grid snap" in result
    assert '(property "Reference" "#PWR' in schematic
    assert "\t\t\t(at 20.32 36.83 0)" in schematic
    assert "\t\t\t(effects (font (size 1.27 1.27)) (hide yes))" in schematic
    assert '(property "Value" "GND"\n\t\t\t(at 20.32 35.56 0)' in schematic


@pytest.mark.anyio
async def test_build_circuit_accepts_power_symbol_mm_aliases(sample_project, mock_kicad) -> None:
    server = build_server("schematic")

    await call_tool_text(
        server,
        "sch_build_circuit",
        {
            "symbols": [],
            "wires": [],
            "labels": [],
            "power_symbols": [{"name": "GND", "x_mm": 20.0, "y_mm": 30.0, "rotation": 0}],
        },
    )

    schematic = (sample_project / "demo.kicad_sch").read_text(encoding="utf-8")
    assert '(lib_id "power:GND")' in schematic
    assert "\t\t(at 20.32 30.48 0)" in schematic


@pytest.mark.anyio
async def test_schematic_end_to_end_editing_and_analysis_tools(
    sample_project,
    mock_kicad,
) -> None:
    server = build_server("schematic")
    await call_tool_text(
        server,
        "sch_build_circuit",
        {
            "symbols": [
                {
                    "library": "Device",
                    "symbol_name": "R",
                    "reference": "R1",
                    "value": "10k",
                    "footprint": "Resistor_SMD:R_0805",
                    "x_mm": 50.8,
                    "y_mm": 50.8,
                },
                {
                    "library": "Device",
                    "symbol_name": "R",
                    "reference": "R2",
                    "value": "22k",
                    "footprint": "Resistor_SMD:R_0805",
                    "x_mm": 76.2,
                    "y_mm": 50.8,
                },
            ],
            "labels": [{"name": "MID", "x_mm": 63.5, "y_mm": 50.8}],
            "wires": [{"x1_mm": 53.34, "y1_mm": 50.8, "x2_mm": 73.66, "y2_mm": 50.8}],
        },
    )

    symbols = await call_tool_text(server, "sch_get_symbols", {})
    pin_positions = await call_tool_text(
        server,
        "sch_get_pin_positions",
        {"library": "Device", "symbol_name": "R", "x_mm": 50.8, "y_mm": 50.8},
    )
    bad_unit = await call_tool_text(
        server,
        "sch_get_pin_positions",
        {"library": "Device", "symbol_name": "R", "x_mm": 50.8, "y_mm": 50.8, "unit": 2},
    )
    swappable = await call_tool_text(server, "sch_list_swappable_pins", {"component_ref": "R1"})
    pin_swap = await call_tool_text(
        server,
        "sch_swap_pins",
        {"component_ref": "R1", "pin_a": "1", "pin_b": "2"},
    )
    gate_swap = await call_tool_text(
        server,
        "sch_swap_gates",
        {"component_ref": "R1", "gate_a": 1, "gate_b": 2},
    )
    routed = await call_tool_text(
        server,
        "sch_route_wire_between_pins",
        {"ref1": "R1", "pin1": "2", "ref2": "R2", "pin2": "1"},
    )
    connectivity = await call_tool_text(server, "sch_get_connectivity_graph", {})
    trace = await call_tool_text(server, "sch_trace_net", {"net_name": "MID"})
    bounding = await call_tool_text(server, "sch_get_bounding_boxes", {})
    free = await call_tool_text(
        server,
        "sch_find_free_placement",
        {"count": 2, "keepout_regions": [[40.0, 40.0, 90.0, 60.0]]},
    )
    resized = await call_tool_text(server, "sch_set_sheet_size", {"paper": "A3"})
    invalid_resize = await call_tool_text(server, "sch_set_sheet_size", {"paper": "BAD"})
    auto_resize = await call_tool_text(server, "sch_auto_resize_sheet", {})
    updated = await call_tool_text(
        server,
        "sch_update_properties",
        {"reference": "R1", "field": "Value", "value": "47k"},
    )
    moved = await call_tool_text(
        server,
        "sch_move_symbol",
        {"reference": "R1", "x_mm": 101.6, "y_mm": 76.2},
    )
    missing_move = await call_tool_text(
        server,
        "sch_move_symbol",
        {"reference": "R99", "x_mm": 10.0, "y_mm": 10.0},
    )
    annotated = await call_tool_text(server, "sch_annotate", {"start_number": 10, "order": "sheet"})
    wires = (sample_project / "demo.kicad_sch").read_text(encoding="utf-8")
    wire_id = re.search(r'\(wire.*?\(uuid "([^"]+)"\)', wires, flags=re.DOTALL)
    assert wire_id is not None
    deleted_wire = await call_tool_text(server, "sch_delete_wire", {"wire_id": wire_id.group(1)})
    missing_wire = await call_tool_text(server, "sch_delete_wire", {"wire_id": "missing"})
    deleted_symbol = await call_tool_text(server, "sch_delete_symbol", {"reference": "R10"})
    missing_symbol = await call_tool_text(server, "sch_delete_symbol", {"reference": "R404"})
    reload_result = await call_tool_text(server, "sch_reload", {})

    assert "Symbols (2 total)" in symbols
    assert "Pin 1" in pin_positions and "Pin 2" in pin_positions
    assert "does not support unit 2" in bad_unit
    assert '"pins"' in swappable
    assert "Recorded pin swap" in pin_swap
    assert "not available" in gate_swap
    assert "Routed" in routed
    assert "Connectivity groups" in connectivity
    assert "Trace for net 'MID'" in trace or "was not found" in trace
    assert "Schematic bounding boxes" in bounding
    assert "Free placement coordinates" in free
    assert "Sheet resized" in resized
    assert "Unknown paper size" in invalid_resize
    assert "already fits all symbols" in auto_resize or "Sheet resized" in auto_resize
    assert "Updated R1.Value" in updated
    assert "Moved symbol 'R1'" in moved
    assert "Reference 'R99' was not found" in missing_move
    assert "Annotated 2 symbol(s)." in annotated
    assert "Deleted wire" in deleted_wire
    assert "was not found" in missing_wire
    assert "Deleted 1 symbol block(s)" in deleted_symbol
    assert "Reference 'R404' was not found" in missing_symbol
    assert "updated" in reload_result.lower() or "reload" in reload_result.lower()


@pytest.mark.anyio
async def test_build_circuit_auto_layout_assigns_missing_coordinates(
    sample_project,
    mock_kicad,
) -> None:
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

    schematic = (sample_project / "demo.kicad_sch").read_text(encoding="utf-8")
    assert "Applied basic auto-layout" in result
    assert '(property "Reference" "R1"\n\t\t\t(at 50.8 46.99 0)' in schematic
    assert "\t\t(at 76.2 50.8 0)" in schematic
    assert "\t\t(at 50.8 68.58 0)" in schematic
    assert '(label "OUT"\n\t\t(at 50.8 86.36 0)' in schematic


@pytest.mark.anyio
async def test_build_circuit_netlist_auto_layout_generates_wires(
    sample_project,
    mock_kicad,
) -> None:
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
            "nets": [
                {"name": "VIN", "endpoints": [{"reference": "R1", "pin": "1"}]},
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

    schematic = (sample_project / "demo.kicad_sch").read_text(encoding="utf-8")
    assert "Applied netlist-aware auto-layout" in result
    assert "generated 7 wire segment" in result
    assert '(label "VIN"' in schematic
    assert '(label "MID"' in schematic
    assert '(lib_id "power:GND")' in schematic
    assert "(pts (xy 53.34 50.8) (xy 86.36 50.8))" in schematic
    assert "(pts (xy 88.9 50.8) (xy 88.9 68.58))" in schematic


@pytest.mark.anyio
async def test_analyze_net_compilation_reports_routable_nets(
    sample_project,
    mock_kicad,
) -> None:
    server = build_server("schematic")

    result = await call_tool_text(
        server,
        "sch_analyze_net_compilation",
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
            "nets": [
                {"name": "VIN", "endpoints": [{"reference": "R1", "pin": "1"}]},
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

    assert "Net compilation analysis:" in result
    assert "- Nets requested: 3" in result
    assert "- Routable nets: 3" in result
    assert "- Unresolved nets: 0" in result
    assert "- Generated wire segments: 7" in result


@pytest.mark.anyio
async def test_analyze_net_compilation_reports_unresolved_endpoints(
    sample_project,
    mock_kicad,
) -> None:
    server = build_server("schematic")

    result = await call_tool_text(
        server,
        "sch_analyze_net_compilation",
        {
            "auto_layout": True,
            "symbols": [
                {
                    "library": "Device",
                    "symbol_name": "R",
                    "reference": "R1",
                    "value": "10k",
                    "footprint": "Resistor_SMD:R_0805",
                }
            ],
            "nets": [
                {
                    "name": "BROKEN_NET",
                    "endpoints": [
                        {"reference": "U9", "pin": "1"},
                        {"reference": "U10", "pin": "2"},
                    ],
                }
            ],
        },
    )

    assert "- Nets requested: 1" in result
    assert "- Routable nets: 0" in result
    assert "- Unresolved nets: 1" in result
    assert "BROKEN_NET" in result
    assert "U9.1" in result
    assert "U10.2" in result


@pytest.mark.anyio
async def test_build_circuit_netlist_auto_layout_raises_when_no_wires_resolve(
    sample_project,
    mock_kicad,
) -> None:
    server = build_server("schematic")

    error_text = await call_tool_text(
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
                }
            ],
            "nets": [
                {
                    "name": "BROKEN_NET",
                    "endpoints": [
                        {"reference": "U9", "pin": "1"},
                        {"reference": "U10", "pin": "2"},
                    ],
                }
            ],
        },
    )

    assert "could not generate any wire segments" in error_text
    assert "BROKEN_NET" in error_text
    assert "U9.1" in error_text
    assert "U10.2" in error_text


@pytest.mark.anyio
async def test_schematic_snap_to_grid_can_be_disabled(sample_project, mock_kicad) -> None:
    server = build_server("schematic")

    result = await call_tool_text(
        server,
        "sch_add_wire",
        {
            "x1_mm": 1.1,
            "y1_mm": 2.2,
            "x2_mm": 3.3,
            "y2_mm": 4.4,
            "snap_to_grid": False,
        },
    )

    schematic = (sample_project / "demo.kicad_sch").read_text(encoding="utf-8")
    assert "Grid snap" not in result
    assert "(pts (xy 1.1 2.2) (xy 3.3 4.4))" in schematic


@pytest.mark.anyio
async def test_schematic_pin_positions_use_electrical_pin_end(
    sample_project,
    mock_kicad,
) -> None:
    server = build_server("schematic")

    text = await call_tool_text(
        server,
        "sch_get_pin_positions",
        {"library": "Device", "symbol_name": "R", "x_mm": 10.16, "y_mm": 10.16},
    )

    assert "Pin 1: (7.6200, 10.1600)" in text
    assert "Pin 2: (12.7000, 10.1600)" in text


@pytest.mark.anyio
async def test_schematic_pin_positions_follow_extended_base_symbol(
    sample_project,
    mock_kicad,
) -> None:
    server = build_server("schematic")

    text = await call_tool_text(
        server,
        "sch_get_pin_positions",
        {"library": "Extended", "symbol_name": "ChildTimer", "x_mm": 20.0, "y_mm": 20.0},
    )

    assert "Pin 1: (17.4600, 20.0000)" in text
    assert "Pin 2: (22.5400, 20.0000)" in text


@pytest.mark.anyio
async def test_schematic_add_symbol_embeds_extended_symbol_chain(
    sample_project,
    mock_kicad,
) -> None:
    server = build_server("schematic")

    await call_tool_text(
        server,
        "sch_add_symbol",
        {
            "library": "Extended",
            "symbol_name": "ChildTimer",
            "x_mm": 20.0,
            "y_mm": 20.0,
            "reference": "U1",
            "value": "ChildTimer",
            "footprint": "Package_DIP:DIP-8_W7.62mm",
            "rotation": 0,
        },
    )

    schematic = (sample_project / "demo.kicad_sch").read_text(encoding="utf-8")
    assert '(symbol "BaseTimer"' in schematic
    assert '(symbol "Extended:ChildTimer"' in schematic


@pytest.mark.anyio
async def test_schematic_pin_positions_support_multi_unit_inherited_symbols(
    sample_project,
    mock_kicad,
) -> None:
    server = build_server("schematic")

    text = await call_tool_text(
        server,
        "sch_get_pin_positions",
        {
            "library": "MultiUnit",
            "symbol_name": "DualChild",
            "x_mm": 40.0,
            "y_mm": 40.0,
            "rotation": 0,
            "unit": 2,
        },
    )

    assert "unit=2" in text
    assert "Pin 5: (32.3800, 42.5400)" in text
    assert "Pin 6: (32.3800, 37.4600)" in text
    assert "Pin 7: (47.6200, 40.0000)" in text


@pytest.mark.anyio
async def test_schematic_add_symbol_records_requested_unit(sample_project, mock_kicad) -> None:
    server = build_server("schematic")

    await call_tool_text(
        server,
        "sch_add_symbol",
        {
            "library": "MultiUnit",
            "symbol_name": "DualChild",
            "x_mm": 30.0,
            "y_mm": 30.0,
            "reference": "U2",
            "value": "DualChild",
            "footprint": "Package_DIP:DIP-8_W7.62mm",
            "rotation": 0,
            "unit": 2,
        },
    )

    schematic = (sample_project / "demo.kicad_sch").read_text(encoding="utf-8")
    symbols = await call_tool_text(server, "sch_get_symbols", {})
    assert "\t\t(unit 2)\n" in schematic
    assert '(reference "U2") (unit 2)' in schematic
    assert "U2 DualChild MultiUnit:DualChild" in symbols
    assert "unit=2" in symbols


@pytest.mark.anyio
async def test_schematic_invalid_unit_reports_available_units(sample_project, mock_kicad) -> None:
    server = build_server("schematic")

    text = await call_tool_text(
        server,
        "sch_get_pin_positions",
        {
            "library": "MultiUnit",
            "symbol_name": "DualChild",
            "x_mm": 40.0,
            "y_mm": 40.0,
            "rotation": 0,
            "unit": 4,
        },
    )

    assert "does not support unit 4" in text
    assert "Available units: 1, 2, 3" in text


@pytest.mark.anyio
async def test_build_circuit_netlist_auto_layout_supports_extended_symbols(
    sample_project,
    mock_kicad,
) -> None:
    server = build_server("schematic")

    result = await call_tool_text(
        server,
        "sch_build_circuit",
        {
            "auto_layout": True,
            "symbols": [
                {
                    "library": "Extended",
                    "symbol_name": "ChildTimer",
                    "reference": "U1",
                    "value": "Timer",
                    "footprint": "Package_DIP:DIP-8_W7.62mm",
                },
                {
                    "library": "Device",
                    "symbol_name": "R",
                    "reference": "R1",
                    "value": "10k",
                    "footprint": "Resistor_SMD:R_0805",
                },
            ],
            "nets": [
                {
                    "name": "SIG",
                    "endpoints": [
                        {"reference": "U1", "pin": "2"},
                        {"reference": "R1", "pin": "1"},
                    ],
                },
                {"name": "GND", "endpoints": [{"reference": "U1", "pin": "1"}]},
            ],
        },
    )

    schematic = (sample_project / "demo.kicad_sch").read_text(encoding="utf-8")
    assert "Applied netlist-aware auto-layout" in result
    assert '(symbol "BaseTimer"' in schematic
    assert '(symbol "Extended:ChildTimer"' in schematic
    assert '(lib_id "power:GND")' in schematic
    assert schematic.count("(wire") >= 2


@pytest.mark.anyio
async def test_build_circuit_netlist_auto_layout_uses_symbol_unit_for_routing(
    sample_project,
    mock_kicad,
) -> None:
    server = build_server("schematic")

    result = await call_tool_text(
        server,
        "sch_build_circuit",
        {
            "auto_layout": True,
            "symbols": [
                {
                    "library": "MultiUnit",
                    "symbol_name": "DualChild",
                    "reference": "U1",
                    "value": "Dual",
                    "footprint": "Package_DIP:DIP-8_W7.62mm",
                    "unit": 2,
                },
                {
                    "library": "Device",
                    "symbol_name": "R",
                    "reference": "R1",
                    "value": "10k",
                    "footprint": "Resistor_SMD:R_0805",
                },
            ],
            "nets": [
                {
                    "name": "OUT2",
                    "endpoints": [
                        {"reference": "U1", "pin": "7"},
                        {"reference": "R1", "pin": "1"},
                    ],
                },
                {
                    "name": "FB2",
                    "endpoints": [
                        {"reference": "U1", "pin": "6"},
                        {"reference": "R1", "pin": "2"},
                    ],
                },
            ],
        },
    )

    schematic = (sample_project / "demo.kicad_sch").read_text(encoding="utf-8")
    assert "Applied netlist-aware auto-layout" in result
    assert '(symbol "DualOpamp"' in schematic
    assert '(symbol "MultiUnit:DualChild"' in schematic
    assert '(label "OUT2"' in schematic
    assert '(label "FB2"' in schematic
    assert schematic.count("(wire") >= 3


@pytest.mark.anyio
async def test_build_circuit_netlist_auto_layout_resolves_pin_names_and_aliases(
    sample_project,
    mock_kicad,
) -> None:
    server = build_server("schematic")

    result = await call_tool_text(
        server,
        "sch_build_circuit",
        {
            "auto_layout": True,
            "symbols": [
                {
                    "library": "MultiUnit",
                    "symbol_name": "DualChild",
                    "reference": "U1",
                    "value": "Dual",
                    "footprint": "Package_DIP:DIP-8_W7.62mm",
                    "unit": 1,
                },
                {
                    "library": "Device",
                    "symbol_name": "R",
                    "reference": "R1",
                    "value": "10k",
                    "footprint": "Resistor_SMD:R_0805",
                },
            ],
            "nets": [
                {
                    "name": "OUT_ALIAS",
                    "endpoints": [
                        {"reference": "U1", "pin_name": "OUTA"},
                        {"reference": "R1", "pin": "1"},
                    ],
                },
                {
                    "name": "INPUT_ALIAS",
                    "endpoints": [
                        {"reference": "U1", "pin": "+A"},
                        {"reference": "R1", "pin": "2"},
                    ],
                },
            ],
        },
    )

    schematic = (sample_project / "demo.kicad_sch").read_text(encoding="utf-8")
    assert "Applied netlist-aware auto-layout" in result
    assert '(label "OUT_ALIAS"' in schematic
    assert '(label "INPUT_ALIAS"' in schematic
    assert schematic.count("(wire") >= 3


@pytest.mark.anyio
async def test_library_assign_footprint_updates_schematic(sample_project, mock_kicad) -> None:
    server = build_server("schematic")
    await server.call_tool(
        "sch_add_symbol",
        {
            "library": "Device",
            "symbol_name": "R",
            "x_mm": 10.0,
            "y_mm": 10.0,
            "reference": "R1",
            "value": "10k",
            "footprint": "",
            "rotation": 0,
        },
    )
    text = await call_tool_text(
        server,
        "lib_assign_footprint",
        {"reference": "R1", "library": "Resistor_SMD", "footprint": "R_0805"},
    )
    assert "Assigned footprint" in text


@pytest.mark.anyio
async def test_schematic_update_property_escapes_quotes(sample_project, mock_kicad) -> None:
    server = build_server("schematic")
    await server.call_tool(
        "sch_add_symbol",
        {
            "library": "Device",
            "symbol_name": "R",
            "x_mm": 10.0,
            "y_mm": 10.0,
            "reference": "R1",
            "value": "10k",
            "footprint": "",
            "rotation": 0,
        },
    )

    text = await call_tool_text(
        server,
        "sch_update_properties",
        {"reference": "R1", "field": "Value", "value": '10k "1%"'},
    )

    schematic = (sample_project / "demo.kicad_sch").read_text(encoding="utf-8")
    assert "Updated R1.Value" in text
    assert '(property "Value" "10k \\"1%\\""' in schematic


@pytest.mark.anyio
async def test_schematic_update_properties_preserves_user_paper_and_updates_all_units(
    sample_project,
    mock_kicad,
) -> None:
    _ = mock_kicad
    (sample_project / "demo.kicad_sch").write_text(
        (
            "(kicad_sch\n"
            "\t(version 20250316)\n"
            '\t(generator "pytest")\n'
            '\t(uuid "00000000-0000-0000-0000-000000000000")\n'
            '\t(paper "User" 298.45 217.3224)\n'
            "\t(lib_symbols)\n"
            '\t(symbol (lib_id "Amplifier:SSI2164") (at 88.9 142.24 0) (unit 1)\n'
            '\t\t(property "Reference" "IC5" (at 88.9 144.78 0))\n'
            '\t\t(property "Value" "V2164SZ" (at 88.9 139.7 0))\n'
            '\t\t(property "Footprint" "Package_SO:SOIC-16" (at 88.9 137.16 0))\n'
            "\t)\n"
            '\t(symbol (lib_id "Amplifier:SSI2164") (at 124.46 81.28 0) (unit 4)\n'
            '\t\t(property "Reference" "IC5" (at 124.46 83.82 0))\n'
            '\t\t(property "Value" "V2164SZ" (at 124.46 78.74 0))\n'
            '\t\t(property "Footprint" "Package_SO:SOIC-16" (at 124.46 76.2 0))\n'
            "\t)\n"
            "\t(sheet_instances\n"
            '\t\t(path "/" (page "1"))\n'
            "\t)\n"
            "\t(embedded_fonts no)\n"
            ")\n"
        ),
        encoding="utf-8",
    )

    server = build_server("schematic")
    text = await call_tool_text(
        server,
        "sch_update_properties",
        {"reference": "IC5", "field": "Value", "value": "SSI2164"},
    )

    schematic = (sample_project / "demo.kicad_sch").read_text(encoding="utf-8")
    assert "Updated IC5.Value on 2 instance(s)." in text
    assert '(paper "User" 298.45 217.3224)' in schematic
    assert schematic.count('(property "Value" "SSI2164"') == 2
    assert "V2164SZ" not in schematic


@pytest.mark.anyio
async def test_schematic_pin_positions_parse_imported_pin_blocks(
    sample_project,
    mock_kicad,
) -> None:
    _ = sample_project, mock_kicad
    symbol_dir = get_config().symbol_library_dir
    assert symbol_dir is not None
    (symbol_dir / "Connector_Audio.kicad_sym").write_text(
        (
            "(kicad_symbol_lib (version 20250316) (generator pytest)\n"
            '  (symbol "PJ301_THONKICONNTME"\n'
            '    (property "Reference" "J" (id 0) (at 0 5.08 0))\n'
            '    (property "Value" "PJ301_THONKICONNTME" (id 1) (at 0 -5.08 0))\n'
            "    (pin passive line (at -2.54 0 0) (length 2.54)\n"
            '      (number "1") (name "SLEEVE"))\n'
            "    (pin passive line (at 0 2.54 270) (length 2.54)\n"
            '      (number "2") (name "SWITCH"))\n'
            "    (pin passive line (at 2.54 0 180) (length 2.54)\n"
            '      (number "3") (name "TIP"))\n'
            "  )\n"
            ")\n"
        ),
        encoding="utf-8",
    )

    server = build_server("schematic")
    text = await call_tool_text(
        server,
        "sch_get_pin_positions",
        {
            "library": "Connector_Audio",
            "symbol_name": "PJ301_THONKICONNTME",
            "x_mm": 10.0,
            "y_mm": 20.0,
        },
    )

    assert "Connector_Audio:PJ301_THONKICONNTME @ (10.0, 20.0)" in text
    assert "- Pin 1:" in text
    assert "- Pin 2:" in text
    assert "- Pin 3:" in text


@pytest.mark.anyio
async def test_analyze_net_compilation_reports_pin_alias_matches(
    sample_project,
    mock_kicad,
) -> None:
    server = build_server("schematic")

    result = await call_tool_text(
        server,
        "sch_analyze_net_compilation",
        {
            "auto_layout": True,
            "symbols": [
                {
                    "library": "MultiUnit",
                    "symbol_name": "DualChild",
                    "reference": "U1",
                    "value": "Dual",
                    "footprint": "Package_DIP:DIP-8_W7.62mm",
                    "unit": 1,
                },
                {
                    "library": "Device",
                    "symbol_name": "R",
                    "reference": "R1",
                    "value": "10k",
                    "footprint": "Resistor_SMD:R_0805",
                },
            ],
            "nets": [
                {
                    "name": "ALIAS_NET",
                    "endpoints": [
                        {"reference": "U1", "pin": "OUTA"},
                        {"reference": "R1", "pin": "1"},
                    ],
                }
            ],
        },
    )

    assert "- Pin alias matches: 1" in result
    assert "- Unresolved nets: 0" in result


@pytest.mark.anyio
async def test_schematic_create_and_inspect_child_sheets(sample_project, mock_kicad) -> None:
    server = build_server("schematic")

    result = await call_tool_text(
        server,
        "sch_create_sheet",
        {"name": "Power", "filename": "power.kicad_sch", "x_mm": 40.64, "y_mm": 50.8},
    )

    assert "Created child sheet 'Power'" in result
    assert (sample_project / "power.kicad_sch").exists()

    listing = await call_tool_text(server, "sch_list_sheets", {})
    assert "Power -> power.kicad_sch" in listing
    assert "size=(30.48, 20.32)" in listing

    info = await call_tool_text(server, "sch_get_sheet_info", {"sheet_name": "Power"})
    assert "Sheet 'Power'" in info
    assert "- File: power.kicad_sch" in info
    assert "- Page: 2" in info


@pytest.mark.anyio
async def test_schematic_global_and_hierarchical_labels_preserve_shape(
    sample_project,
    mock_kicad,
) -> None:
    server = build_server("schematic")

    await call_tool_text(
        server,
        "sch_add_global_label",
        {"text": "VCC", "x_mm": 25.4, "y_mm": 25.4, "shape": "output"},
    )
    await call_tool_text(
        server,
        "sch_add_hierarchical_label",
        {"text": "SIG", "x_mm": 30.48, "y_mm": 30.48, "shape": "bidirectional"},
    )

    schematic = (sample_project / "demo.kicad_sch").read_text(encoding="utf-8")
    assert '(global_label "VCC"' in schematic
    assert "\t\t(shape output)\n" in schematic
    assert '(hierarchical_label "SIG"' in schematic
    assert "\t\t(shape bidirectional)\n" in schematic


@pytest.mark.anyio
async def test_schematic_route_wire_between_pins_updates_connectivity_graph(
    sample_project,
    mock_kicad,
) -> None:
    server = build_server("schematic")

    await call_tool_text(
        server,
        "sch_build_circuit",
        {
            "symbols": [
                {
                    "library": "Device",
                    "symbol_name": "R",
                    "x_mm": 10.16,
                    "y_mm": 10.16,
                    "reference": "R1",
                    "value": "10k",
                    "footprint": "Resistor_SMD:R_0805",
                },
                {
                    "library": "Device",
                    "symbol_name": "R",
                    "x_mm": 20.32,
                    "y_mm": 10.16,
                    "reference": "R2",
                    "value": "22k",
                    "footprint": "Resistor_SMD:R_0805",
                },
            ],
        },
    )

    route_text = await call_tool_text(
        server,
        "sch_route_wire_between_pins",
        {"ref1": "R1", "pin1": "2", "ref2": "R2", "pin2": "1"},
    )
    await call_tool_text(
        server,
        "sch_add_label",
        {"name": "MID", "x_mm": 12.7, "y_mm": 10.16, "rotation": 0},
    )

    graph = await call_tool_text(server, "sch_get_connectivity_graph", {})
    schematic = (sample_project / "demo.kicad_sch").read_text(encoding="utf-8")

    assert "Routed 1 wire segment" in route_text
    assert "(pts (xy 12.7 10.16) (xy 17.78 10.16))" in schematic
    assert "MID" in graph
    assert "R1:2" in graph
    assert "R2:1" in graph


@pytest.mark.anyio
async def test_schematic_trace_net_reports_child_sheet_matches(sample_project, mock_kicad) -> None:
    server = build_server("schematic")

    await call_tool_text(
        server,
        "sch_create_sheet",
        {"name": "Power", "filename": "power.kicad_sch", "x_mm": 40.64, "y_mm": 50.8},
    )
    await call_tool_text(
        server,
        "sch_create_sheet",
        {"name": "Control", "filename": "control.kicad_sch", "x_mm": 81.28, "y_mm": 50.8},
    )
    await call_tool_text(
        server,
        "sch_add_global_label",
        {"text": "VIN", "x_mm": 20.32, "y_mm": 20.32, "shape": "input"},
    )

    child_template = (
        "(kicad_sch\n"
        "\t(version 20250316)\n"
        '\t(generator "pytest")\n'
        '\t(uuid "11111111-1111-1111-1111-111111111111")\n'
        '\t(paper "A4")\n'
        "\t(lib_symbols)\n"
        '\t(hierarchical_label "VIN"\n'
        "\t\t(shape input)\n"
        "\t\t(at 10.16 10.16 0)\n"
        "\t\t(effects (font (size 1.27 1.27)))\n"
        '\t\t(uuid "22222222-2222-2222-2222-222222222222")\n'
        "\t)\n"
        "\t(sheet_instances\n"
        '\t\t(path "/" (page "1"))\n'
        "\t)\n"
        "\t(embedded_fonts no)\n"
        ")\n"
    )
    (sample_project / "power.kicad_sch").write_text(child_template, encoding="utf-8")
    (sample_project / "control.kicad_sch").write_text(child_template, encoding="utf-8")

    trace = await call_tool_text(server, "sch_trace_net", {"net_name": "VIN"})

    assert "Trace for net 'VIN':" in trace
    assert "Top level match" in trace
    assert "Child sheet matches:" in trace
    assert "Power" in trace
    assert "Control" in trace


@pytest.mark.anyio
async def test_schematic_auto_place_symbols_repositions_requested_references(
    sample_project,
    mock_kicad,
) -> None:
    server = build_server("schematic")

    await call_tool_text(
        server,
        "sch_build_circuit",
        {
            "symbols": [
                {
                    "library": "Device",
                    "symbol_name": "R",
                    "x_mm": 10.16,
                    "y_mm": 10.16,
                    "reference": "R1",
                    "value": "10k",
                    "footprint": "Resistor_SMD:R_0805",
                },
                {
                    "library": "Device",
                    "symbol_name": "R",
                    "x_mm": 10.16,
                    "y_mm": 20.32,
                    "reference": "R2",
                    "value": "22k",
                    "footprint": "Resistor_SMD:R_0805",
                },
            ],
        },
    )

    result = await call_tool_text(
        server,
        "sch_auto_place_symbols",
        {"symbol_list": ["R1", "R2"], "strategy": "linear"},
    )
    symbols = await call_tool_text(server, "sch_get_symbols", {})

    assert "Auto-placed 2 symbol(s) using the linear strategy." in result
    assert "R1 10k Device:R @ (50.80, 50.80)" in symbols
    assert "R2 22k Device:R @ (76.20, 50.80)" in symbols


@pytest.mark.anyio
async def test_schematic_move_symbol_updates_symbol_anchor(sample_project, mock_kicad) -> None:
    server = build_server("schematic")

    await call_tool_text(
        server,
        "sch_build_circuit",
        {
            "symbols": [
                {
                    "library": "Device",
                    "symbol_name": "R",
                    "x_mm": 10.16,
                    "y_mm": 10.16,
                    "reference": "R1",
                    "value": "10k",
                    "footprint": "Resistor_SMD:R_0805",
                }
            ]
        },
    )

    result = await call_tool_text(
        server,
        "sch_move_symbol",
        {"reference": "R1", "x_mm": 25.4, "y_mm": 30.48},
    )
    symbols = await call_tool_text(server, "sch_get_symbols", {})
    schematic = (sample_project / "demo.kicad_sch").read_text(encoding="utf-8")

    assert "Moved symbol 'R1' to (25.40, 30.48) mm." in result
    assert "R1 10k Device:R @ (25.40, 30.48)" in symbols
    assert "(at 25.4 30.48 0)" in schematic


@pytest.mark.anyio
async def test_schematic_delete_wire_uses_wire_uuid_surface(sample_project, mock_kicad) -> None:
    server = build_server("schematic")

    await call_tool_text(
        server,
        "sch_build_circuit",
        {
            "symbols": [
                {
                    "library": "Device",
                    "symbol_name": "R",
                    "x_mm": 10.16,
                    "y_mm": 10.16,
                    "reference": "R1",
                    "value": "10k",
                    "footprint": "Resistor_SMD:R_0805",
                },
                {
                    "library": "Device",
                    "symbol_name": "R",
                    "x_mm": 20.32,
                    "y_mm": 10.16,
                    "reference": "R2",
                    "value": "22k",
                    "footprint": "Resistor_SMD:R_0805",
                },
            ]
        },
    )
    await call_tool_text(
        server,
        "sch_route_wire_between_pins",
        {"ref1": "R1", "pin1": "2", "ref2": "R2", "pin2": "1"},
    )

    wires = await call_tool_text(server, "sch_get_wires", {})
    match = re.search(r"- ([0-9a-f-]{36}) \(", wires, flags=re.IGNORECASE)
    assert match is not None
    wire_id = match.group(1)

    result = await call_tool_text(server, "sch_delete_wire", {"wire_id": wire_id[:8]})
    wires_after = await call_tool_text(server, "sch_get_wires", {})
    schematic = (sample_project / "demo.kicad_sch").read_text(encoding="utf-8")

    assert f"Deleted wire '{wire_id}'" in result
    assert "contains no wires" in wires_after
    assert "(wire" not in schematic


@pytest.mark.anyio
async def test_schematic_delete_symbol_removes_attached_wires(sample_project, mock_kicad) -> None:
    server = build_server("schematic")

    await call_tool_text(
        server,
        "sch_build_circuit",
        {
            "symbols": [
                {
                    "library": "Device",
                    "symbol_name": "R",
                    "x_mm": 10.16,
                    "y_mm": 10.16,
                    "reference": "R1",
                    "value": "10k",
                    "footprint": "Resistor_SMD:R_0805",
                },
                {
                    "library": "Device",
                    "symbol_name": "R",
                    "x_mm": 20.32,
                    "y_mm": 10.16,
                    "reference": "R2",
                    "value": "22k",
                    "footprint": "Resistor_SMD:R_0805",
                },
            ]
        },
    )
    await call_tool_text(
        server,
        "sch_route_wire_between_pins",
        {"ref1": "R1", "pin1": "2", "ref2": "R2", "pin2": "1"},
    )

    result = await call_tool_text(server, "sch_delete_symbol", {"reference": "R1"})
    symbols = await call_tool_text(server, "sch_get_symbols", {})
    wires = await call_tool_text(server, "sch_get_wires", {})

    assert "Deleted 1 symbol block(s) for 'R1' and 1 directly connected wire(s)." in result
    assert "R1" not in symbols
    assert "R2" in symbols
    assert "contains no wires" in wires


@pytest.mark.anyio
async def test_schematic_template_surface_includes_benchmark_templates(
    sample_project,
    mock_kicad,
) -> None:
    server = build_server("schematic")

    listing = await call_tool_text(server, "sch_list_templates", {})
    info = await call_tool_text(
        server,
        "sch_get_template_info",
        {"template_name": "supercap_backup"},
    )
    plan = await call_tool_text(
        server,
        "sch_instantiate_template",
        {
            "template_name": "buzzer_nmos_driver",
            "prefix": "AUD_",
            "params": {"supply_v": 5.0},
        },
    )

    assert "buzzer_nmos_driver" in listing
    assert "supercap_backup" in listing
    assert "hold_up_ms" in info
    assert "AUD_BZ1" in plan
    assert "lib_bind_part_to_symbol" in plan


@pytest.mark.anyio
async def test_schematic_template_info_lists_declared_pins(
    sample_project,
    mock_kicad,
) -> None:
    server = build_server("schematic")
    templates_dir = Path("src/kicad_mcp/templates/subcircuits")

    for template_path in sorted(templates_dir.glob("*.yaml")):
        data = yaml.safe_load(template_path.read_text(encoding="utf-8"))
        info = await call_tool_text(
            server,
            "sch_get_template_info",
            {"template_name": template_path.stem},
        )

        for symbol in data.get("symbols", []):
            left_pins = [str(pin) for pin in symbol.get("pins_left", [])]
            right_pins = [str(pin) for pin in symbol.get("pins_right", [])]
            if left_pins:
                assert f"left: {', '.join(left_pins)}" in info
            if right_pins:
                assert f"right: {', '.join(right_pins)}" in info


@pytest.mark.anyio
async def test_schematic_bounding_boxes_include_long_pin_positions(
    sample_project,
    mock_kicad,
) -> None:
    symbols_dir = sample_project.parent / "symbols"
    (symbols_dir / "LongPins.kicad_sym").write_text(
        (
            "(kicad_symbol_lib (version 20250316) (generator pytest)\n"
            '  (symbol "LongPin"\n'
            '    (property "Reference" "J" (id 0) (at 0 5.08 0))\n'
            '    (property "Value" "LongPin" (id 1) (at 0 -5.08 0))\n'
            '    (pin passive line (at -25.4 0 0) (length 2.54) (name "1") (number "1"))\n'
            '    (pin passive line (at 25.4 0 180) (length 2.54) (name "2") (number "2"))\n'
            "  )\n"
            ")\n"
        ),
        encoding="utf-8",
    )

    server = build_server("schematic")
    await call_tool_text(
        server,
        "sch_add_symbol",
        {
            "library": "LongPins",
            "symbol_name": "LongPin",
            "x_mm": 50.8,
            "y_mm": 50.8,
            "reference": "J1",
            "value": "LongPin",
            "footprint": "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical",
        },
    )

    boxes = await call_tool_text(server, "sch_get_bounding_boxes", {})
    assert "J1" in boxes
    assert "25.40" in boxes
    assert "76.20" in boxes


@pytest.mark.anyio
async def test_schematic_find_free_placement_respects_keepout_regions(
    sample_project,
    mock_kicad,
) -> None:
    server = build_server("schematic")

    text = await call_tool_text(
        server,
        "sch_find_free_placement",
        {"keepout_regions": [[45.0, 45.0, 55.0, 55.0]]},
    )

    assert "1 keepout region(s) respected" in text
    assert "x_mm=50.8" not in text
    assert "x_mm=101.6" in text


def _symbol_positions(project_dir: Path) -> dict[str, tuple[float, float]]:
    schematic = parse_schematic_file(project_dir / "demo.kicad_sch")
    return {
        str(symbol["reference"]): (
            float(symbol.get("x", symbol.get("x_mm", 0.0)) or 0.0),
            float(symbol.get("y", symbol.get("y_mm", 0.0)) or 0.0),
        )
        for symbol in schematic["symbols"]
    }


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("anchor_ref", "anchored_refs"),
    [
        (None, []),
        ("U1", ["U1"]),
        (["U1", "J1"], ["U1", "J1"]),
    ],
)
async def test_schematic_auto_place_functional_honors_anchor_refs(
    sample_project,
    mock_kicad,
    anchor_ref,
    anchored_refs,
) -> None:
    symbols_dir = sample_project.parent / "symbols"
    (symbols_dir / "STM32.kicad_sym").write_text(
        (symbols_dir / "Device.kicad_sym").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    server = build_server("full")
    await call_tool_text(
        server,
        "sch_build_circuit",
        {
            "symbols": [
                {
                    "library": "Device",
                    "symbol_name": "R",
                    "x_mm": 20.0,
                    "y_mm": 20.0,
                    "reference": "J1",
                    "value": "Conn",
                    "footprint": "Resistor_SMD:R_0805",
                },
                {
                    "library": "STM32",
                    "symbol_name": "R",
                    "x_mm": 160.0,
                    "y_mm": 160.0,
                    "reference": "U1",
                    "value": "MCU",
                    "footprint": "Resistor_SMD:R_0805",
                },
                {
                    "library": "Device",
                    "symbol_name": "R",
                    "x_mm": 220.0,
                    "y_mm": 160.0,
                    "reference": "LED1",
                    "value": "STATUS",
                    "footprint": "Resistor_SMD:R_0805",
                },
            ],
            "wires": [],
            "labels": [],
            "power_symbols": [],
        },
    )

    before = _symbol_positions(sample_project)
    arguments = {} if anchor_ref is None else {"anchor_ref": anchor_ref}
    result = await call_tool_text(server, "sch_auto_place_functional", arguments)
    after = _symbol_positions(sample_project)

    for reference in anchored_refs:
        assert after[reference] == before[reference]
    if anchored_refs:
        assert f"Anchored refs preserved: {', '.join(anchored_refs)}." in result
    else:
        assert any(after[reference] != before[reference] for reference in ("J1", "U1", "LED1"))

    for reference in {"J1", "U1", "LED1"} - set(anchored_refs):
        assert after[reference] != before[reference]


@pytest.mark.anyio
async def test_schematic_auto_place_functional_applies_design_intent_spacing(
    sample_project,
    mock_kicad,
) -> None:
    symbols_dir = sample_project.parent / "symbols"
    (symbols_dir / "STM32.kicad_sym").write_text(
        (symbols_dir / "Device.kicad_sym").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    server = build_server("full")
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
                    "reference": "J1",
                    "value": "Conn",
                    "footprint": "Resistor_SMD:R_0805",
                },
                {
                    "library": "STM32",
                    "symbol_name": "R",
                    "x_mm": 12.0,
                    "y_mm": 12.0,
                    "reference": "U1",
                    "value": "MCU",
                    "footprint": "Resistor_SMD:R_0805",
                },
                {
                    "library": "Device",
                    "symbol_name": "R",
                    "x_mm": 14.0,
                    "y_mm": 14.0,
                    "reference": "LED1",
                    "value": "STATUS",
                    "footprint": "Resistor_SMD:R_0805",
                },
            ],
            "wires": [],
            "labels": [],
            "power_symbols": [],
        },
    )
    await call_tool_text(
        server,
        "project_set_design_intent",
        {"functional_spacing_mm": 60.0},
    )
    await call_tool_text(server, "sch_set_sheet_size", {"paper": "A3"})

    result = await call_tool_text(server, "sch_auto_place_functional", {})
    positions = _symbol_positions(sample_project)

    assert "Functional spacing target: 60.00 mm." in result
    assert positions["U1"][0] - positions["J1"][0] >= 100.0
    assert positions["LED1"][0] > positions["U1"][0]


# ── sch_build_circuit ──────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_build_circuit_empty(sample_project, mock_kicad) -> None:
    """sch_build_circuit with all empty lists must not raise."""
    server = build_server("schematic")
    text = await call_tool_text(
        server,
        "sch_build_circuit",
        {"symbols": [], "wires": [], "labels": [], "power_symbols": []},
    )
    # Any success response is acceptable
    assert text is not None


@pytest.mark.anyio
async def test_build_circuit_symbol_missing_fields_raises(sample_project, mock_kicad) -> None:
    """sch_build_circuit raises a clear ValidationError when required symbol fields are absent."""
    server = build_server("schematic")
    error_text = await call_tool_text(
        server,
        "sch_build_circuit",
        {
            "symbols": [{}],  # all required fields missing
            "wires": [],
            "labels": [],
            "power_symbols": [],
        },
    )
    # The error must mention the missing field names — not a bare KeyError
    assert "library" in error_text or "symbol_name" in error_text


@pytest.mark.anyio
async def test_build_circuit_wire_missing_fields_raises(sample_project, mock_kicad) -> None:
    """Wire dicts without required coords raise a clear ValidationError."""
    server = build_server("schematic")
    error_text = await call_tool_text(
        server,
        "sch_build_circuit",
        {"symbols": [], "wires": [{}], "labels": [], "power_symbols": []},
    )
    assert any(field in error_text for field in ("x1_mm", "y1_mm", "x2_mm", "y2_mm"))


@pytest.mark.anyio
async def test_build_circuit_label_missing_fields_raises(sample_project, mock_kicad) -> None:
    """Label dicts without required fields raise a clear ValidationError."""
    server = build_server("schematic")
    error_text = await call_tool_text(
        server,
        "sch_build_circuit",
        {"symbols": [], "wires": [], "labels": [{}], "power_symbols": []},
    )
    assert any(field in error_text for field in ("name", "x_mm", "y_mm"))


@pytest.mark.anyio
async def test_build_circuit_power_symbol_missing_fields_raises(sample_project, mock_kicad) -> None:
    """Power symbol dicts without required fields raise a clear ValidationError."""
    server = build_server("schematic")
    error_text = await call_tool_text(
        server,
        "sch_build_circuit",
        {"symbols": [], "wires": [], "labels": [], "power_symbols": [{}]},
    )
    assert any(field in error_text for field in ("name", "x", "y"))


@pytest.mark.anyio
async def test_build_circuit_full_resistor(sample_project, mock_kicad) -> None:
    """sch_build_circuit places a resistor with a wire and a label end-to-end."""
    server = build_server("schematic")
    text = await call_tool_text(
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
                    "rotation": 0,
                }
            ],
            "wires": [{"x1_mm": 7.46, "y1_mm": 10.0, "x2_mm": 5.0, "y2_mm": 10.0}],
            "labels": [{"name": "NET_A", "x_mm": 5.0, "y_mm": 10.0, "rotation": 0}],
            "power_symbols": [],
        },
    )
    # Success or KiCad-not-connected message — either is acceptable in CI
    assert text is not None

    # Verify schematic file was written with the expected content
    import os
    from pathlib import Path

    sch_file = next(Path(os.environ["KICAD_MCP_PROJECT_DIR"]).glob("*.kicad_sch"))
    content = sch_file.read_text(encoding="utf-8")
    assert "Device:R" in content
    assert "R1" in content
    assert "NET_A" in content
