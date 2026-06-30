"""Integration tests for the sch_autoplace_fields tool (field auto-placement)."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from kicad_mcp.server import build_server
from tests.conftest import call_tool_text


async def _add_two_resistors(server: object) -> None:
    await call_tool_text(
        server,
        "sch_add_symbol",
        {
            "library": "Device",
            "symbol_name": "R",
            "x_mm": 100.0,
            "y_mm": 100.0,
            "reference": "R1",
            "value": "10k",
        },
    )
    await call_tool_text(
        server,
        "sch_add_symbol",
        {
            "library": "Device",
            "symbol_name": "R",
            "x_mm": 120.0,
            "y_mm": 100.0,
            "reference": "R2",
            "value": "10k",
        },
    )


def _force_reference_overlap(sch_file: Path) -> None:
    """Drag both Reference fields onto the same coordinate to create a defect."""
    text = sch_file.read_text(encoding="utf-8")
    # Move every Reference property's own (at ...) to a shared point between the
    # two symbols so their reference text collides.
    text = re.sub(
        r'(\(property\s+"Reference"\s+"R\d+"\s*\(at\s+)[-\d.]+\s+[-\d.]+\s+[-\d.]+(\))',
        r"\g<1>110 100 0\g<2>",
        text,
    )
    sch_file.write_text(text, encoding="utf-8")


def _text_overlap_codes(raw: str) -> set[str]:
    payload = json.loads(raw)
    return {
        finding["code"]
        for sheet in payload.get("sheets", [])
        for finding in sheet.get("findings", [])
    }


@pytest.mark.anyio
async def test_autoplace_fields_clears_text_overlap(sample_project, mock_kicad) -> None:
    server = build_server("schematic")
    await _add_two_resistors(server)

    sch_file = sample_project / "demo.kicad_sch"
    _force_reference_overlap(sch_file)

    before = _text_overlap_codes(await call_tool_text(server, "sch_visual_qa", {}))
    assert "text_overlap" in before

    result = await call_tool_text(server, "sch_autoplace_fields", {})
    assert "Auto-placed" in result

    after = _text_overlap_codes(await call_tool_text(server, "sch_visual_qa", {}))
    assert "text_overlap" not in after


@pytest.mark.anyio
async def test_autoplace_fields_dry_run_does_not_write(sample_project, mock_kicad) -> None:
    server = build_server("schematic")
    await _add_two_resistors(server)
    sch_file = sample_project / "demo.kicad_sch"
    _force_reference_overlap(sch_file)
    before = sch_file.read_text(encoding="utf-8")

    result = await call_tool_text(server, "sch_autoplace_fields", {"dry_run": True})
    assert "Dry run" in result
    assert sch_file.read_text(encoding="utf-8") == before


@pytest.mark.anyio
async def test_autoplace_fields_limits_to_requested_reference(sample_project, mock_kicad) -> None:
    server = build_server("schematic")
    await _add_two_resistors(server)
    sch_file = sample_project / "demo.kicad_sch"
    _force_reference_overlap(sch_file)

    result = await call_tool_text(
        server, "sch_autoplace_fields", {"references": ["R1"], "dry_run": True}
    )
    # Only R1 is in scope, so at most R1 is reported as repositioned.
    assert "R2" not in result
