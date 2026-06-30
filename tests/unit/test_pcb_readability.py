"""Unit tests for the headless PCB readability engine."""

from __future__ import annotations

from kicad_mcp.utils.pcb_readability import (
    detect_body_overlap,
    detect_offboard,
    detect_ref_silk_overlap,
    run_pcb_readability,
)


def _footprint(
    ref: str,
    x: float,
    y: float,
    *,
    w: float = 2.0,
    h: float = 1.0,
    rot: float = 0.0,
    ref_at: tuple[float, float] = (0.0, -1.5),
) -> dict[str, object]:
    block = (
        f'(footprint "R_0402" (layer "F.Cu") (at {x} {y} {rot})\n'
        f'  (property "Reference" "{ref}" (at {ref_at[0]} {ref_at[1]} 0)'
        '    (layer "F.SilkS") (effects (font (size 1 1))))\n'
        ")"
    )
    return {
        "name": "R_0402",
        "block": block,
        "value": "10k",
        "x_mm": x,
        "y_mm": y,
        "rotation": rot,
        "width_mm": w,
        "height_mm": h,
        "layer_name": "F.Cu",
    }


def test_offboard_detection() -> None:
    bounds = (0.0, 0.0, 50.0, 50.0)
    footprints = {
        "R1": _footprint("R1", 25.0, 25.0),  # inside
        "R2": _footprint("R2", 49.9, 25.0),  # body crosses the right edge
    }
    findings = detect_offboard(footprints, bounds)
    codes = {(f.code, f.ref) for f in findings}
    assert ("offboard_component", "R2") in codes
    assert ("offboard_component", "R1") not in codes


def test_offboard_no_bounds_returns_nothing() -> None:
    assert detect_offboard({"R1": _footprint("R1", 10.0, 10.0)}, None) == []


def test_ref_silk_overlap_detection() -> None:
    # Two parts whose reference texts land on the same spot.
    footprints = {
        "R1": _footprint("R1", 10.0, 10.0, ref_at=(0.0, 0.0)),
        "R2": _footprint("R2", 10.3, 10.0, ref_at=(0.0, 0.0)),
    }
    findings = detect_ref_silk_overlap(footprints)
    assert any(f.code == "ref_silk_overlap" for f in findings)


def test_ref_silk_no_overlap_when_separated() -> None:
    footprints = {
        "R1": _footprint("R1", 10.0, 10.0, ref_at=(0.0, 0.0)),
        "R2": _footprint("R2", 40.0, 40.0, ref_at=(0.0, 0.0)),
    }
    assert detect_ref_silk_overlap(footprints) == []


def test_body_overlap_is_informational() -> None:
    footprints = {
        "R1": _footprint("R1", 10.0, 10.0, w=4.0, h=4.0),
        "R2": _footprint("R2", 11.0, 10.0, w=4.0, h=4.0),
    }
    findings = detect_body_overlap(footprints)
    assert findings
    assert all(f.level == "INFO" for f in findings)


def test_run_pcb_readability_rolls_up_status() -> None:
    bounds = (0.0, 0.0, 50.0, 50.0)
    footprints = {
        "R1": _footprint("R1", 10.0, 10.0, ref_at=(0.0, 0.0)),
        "R2": _footprint("R2", 10.3, 10.0, ref_at=(0.0, 0.0)),
    }
    report = run_pcb_readability(footprints, bounds)
    assert report["status"] == "WARN"
    assert report["footprint_count"] == 2
    codes = {f["code"] for f in report["findings"]}
    assert "ref_silk_overlap" in codes


def test_clean_board_passes() -> None:
    bounds = (0.0, 0.0, 100.0, 100.0)
    footprints = {
        "R1": _footprint("R1", 20.0, 20.0, ref_at=(0.0, -2.0)),
        "R2": _footprint("R2", 60.0, 60.0, ref_at=(0.0, -2.0)),
    }
    report = run_pcb_readability(footprints, bounds)
    assert report["status"] == "PASS"
