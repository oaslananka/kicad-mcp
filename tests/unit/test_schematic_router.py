from __future__ import annotations

from kicad_mcp.utils.schematic_router import RouterBBox, SchematicRouter


def test_schematic_router_routes_straight_line_without_obstacles() -> None:
    router = SchematicRouter(grid_mm=2.54)

    assert router.route((0.0, 0.0), (7.62, 0.0)) == [(0.0, 0.0, 7.62, 0.0)]


def test_schematic_router_bypasses_obstacle() -> None:
    router = SchematicRouter(
        grid_mm=2.54,
        obstacles=[RouterBBox(2.0, -1.0, 6.0, 1.0)],
        max_steps=300,
    )

    segments = router.route((0.0, 0.0), (10.16, 0.0))

    assert segments is not None
    assert len(segments) >= 3
    assert all(not (2.0 <= x1 <= 6.0 and -1.0 <= y1 <= 1.0) for x1, y1, _, _ in segments)


def test_schematic_router_returns_none_when_bend_budget_is_too_small() -> None:
    router = SchematicRouter(
        grid_mm=2.54,
        obstacles=[RouterBBox(2.0, -1.0, 6.0, 1.0)],
        max_steps=80,
    )

    assert router.route((0.0, 0.0), (10.16, 0.0), max_bends=0) is None
