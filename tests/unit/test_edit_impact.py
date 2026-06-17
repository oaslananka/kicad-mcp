"""Edit-impact analysis (work order P4-T4)."""

from __future__ import annotations

from kicad_mcp.tools.edit_impact import (
    ALL_GATES,
    impact_of_changes,
    render_impact_report,
    semantic_intent_diff,
)

_BASE = {
    "critical_nets": ["USB_DP", "USB_DM"],
    "power_rails": [{"name": "+3V3"}, {"name": "+5V"}],
    "thermal_hotspots": ["U1"],
    "manufacturer": "JLCPCB",
    "manufacturer_tier": "standard",
}


def test_no_changes_preserves_every_gate() -> None:
    changes = semantic_intent_diff(_BASE, dict(_BASE))
    assert changes == []
    report = impact_of_changes(changes)
    assert report.affected_gates == []
    assert set(report.preserved_gates) == set(ALL_GATES)
    assert "preserved" in report.summary


def test_added_critical_net_impacts_only_signal_related_gates() -> None:
    after = {**_BASE, "critical_nets": ["USB_DP", "USB_DM", "PCIE_TX"]}
    changes = semantic_intent_diff(_BASE, after)
    assert any(c.kind == "added" and c.detail == "PCIE_TX" for c in changes)
    report = impact_of_changes(changes)
    # Signal/connectivity/pcb re-run; thermal/power/manufacturing preserved.
    assert set(report.affected_gates) == {"signal_integrity", "connectivity", "pcb"}
    assert "thermal" in report.preserved_gates
    assert "manufacturing" in report.preserved_gates


def test_power_rail_change_impacts_power_and_pcb_only() -> None:
    after = {**_BASE, "power_rails": [{"name": "+3V3"}]}  # removed +5V
    changes = semantic_intent_diff(_BASE, after)
    assert any(c.kind == "removed" and c.detail == "+5V" for c in changes)
    report = impact_of_changes(changes)
    assert set(report.affected_gates) == {"power", "pcb"}
    assert "signal_integrity" in report.preserved_gates


def test_manufacturer_change_impacts_manufacturing_and_dfm() -> None:
    after = {**_BASE, "manufacturer": "PCBWay"}
    changes = semantic_intent_diff(_BASE, after)
    assert any(c.category == "manufacturer" and c.kind == "modified" for c in changes)
    report = impact_of_changes(changes)
    assert set(report.affected_gates) == {"manufacturing", "dfm"}


def test_modified_dict_entry_is_detected() -> None:
    after = {**_BASE, "power_rails": [{"name": "+3V3", "current_a": 2.0}, {"name": "+5V"}]}
    changes = semantic_intent_diff(_BASE, after)
    assert any(c.kind == "modified" and c.detail == "+3V3" for c in changes)


def test_render_impact_report_is_human_readable() -> None:
    after = {**_BASE, "critical_nets": ["USB_DP"]}  # removed USB_DM
    report = impact_of_changes(semantic_intent_diff(_BASE, after))
    text = render_impact_report(report)
    assert "Edit-impact analysis:" in text
    assert "Gates to re-run:" in text
    assert "Gates preserved:" in text
