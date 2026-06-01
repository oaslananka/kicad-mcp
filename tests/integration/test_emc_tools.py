from __future__ import annotations

from types import SimpleNamespace

import pytest
from kipy.proto.board.board_types_pb2 import BoardLayer

from kicad_mcp.server import build_server
from tests.conftest import call_tool_text


def _field(value: str) -> SimpleNamespace:
    return SimpleNamespace(text=SimpleNamespace(value=value))


def _configure_emc_board(mock_board) -> None:
    usb_dp_main = SimpleNamespace(
        start=SimpleNamespace(x_nm=5_000_000, y_nm=10_000_000),
        end=SimpleNamespace(x_nm=15_000_000, y_nm=10_000_000),
        width=180_000,
        layer=BoardLayer.BL_F_Cu,
        net=SimpleNamespace(name="USB_DP"),
    )
    usb_dp_stub = SimpleNamespace(
        start=SimpleNamespace(x_nm=15_000_000, y_nm=10_000_000),
        end=SimpleNamespace(x_nm=15_400_000, y_nm=10_000_000),
        width=180_000,
        layer=BoardLayer.BL_F_Cu,
        net=SimpleNamespace(name="USB_DP"),
    )
    usb_dn = SimpleNamespace(
        start=SimpleNamespace(x_nm=5_000_000, y_nm=11_000_000),
        end=SimpleNamespace(x_nm=14_900_000, y_nm=11_000_000),
        width=182_000,
        layer=BoardLayer.BL_F_Cu,
        net=SimpleNamespace(name="USB_DN"),
    )
    hs_clk = SimpleNamespace(
        start=SimpleNamespace(x_nm=6_000_000, y_nm=15_000_000),
        end=SimpleNamespace(x_nm=20_000_000, y_nm=15_000_000),
        width=150_000,
        layer=BoardLayer.BL_F_Cu,
        net=SimpleNamespace(name="HS_CLK"),
    )
    gnd_zone_bottom = SimpleNamespace(
        name="GND_BOTTOM",
        net=SimpleNamespace(name="GND"),
        layers=[BoardLayer.BL_B_Cu],
        filled=True,
    )
    gnd_zone_inner = SimpleNamespace(
        name="GND_INNER",
        net=SimpleNamespace(name="GND"),
        layers=[BoardLayer.BL_In1_Cu],
        filled=True,
    )
    power_zone = SimpleNamespace(
        name="3V3_PLANE",
        net=SimpleNamespace(name="3V3"),
        layers=[BoardLayer.BL_In2_Cu],
        filled=True,
    )
    u1 = SimpleNamespace(
        reference_field=_field("U1"),
        value_field=_field("MCU"),
        position=SimpleNamespace(x_nm=10_000_000, y_nm=20_000_000),
    )
    c1 = SimpleNamespace(
        reference_field=_field("C1"),
        value_field=_field("100n"),
        position=SimpleNamespace(x_nm=11_000_000, y_nm=20_000_000),
    )
    gnd_vias = [
        SimpleNamespace(
            position=SimpleNamespace(x_nm=5_000_000, y_nm=5_000_000),
            net=SimpleNamespace(name="GND"),
        ),
        SimpleNamespace(
            position=SimpleNamespace(x_nm=10_000_000, y_nm=5_000_000),
            net=SimpleNamespace(name="GND"),
        ),
        SimpleNamespace(
            position=SimpleNamespace(x_nm=15_000_000, y_nm=5_000_000),
            net=SimpleNamespace(name="GND"),
        ),
        SimpleNamespace(
            position=SimpleNamespace(x_nm=20_000_000, y_nm=5_000_000),
            net=SimpleNamespace(name="GND"),
        ),
    ]
    edge_rect = SimpleNamespace(
        layer=BoardLayer.BL_Edge_Cuts,
        top_left=SimpleNamespace(x_nm=0, y_nm=0),
        bottom_right=SimpleNamespace(x_nm=40_000_000, y_nm=30_000_000),
    )

    mock_board.get_tracks.return_value = [usb_dp_main, usb_dp_stub, usb_dn, hs_clk]
    mock_board.get_zones.return_value = [gnd_zone_bottom, gnd_zone_inner, power_zone]
    mock_board.get_footprints.return_value = [u1, c1]
    mock_board.get_vias.return_value = gnd_vias
    mock_board.get_shapes.return_value = [edge_rect]


@pytest.mark.anyio
async def test_emc_surface(sample_project, mock_board) -> None:
    _configure_emc_board(mock_board)
    server = build_server("full")
    await call_tool_text(server, "kicad_set_project", {"project_dir": str(sample_project)})
    await call_tool_text(
        server,
        "project_set_design_intent",
        {"critical_nets": ["USB_DP", "USB_DN"]},
    )

    ground = await call_tool_text(
        server,
        "emc_check_ground_plane_voids",
        {"max_void_area_mm2": 25.0},
    )
    return_path = await call_tool_text(
        server,
        "emc_check_return_path_continuity",
        {"signal_net": "USB_DP", "reference_plane_layer": "B_Cu"},
    )
    critical_return_path = await call_tool_text(
        server,
        "emc_check_return_path_continuity",
        {"reference_plane_layer": "auto", "search_radius_mm": 2.0},
    )
    split_plane = await call_tool_text(
        server,
        "emc_check_split_plane_crossing",
        {"signal_nets": ["USB_DP", "USB_DN", "HS_CLK"]},
    )
    decoupling = await call_tool_text(
        server,
        "emc_check_decoupling_placement",
        {"max_distance_mm": 3.0},
    )
    stitching = await call_tool_text(
        server,
        "emc_check_via_stitching",
        {"max_gap_mm": 5.0, "ground_net": "GND"},
    )
    diff_pair = await call_tool_text(
        server,
        "emc_check_differential_pair_symmetry",
        {"net_p": "USB_DP", "net_n": "USB_DN", "max_skew_ps": 10.0},
    )
    routing = await call_tool_text(
        server,
        "emc_check_high_speed_routing_rules",
        {"net_class": "USB", "max_stub_length_mm": 1.0},
    )
    full = await call_tool_text(
        server,
        "emc_run_full_compliance",
        {"standard": "FCC"},
    )

    assert "Ground plane void review" in ground
    assert "(PASS)" in ground
    assert "Return path continuity" in return_path
    assert "All 2 checked net(s)" in critical_return_path
    assert "Split-plane crossing review" in split_plane
    assert "Decoupling placement review" in decoupling
    assert "Via stitching review" in stitching
    assert "Differential-pair symmetry" in diff_pair
    assert "High-speed routing rule review" in routing
    assert "EMC compliance sweep (FCC)" in full
    assert "Checks run: 10" in full


@pytest.mark.anyio
async def test_emc_split_ground_names_are_treated_as_ground(sample_project, mock_board) -> None:
    _configure_emc_board(mock_board)
    zones = mock_board.get_zones.return_value
    zones[0].net.name = "GND_DIG"
    zones[1].net.name = "GND_ANA"
    server = build_server("full")
    await call_tool_text(server, "kicad_set_project", {"project_dir": str(sample_project)})

    ground = await call_tool_text(
        server,
        "emc_check_ground_plane_voids",
        {"max_void_area_mm2": 25.0},
    )
    return_path = await call_tool_text(
        server,
        "emc_check_return_path_continuity",
        {"signal_net": "USB_DP", "reference_plane_layer": "B_Cu"},
    )

    assert "(PASS)" in ground
    assert "No GND plane was found" not in return_path
