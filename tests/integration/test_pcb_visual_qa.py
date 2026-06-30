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
