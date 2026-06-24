"""Shared validation gate data structures."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

GateStatus = Literal["PASS", "FAIL", "BLOCKED", "EMPTY", "WARN"]


@dataclass(slots=True)
class GateOutcome:
    """Structured status for a validation gate."""

    name: str
    status: GateStatus
    summary: str
    details: list[str] = field(default_factory=list)


def _combined_status(outcomes: list[GateOutcome]) -> GateStatus:
    statuses = {outcome.status for outcome in outcomes}
    if "EMPTY" in statuses:
        return "EMPTY"
    if "BLOCKED" in statuses:
        return "BLOCKED"
    if "FAIL" in statuses:
        return "FAIL"
    if "WARN" in statuses:
        return "WARN"
    return "PASS"
