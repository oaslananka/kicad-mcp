"""Unit tests for the pure electrical-design-rule engine (issue #197)."""

from __future__ import annotations

from kicad_mcp.utils.schematic_rules import (
    is_ground_name,
    is_i2c_name,
    is_supply_rail_name,
    merge_nets_by_name,
    run_schematic_design_rules,
)


def _net(names: list[str], pins: list[tuple[str, str]]) -> dict:
    return {
        "names": names,
        "pins": [{"reference": ref, "pin": pin, "value": ""} for ref, pin in pins],
    }


def test_supply_rail_classification() -> None:
    for name in ["VCC", "VDD", "+3V3", "+5V", "3V3", "5V", "VBAT", "AVDD", "+12V"]:
        assert is_supply_rail_name(name), name
    for name in ["GND", "AGND", "VSS", "0V", "SDA", "NET1"]:
        assert not is_supply_rail_name(name), name


def test_ground_and_i2c_classification() -> None:
    assert is_ground_name("GND") and is_ground_name("agnd")
    assert is_i2c_name("SDA") and is_i2c_name("I2C_SCL") and is_i2c_name("SENSOR_SDA")
    assert not is_i2c_name("SDATA") and not is_i2c_name("VCC")


def test_merge_nets_by_name_unions_cross_sheet_named_nets() -> None:
    nets = [
        _net(["VCC"], [("U1", "1")]),
        _net(["VCC"], [("C1", "1")]),
        _net([], [("R9", "2")]),
    ]
    merged = merge_nets_by_name(nets)
    vcc = [n for n in merged if "VCC" in n["names"]]
    assert len(vcc) == 1
    refs = {p["reference"] for p in vcc[0]["pins"]}
    assert refs == {"U1", "C1"}
    # Unnamed groups pass through untouched.
    assert any(n["names"] == [] for n in merged)


def test_i2c_without_pullup_is_flagged_and_with_pullup_is_clean() -> None:
    flagged = run_schematic_design_rules([_net(["I2C_SDA"], [("U1", "5")])])
    assert any(f.rule_id == "i2c_pullups" for f in flagged)

    clean = run_schematic_design_rules([_net(["I2C_SDA"], [("U1", "5"), ("R1", "1")])])
    assert not any(f.rule_id == "i2c_pullups" for f in clean)


def test_supply_rail_without_decoupling_is_flagged() -> None:
    flagged = run_schematic_design_rules([_net(["+3V3"], [("U1", "1")])])
    decoupling = [f for f in flagged if f.rule_id == "power_rail_decoupling"]
    assert len(decoupling) == 1
    assert "U1" in decoupling[0].refs


def test_supply_rail_with_cap_or_without_ic_is_clean() -> None:
    with_cap = run_schematic_design_rules([_net(["+3V3"], [("U1", "1"), ("C1", "1")])])
    assert not any(f.rule_id == "power_rail_decoupling" for f in with_cap)

    # A rail with no IC on it (e.g. just a connector) is not flagged for decoupling.
    no_ic = run_schematic_design_rules([_net(["+3V3"], [("J1", "2"), ("C1", "1")])])
    assert not any(f.rule_id == "power_rail_decoupling" for f in no_ic)

    # Ground is never flagged as needing decoupling.
    gnd = run_schematic_design_rules([_net(["GND"], [("U1", "8")])])
    assert not any(f.rule_id == "power_rail_decoupling" for f in gnd)


def test_design_rule_check_tool_is_declared_in_validation_category() -> None:
    from kicad_mcp.tools.router import TOOL_CATEGORIES

    assert "schematic_design_rule_check" in TOOL_CATEGORIES["validation"]["tools"]


def test_findings_are_sorted_and_typed() -> None:
    findings = run_schematic_design_rules(
        [
            _net(["+3V3"], [("U1", "1")]),
            _net(["I2C_SCL"], [("U1", "6")]),
        ]
    )
    assert {f.rule_id for f in findings} == {"power_rail_decoupling", "i2c_pullups"}
    assert all(f.severity in {"error", "warning", "info"} for f in findings)
    # Stable ordering by (severity, rule_id, message).
    assert findings == sorted(findings, key=lambda f: f.sort_key())
