"""Component derating and approved-vendor (AVL) checks (work order P4-T3).

Derating keeps a part operating below its absolute ratings for reliability — e.g. a
ceramic capacitor used at <=80% of its rated voltage. These are conservative,
general-practice factors (widely used industry rules of thumb), NOT a specific
MIL-HDBK-217 / IPC mandate; the verdict says so. AVL enforcement flags a selected
part whose manufacturer is not on the project's approved-vendor list.

Pure and KiCad-free so it is unit-testable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ComplianceVerdict = Literal["PASS", "WARN", "FAIL"]

# kind -> parameter -> maximum utilization (operating / rated) allowed by derating.
# Conservative general-practice values; document them as such, not a named standard.
DERATING_POLICY: dict[str, dict[str, float]] = {
    "capacitor": {"voltage": 0.80},
    "resistor": {"power": 0.60},
    "inductor": {"current": 0.80},
    "mosfet": {"vds": 0.80, "id": 0.80},
    "diode": {"vr": 0.80, "if": 0.80},
    "led": {"if": 0.80},
    "connector": {"current": 0.80},
    "regulator": {"power": 0.70, "current": 0.80},
}

_WARN_BAND = 0.90  # within 90% of the derating limit -> WARN (approaching)


@dataclass
class DeratingResult:
    verdict: ComplianceVerdict
    utilization: float
    limit: float
    summary: str


def derating_check(
    kind: str,
    parameter: str,
    rated_value: float,
    operating_value: float,
    *,
    policy: dict[str, dict[str, float]] | None = None,
) -> DeratingResult:
    """Check operating value against the derating limit for a component parameter."""
    policy = policy or DERATING_POLICY
    kind_key = kind.strip().casefold()
    parameter_key = parameter.strip().casefold()
    limits = policy.get(kind_key)
    if limits is None or parameter_key not in limits:
        known = ", ".join(f"{k}:{'/'.join(v)}" for k, v in policy.items())
        raise ValueError(f"No derating policy for {kind!r}/{parameter!r}. Known: {known}")
    if rated_value <= 0:
        raise ValueError("rated_value must be positive.")
    if operating_value < 0:
        raise ValueError("operating_value must not be negative.")

    limit = limits[parameter_key]
    utilization = operating_value / rated_value
    if utilization > 1.0:
        verdict: ComplianceVerdict = "FAIL"
        summary = (
            f"{kind} {parameter}: operating {operating_value:g} EXCEEDS absolute rating "
            f"{rated_value:g} (utilization {utilization:.0%}) — overstress."
        )
    elif utilization > limit:
        verdict = "FAIL"
        summary = (
            f"{kind} {parameter}: utilization {utilization:.0%} exceeds the {limit:.0%} "
            "derating limit — reliability risk; pick a higher-rated part."
        )
    elif utilization > limit * _WARN_BAND:
        verdict = "WARN"
        summary = (
            f"{kind} {parameter}: utilization {utilization:.0%} is close to the {limit:.0%} "
            "derating limit — little margin."
        )
    else:
        verdict = "PASS"
        summary = (
            f"{kind} {parameter}: utilization {utilization:.0%} is within the {limit:.0%} "
            "derating limit."
        )
    return DeratingResult(verdict=verdict, utilization=utilization, limit=limit, summary=summary)


def avl_check(manufacturer: str, approved_vendors: list[str]) -> tuple[ComplianceVerdict, str]:
    """Check a part's manufacturer against the approved-vendor list."""
    if not approved_vendors:
        return ("WARN", "No approved-vendor list configured — AVL not enforced.")
    if not manufacturer.strip():
        return ("WARN", "Part has no manufacturer to check against the AVL.")
    needle = manufacturer.strip().casefold()
    for vendor in approved_vendors:
        candidate = vendor.strip().casefold()
        if candidate and (candidate in needle or needle in candidate):
            return ("PASS", f"{manufacturer} is on the approved-vendor list.")
    return (
        "FAIL",
        f"{manufacturer} is NOT on the approved-vendor list ({', '.join(approved_vendors)}).",
    )


def _worst(*verdicts: ComplianceVerdict) -> ComplianceVerdict:
    if "FAIL" in verdicts:
        return "FAIL"
    if "WARN" in verdicts:
        return "WARN"
    return "PASS"
