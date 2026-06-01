from __future__ import annotations

import pytest

from kicad_mcp.utils.impedance import (
    differential_impedance,
    get_dielectric,
    list_dielectric_materials,
    propagation_delay_ps_per_mm,
    recommend_dielectric_for_frequency,
    recommended_decoupling_distance_mm,
    solve_spacing_for_differential_impedance,
    solve_width_for_impedance,
    trace_impedance,
    via_stub_resonance_ghz,
    via_stub_risk_level,
)


def test_microstrip_impedance_matches_expected_envelope() -> None:
    impedance_ohm, effective_er = trace_impedance(
        0.34,
        0.18,
        4.2,
        trace_type="microstrip",
        copper_oz=1.0,
        spacing_mm=0.2,
    )

    assert 47.0 <= impedance_ohm <= 52.0
    assert 2.7 <= effective_er <= 3.6


def test_width_solver_rechecks_close_to_target() -> None:
    width_mm = solve_width_for_impedance(
        50.0,
        0.18,
        4.2,
        trace_type="microstrip",
        copper_oz=1.0,
        spacing_mm=0.2,
    )
    impedance_ohm, _ = trace_impedance(
        width_mm,
        0.18,
        4.2,
        trace_type="microstrip",
        copper_oz=1.0,
        spacing_mm=0.2,
    )

    assert 0.2 <= width_mm <= 0.5
    assert abs(impedance_ohm - 50.0) <= 0.25


def test_differential_spacing_solver_rechecks_close_to_target() -> None:
    width_mm = solve_width_for_impedance(
        50.0,
        0.18,
        4.2,
        trace_type="microstrip",
        copper_oz=1.0,
        spacing_mm=0.2,
    )
    diff_width_mm = width_mm * 0.55
    spacing_mm = solve_spacing_for_differential_impedance(
        100.0,
        diff_width_mm,
        0.18,
        4.2,
        trace_type="microstrip",
        copper_oz=1.0,
    )
    differential_ohm, _ = differential_impedance(
        diff_width_mm,
        0.18,
        spacing_mm,
        4.2,
        trace_type="microstrip",
        copper_oz=1.0,
    )

    assert 0.05 <= spacing_mm <= 0.5
    assert abs(differential_ohm - 100.0) <= 0.75


def test_via_stub_resonance_looks_reasonable() -> None:
    resonance_ghz = via_stub_resonance_ghz(1.6, er=4.0)

    assert 23.0 <= resonance_ghz <= 24.0


def test_propagation_delay_and_decoupling_heuristic_ranges() -> None:
    assert 5.7 <= propagation_delay_ps_per_mm(3.0) <= 5.9
    assert recommended_decoupling_distance_mm(50.0) == 10.0
    assert recommended_decoupling_distance_mm(250.0) == 2.0
    assert recommended_decoupling_distance_mm(2_000.0) == 0.5


def test_dielectric_library_lookup_and_frequency_recommendations() -> None:
    materials = list_dielectric_materials()

    assert any(item["key"] == "fr4_standard" for item in materials)
    assert get_dielectric("ro4350b")[1] == pytest.approx(3.48)
    assert recommend_dielectric_for_frequency(0.5) == "fr4_standard"
    assert recommend_dielectric_for_frequency(2.0) == "fr4_midloss"
    assert recommend_dielectric_for_frequency(4.0) == "fr4_lowloss"
    assert recommend_dielectric_for_frequency(10.0) == "ro4350b"
    assert recommend_dielectric_for_frequency(20.0) == "ro4003c"
    assert recommend_dielectric_for_frequency(45.0) == "ptfe"
    with pytest.raises(ValueError, match="Unknown dielectric"):
        get_dielectric("mystery")


def test_stripline_and_coplanar_paths_are_supported() -> None:
    stripline_impedance, stripline_er = trace_impedance(
        0.18,
        0.12,
        3.8,
        trace_type="stripline",
        copper_oz=0.5,
    )
    coplanar_impedance, coplanar_er = trace_impedance(
        0.2,
        0.18,
        4.2,
        trace_type="coplanar",
        copper_oz=1.0,
        spacing_mm=0.15,
    )

    assert stripline_impedance > 0.0
    assert stripline_er == pytest.approx(3.8)
    assert coplanar_impedance > 0.0
    assert 1.0 < coplanar_er < 4.2
    stripline_diff_ohm, _ = differential_impedance(
        0.16,
        0.12,
        0.18,
        3.8,
        trace_type="stripline",
        copper_oz=0.5,
    )
    assert stripline_diff_ohm > 0.0


def test_impedance_helpers_reject_invalid_inputs_and_classify_stub_risk() -> None:
    with pytest.raises(ValueError, match="positive"):
        trace_impedance(0.0, 0.18, 4.2)
    with pytest.raises(ValueError, match="positive spacing_mm"):
        trace_impedance(0.2, 0.18, 4.2, trace_type="coplanar", spacing_mm=0.0)
    with pytest.raises(ValueError, match="Unsupported trace type"):
        trace_impedance(0.2, 0.18, 4.2, trace_type="unknown")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="must be positive"):
        via_stub_resonance_ghz(0.0)
    zero_thickness_impedance, _ = trace_impedance(0.2, 0.18, 4.2, copper_oz=0.0)
    assert zero_thickness_impedance > 0.0

    assert via_stub_risk_level(1.6, 10.0, er=4.0) == "high"
    assert via_stub_risk_level(1.6, 4.0, er=4.0) == "medium"
    assert via_stub_risk_level(1.6, 1.0, er=4.0) == "low"
