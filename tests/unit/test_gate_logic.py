from __future__ import annotations

from pathlib import Path

import pytest

from kicad_mcp.tools.validation import (
    GateOutcome,
    _combined_status,
    _empty_project_onboarding_outcome,
    _is_project_empty,
    _project_gate_report_payload,
)


def test_gate_logic_prefers_blocked_then_fail_then_pass() -> None:
    assert _combined_status([GateOutcome("Schematic", "PASS", "ok")]) == "PASS"
    assert _combined_status([GateOutcome("PCB", "FAIL", "fix")]) == "FAIL"
    assert (
        _combined_status(
            [
                GateOutcome("PCB", "FAIL", "fix"),
                GateOutcome("Manufacturing", "BLOCKED", "blocked"),
            ]
        )
        == "BLOCKED"
    )
    # EMPTY should override PASS/FAIL/BLOCKED
    assert (
        _combined_status(
            [
                GateOutcome("PCB", "EMPTY", "empty"),
                GateOutcome("Manufacturing", "BLOCKED", "blocked"),
            ]
        )
        == "EMPTY"
    )


def test_project_gate_payload_renders_summary() -> None:
    payload = _project_gate_report_payload(
        [
            GateOutcome("Schematic", "PASS", "Ready"),
            GateOutcome("PCB", "FAIL", "Clearance issues", ["Too close"]),
        ]
    )
    assert payload.status == "FAIL"
    assert "Project quality gate: FAIL" in payload.text
    assert payload.outcomes[1].details == ["Too close"]


def test_is_project_empty_detects_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("kicad_mcp.tools.schematic.project_schematic_files", lambda: [])
    monkeypatch.setattr(
        "kicad_mcp.tools.validation._get_pcb_file", lambda: Path("nonexistent.kicad_pcb")
    )
    assert _is_project_empty() is True


def test_empty_project_onboarding_outcome() -> None:
    outcome = _empty_project_onboarding_outcome()
    assert outcome.status == "EMPTY"
    assert outcome.name == "Project Onboarding"
    assert any("project_set_design_intent" in step for step in outcome.details)
