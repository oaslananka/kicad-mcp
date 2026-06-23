from kicad_mcp.tools.schematic import _pin_label_stub_direction


def test_single_column_connector_pins_stub_sideways_not_through_pin_stack() -> None:
    all_points = [(10.0, 10.0), (10.0, 12.54), (10.0, 15.08)]

    assert _pin_label_stub_direction((10.0, 10.0), (15.0, 12.54), all_points) == (-1.0, 0.0)
    assert _pin_label_stub_direction((10.0, 15.08), (15.0, 12.54), all_points) == (-1.0, 0.0)


def test_single_row_connector_pins_stub_vertically_not_through_pin_stack() -> None:
    all_points = [(10.0, 10.0), (12.54, 10.0), (15.08, 10.0)]

    assert _pin_label_stub_direction((10.0, 10.0), (12.54, 5.0), all_points) == (0.0, 1.0)
    assert _pin_label_stub_direction((15.08, 10.0), (12.54, 5.0), all_points) == (0.0, 1.0)
