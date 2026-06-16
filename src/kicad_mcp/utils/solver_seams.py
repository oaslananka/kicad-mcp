"""Solver adapter seams for power-integrity and thermal analysis (work order P3-T2/P3-T4).

Like the field-solver seam for impedance (:mod:`kicad_mcp.utils.field_solver`), the
power-integrity and thermal tools use first-order, lumped/closed-form estimates — not a
distributed IR-drop / current-density solve (P3-T2) or a thermal-network / FEA solve
(P3-T4). This module is the seam where a real solver plugs in. Until one is wired, the
``*_available`` probes return ``False`` and callers label results with the honest method
so a number never implies solver-grade accuracy. This is the explicit "solver
unavailable" fallback the work order mandates, instead of silently passing a lumped
estimate off as a distributed-solver result.
"""

from __future__ import annotations

from typing import Any

PDN_CLOSED_FORM_METHOD = "lumped closed-form (R = rho*L/A, single trace)"
PDN_CLOSED_FORM_ACCURACY = (
    "first-order DC estimate for one trace; not a distributed plane IR-drop / current-density solve"
)
THERMAL_CLOSED_FORM_METHOD = "first-order resistive estimate (theta_JA / via-count rule of thumb)"
THERMAL_CLOSED_FORM_ACCURACY = (
    "first-order; not a thermal-network / FEA solve with copper spreading and airflow"
)
PDN_MESH_METHOD = "distributed multi-load resistive PDN mesh (DC) + lumped-branch Z(f)"
PDN_MESH_ACCURACY = (
    "real network solve across all loads using 1-D equivalent trace resistance and "
    "lumped decoupling branches; not a 2-D copper-plane field solve"
)


def pdn_solver_available() -> bool:
    """Return ``True`` only when a distributed IR-drop / current-density solver is wired."""
    return False


def thermal_solver_available() -> bool:
    """Return ``True`` only when a thermal-network / FEA solver is wired."""
    return False


def _method(
    *,
    available: bool,
    solver_method: str,
    closed_method: str,
    closed_accuracy: str,
    what: str,
) -> dict[str, Any]:
    if available:  # pragma: no cover - no solver integrated yet
        return {"method": solver_method, "solver_grade": True, "accuracy": "solver-grade"}
    return {
        "method": closed_method,
        "solver_grade": False,
        "accuracy": closed_accuracy,
        "note": (
            f"No {what} solver is integrated; this is a first-order estimate, not a "
            "solver-grade or sign-off figure."
        ),
    }


def ir_drop_method() -> dict[str, Any]:
    """Describe the active DC IR-drop / current-density computation method, honestly."""
    return _method(
        available=pdn_solver_available(),
        solver_method="distributed IR-drop / current-density solver",
        closed_method=PDN_CLOSED_FORM_METHOD,
        closed_accuracy=PDN_CLOSED_FORM_ACCURACY,
        what="distributed IR-drop",
    )


def pdn_mesh_method() -> dict[str, Any]:
    """Describe check_power_integrity's distributed PDN mesh solve, honestly.

    Unlike the single-trace lumped estimate (:func:`ir_drop_method`), this is a genuine
    multi-load resistive network solve with frequency-domain PDN impedance, so it is
    solver-grade — but it models traces as 1-D equivalent resistances, not a 2-D
    copper-plane field solver.
    """
    return {
        "method": PDN_MESH_METHOD,
        "solver_grade": True,
        "accuracy": PDN_MESH_ACCURACY,
    }


def thermal_method() -> dict[str, Any]:
    """Describe the active thermal computation method, honestly."""
    return _method(
        available=thermal_solver_available(),
        solver_method="thermal-network / FEA solver",
        closed_method=THERMAL_CLOSED_FORM_METHOD,
        closed_accuracy=THERMAL_CLOSED_FORM_ACCURACY,
        what="thermal FEA",
    )
