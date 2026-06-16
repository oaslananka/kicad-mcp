"""IPC-7351B footprint validation (work order P4-T3)."""

from __future__ import annotations

from kicad_mcp.utils.footprint_gen import _chip_passive
from kicad_mcp.utils.footprint_validate import (
    parse_smd_pads,
    validate_chip_footprint,
)


def test_generated_chip_footprint_validates_pass() -> None:
    # The generator and validator share the IPC nominal, so a generated footprint
    # must validate PASS against its own size/density.
    for size in ("0402", "0603", "0805", "1206"):
        text = _chip_passive(size, "B")
        pads = parse_smd_pads(text)
        assert len(pads) == 2, f"{size}: expected 2 pads, parsed {len(pads)}"
        result = validate_chip_footprint(size, pads, density="B")
        assert result.verdict == "PASS", f"{size}: {result.summary} {result.findings}"


def test_wrong_size_code_is_a_hard_fail() -> None:
    # An 0805 land pattern checked against 0402 is grossly oversized -> blocking FAIL.
    pads = parse_smd_pads(_chip_passive("0805", "B"))
    result = validate_chip_footprint("0402", pads, density="B")
    assert result.verdict == "FAIL"
    assert result.findings


def test_pad_count_other_than_two_fails() -> None:
    one_pad = (
        '(footprint "X" (pad "1" smd rect (at -0.5 0) (size 0.6 0.6) (layers F.Cu F.Mask F.Paste)))'
    )
    pads = parse_smd_pads(one_pad)
    assert len(pads) == 1
    result = validate_chip_footprint("0402", pads, density="B")
    assert result.verdict == "FAIL"
    assert "pad count" in result.findings[0]


def test_minor_deviation_warns_not_fails() -> None:
    pads = parse_smd_pads(_chip_passive("0805", "B"))
    # Nudge one pad width by ~0.15 mm: beyond the 0.12 tol but under the 0.24 fail.
    nudged = [
        type(pads[0])(num=pads[0].num, x=pads[0].x, y=pads[0].y, w=pads[0].w + 0.15, h=pads[0].h),
        pads[1],
    ]
    result = validate_chip_footprint("0805", nudged, density="B")
    assert result.verdict == "WARN"
    assert result.findings


def test_parse_smd_pads_reads_position_and_size() -> None:
    pads = parse_smd_pads(_chip_passive("0603", "B"))
    assert {pad.num for pad in pads} == {"1", "2"}
    # Pads are mirrored about the origin on the x-axis.
    assert pads[0].x == -pads[1].x
    assert pads[0].w == pads[1].w
