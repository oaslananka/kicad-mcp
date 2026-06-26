"""Field-solver adapter seam honesty (work order P3-T1)."""

from __future__ import annotations

from kicad_mcp.tools.signal_integrity import _format_impedance_result
from kicad_mcp.utils.field_solver import (
    CLOSED_FORM_METHOD,
    field_solver_available,
    impedance_method,
)
from kicad_mcp.utils.solver_seams import format_solver_verdict


def test_no_field_solver_is_integrated_yet() -> None:
    # The seam must not claim a solver it does not have.
    assert field_solver_available() is False
    method = impedance_method()
    assert method["solver_grade"] is False
    assert method["verdict"] == "requires-expert-solver"
    assert method["release_signoff"] == "blocked"
    assert method["critic_only"] is True
    assert method["method"] == CLOSED_FORM_METHOD
    assert "not a" in method["note"].lower()
    assert "requires-expert-solver" in format_solver_verdict(method)


def test_impedance_result_states_its_method() -> None:
    text = _format_impedance_result(
        title="Trace impedance estimate:",
        trace_type="microstrip",
        width_mm=0.3,
        height_mm=0.2,
        er=4.2,
        copper_oz=1.0,
        impedance_ohm=50.0,
        effective_er=3.2,
    )
    # A reader can tell from the result alone that this is closed-form, not a solver.
    assert "Method: closed-form" in text
    assert "Solver verdict: requires-expert-solver" in text
    assert "release_signoff=blocked" in text
    assert "not a" in text.lower()
