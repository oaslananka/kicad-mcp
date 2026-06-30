"""Integration test: build_circuit grows the sheet so nothing lands off-page."""

from __future__ import annotations

import json
import re

import pytest

from kicad_mcp.server import build_server
from tests.conftest import call_tool_text


@pytest.mark.anyio
async def test_build_circuit_auto_layout_grows_paper(sample_project, mock_kicad) -> None:
    server = build_server("schematic")
    symbols = [
        {"library": "Device", "symbol_name": "R", "reference": f"R{i}", "value": "10k"}
        for i in range(80)
    ]

    await call_tool_text(
        server,
        "sch_build_circuit",
        {"symbols": symbols, "auto_layout": True},
    )

    sch_text = (sample_project / "demo.kicad_sch").read_text(encoding="utf-8")
    paper = re.search(r'\(paper\s+"([^"]+)"', sch_text)
    assert paper is not None
    # 80 parts do not fit an A4 grid, so the sheet must have grown.
    assert paper.group(1) != "A4"

    raw = await call_tool_text(server, "sch_visual_qa", {})
    payload = json.loads(raw)
    codes = {
        finding["code"]
        for sheet in payload.get("sheets", [])
        for finding in sheet.get("findings", [])
    }
    assert "offsheet_symbol" not in codes
