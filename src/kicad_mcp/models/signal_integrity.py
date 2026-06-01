"""Pydantic models for signal-integrity calculations and board analysis."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field

TraceType = Literal["microstrip", "stripline", "coplanar"]
ManufacturerName = Literal["JLCPCB", "PCBWay", "Generic"]
CoordMM = Annotated[
    float,
    Field(ge=-2000.0, le=2000.0, description="Coordinate in millimeters."),
]


class TraceImpedanceInput(BaseModel):
    """Single-ended trace impedance request."""

    width_mm: float = Field(gt=0.0, le=25.0)
    height_mm: float = Field(gt=0.0, le=10.0)
    er: float = Field(default=4.2, gt=1.0, le=20.0)
    trace_type: TraceType = Field(default="microstrip")
    copper_oz: float = Field(default=1.0, gt=0.1, le=10.0)
    spacing_mm: float = Field(
        default=0.2,
        ge=0.0,
        le=25.0,
        description="Ground gap or edge-coupled spacing when applicable.",
    )


class TraceWidthForImpedanceInput(BaseModel):
    """Width synthesis request for a target impedance."""

    target_ohm: float = Field(gt=1.0, le=200.0)
    height_mm: float = Field(gt=0.0, le=10.0)
    er: float = Field(default=4.2, gt=1.0, le=20.0)
    trace_type: TraceType = Field(default="microstrip")
    copper_oz: float = Field(default=1.0, gt=0.1, le=10.0)
    spacing_mm: float = Field(default=0.2, ge=0.0, le=25.0)


class DifferentialPairSkewInput(BaseModel):
    """Differential-pair skew analysis request."""

    net_p: str = Field(min_length=1, max_length=200)
    net_n: str = Field(min_length=1, max_length=200)
    er: float = Field(default=4.2, gt=1.0, le=20.0)
    trace_type: TraceType = Field(default="microstrip")


class LengthMatchingInput(BaseModel):
    """Length-matching validation request."""

    net_groups: list[list[str]] = Field(min_length=1)
    tolerance_mm: float = Field(default=2.0, ge=0.0, le=1000.0)


class StackupInput(BaseModel):
    """Stackup recommendation request."""

    layer_count: Literal[2, 4, 6] = Field(default=4)
    target_impedance_ohm: float = Field(default=50.0, gt=1.0, le=200.0)
    manufacturer: ManufacturerName = Field(default="JLCPCB")
    er: float = Field(default=4.2, gt=1.0, le=20.0)
    copper_oz: float = Field(default=1.0, gt=0.1, le=10.0)


class ViaStubInput(BaseModel):
    """Via-stub analysis request."""

    via_positions: list[tuple[CoordMM, CoordMM]] = Field(default_factory=list)
    frequency_ghz: float = Field(gt=0.0, le=1000.0)
    er: float = Field(default=4.0, gt=1.0, le=20.0)


class DecouplingPlacementInput(BaseModel):
    """Decoupling placement heuristic request."""

    ic_ref: str = Field(min_length=1, max_length=200)
    power_pin: str = Field(min_length=1, max_length=200)
    target_freq_mhz: float = Field(gt=0.0, le=100_000.0)
