"""PDN/thermal solver-seam honesty (work order P3-T2/P3-T4).

Mirrors the field-solver seam (test_field_solver.py): the seam must never claim a
solver it does not have, and results must be labeled with the honest method.
"""

from __future__ import annotations

from kicad_mcp.utils.solver_seams import (
    PDN_CLOSED_FORM_METHOD,
    THERMAL_CLOSED_FORM_METHOD,
    ir_drop_method,
    pdn_solver_available,
    thermal_method,
    thermal_solver_available,
)


def test_no_pdn_solver_is_integrated_yet() -> None:
    assert pdn_solver_available() is False
    method = ir_drop_method()
    assert method["solver_grade"] is False
    assert method["method"] == PDN_CLOSED_FORM_METHOD
    assert "not a" in method["note"].lower()


def test_no_thermal_solver_is_integrated_yet() -> None:
    assert thermal_solver_available() is False
    method = thermal_method()
    assert method["solver_grade"] is False
    assert method["method"] == THERMAL_CLOSED_FORM_METHOD
    assert "not a" in method["note"].lower()
