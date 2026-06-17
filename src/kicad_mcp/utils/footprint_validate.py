"""IPC-7351B footprint validation (work order P4-T3).

Checks an existing two-terminal chip footprint's land geometry against the
IPC-7351B nominal computed by :func:`footprint_gen.chip_pad_geometry` — the same
math the generator uses, so a footprint is validated against exactly what we would
have produced. Gross deviation fails (a hard gate), minor deviation warns.

Scope is honest: this validates chip passives (0201–2512) against the IPC-7351B
*standard* nominal. It is not a datasheet-specific land-pattern check (that needs
the part's recommended pattern) and does not yet cover SOIC/QFP/QFN/BGA.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

from .footprint_gen import DensityLevel, chip_pad_geometry

FootprintVerdict = Literal["PASS", "WARN", "FAIL"]

# A pad whose width/height/pitch is off by more than this many mm is a hard fail;
# between the tolerance and this it is a warning.
_DEFAULT_TOL_MM = 0.12
_FAIL_MULTIPLIER = 2.0

_PAD_RE = re.compile(
    r"\(pad\s+\"?(?P<num>[^\s\"]+)\"?\s+smd\s+\w+\s+"
    r"\(at\s+(?P<x>-?\d+(?:\.\d+)?)\s+(?P<y>-?\d+(?:\.\d+)?)(?:\s+-?\d+(?:\.\d+)?)?\s*\)\s+"
    r"\(size\s+(?P<w>\d+(?:\.\d+)?)\s+(?P<h>\d+(?:\.\d+)?)\s*\)",
)


@dataclass(frozen=True)
class ParsedPad:
    num: str
    x: float
    y: float
    w: float
    h: float


@dataclass
class FootprintCheck:
    verdict: FootprintVerdict
    summary: str
    findings: list[str] = field(default_factory=list)


def parse_smd_pads(footprint_text: str) -> list[ParsedPad]:
    """Extract SMD rectangular/roundrect/oval pads from .kicad_mod text."""
    pads: list[ParsedPad] = []
    for match in _PAD_RE.finditer(footprint_text):
        pads.append(
            ParsedPad(
                num=match.group("num"),
                x=float(match.group("x")),
                y=float(match.group("y")),
                w=float(match.group("w")),
                h=float(match.group("h")),
            )
        )
    return pads


def validate_chip_footprint(
    size_code: str,
    pads: list[ParsedPad],
    *,
    density: DensityLevel = "B",
    tol_mm: float = _DEFAULT_TOL_MM,
) -> FootprintCheck:
    """Validate a two-terminal chip footprint against its IPC-7351B nominal."""
    nominal = chip_pad_geometry(size_code, density)
    findings: list[str] = []
    fail_tol = tol_mm * _FAIL_MULTIPLIER
    worst: float = 0.0

    if len(pads) != 2:
        return FootprintCheck(
            verdict="FAIL",
            summary=(
                f"Expected 2 SMD pads for chip {size_code}, found {len(pads)}. "
                "Not a recognizable two-terminal chip land pattern."
            ),
            findings=[f"pad count {len(pads)} != 2"],
        )

    def _check(label: str, actual: float, nominal_value: float) -> None:
        nonlocal worst
        deviation = abs(actual - nominal_value)
        worst = max(worst, deviation)
        if deviation > tol_mm:
            findings.append(
                f"{label}: {actual:.3f} mm vs IPC nominal {nominal_value:.3f} mm "
                f"(Δ {deviation:.3f} mm)"
            )

    for pad in pads:
        _check(f"pad {pad.num} width", pad.w, nominal.pad_w)
        _check(f"pad {pad.num} height", pad.h, nominal.pad_h)
    measured_pitch = abs(pads[0].x - pads[1].x)
    _check("pad pitch", measured_pitch, nominal.pitch)

    if worst > fail_tol:
        verdict: FootprintVerdict = "FAIL"
        summary = (
            f"Chip {size_code} footprint deviates from IPC-7351B density {density} by "
            f"up to {worst:.3f} mm (> {fail_tol:.3f} mm) — blocking."
        )
    elif findings:
        verdict = "WARN"
        summary = (
            f"Chip {size_code} footprint is within {fail_tol:.3f} mm of IPC-7351B but "
            f"deviates beyond {tol_mm:.3f} mm on some dimensions."
        )
    else:
        verdict = "PASS"
        summary = (
            f"Chip {size_code} footprint matches IPC-7351B density {density} within "
            f"{tol_mm:.3f} mm."
        )
    return FootprintCheck(verdict=verdict, summary=summary, findings=findings)
