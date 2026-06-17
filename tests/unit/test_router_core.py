"""Headless Specctra SES -> .kicad_pcb applier (work order P4-T1)."""

from __future__ import annotations

from kicad_mcp.utils.router_core import (
    apply_ses_to_pcb,
    parse_net_numbers,
    parse_ses,
    render_pcb_items,
)

_SES = """(session test.dsn
  (routes
    (resolution um 10)
    (network_out
      (net "GND"
        (wire (path F.Cu 250 100000 50000 110000 50000) (type protect))
        (wire (path B.Cu 250 110000 50000 110000 60000))
        (via "Via[0-1]_600:300_um" 110000 50000)
      )
      (net "VCC"
        (wire (path "F.Cu" 200 200000 200000 250000 200000))
      )
    )
  )
)"""

_PCB = '(kicad_pcb\n\t(version 20250216)\n\t(net 0 "")\n\t(net 1 "GND")\n\t(net 2 "VCC")\n)\n'


def test_parse_ses_scales_and_unflips_coordinates() -> None:
    route = parse_ses(_SES)
    assert route.units_per_mm == 10000.0  # (resolution um 10) -> 10 * 1000
    assert len(route.segments) == 3
    assert len(route.vias) == 1

    gnd_f = next(s for s in route.segments if s.net_name == "GND" and s.layer == "F.Cu")
    # 100000 units / 10000 = 10 mm; Specctra Y is up, KiCad Y is down -> 50000 -> -5 mm.
    assert gnd_f.start == (10.0, -5.0)
    assert gnd_f.end == (11.0, -5.0)
    assert gnd_f.width_mm == 0.025  # 250 units / 10000

    via = route.vias[0]
    assert via.at == (11.0, -5.0)
    # Padstack Via[0-1]_600:300_um -> 0.6 mm size, 0.3 mm drill.
    assert via.size_mm == 0.6
    assert via.drill_mm == 0.3
    assert via.layers == ("F.Cu", "B.Cu")


def test_parse_net_numbers_reads_the_pcb_net_table() -> None:
    assert parse_net_numbers(_PCB) == {"": 0, "GND": 1, "VCC": 2}


def test_apply_ses_is_deterministic_and_round_trip_safe() -> None:
    out_a, route = apply_ses_to_pcb(_PCB, _SES)
    out_b, _ = apply_ses_to_pcb(_PCB, _SES)

    # Byte-identical on re-apply (deterministic UUIDs, sorted, fixed formatting).
    assert out_a == out_b

    # The original document is preserved verbatim; routing is appended inside the block.
    assert "(version 20250216)" in out_a
    assert '(net 1 "GND")' in out_a
    assert out_a.rstrip().endswith(")")

    # Net names are mapped to numbers; GND -> 1, VCC -> 2.
    assert '(layer "F.Cu") (net 1)' in out_a  # GND segment
    assert '(layer "F.Cu") (net 2)' in out_a  # VCC segment
    assert '(via (at 11 -5) (size 0.6) (drill 0.3) (layers "F.Cu" "B.Cu") (net 1)' in out_a
    # Three segments + one via were added.
    assert out_a.count("(segment ") == 3
    assert out_a.count("(via ") == 1


def test_apply_ses_is_idempotent_on_re_application() -> None:
    # Applying the SES to an already-routed board replaces (not duplicates) our items.
    once, _ = apply_ses_to_pcb(_PCB, _SES)
    twice, _ = apply_ses_to_pcb(once, _SES)
    assert once == twice
    assert twice.count("(segment ") == 3
    assert twice.count("(via ") == 1


def test_nets_absent_from_the_pcb_table_are_skipped() -> None:
    # A board that only declares GND drops the VCC routing rather than emitting (net None).
    pcb_gnd_only = '(kicad_pcb\n\t(version 20250216)\n\t(net 1 "GND")\n)\n'
    out, _ = apply_ses_to_pcb(pcb_gnd_only, _SES)
    assert "(net 1)" in out
    assert out.count("(segment ") == 2  # only the two GND segments
    assert "(net 2)" not in out


def test_empty_route_leaves_the_board_unchanged() -> None:
    empty_ses = "(session x.dsn (routes (resolution um 10) (network_out)))"
    out, route = apply_ses_to_pcb(_PCB, empty_ses)
    assert out == _PCB
    assert route.segments == []


def test_render_pcb_items_orders_segments_before_vias_deterministically() -> None:
    route = parse_ses(_SES)
    rendered = render_pcb_items(route, {"GND": 1, "VCC": 2})
    assert rendered.index("(segment ") < rendered.index("(via ")
    # Stable order: same input -> same string.
    assert rendered == render_pcb_items(parse_ses(_SES), {"GND": 1, "VCC": 2})
