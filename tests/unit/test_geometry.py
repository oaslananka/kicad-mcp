"""Unit tests for the pure-domain schematic geometry model."""

from __future__ import annotations

import math

from kicad_mcp.utils.geometry import (
    DEFAULT_FONT_MM,
    GLYPH_ASPECT,
    Box,
    TextField,
    body_box_from_pins,
    boxes_overlap_pairs,
    distance,
    parse_justify,
    symbol_extent,
    text_extent,
    union,
)


def test_box_basic_properties() -> None:
    box = Box(0.0, 0.0, 4.0, 2.0)
    assert box.width == 4.0
    assert box.height == 2.0
    assert box.center == (2.0, 1.0)
    assert box.area == 8.0
    assert box.contains_point(2.0, 1.0)
    assert not box.contains_point(5.0, 1.0)


def test_box_from_center_roundtrip() -> None:
    box = Box.from_center(10.0, 5.0, 4.0, 2.0)
    assert box == Box(8.0, 4.0, 12.0, 6.0)
    assert box.center == (10.0, 5.0)


def test_box_expanded_grows_all_sides() -> None:
    box = Box(0.0, 0.0, 2.0, 2.0).expanded(1.0)
    assert box == Box(-1.0, -1.0, 3.0, 3.0)


def test_overlap_detection_and_gap() -> None:
    a = Box(0.0, 0.0, 2.0, 2.0)
    b = Box(2.5, 0.0, 4.0, 2.0)
    # 0.5 mm apart: no strict overlap, but a 1 mm clearance makes them collide.
    assert not a.overlaps(b)
    assert a.overlaps(b, gap_mm=1.0)
    assert a.overlaps(Box(1.0, 1.0, 3.0, 3.0))


def test_intersection_area() -> None:
    a = Box(0.0, 0.0, 2.0, 2.0)
    b = Box(1.0, 1.0, 3.0, 3.0)
    assert a.intersection_area(b) == 1.0
    assert a.intersection_area(Box(5.0, 5.0, 6.0, 6.0)) == 0.0


def test_inside_with_margin() -> None:
    container = Box(0.0, 0.0, 100.0, 100.0)
    assert Box(10.0, 10.0, 20.0, 20.0).inside(container)
    assert not Box(10.0, 10.0, 20.0, 20.0).inside(container, margin_mm=15.0)
    assert not Box(-1.0, 10.0, 20.0, 20.0).inside(container)


def test_union_and_empty() -> None:
    assert union([]) is None
    merged = union([Box(0.0, 0.0, 1.0, 1.0), Box(5.0, 5.0, 6.0, 7.0)])
    assert merged == Box(0.0, 0.0, 6.0, 7.0)


def test_text_extent_scales_with_length() -> None:
    assert text_extent("") == (0.0, 0.0)
    w1, h1 = text_extent("R1")
    assert h1 == DEFAULT_FONT_MM
    assert math.isclose(w1, 2 * DEFAULT_FONT_MM * GLYPH_ASPECT)
    w_long, _ = text_extent("STM32F407VGT6")
    assert w_long > w1
    # Bold is wider than normal for the same string.
    assert text_extent("VCC", bold=True)[0] > text_extent("VCC")[0]


def test_text_field_justify_anchoring() -> None:
    centered = TextField("R1", x=10.0, y=5.0).box()
    assert math.isclose(centered.center[0], 10.0)
    left = TextField("R1", x=10.0, y=5.0, justify=parse_justify("left")).box()
    assert math.isclose(left.x_min, 10.0)
    right = TextField("R1", x=10.0, y=5.0, justify=parse_justify("right")).box()
    assert math.isclose(right.x_max, 10.0)


def test_text_field_vertical_rotation_swaps_footprint() -> None:
    horizontal = TextField("LONGNET", x=0.0, y=0.0, angle=0.0).box()
    vertical = TextField("LONGNET", x=0.0, y=0.0, angle=90.0).box()
    assert math.isclose(horizontal.width, vertical.height)
    assert math.isclose(horizontal.height, vertical.width)


def test_parse_justify_filters_tokens() -> None:
    assert parse_justify("left bottom mirror") == frozenset({"left", "bottom"})
    assert parse_justify(None) == frozenset()
    assert parse_justify(["right"]) == frozenset({"right"})


def test_body_box_from_pins_uses_extent() -> None:
    box = body_box_from_pins([(0.0, 0.0), (10.0, 6.0)], pad_mm=1.0)
    assert box == Box(-1.0, -1.0, 11.0, 7.0)


def test_body_box_from_pins_empty_falls_back_to_center() -> None:
    box = body_box_from_pins([], min_half_mm=2.0, center=(50.0, 40.0))
    assert box == Box(48.0, 38.0, 52.0, 42.0)


def test_symbol_extent_includes_text_fields() -> None:
    body = Box(0.0, 0.0, 4.0, 4.0)
    # A reference field placed to the right of the body widens the extent.
    fields = [TextField("R1", x=8.0, y=2.0, justify=parse_justify("left"))]
    extent = symbol_extent(body, fields)
    assert extent.x_max > body.x_max
    assert extent.y_min <= body.y_min or extent.x_min == body.x_min


def test_symbol_extent_ignores_empty_fields() -> None:
    body = Box(0.0, 0.0, 4.0, 4.0)
    assert symbol_extent(body, [TextField("", x=99.0, y=99.0)]) == body


def test_boxes_overlap_pairs_reports_colliding_only() -> None:
    boxes = [
        ("A", Box(0.0, 0.0, 2.0, 2.0)),
        ("B", Box(1.0, 1.0, 3.0, 3.0)),
        ("C", Box(10.0, 10.0, 11.0, 11.0)),
    ]
    pairs = boxes_overlap_pairs(boxes)
    assert len(pairs) == 1
    assert pairs[0][0] == "A"
    assert pairs[0][1] == "B"
    assert pairs[0][2] == 1.0


def test_boxes_overlap_pairs_honours_gap() -> None:
    boxes = [("A", Box(0.0, 0.0, 2.0, 2.0)), ("B", Box(2.5, 0.0, 4.0, 2.0))]
    assert boxes_overlap_pairs(boxes) == []
    assert len(boxes_overlap_pairs(boxes, gap_mm=1.0)) == 1


def test_distance() -> None:
    assert distance((0.0, 0.0), (3.0, 4.0)) == 5.0
