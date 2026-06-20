"""Unit tests for the headless schematic visual-QA engine (issue #153)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from kicad_mcp.models.visual_qa import (
    detect_label_collisions,
    detect_offsheet,
    parse_labels,
    parse_paper_extent,
    parse_symbols,
    run_visual_qa,
)

CLEAN_SCH = """
(kicad_sch (version 20240101) (paper "A4")
  (title_block (title "Demo Board") (rev "A") (date "2026-01-01") (company "Acme"))
  (label "NET_A" (at 50 40 0))
  (label "NET_B" (at 150 100 0))
  (symbol (lib_id "Device:R") (at 100 50 0)
    (property "Reference" "R1" (at 102 49 0))
    (property "Footprint" "Resistor_SMD:R_0402_1005Metric" (at 100 50 0))
  )
)
"""

DEFECT_SCH = """
(kicad_sch (version 20240101) (paper "A4")
  (label "OVERLAP_1" (at 80 60 0))
  (label "OVERLAP_2" (at 80.3 60 0))
  (symbol (lib_id "Device:R") (at 5000 9000 0)
    (property "Reference" "R9" (at 5002 8999 0))
  )
)
"""


def test_parse_paper_extent_default_and_portrait() -> None:
    assert parse_paper_extent('(paper "A4")') == (297.0, 210.0)
    assert parse_paper_extent('(paper "A4" portrait)') == (210.0, 297.0)
    assert parse_paper_extent('(paper "User" 200 150)') == (200.0, 150.0)
    assert parse_paper_extent("(no paper here)") == (297.0, 210.0)


def test_parse_labels_and_symbols() -> None:
    labels = parse_labels(CLEAN_SCH)
    assert {label.text for label in labels} == {"NET_A", "NET_B"}
    symbols = parse_symbols(CLEAN_SCH)
    assert len(symbols) == 1
    assert symbols[0].reference == "R1"
    assert symbols[0].lib_id == "Device:R"


def test_detect_label_collisions_flags_overlap() -> None:
    findings = detect_label_collisions(parse_labels(DEFECT_SCH))
    assert len(findings) == 1
    assert findings[0].code == "label_overlap"


def test_detect_offsheet_flags_far_symbol() -> None:
    findings = detect_offsheet(parse_symbols(DEFECT_SCH), parse_labels(DEFECT_SCH), (297.0, 210.0))
    codes = {finding.code for finding in findings}
    assert "offsheet_symbol" in codes


def test_clean_schematic_passes() -> None:
    report = run_visual_qa(CLEAN_SCH)
    assert report["status"] == "PASS"
    assert report["symbol_count"] == 1
    assert report["label_count"] == 2


def test_defect_schematic_warns() -> None:
    report = run_visual_qa(DEFECT_SCH)
    assert report["status"] == "WARN"
    codes = {finding["code"] for finding in report["findings"]}
    assert {"label_overlap", "offsheet_symbol", "title_block_missing"} <= codes


@pytest.mark.anyio
async def test_sch_visual_qa_tool(tmp_path: Path) -> None:
    from kicad_mcp.server import create_server
    from tests.conftest import call_tool_text

    (tmp_path / "test.kicad_pro").write_text("{}", encoding="utf-8")
    (tmp_path / "test.kicad_pcb").write_text("", encoding="utf-8")
    (tmp_path / "test.kicad_sch").write_text(DEFECT_SCH, encoding="utf-8")

    server = create_server()
    await call_tool_text(server, "kicad_set_project", {"project_dir": str(tmp_path)})
    raw = await call_tool_text(server, "sch_visual_qa", {})
    payload = json.loads(raw)
    assert payload["status"] == "WARN"
    assert payload["sheets"]
    codes = {f["code"] for sheet in payload["sheets"] for f in sheet["findings"]}
    assert "label_overlap" in codes
