"""Pydantic models for export and project operations."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class SetProjectInput(BaseModel):
    """Project activation parameters."""

    project_dir: Path
    pcb_file: Path | None = None
    sch_file: Path | None = None
    output_dir: Path | None = None


class ExportGerberInput(BaseModel):
    """Gerber export options."""

    output_subdir: str = Field(default="gerber", min_length=1, max_length=120)
    layers: list[str] = Field(default_factory=list)


class ExportBOMInput(BaseModel):
    """BOM export options."""

    format: Literal["csv", "xml"] = "csv"


class ExportNetlistInput(BaseModel):
    """Netlist export options."""

    format: Literal["kicad", "spice", "cadstar", "orcadpcb2"] = "kicad"


class ExportPdfInput(BaseModel):
    """PDF export options."""

    layers: list[str] = Field(default_factory=list)


class ExportRenderInput(BaseModel):
    """3D render export options."""

    output_file: str = Field(default="render.png", min_length=1, max_length=240)
    side: Literal["top", "bottom", "front", "back", "left", "right"] = "top"
    zoom: float = Field(default=1.0, gt=0.05, le=20.0)
    width: int | None = Field(default=None, ge=64, le=8192)
    height: int | None = Field(default=None, ge=64, le=8192)
    quality: float | None = Field(default=None, ge=0.0, le=1.0)
    preset: str | None = None
    use_board_stackup_colors: bool = False
    floor: bool = True
    perspective: bool = True
    pan_x: float | None = None
    pan_y: float | None = None
    rotate_x: float | None = None
    rotate_y: float | None = None
    rotate_z: float | None = None
    light_top: float | None = Field(default=None, ge=0.0, le=1.0)
    light_bottom: float | None = Field(default=None, ge=0.0, le=1.0)
    light_side: float | None = Field(default=None, ge=0.0, le=1.0)
    light_camera: float | None = Field(default=None, ge=0.0, le=1.0)
    light_side_elevation: float | None = None
