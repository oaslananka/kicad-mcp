"""Semantic EDA Intermediate Representation (IR).

The IR provides an agent-friendly structured description of a KiCad circuit
design.  It decouples "what the circuit is" (components, nets, pin roles,
power domains, interfaces) from "how KiCad stores it" (geometry, UUIDs, file
format).

Modules
-------
circuit_ir : Core data model (IRCircuit, IRComponent, IRPin, IRNet, …)
from_kicad : KiCad ``.kicad_sch`` → IR parser
to_kicad   : IR → KiCad ``.kicad_sch`` serializer  (planned)
diff       : Semantic IR differ
lint       : IR-invariant lint rules
"""

from __future__ import annotations

from .circuit_ir import (
    IRCircuit,
    IRComponent,
    IRConstraint,
    IRInterface,
    IRNet,
    IRPin,
    IRPowerRail,
    PinElectricalType,
    PinRole,
)
from .diff import IRDiff, IRDiffKind, circuit_diff, render_diff, render_diff_summary
from .from_kicad import parse_schematic as parse_schematic_to_ir
from .lint import IRLintFinding, IRLintSeverity, lint_circuit

__all__ = [
    "IRCircuit",
    "IRComponent",
    "IRConstraint",
    "IRInterface",
    "IRNet",
    "IRPin",
    "IRPowerRail",
    "PinElectricalType",
    "PinRole",
    # from_kicad
    "parse_schematic_to_ir",
    # diff
    "IRDiff",
    "IRDiffKind",
    "circuit_diff",
    "render_diff",
    "render_diff_summary",
    # lint
    "IRLintFinding",
    "IRLintSeverity",
    "lint_circuit",
]
