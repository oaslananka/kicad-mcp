"""Pydantic models for simulation operations."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SimulationBaseInput(BaseModel):
    """Common simulation input parameters."""

    netlist_path: str = Field(default="", max_length=1000)
    probe_nets: list[str] = Field(default_factory=list, max_length=32)


class OperatingPointInput(SimulationBaseInput):
    """Operating-point analysis parameters."""


class ACAnalysisInput(SimulationBaseInput):
    """Small-signal AC analysis parameters."""

    start_freq_hz: float = Field(gt=0.0, le=1.0e15)
    stop_freq_hz: float = Field(gt=0.0, le=1.0e15)
    points_per_decade: int = Field(default=20, ge=1, le=2000)


class TransientAnalysisInput(SimulationBaseInput):
    """Transient analysis parameters."""

    stop_time_s: float = Field(gt=0.0, le=1.0e9)
    step_time_s: float = Field(gt=0.0, le=1.0e9)


class DCSweepInput(SimulationBaseInput):
    """DC sweep analysis parameters."""

    source_ref: str = Field(min_length=1, max_length=120)
    start_v: float = Field(ge=-1.0e9, le=1.0e9)
    stop_v: float = Field(ge=-1.0e9, le=1.0e9)
    step_v: float = Field(gt=0.0, le=1.0e9)


class StabilityCheckInput(BaseModel):
    """Closed-loop stability check parameters."""

    output_net: str = Field(min_length=1, max_length=240)
    feedback_net: str = Field(min_length=1, max_length=240)
    start_freq_hz: float = Field(default=10.0, gt=0.0, le=1.0e15)
    stop_freq_hz: float = Field(default=1.0e7, gt=0.0, le=1.0e15)
    points_per_decade: int = Field(default=20, ge=1, le=2000)
    netlist_path: str = Field(default="", max_length=1000)


class SpiceDirectiveInput(BaseModel):
    """Persisted MCP simulation directive parameters."""

    directive: str = Field(min_length=1, max_length=4000)


class SpiceModelAssignmentInput(BaseModel):
    """Assign SPICE model properties to a symbol in the schematic."""

    reference: str = Field(
        min_length=1,
        max_length=120,
        description="Component reference designator (e.g. U1, Q1, D3).",
    )
    model_name: str = Field(
        default="",
        max_length=240,
        description="SPICE model name assigned to Sim.Name.",
    )
    library: str = Field(
        default="",
        max_length=500,
        description="SPICE library path or name assigned to Sim.Library.",
    )
    model_type: str = Field(
        default="",
        max_length=60,
        description="Device sub-type (e.g. op-amp, comparator) assigned to Sim.Type.",
    )
    pins: str = Field(
        default="",
        max_length=500,
        description="Pin map string assigned to Sim.Pins.",
    )
    params: str = Field(
        default="",
        max_length=2000,
        description="Instance parameters assigned to Sim.Params.",
    )
    enabled: bool | None = Field(
        default=None,
        description="Sim.Enabled override (None leaves unchanged).",
    )


class SpiceLibraryEntry(BaseModel):
    """A SPICE model library entry in the KiCad project file."""

    name: str = Field(min_length=1, max_length=240)
    uri: str = Field(min_length=1, max_length=1000)
