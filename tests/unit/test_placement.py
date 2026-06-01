from __future__ import annotations

from kicad_mcp.tools.pcb import _placement_net_weight, _placement_nets_from_footprints
from kicad_mcp.utils.placement import (
    BGABall,
    ForceDirectedConfig,
    PlacementComponent,
    PlacementNet,
    _centroid,
    _snap,
    force_directed_placement,
    generate_bga_fanout_plan,
)


def test_force_directed_placement_is_deterministic_and_snaps_to_grid() -> None:
    components = [
        PlacementComponent(ref="J1", x=2.0, y=2.0, w=3.0, h=3.0),
        PlacementComponent(ref="U1", x=18.0, y=8.0, w=4.0, h=4.0),
        PlacementComponent(ref="U2", x=32.0, y=18.0, w=4.0, h=4.0),
    ]
    nets = [PlacementNet(name="USB_DP", refs=["J1", "U1", "U2"], weight=1.0)]
    cfg = ForceDirectedConfig(
        iterations=80,
        board_w=40.0,
        board_h=25.0,
        grid_mm=1.0,
        seed=7,
    )

    first = force_directed_placement(components, nets, cfg)
    second = force_directed_placement(components, nets, cfg)

    assert [(item.ref, item.x, item.y) for item in first] == [
        (item.ref, item.x, item.y) for item in second
    ]
    assert all(item.x == round(item.x) for item in first)
    assert all(item.y == round(item.y) for item in first)


def test_force_directed_placement_respects_keepout_regions() -> None:
    components = [PlacementComponent(ref="U1", x=15.0, y=10.0, w=4.0, h=4.0)]
    cfg = ForceDirectedConfig(
        iterations=20,
        board_w=30.0,
        board_h=20.0,
        grid_mm=0.5,
        keepout_regions=[(12.0, 8.0, 18.0, 12.0)],
    )

    placed = force_directed_placement(components, [], cfg)[0]

    assert 0.0 <= placed.x - 2.0
    assert placed.x + 2.0 <= 30.0
    assert 0.0 <= placed.y - 2.0
    assert placed.y + 2.0 <= 20.0
    assert (
        placed.x + 2.0 <= 12.0
        or placed.x - 2.0 >= 18.0
        or placed.y + 2.0 <= 8.0
        or placed.y - 2.0 >= 12.0
    )


def test_board_placement_net_weights_prioritize_power_and_differential_pairs() -> None:
    assert _placement_net_weight("GND") == 3.0
    assert _placement_net_weight("+3V3") == 3.0
    assert _placement_net_weight("USB_DP_P") == 5.0
    assert _placement_net_weight("VIN") == 1.0
    assert _placement_net_weight("NC") == 0.0


def test_board_placement_nets_skip_single_footprint_nets() -> None:
    nets = _placement_nets_from_footprints(
        {
            "U1": {"pad_nets": {"1": "+3V3", "2": "USB_DP_P"}},
            "C1": {"pad_nets": {"1": "+3V3"}},
            "J1": {"pad_nets": {"1": "USB_DP_P", "2": "VIN"}},
        }
    )

    assert [(net.name, net.refs, net.weight) for net in nets] == [
        ("+3V3", ["C1", "U1"], 3.0),
        ("USB_DP_P", ["J1", "U1"], 5.0),
    ]


def test_placement_geometry_helpers_and_bga_fanout_strategies() -> None:
    components = [
        PlacementComponent(ref="U1", x=10.0, y=20.0),
        PlacementComponent(ref="U2", x=20.0, y=40.0),
    ]
    center = _centroid(components, ["U1", "U2"])
    missing_center = _centroid(components, ["J404"])
    balls = [
        BGABall(row="A", col=1, net="D0", x_mm=0.0, y_mm=0.0),
        BGABall(row="B", col=2, net="D1", x_mm=0.8, y_mm=0.8),
    ]

    dog_ear = generate_bga_fanout_plan(balls, pitch_mm=0.5, strategy="dog_ear")
    inline = generate_bga_fanout_plan(balls, pitch_mm=0.8, strategy="inline")

    assert center.x == 15.0
    assert center.y == 30.0
    assert missing_center.x == 0.0
    assert _snap(1.26, 0.5) == 1.5
    assert _snap(1.26, 0.0) == 1.26
    assert dog_ear[0]["track_width_mm"] == 0.1
    assert dog_ear[0]["dog_ear_dx"] != 0.0
    assert inline[0]["track_width_mm"] == 0.15
    assert inline[0]["dog_ear_dx"] == 0.0
