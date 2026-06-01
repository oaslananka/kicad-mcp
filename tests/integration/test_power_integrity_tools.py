from __future__ import annotations

from types import SimpleNamespace

import pytest
from kipy.proto.board.board_types_pb2 import BoardLayer

from kicad_mcp.server import build_server
from tests.conftest import call_tool_text


def _field(value: str) -> SimpleNamespace:
    return SimpleNamespace(text=SimpleNamespace(value=value))


def _configure_power_board(mock_board) -> None:
    track_3v3 = SimpleNamespace(
        start=SimpleNamespace(x_nm=0, y_nm=0),
        end=SimpleNamespace(x_nm=30_000_000, y_nm=0),
        width=500_000,
        layer=BoardLayer.BL_F_Cu,
        net=SimpleNamespace(name="3V3"),
    )
    u1 = SimpleNamespace(
        reference_field=_field("U1"),
        value_field=_field("MCU"),
        position=SimpleNamespace(x_nm=10_000_000, y_nm=10_000_000),
    )
    u2 = SimpleNamespace(
        reference_field=_field("U2"),
        value_field=_field("SENSOR"),
        position=SimpleNamespace(x_nm=25_000_000, y_nm=10_000_000),
    )
    c1 = SimpleNamespace(
        reference_field=_field("C1"),
        value_field=_field("100n"),
        position=SimpleNamespace(x_nm=11_000_000, y_nm=10_000_000),
    )
    c2 = SimpleNamespace(
        reference_field=_field("C2"),
        value_field=_field("1u"),
        position=SimpleNamespace(x_nm=26_000_000, y_nm=10_000_000),
    )
    edge_rect = SimpleNamespace(
        layer=BoardLayer.BL_Edge_Cuts,
        top_left=SimpleNamespace(x_nm=0, y_nm=0),
        bottom_right=SimpleNamespace(x_nm=40_000_000, y_nm=30_000_000),
    )
    gnd_zone = SimpleNamespace(
        name="GND_PLANE",
        net=SimpleNamespace(name="GND"),
        layers=[BoardLayer.BL_B_Cu],
    )
    stackup = SimpleNamespace(
        layers=[
            SimpleNamespace(layer=BoardLayer.BL_F_Cu, thickness=35_000, material_name="Copper"),
            SimpleNamespace(layer="Core", thickness=1_530_000, material_name="FR4"),
            SimpleNamespace(layer=BoardLayer.BL_B_Cu, thickness=35_000, material_name="Copper"),
        ]
    )

    mock_board.get_tracks.return_value = [track_3v3]
    mock_board.get_footprints.return_value = [u1, u2, c1, c2]
    mock_board.get_shapes.return_value = [edge_rect]
    mock_board.get_zones.return_value = [gnd_zone]
    mock_board.get_stackup.return_value = stackup


@pytest.mark.anyio
async def test_power_integrity_surface(sample_project, mock_board) -> None:
    _configure_power_board(mock_board)
    server = build_server("full")
    await call_tool_text(server, "kicad_set_project", {"project_dir": str(sample_project)})

    drop = await call_tool_text(
        server,
        "pdn_calculate_voltage_drop",
        {
            "current_a": 1.0,
            "trace_width_mm": 0.5,
            "trace_length_mm": 100.0,
            "copper_oz": 1.0,
        },
    )
    decoupling = await call_tool_text(
        server,
        "pdn_recommend_decoupling_caps",
        {
            "ic_refs": ["U1", "U2"],
            "vcc_net": "3V3",
            "supply_voltage_v": 3.3,
            "target_ripple_mv": 20.0,
        },
    )
    copper = await call_tool_text(
        server,
        "pdn_check_copper_weight",
        {
            "net_name": "3V3",
            "expected_current_a": 1.0,
            "ambient_temp_c": 25.0,
            "max_temp_rise_c": 10.0,
        },
    )
    plane = await call_tool_text(
        server,
        "pdn_generate_power_plane",
        {"net_name": "3V3", "layer": "F_Cu", "clearance_mm": 0.5},
    )
    vias = await call_tool_text(
        server,
        "thermal_calculate_via_count",
        {"power_w": 1.5, "via_diameter_mm": 0.3, "thermal_resistance_target": 5.0},
    )
    package_vias = await call_tool_text(
        server,
        "thermal_calculate_via_count",
        {
            "package_power_w": 2.0,
            "ambient_c": 35.0,
            "max_junction_c": 95.0,
            "theta_ja_deg_c_w": 60.0,
            "via_diameter_mm": 0.3,
        },
    )
    thermal = await call_tool_text(
        server,
        "thermal_check_copper_pour",
        {"net_name": "GND", "expected_power_w": 1.0},
    )

    assert "PDN voltage-drop estimate" in drop
    assert "Estimated voltage drop" in drop
    assert "Decoupling recommendation for 3V3" in decoupling
    assert "nearest capacitor is C1" in decoupling
    assert "Copper weight check for 3V3" in copper
    assert "Generated a copper plane for '3V3'" in plane
    assert mock_board.create_items.called
    assert mock_board.refill_zones.called
    assert "Thermal via estimate" in vias
    assert "Required via count" in vias
    assert "Package theta JA: 60.00 C/W" in package_vias
    assert "Required via-network resistance" in package_vias
    assert "Thermal copper-pour review for GND" in thermal


@pytest.mark.anyio
async def test_power_integrity_edge_paths(sample_project, mock_board) -> None:
    mock_board.get_tracks.return_value = []
    mock_board.get_footprints.return_value = []
    mock_board.get_shapes.return_value = []
    mock_board.get_zones.return_value = []
    mock_board.get_stackup.return_value.layers = []
    server = build_server("full")
    await call_tool_text(server, "kicad_set_project", {"project_dir": str(sample_project)})

    missing_tracks = await call_tool_text(
        server,
        "pdn_check_copper_weight",
        {"net_name": "VBUS", "expected_current_a": 2.0},
    )
    no_caps = await call_tool_text(
        server,
        "pdn_recommend_decoupling_caps",
        {"ic_refs": ["U404"], "vcc_net": "3V3", "supply_voltage_v": 3.3},
    )
    unsupported_plane = await call_tool_text(
        server,
        "pdn_generate_power_plane",
        {"net_name": "3V3", "layer": "In1_Cu"},
    )
    no_bounds_plane = await call_tool_text(
        server,
        "pdn_generate_power_plane",
        {"net_name": "3V3", "layer": "F_Cu"},
    )
    thermal = await call_tool_text(
        server,
        "thermal_check_copper_pour",
        {"net_name": "3V3", "expected_power_w": 2.0},
    )
    pdn = await call_tool_text(
        server,
        "check_power_integrity",
        {
            "net_name": "3V3",
            "source_ref": "U_REG",
            "load_refs": ["U1", "U2"],
            "trace_width_mm": 0.1,
            "load_current_a": 1.0,
            "trace_length_mm": 200.0,
        },
    )

    assert "No routed tracks" in missing_tracks
    assert "add one 100 nF local cap" in no_caps
    assert "supports only F_Cu and B_Cu" in unsupported_plane
    assert "Could not determine board bounds" in no_bounds_plane
    assert "No copper pours were found" in thermal
    assert "PDN mesh check" in pdn
    assert "- FAIL:" in pdn
