"""Structured verdict payloads for high-traffic agent tools."""

from __future__ import annotations

from pathlib import Path

import pytest

from kicad_mcp.server import build_server
from kicad_mcp.tools.gates import GateOutcome
from tests.conftest import call_tool_payload, call_tool_text


@pytest.mark.anyio
async def test_run_drc_returns_structured_verdict_with_stable_finding_ids(
    sample_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report = {
        "violations": [
            {
                "uuid": "clearance-1",
                "severity": "error",
                "type": "clearance",
                "description": "Clearance violation",
            }
        ],
        "unconnected_items": [],
        "items_not_passing_courtyard": [],
    }

    def fake_run_drc(report_name: str) -> tuple[Path, dict[str, object], None]:
        return sample_project / "output" / report_name, report, None

    monkeypatch.setattr("kicad_mcp.tools.validation._run_drc_report", fake_run_drc)
    server = build_server("full")
    await call_tool_text(server, "kicad_set_project", {"project_dir": str(sample_project)})

    first = await call_tool_payload(server, "run_drc", {"save_report": True})
    second = await call_tool_payload(server, "run_drc", {"save_report": True})

    assert isinstance(first, dict)
    assert first["text"].startswith("DRC summary:")
    assert first["verdict"] == "FAIL"
    assert first["findings"][0]["severity"] == "error"
    assert first["findings"][0]["suggested_fix"]["tool"] == "run_drc"
    assert first["findings"][0]["id"] == second["findings"][0]["id"]


@pytest.mark.anyio
async def test_quality_gate_returns_verdict_report(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "kicad_mcp.tools.validation._evaluate_schematic_gate",
        lambda: GateOutcome(
            name="Schematic",
            status="FAIL",
            summary="ERC reported blocking issues.",
            details=["FAIL: U1 pin 3 is not connected."],
        ),
    )
    server = build_server("full")

    payload = await call_tool_payload(server, "schematic_quality_gate", {})

    assert isinstance(payload, dict)
    assert payload["text"].startswith("Schematic quality gate: FAIL")
    assert payload["verdict"] == "FAIL"
    assert payload["findings"][0]["location"] == "Schematic"
    assert payload["findings"][0]["suggested_fix"]["tool"] == "sch_annotate"


@pytest.mark.anyio
async def test_project_next_action_includes_verdict_and_finding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "kicad_mcp.tools.validation._evaluate_project_gate",
        lambda: [
            GateOutcome(
                name="PCB",
                status="FAIL",
                summary="PCB still has blocking physical-rule issues.",
                details=["FAIL: clearance between J1 and U1."],
            )
        ],
    )
    server = build_server("full")

    payload = await call_tool_payload(server, "project_get_next_action", {})

    assert isinstance(payload, dict)
    assert payload["status"] == "FAIL"
    assert payload["verdict"] == "FAIL"
    assert payload["suggested_tool"] == "run_drc()"
    assert payload["findings"][0]["suggested_fix"]["tool"] == "run_drc"


@pytest.mark.anyio
async def test_pcb_board_summary_returns_verdict_report(mock_board: object) -> None:
    server = build_server("pcb")

    payload = await call_tool_payload(server, "pcb_get_board_summary", {})

    assert isinstance(payload, dict)
    assert payload["text"].startswith("Board summary:")
    assert payload["verdict"] == "PASS"
    assert payload["metadata"]["source"] == "live-gui"
    assert payload["metadata"]["tracks"] == 0
