"""Integration test for the headless pcb_visual_qa tool."""

from __future__ import annotations

import json

import pytest

from kicad_mcp.server import build_server
from tests.conftest import call_tool_text


def _fp(ref: str, x: float, y: float, half_w: float) -> str:
    return "\n".join(
        [
            '\t(footprint "R_0402"',
            '\t\t(layer "F.Cu")',
            f"\t\t(at {x} {y} 0)",
            f'\t\t(property "Reference" "{ref}"',
            "\t\t\t(at 0 0 0)",
            '\t\t\t(layer "F.SilkS")',
            "\t\t\t(effects (font (size 1 1)))",
            "\t\t)",
            f'\t\t(fp_rect (start {-half_w} -0.5) (end {half_w} 0.5) (layer "F.SilkS"))',
            "\t)",
        ]
    )


_BOARD = "\n".join(
    [
        "(kicad_pcb",
        "\t(version 20240101)",
        "\t(generator pcbnew)",
        '\t(gr_rect (start 0 0) (end 50 50) (layer "Edge.Cuts"))',
        _fp("R1", 25.0, 25.0, 1.0),
        _fp("R2", 25.3, 25.0, 1.0),
        _fp("R3", 49.8, 10.0, 1.5),
        ")",
        "",
    ]
)


def _silk_codes(raw: str) -> set[str]:
    return {f["code"] for f in json.loads(raw)["findings"]}


@pytest.mark.anyio
async def test_pcb_visual_qa_flags_offboard_and_silk_overlap(sample_project, mock_kicad) -> None:
    (sample_project / "demo.kicad_pcb").write_text(_BOARD, encoding="utf-8")

    server = build_server("full")
    raw = await call_tool_text(server, "pcb_visual_qa", {})
    report = json.loads(raw)

    assert report["status"] == "WARN"
    assert report["footprint_count"] == 3
    codes = {finding["code"] for finding in report["findings"]}
    assert "ref_silk_overlap" in codes
    assert "offboard_component" in codes


def _fp_ref(ref: str, x: float, y: float, ref_dx: float) -> str:
    """A footprint whose Reference silk text is offset by ``ref_dx`` locally."""
    return "\n".join(
        [
            '\t(footprint "R_0402"',
            '\t\t(layer "F.Cu")',
            f"\t\t(at {x} {y} 0)",
            f'\t\t(property "Reference" "{ref}"',
            f"\t\t\t(at {ref_dx} 0 0)",
            '\t\t\t(layer "F.SilkS")',
            "\t\t\t(effects (font (size 1 1)))",
            "\t\t)",
            '\t\t(fp_rect (start -1.0 -0.5) (end 1.0 0.5) (layer "F.SilkS"))',
            "\t)",
        ]
    )


# Two on-board parts spaced 4 mm apart, but their reference texts are both pulled
# onto the midpoint (x≈25) so the silk overlaps until auto-placed.
_SILK_BOARD = "\n".join(
    [
        "(kicad_pcb",
        "\t(version 20240101)",
        "\t(generator pcbnew)",
        '\t(gr_rect (start 0 0) (end 50 50) (layer "Edge.Cuts"))',
        _fp_ref("R1", 23.0, 25.0, 2.0),
        _fp_ref("R2", 27.0, 25.0, -2.0),
        ")",
        "",
    ]
)


@pytest.mark.anyio
async def test_pcb_autoplace_reference_text_clears_silk_overlap(sample_project, mock_kicad) -> None:
    board = sample_project / "demo.kicad_pcb"
    board.write_text(_SILK_BOARD, encoding="utf-8")
    server = build_server("full")

    assert "ref_silk_overlap" in _silk_codes(await call_tool_text(server, "pcb_visual_qa", {}))

    result = await call_tool_text(
        server, "pcb_autoplace_reference_text", {"allow_open_board": True}
    )
    assert "Repositioned reference text" in result

    assert "ref_silk_overlap" not in _silk_codes(await call_tool_text(server, "pcb_visual_qa", {}))


@pytest.mark.anyio
async def test_pcb_autoplace_reference_text_dry_run(sample_project, mock_kicad) -> None:
    board = sample_project / "demo.kicad_pcb"
    board.write_text(_SILK_BOARD, encoding="utf-8")
    before = board.read_text(encoding="utf-8")
    server = build_server("full")

    result = await call_tool_text(server, "pcb_autoplace_reference_text", {"dry_run": True})
    assert "Dry run" in result
    assert board.read_text(encoding="utf-8") == before
