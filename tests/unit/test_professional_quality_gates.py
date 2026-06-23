from kicad_mcp.tools.validation import (
    _pcb_layer_table_copper_layers,
    _pcb_stackup_copper_layers,
    _pcb_track_segments_from_text,
    _route_90_degree_corners,
)


def test_stackup_consistency_parser_detects_missing_inner_layers() -> None:
    pcb_text = """
(kicad_pcb
  (layers
    (0 "F.Cu" signal)
    (2 "B.Cu" signal)
  )
  (setup
    (stackup
      (layer "F.Cu" (type "signal"))
      (layer "In1.Cu" (type "ground"))
      (layer "In2.Cu" (type "power"))
      (layer "B.Cu" (type "signal"))
    )
  )
)
"""
    assert _pcb_layer_table_copper_layers(pcb_text) == ["F.Cu", "B.Cu"]
    assert _pcb_stackup_copper_layers(pcb_text) == ["F.Cu", "In1.Cu", "In2.Cu", "B.Cu"]


def test_route_corner_style_flags_orthogonal_corner() -> None:
    pcb_text = """
(kicad_pcb
  (segment (start 10 10) (end 20 10) (width 0.2) (layer "F.Cu") (net "USB_D_P"))
  (segment (start 20 10) (end 20 20) (width 0.2) (layer "F.Cu") (net "USB_D_P"))
)
"""
    segments = _pcb_track_segments_from_text(pcb_text)
    corners = _route_90_degree_corners(segments)
    assert corners == ["USB_D_P on F.Cu has a 90° corner at (20.000, 10.000)"]


def test_route_corner_style_ignores_45_degree_chamfer() -> None:
    pcb_text = """
(kicad_pcb
  (segment (start 10 10) (end 18 10) (width 0.2) (layer "F.Cu") (net "USB_D_P"))
  (segment (start 18 10) (end 20 12) (width 0.2) (layer "F.Cu") (net "USB_D_P"))
  (segment (start 20 12) (end 20 20) (width 0.2) (layer "F.Cu") (net "USB_D_P"))
)
"""
    segments = _pcb_track_segments_from_text(pcb_text)
    assert _route_90_degree_corners(segments) == []
