"""PDN/thermal solver-seam honesty (work order P3-T2/P3-T4).

Mirrors the field-solver seam (test_field_solver.py): the seam must never claim a
solver it does not have, and results must be labeled with the honest method.
"""

from __future__ import annotations

from kicad_mcp.utils.solver_seams import (
    EMC_HEURISTIC_METHOD,
    PDN_CLOSED_FORM_METHOD,
    PDN_MESH_METHOD,
    SOLVER_VERDICT_REQUIRES_EXPERT,
    SOLVER_VERDICT_SOLVER_GRADE,
    THERMAL_CLOSED_FORM_METHOD,
    channel_method,
    emc_method,
    emc_solver_available,
    format_solver_verdict,
    ir_drop_method,
    pdn_mesh_method,
    pdn_solver_available,
    thermal_method,
    thermal_solver_available,
)


def _assert_requires_expert_solver(method: dict[str, object]) -> None:
    assert method["solver_grade"] is False
    assert method["verdict"] == SOLVER_VERDICT_REQUIRES_EXPERT
    assert method["release_signoff"] == "blocked"
    assert method["critic_only"] is True
    assert "requires-expert-solver" in format_solver_verdict(method)


def _assert_solver_grade(method: dict[str, object]) -> None:
    assert method["solver_grade"] is True
    assert method["verdict"] == SOLVER_VERDICT_SOLVER_GRADE
    assert method["release_signoff"] == "eligible"
    assert method["critic_only"] is False


def test_no_pdn_solver_is_integrated_yet() -> None:
    assert pdn_solver_available() is False
    method = ir_drop_method()
    _assert_requires_expert_solver(method)
    assert method["method"] == PDN_CLOSED_FORM_METHOD
    assert "not a" in method["note"].lower()


def test_pdn_mesh_is_a_real_distributed_solve_but_not_a_field_solver() -> None:
    """The multi-load PDN mesh is solver-grade, but honest about being 1-D resistive."""
    method = pdn_mesh_method()
    _assert_solver_grade(method)
    assert method["method"] == PDN_MESH_METHOD
    assert "not a 2-d" in method["accuracy"].lower()


def test_no_thermal_solver_is_integrated_yet() -> None:
    assert thermal_solver_available() is False
    method = thermal_method()
    _assert_requires_expert_solver(method)
    assert method["method"] == THERMAL_CLOSED_FORM_METHOD
    assert "not a" in method["note"].lower()


def test_no_emc_solver_is_integrated_yet() -> None:
    assert emc_solver_available() is False
    method = emc_method()
    _assert_requires_expert_solver(method)
    assert method["method"] == EMC_HEURISTIC_METHOD
    assert "not a" in method["note"].lower()


def test_channel_fallback_is_critic_only_until_ngspice_runs() -> None:
    method = channel_method(measured=False)
    _assert_requires_expert_solver(method)
    assert "not a measured" in method["note"].lower()


def test_channel_ngspice_result_is_solver_grade_but_bounded() -> None:
    method = channel_method(measured=True)
    _assert_solver_grade(method)
    assert "approximate" in method["accuracy"].lower()
