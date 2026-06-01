"""Pydantic models for power-integrity and thermal design tools."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class VoltageDropInput(BaseModel):
    """Trace voltage-drop request."""

    current_a: float = Field(gt=0.0, le=1_000.0)
    trace_width_mm: float = Field(gt=0.0, le=100.0)
    trace_length_mm: float = Field(gt=0.0, le=10_000.0)
    copper_oz: float = Field(default=1.0, gt=0.1, le=10.0)


class DecouplingRecommendationInput(BaseModel):
    """Decoupling recommendation request."""

    ic_refs: list[str] = Field(min_length=1)
    vcc_net: str = Field(min_length=1, max_length=200)
    supply_voltage_v: float = Field(gt=0.0, le=1000.0)
    target_ripple_mv: float = Field(default=20.0, gt=0.0, le=1000.0)


class CopperWeightCheckInput(BaseModel):
    """Current-carrying capacity request."""

    net_name: str = Field(min_length=1, max_length=200)
    expected_current_a: float = Field(gt=0.0, le=1_000.0)
    ambient_temp_c: float = Field(default=25.0, ge=-55.0, le=200.0)
    max_temp_rise_c: float = Field(default=10.0, gt=0.0, le=200.0)


class PowerPlaneInput(BaseModel):
    """Power-plane generation request."""

    net_name: str = Field(min_length=1, max_length=200)
    layer: str = Field(min_length=1, max_length=64)
    clearance_mm: float = Field(default=0.5, ge=0.0, le=25.0)


class ThermalViaInput(BaseModel):
    """Thermal via count request."""

    power_w: float | None = Field(default=None, gt=0.0, le=10_000.0)
    package_power_w: float | None = Field(default=None, gt=0.0, le=10_000.0)
    ambient_c: float = Field(default=25.0, ge=-55.0, le=200.0)
    max_junction_c: float = Field(default=125.0, gt=-55.0, le=250.0)
    theta_ja_deg_c_w: float = Field(default=40.0, gt=0.1, le=1_000.0)
    via_diameter_mm: float = Field(default=0.3, gt=0.05, le=5.0)
    thermal_resistance_target: float = Field(default=5.0, gt=0.1, le=1_000.0)


class ThermalPourInput(BaseModel):
    """Copper-pour thermal spreading request."""

    net_name: str = Field(min_length=1, max_length=200)
    expected_power_w: float = Field(gt=0.0, le=10_000.0)
    preferred_layer: Literal["auto", "F_Cu", "B_Cu"] = Field(default="auto")
