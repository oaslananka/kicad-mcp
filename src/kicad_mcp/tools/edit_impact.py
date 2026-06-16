"""Edit-impact analysis for first-class edit/ingest mode (work order P4-T4).

When an existing board is edited, you do not want to blindly re-run every gate.
This module computes a *semantic diff* between two design-intent snapshots and maps
each change to the gates it can affect, so a caller can re-run only the impacted
gates and assert the rest are preserved.

Pure and KiCad-free so it is unit-testable; the live ``project_assess_edit_impact``
tool supplies the before/after intent dicts.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

# Every gate category the project gate can produce. "Preserved" = ALL − affected.
ALL_GATES: tuple[str, ...] = (
    "schematic",
    "connectivity",
    "signal_integrity",
    "power",
    "thermal",
    "pcb",
    "manufacturing",
    "dfm",
    "emc",
)

# Which gates a change in each intent category can invalidate.
_CATEGORY_GATES: dict[str, tuple[str, ...]] = {
    "critical_nets": ("signal_integrity", "connectivity", "pcb"),
    "interfaces": ("signal_integrity", "connectivity", "pcb"),
    "power": ("power", "pcb"),
    "thermal": ("thermal", "pcb"),
    "compliance": ("emc", "manufacturing"),
    "manufacturer": ("manufacturing", "dfm"),
}

# (intent field, category, identity-key-for-dicts-or-None-for-scalars-or-"*"-for-str-lists)
_LIST_STR_FIELDS = (
    ("critical_nets", "critical_nets"),
    ("power_tree_refs", "power"),
    ("thermal_hotspots", "thermal"),
)
_LIST_DICT_FIELDS = (
    ("power_rails", "power"),
    ("interfaces", "interfaces"),
    ("compliance", "compliance"),
)
_SCALAR_FIELDS = (
    ("manufacturer", "manufacturer"),
    ("manufacturer_tier", "manufacturer"),
)


@dataclass(frozen=True)
class IntentChange:
    category: str
    kind: str  # "added" | "removed" | "modified"
    detail: str


@dataclass
class ImpactReport:
    changes: list[IntentChange] = field(default_factory=list)
    affected_gates: list[str] = field(default_factory=list)
    preserved_gates: list[str] = field(default_factory=list)
    summary: str = ""


def _identity(item: object) -> str:
    if isinstance(item, dict):
        for key in ("name", "standard", "ref", "net"):
            value = item.get(key)
            if value:
                return str(value)
        return json.dumps(item, sort_keys=True)
    return str(item)


def _diff_collection(category: str, before: list[Any], after: list[Any]) -> list[IntentChange]:
    before_by_id = {_identity(item): item for item in before}
    after_by_id = {_identity(item): item for item in after}
    changes: list[IntentChange] = []
    for ident in sorted(set(after_by_id) - set(before_by_id)):
        changes.append(IntentChange(category, "added", ident))
    for ident in sorted(set(before_by_id) - set(after_by_id)):
        changes.append(IntentChange(category, "removed", ident))
    for ident in sorted(set(before_by_id) & set(after_by_id)):
        if before_by_id[ident] != after_by_id[ident]:
            changes.append(IntentChange(category, "modified", ident))
    return changes


def semantic_intent_diff(before: dict[str, Any], after: dict[str, Any]) -> list[IntentChange]:
    """Return the structured semantic changes between two design-intent dicts."""
    changes: list[IntentChange] = []
    for field_name, category in (*_LIST_STR_FIELDS, *_LIST_DICT_FIELDS):
        changes.extend(
            _diff_collection(
                category,
                list(before.get(field_name) or []),
                list(after.get(field_name) or []),
            )
        )
    for field_name, category in _SCALAR_FIELDS:
        before_value = str(before.get(field_name) or "")
        after_value = str(after.get(field_name) or "")
        if before_value != after_value:
            detail = f"{field_name}: {before_value!r} -> {after_value!r}"
            changes.append(IntentChange(category, "modified", detail))
    return changes


def impact_of_changes(changes: list[IntentChange]) -> ImpactReport:
    """Map semantic changes to the gates that must be re-run vs. preserved."""
    affected: set[str] = set()
    for change in changes:
        affected.update(_CATEGORY_GATES.get(change.category, ()))
    affected_gates = [gate for gate in ALL_GATES if gate in affected]
    preserved_gates = [gate for gate in ALL_GATES if gate not in affected]
    if not changes:
        summary = "No semantic intent changes — every previously-passing gate is preserved."
    else:
        summary = (
            f"{len(changes)} change(s) impact {len(affected_gates)} gate(s); "
            f"{len(preserved_gates)} gate(s) preserved (no re-run needed)."
        )
    return ImpactReport(
        changes=list(changes),
        affected_gates=affected_gates,
        preserved_gates=preserved_gates,
        summary=summary,
    )


def render_impact_report(report: ImpactReport) -> str:
    """Render the impact report as a human-readable text block."""
    lines = ["Edit-impact analysis:", f"- {report.summary}", "", "Changes:"]
    if report.changes:
        for change in report.changes:
            lines.append(f"  [{change.kind}] {change.category}: {change.detail}")
    else:
        lines.append("  (none)")
    lines.append("")
    lines.append(f"Gates to re-run: {', '.join(report.affected_gates) or '(none)'}")
    lines.append(f"Gates preserved: {', '.join(report.preserved_gates) or '(none)'}")
    return "\n".join(lines)
