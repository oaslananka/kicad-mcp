"""Structured verdict report for high-traffic gate/check tools (work order P1-T4).

A ``VerdictReport`` carries both a human-readable ``text`` block (kept for clients that
only read text) and structured fields an agent can act on without parsing English:
a PASS/WARN/FAIL ``verdict``, a list of ``findings`` with stable, diffable IDs and an
optional ``suggested_fix``, and a ``next_action``. FastMCP returns the model as MCP
structured content alongside the JSON text, so both surfaces stay in sync.
"""

from __future__ import annotations

import hashlib
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

Verdict = Literal["PASS", "WARN", "FAIL"]

_FAIL_SEVERITIES = frozenset({"error", "fail", "failed", "critical"})
_WARN_SEVERITIES = frozenset({"warning", "warn", "marginal"})


def stable_finding_id(*parts: object) -> str:
    """Return a deterministic, diffable short id from rule + location parts.

    The id is a hash of the supplied parts (typically a rule/type and a location or
    description), so the same finding keeps the same id across runs — letting an agent
    prove a fix worked by diffing finding ids rather than re-reading prose.
    """
    raw = "|".join(str(part) for part in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]


class SuggestedFix(BaseModel):
    """A concrete, machine-actionable next step for a finding."""

    model_config = ConfigDict(frozen=True)

    tool: str = ""
    args: dict[str, Any] = Field(default_factory=dict)


class Finding(BaseModel):
    """A single structured finding with a stable id."""

    model_config = ConfigDict(frozen=True)

    id: str
    severity: str = "error"
    location: str = ""
    description: str = ""
    suggested_fix: SuggestedFix | None = None


class VerdictReport(BaseModel):
    """Verdict triplet returned by high-traffic gate/check tools."""

    model_config = ConfigDict(frozen=False)

    # Human-readable rendering, preserved alongside the structured fields so text-only
    # clients keep working. FastMCP serializes the whole model to JSON text content.
    text: str = ""
    summary: str = ""
    verdict: Verdict = "PASS"
    findings: list[Finding] = Field(default_factory=list)
    next_action: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)

    @staticmethod
    def verdict_for(severities: list[str]) -> Verdict:
        """Aggregate a verdict from finding severities (FAIL > WARN > PASS)."""
        lowered = {str(severity).casefold() for severity in severities}
        if lowered & _FAIL_SEVERITIES:
            return "FAIL"
        if lowered & _WARN_SEVERITIES:
            return "WARN"
        return "PASS"
