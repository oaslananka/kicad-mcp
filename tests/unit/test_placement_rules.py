"""Unit tests for the constraint-driven placement critic (issue #203)."""

from __future__ import annotations

from kicad_mcp.utils.placement_rules import (
    PlacementThresholds,
    critique_placement,
)

_T = PlacementThresholds()


def _fp(
    ref: str,
    value: str = "",
    x_mm: float = 0.0,
    y_mm: float = 0.0,
    net_names: list[str] | None = None,
) -> dict:
    return {
        "name": f"lib:{ref}",
        "value": value,
        "x_mm": x_mm,
        "y_mm": y_mm,
        "net_names": net_names or [],
    }


# ---------------------------------------------------------------------------
# PLR-001: decap-to-IC distance
# ---------------------------------------------------------------------------


def test_no_findings_on_empty_board() -> None:
    assert critique_placement({}) == []


def test_decap_close_to_ic_no_finding() -> None:
    footprints = {
        "U1": _fp("U1", "STM32F4", x_mm=0.0, y_mm=0.0),
        "C1": _fp("C1", "100nF", x_mm=2.0, y_mm=0.0),
    }
    findings = critique_placement(footprints, _T)
    plr001 = [f for f in findings if f.rule_id == "PLR-001"]
    assert plr001 == [], f"Expected no PLR-001 finding, got {plr001}"


def test_decap_far_from_ic_triggers_plr001() -> None:
    footprints = {
        "U1": _fp("U1", "STM32F4", x_mm=0.0, y_mm=0.0),
        "C1": _fp("C1", "100nF", x_mm=20.0, y_mm=0.0),
    }
    findings = critique_placement(footprints, _T)
    plr001 = [f for f in findings if f.rule_id == "PLR-001"]
    assert len(plr001) == 1
    assert "C1" in plr001[0].refs
    assert "U1" in plr001[0].refs
    assert plr001[0].detail["distance_mm"] > 5.0


def test_no_decap_no_finding() -> None:
    footprints = {"U1": _fp("U1", "STM32F4", x_mm=0.0)}
    assert critique_placement(footprints, _T) == []


def test_no_ic_no_decap_finding() -> None:
    footprints = {"C1": _fp("C1", "100nF", x_mm=0.0)}
    assert critique_placement(footprints, _T) == []


# ---------------------------------------------------------------------------
# PLR-002: crystal-to-IC distance
# ---------------------------------------------------------------------------


def test_crystal_close_to_ic_no_finding() -> None:
    footprints = {
        "U1": _fp("U1", "STM32F4", x_mm=0.0, y_mm=0.0),
        "Y1": _fp("Y1", "16MHz", x_mm=5.0, y_mm=0.0),
    }
    findings = critique_placement(footprints, _T)
    plr002 = [f for f in findings if f.rule_id == "PLR-002"]
    assert plr002 == []


def test_crystal_far_from_ic_triggers_plr002() -> None:
    footprints = {
        "U1": _fp("U1", "STM32F4", x_mm=0.0, y_mm=0.0),
        "Y1": _fp("Y1", "16MHz", x_mm=50.0, y_mm=0.0),
    }
    findings = critique_placement(footprints, _T)
    plr002 = [f for f in findings if f.rule_id == "PLR-002"]
    assert len(plr002) == 1
    assert "Y1" in plr002[0].refs
    assert plr002[0].detail["distance_mm"] > 8.0


# ---------------------------------------------------------------------------
# PLR-003: SMPS hot-loop
# ---------------------------------------------------------------------------


def test_smps_hot_loop_tight_no_finding() -> None:
    footprints = {
        "U1": _fp("U1", "MP2307", x_mm=0.0, y_mm=0.0),
        "L1": _fp("L1", "10uH", x_mm=5.0, y_mm=0.0),
        "C1": _fp("C1", "100uF", x_mm=10.0, y_mm=0.0),
        "C2": _fp("C2", "10uF", x_mm=3.0, y_mm=2.0),
    }
    findings = critique_placement(footprints, _T)
    plr003 = [f for f in findings if f.rule_id == "PLR-003"]
    assert plr003 == [], f"Expected no PLR-003, got {plr003}"


def test_smps_hot_loop_large_triggers_plr003() -> None:
    footprints = {
        "U1": _fp("U1", "MP2307", x_mm=0.0, y_mm=0.0),
        "L1": _fp("L1", "10uH", x_mm=25.0, y_mm=0.0),
        "C1": _fp("C1", "100uF", x_mm=0.0, y_mm=20.0),
        "C2": _fp("C2", "10uF", x_mm=10.0, y_mm=10.0),
    }
    findings = critique_placement(footprints, _T)
    plr003 = [f for f in findings if f.rule_id == "PLR-003"]
    assert len(plr003) == 1
    assert plr003[0].detail["hot_loop_area_mm2"] > 200.0


# ---------------------------------------------------------------------------
# PLR-004: analog / digital mixing
# ---------------------------------------------------------------------------


def test_analog_digital_separated_no_finding() -> None:
    footprints = {
        "U1": _fp("U1", "ADC", x_mm=0.0, y_mm=0.0, net_names=["AGND", "AVCC"]),
        "U2": _fp("U2", "MCU", x_mm=20.0, y_mm=0.0, net_names=["DVDD", "GND"]),
    }
    findings = critique_placement(footprints, _T)
    plr004 = [f for f in findings if f.rule_id == "PLR-004"]
    assert plr004 == []


def test_analog_digital_mixed_triggers_plr004() -> None:
    footprints = {
        "U1": _fp("U1", "ADC", x_mm=0.0, y_mm=0.0, net_names=["AGND", "AVCC"]),
        "U2": _fp("U2", "MCU", x_mm=2.0, y_mm=0.0, net_names=["DVDD", "GND"]),
    }
    findings = critique_placement(footprints, _T)
    plr004 = [f for f in findings if f.rule_id == "PLR-004"]
    assert len(plr004) == 1
    assert plr004[0].detail["mixing_pair_count"] >= 1


# ---------------------------------------------------------------------------
# Custom thresholds
# ---------------------------------------------------------------------------


def test_custom_threshold_tighter_decap() -> None:
    tight = PlacementThresholds(decap_max_distance_mm=1.0)
    footprints = {
        "U1": _fp("U1", "STM32F4", x_mm=0.0),
        "C1": _fp("C1", "100nF", x_mm=2.0),
    }
    findings = critique_placement(footprints, tight)
    plr001 = [f for f in findings if f.rule_id == "PLR-001"]
    assert len(plr001) == 1  # 2 mm > 1 mm threshold


def test_to_dict_has_expected_keys() -> None:
    footprints = {
        "U1": _fp("U1", "STM32F4", x_mm=0.0),
        "C1": _fp("C1", "100nF", x_mm=20.0),
    }
    findings = critique_placement(footprints, _T)
    assert findings
    d = findings[0].to_dict()
    assert {"rule_id", "severity", "message", "refs"}.issubset(d.keys())
