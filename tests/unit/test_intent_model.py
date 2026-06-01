"""Unit tests for the ProjectDesignIntent v1 → v2 migration and new sub-models.

Validates that:
- v1 JSON (kicad-mcp-pro ≤ 2.0.x) loads without error; new fields default correctly.
- v2 JSON round-trips through model_validate → model_dump → model_validate.
- Sub-models (PowerRailSpec, InterfaceSpec, etc.) validate correctly.
- _normalize_design_intent is idempotent.
"""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from kicad_mcp.models.intent import (
    ComplianceTarget,
    CostTarget,
    InterfaceSpec,
    MechanicalConstraint,
    MountHoleSpec,
    PowerRailSpec,
    ThermalEnvelope,
)
from kicad_mcp.tools.project import (
    ProjectDesignIntent,
    _normalize_design_intent,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

V1_INTENT_JSON = {
    "connector_refs": ["J1", "J2"],
    "decoupling_pairs": [{"ic_ref": "U1", "cap_refs": ["C1", "C2"], "max_distance_mm": 3.0}],
    "critical_nets": ["USB_DP", "USB_DM"],
    "power_tree_refs": ["J1", "U2"],
    "analog_refs": ["U3"],
    "digital_refs": ["U1"],
    "sensor_cluster_refs": ["U4"],
    "rf_keepout_regions": [{"name": "ANT", "x_mm": 10.0, "y_mm": 20.0, "w_mm": 5.0, "h_mm": 5.0}],
    "manufacturer": "jlcpcb",
    "manufacturer_tier": "standard",
}

V2_EXTRA_FIELDS = {
    "power_rails": [
        {
            "name": "+3V3",
            "voltage_v": 3.3,
            "current_max_a": 1.0,
            "tolerance_pct": 3.0,
            "source_ref": "U2",
            "decoupling_strategy": "bulk",
        }
    ],
    "interfaces": [
        {
            "kind": "usb2",
            "refs": ["J1"],
            "net_prefix": "USB_",
            "impedance_target_ohm": 90.0,
            "differential": True,
            "diff_skew_max_ps": 100.0,
            "length_target_mm": 50.0,
            "length_match_tolerance_mm": 2.0,
        }
    ],
    "mechanical": {
        "max_height_mm": 8.0,
        "connector_placement": [{"ref": "J1", "edge": "bottom", "margin_mm": 2.0}],
    },
    "compliance": [{"kind": "fcc_b"}, {"kind": "ce_emc"}],
    "cost": {"unit_cost_usd_max": 15.0, "volume_units": 1000},
    "thermal": {"ambient_c": 25.0, "max_component_c": 85.0, "airflow": "natural"},
}


# ---------------------------------------------------------------------------
# v1 backward-compat
# ---------------------------------------------------------------------------


def test_v1_json_loads_without_error() -> None:
    """v1 intent JSON must load cleanly; new v2 fields default to empty/None."""
    intent = ProjectDesignIntent.model_validate(V1_INTENT_JSON)

    assert intent.connector_refs == ["J1", "J2"]
    assert len(intent.decoupling_pairs) == 1
    assert intent.decoupling_pairs[0].ic_ref == "U1"
    assert intent.manufacturer == "jlcpcb"

    # v2 fields should all be at their defaults.
    assert intent.power_rails == []
    assert intent.interfaces == []
    assert intent.mechanical == MechanicalConstraint()
    assert intent.compliance == []
    assert intent.cost == CostTarget()
    assert intent.thermal == ThermalEnvelope()


def test_v1_json_normalise_is_idempotent() -> None:
    intent = ProjectDesignIntent.model_validate(V1_INTENT_JSON)
    once = _normalize_design_intent(intent)
    twice = _normalize_design_intent(once)
    assert once.model_dump() == twice.model_dump()


def test_v1_round_trip_through_json() -> None:
    """model_dump → JSON → model_validate must be lossless for v1 payloads."""
    intent = ProjectDesignIntent.model_validate(V1_INTENT_JSON)
    dumped = json.loads(json.dumps(intent.model_dump()))
    restored = ProjectDesignIntent.model_validate(dumped)
    assert restored == intent


# ---------------------------------------------------------------------------
# v2 full round-trip
# ---------------------------------------------------------------------------


def test_v2_json_loads_correctly() -> None:
    payload = {**V1_INTENT_JSON, **V2_EXTRA_FIELDS}
    intent = ProjectDesignIntent.model_validate(payload)

    assert len(intent.power_rails) == 1
    rail = intent.power_rails[0]
    assert rail.name == "+3V3"
    assert rail.voltage_v == pytest.approx(3.3)
    assert rail.current_max_a == pytest.approx(1.0)

    assert len(intent.interfaces) == 1
    iface = intent.interfaces[0]
    assert iface.kind == "usb2"
    assert iface.differential is True
    assert iface.impedance_target_ohm == pytest.approx(90.0)

    assert intent.mechanical.max_height_mm == pytest.approx(8.0)
    assert len(intent.mechanical.connector_placement) == 1

    assert len(intent.compliance) == 2
    assert {c.kind for c in intent.compliance} == {"fcc_b", "ce_emc"}

    assert intent.cost.unit_cost_usd_max == pytest.approx(15.0)
    assert intent.cost.volume_units == 1000

    assert intent.thermal.ambient_c == pytest.approx(25.0)


def test_v2_round_trip() -> None:
    payload = {**V1_INTENT_JSON, **V2_EXTRA_FIELDS}
    intent = ProjectDesignIntent.model_validate(payload)
    normalised = _normalize_design_intent(intent)
    dumped = json.loads(json.dumps(normalised.model_dump()))
    restored = ProjectDesignIntent.model_validate(dumped)
    assert restored == normalised


# ---------------------------------------------------------------------------
# Sub-model validation
# ---------------------------------------------------------------------------


def test_power_rail_spec_valid() -> None:
    rail = PowerRailSpec(name="+5V", voltage_v=5.0, current_max_a=2.0)
    assert rail.tolerance_pct == pytest.approx(5.0)
    assert rail.decoupling_strategy == ""


def test_power_rail_spec_invalid_voltage() -> None:
    with pytest.raises(ValidationError):
        PowerRailSpec(name="+5V", voltage_v=-1.0, current_max_a=1.0)


def test_power_rail_spec_invalid_current() -> None:
    with pytest.raises(ValidationError):
        PowerRailSpec(name="+5V", voltage_v=5.0, current_max_a=0.0)


def test_interface_spec_usb2_defaults() -> None:
    iface = InterfaceSpec(kind="usb2")
    assert iface.differential is False
    assert iface.impedance_target_ohm is None
    assert iface.length_match_tolerance_mm == pytest.approx(5.0)


def test_interface_spec_invalid_kind() -> None:
    with pytest.raises(ValidationError):
        InterfaceSpec(kind="unknownprotocol")


def test_mechanical_constraint_defaults() -> None:
    mc = MechanicalConstraint()
    assert mc.mount_holes == []
    assert mc.max_height_mm is None


def test_mount_hole_spec() -> None:
    hole = MountHoleSpec(x_mm=10.0, y_mm=5.0, diameter_mm=3.2)
    assert hole.label == ""


def test_compliance_target_valid_kind() -> None:
    ct = ComplianceTarget(kind="automotive_aec_q100")
    assert ct.notes == ""


def test_compliance_target_invalid_kind() -> None:
    with pytest.raises(ValidationError):
        ComplianceTarget(kind="iso_9001")


def test_cost_target_defaults() -> None:
    ct = CostTarget()
    assert ct.unit_cost_usd_max is None
    assert ct.volume_units == 1


def test_thermal_envelope_defaults() -> None:
    te = ThermalEnvelope()
    assert te.ambient_c == pytest.approx(25.0)
    assert te.max_component_c == pytest.approx(85.0)
    assert te.airflow == "natural"


# ---------------------------------------------------------------------------
# _normalize_design_intent preserves v1 deduplication logic
# ---------------------------------------------------------------------------


def test_normalize_deduplicates_connector_refs() -> None:
    intent = ProjectDesignIntent(
        connector_refs=["J1", "j1", "J2", "J1"],
    )
    normalised = _normalize_design_intent(intent)
    assert normalised.connector_refs == ["J1", "J2"]


def test_normalize_strips_whitespace_from_refs() -> None:
    intent = ProjectDesignIntent(
        critical_nets=["  USB_DP  ", "USB_DM"],
    )
    normalised = _normalize_design_intent(intent)
    assert normalised.critical_nets == ["USB_DP", "USB_DM"]
