"""Shared project design-intent models and resolver hook."""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal

from pydantic import BaseModel, Field

from ..models.intent import (
    ComplianceTarget,
    CostTarget,
    InterfaceSpec,
    MechanicalConstraint,
    PowerRailSpec,
    ThermalEnvelope,
)

ProjectSpecSource = Literal["project_spec", "legacy_design_intent", "none"]


class DecouplingPairIntent(BaseModel):
    """Intent describing which capacitors should stay close to an IC."""

    ic_ref: str = Field(min_length=1, max_length=50)
    cap_refs: list[str] = Field(min_length=1, max_length=20)
    max_distance_mm: float = Field(default=3.0, gt=0.0, le=50.0)


class RFKeepoutIntent(BaseModel):
    """Intent describing an RF-sensitive keepout area."""

    name: str = Field(default="RF Keepout", min_length=1, max_length=100)
    x_mm: float
    y_mm: float
    w_mm: float = Field(gt=0.0, le=5000.0)
    h_mm: float = Field(gt=0.0, le=5000.0)
    frequency_mhz: float | None = Field(default=None, gt=0.0, le=300_000.0)


class ProjectDesignIntent(BaseModel):
    """Persisted high-level design intent used by validation and workflow tools."""

    connector_refs: list[str] = Field(default_factory=list)
    decoupling_pairs: list[DecouplingPairIntent] = Field(default_factory=list)
    critical_nets: list[str] = Field(default_factory=list)
    power_tree_refs: list[str] = Field(default_factory=list)
    analog_refs: list[str] = Field(default_factory=list)
    digital_refs: list[str] = Field(default_factory=list)
    sensor_cluster_refs: list[str] = Field(default_factory=list)
    rf_keepout_regions: list[RFKeepoutIntent] = Field(default_factory=list)
    manufacturer: str = Field(default="")
    manufacturer_tier: str = Field(default="")
    functional_spacing_mm: float = Field(default=5.0, ge=0.0, le=100.0)
    thermal_hotspots: list[str] = Field(default_factory=list)
    critical_frequencies_mhz: list[float] = Field(default_factory=list)
    power_rails: list[PowerRailSpec] = Field(
        default_factory=list,
        description="Voltage rails with current budgets, tolerance, and decoupling strategy.",
    )
    interfaces: list[InterfaceSpec] = Field(
        default_factory=list,
        description="High-speed or protocol-critical interface specifications.",
    )
    mechanical: MechanicalConstraint = Field(
        default_factory=MechanicalConstraint,
        description="Board-level mechanical constraints (outline, mount holes, connector edges).",
    )
    compliance: list[ComplianceTarget] = Field(
        default_factory=list,
        description="Regulatory compliance targets (FCC, CE, UL, automotive, medical).",
    )
    cost: CostTarget = Field(
        default_factory=CostTarget,
        description="Unit-cost and NRE budget constraints.",
    )
    thermal: ThermalEnvelope = Field(
        default_factory=ThermalEnvelope,
        description="Thermal operating-environment specification.",
    )


ProjectDesignSpec = ProjectDesignIntent


class ProjectSpecResolution(BaseModel):
    """Combined explicit and inferred design-spec view for agent workflows."""

    source: ProjectSpecSource = "none"
    path: str = ""
    explicit: ProjectDesignSpec = Field(default_factory=ProjectDesignSpec)
    inferred: ProjectDesignSpec = Field(default_factory=ProjectDesignSpec)
    resolved: ProjectDesignSpec = Field(default_factory=ProjectDesignSpec)
    notes: list[str] = Field(default_factory=list)


_resolver: Callable[[], ProjectSpecResolution] | None = None


def set_design_intent_resolver(resolver: Callable[[], ProjectSpecResolution]) -> None:
    global _resolver
    _resolver = resolver


def resolve_design_intent() -> ProjectSpecResolution:
    if _resolver is not None:
        return _resolver()
    return ProjectSpecResolution(notes=["Project design-intent resolver is not registered."])
