"""Validation and design-check tools."""

from __future__ import annotations

import hashlib
import json
import math
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from .. import __version__
from ..config import get_config
from ..connection import KiCadConnectionError, get_board
from ..discovery import get_cli_capabilities
from ..models.component_contracts import find_component_contract
from ..models.verdict import Finding, SuggestedFix, Verdict, VerdictReport, stable_finding_id
from ..utils.dru import (
    SExprNode,
    delete_rule,
    dump_dru,
    find_rule,
    iter_rule_nodes,
    parse_dru,
    upsert_rule,
)
from .export_support import _ensure_output_dir, _get_pcb_file, _get_sch_file, _run_cli_variants
from .gates import GateOutcome, GateStatus, _combined_status
from .metadata import headless_compatible
from .schematic_transfer import _collect_schematic_components, _export_schematic_net_map

if TYPE_CHECKING:
    from .design_intent_state import ProjectDesignIntent


@dataclass(slots=True)
class PlacementAnalysis:
    """Detailed placement scoring used by both the gate and the score tool."""

    footprint_count: int
    board_width_mm: float
    board_height_mm: float
    board_area_mm2: float
    footprint_area_mm2: float
    density_pct: float
    score: int
    hard_failures: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    checked_connectors: int = 0
    checked_decoupling_pairs: int = 0
    checked_keepouts: int = 0
    checked_power_tree_refs: int = 0
    checked_analog_refs: int = 0
    checked_digital_refs: int = 0
    checked_sensor_cluster_refs: int = 0
    critical_net_proxy_mm: float = 0.0
    critical_net_proxy_density: float = 0.0
    checked_thermal_hotspot_refs: int = 0
    thermal_proximity_sum: float = 0.0


class GateOutcomePayload(BaseModel):
    """Machine-readable gate outcome for MCP clients that support structured output."""

    name: str
    status: GateStatus
    summary: str
    details: list[str] = Field(default_factory=list)


class ProjectGateReportPayload(BaseModel):
    """Structured project-quality-gate report."""

    text: str
    status: GateStatus
    summary: str
    outcomes: list[GateOutcomePayload] = Field(default_factory=list)


class PlacementGateReportPayload(BaseModel):
    """Structured placement analysis payload."""

    text: str
    status: GateStatus
    summary: str
    score: int | None = None
    footprint_count: int | None = None
    checked_connectors: int = 0
    checked_decoupling_pairs: int = 0
    checked_keepouts: int = 0
    checked_power_tree_refs: int = 0
    checked_analog_refs: int = 0
    checked_digital_refs: int = 0
    checked_sensor_cluster_refs: int = 0
    critical_net_proxy_mm: float = 0.0
    critical_net_proxy_density: float = 0.0
    checked_thermal_hotspot_refs: int = 0
    thermal_proximity_sum: float = 0.0
    hard_failures: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


def _pcb_transfer_helpers() -> tuple[
    Callable[[], tuple[list[dict[str, Any]], list[str]]],
    Callable[[], tuple[dict[tuple[str, str], str], str]],
]:
    """Return transfer helpers while honoring the legacy pcb monkeypatch path."""
    pcb_module = sys.modules.get("kicad_mcp.tools.pcb")
    if pcb_module is None:
        return _collect_schematic_components, _export_schematic_net_map

    collect = getattr(pcb_module, "_collect_schematic_components", _collect_schematic_components)
    export = getattr(pcb_module, "_export_schematic_net_map", _export_schematic_net_map)
    return cast(Callable[[], tuple[list[dict[str, Any]], list[str]]], collect), cast(
        Callable[[], tuple[dict[tuple[str, str], str], str]],
        export,
    )


def _load_report(path: Path) -> dict[str, object]:
    return cast(dict[str, object], json.loads(path.read_text(encoding="utf-8")))


def _entries(report: dict[str, object], key: str) -> list[dict[str, object]]:
    return cast(list[dict[str, object]], report.get(key, []))


def _normalize_erc_sheet_id(value: object) -> str:
    return str(value or "").strip().strip("/").replace("\\", "/")


def _erc_sheet_matches_any(sheet: dict[str, object], ignored_sheet_ids: set[str]) -> bool:
    if not ignored_sheet_ids:
        return False
    candidates = {
        _normalize_erc_sheet_id(sheet.get("path")),
        _normalize_erc_sheet_id(sheet.get("sheet")),
        _normalize_erc_sheet_id(sheet.get("name")),
        _normalize_erc_sheet_id(sheet.get("file")),
        _normalize_erc_sheet_id(sheet.get("filename")),
    }
    return any(candidate and candidate in ignored_sheet_ids for candidate in candidates)


def _erc_violations(
    report: dict[str, object],
    ignored_sheet_ids: set[str] | None = None,
) -> list[dict[str, object]]:
    ignored = ignored_sheet_ids or set()
    violations = list(_entries(report, "violations"))
    for sheet in cast(list[dict[str, object]], report.get("sheets", [])):
        if _erc_sheet_matches_any(sheet, ignored):
            continue
        violations.extend(cast(list[dict[str, object]], sheet.get("violations", [])))
    return violations


def _type_breakdown(entries: list[dict[str, object]]) -> str:
    counts: dict[str, int] = {}
    for entry in entries:
        issue_type = str(entry.get("type", "unknown"))
        counts[issue_type] = counts.get(issue_type, 0) + 1
    ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return ", ".join(f"{name}={count}" for name, count in ordered[:8])


def _format_violations(title: str, entries: list[dict[str, object]]) -> str:
    if not entries:
        return f"{title}: none"
    lines = [f"{title} ({len(entries)} total):"]
    for entry in entries[: get_config().max_items_per_response]:
        severity = str(entry.get("severity", "?"))
        description = str(entry.get("description", "(no description)"))
        lines.append(f"- [{severity}] {description}")
    return "\n".join(lines)


def _normalize_report_severity(severity: object) -> str:
    normalized = str(severity or "error").casefold()
    if normalized in {"warning", "warn", "marginal"}:
        return "warning"
    return "error"


def _entry_location(entry: dict[str, object], fallback: str) -> str:
    for key in ("uuid", "location", "sheet", "path", "item", "ref", "reference"):
        value = entry.get(key)
        if value:
            return str(value)
    return fallback


def _report_entry_finding(
    source: str,
    entry: dict[str, object],
    *,
    default_severity: str = "error",
    fix_tool: str,
) -> Finding:
    issue_type = str(entry.get("type") or source)
    description = str(entry.get("description") or entry.get("message") or issue_type)
    severity = _normalize_report_severity(entry.get("severity", default_severity))
    location = _entry_location(entry, source)
    return Finding(
        id=stable_finding_id(source, issue_type, location, description),
        severity=severity,
        location=location,
        description=description,
        suggested_fix=SuggestedFix(tool=fix_tool, args={"save_report": True}),
    )


def _gate_status_verdict(status: GateStatus) -> Verdict:
    if status == "PASS":
        return "PASS"
    if status == "EMPTY":
        return "WARN"
    return "FAIL"


def _fix_for_gate(gate_name: str) -> SuggestedFix | None:
    from .fixers import fixers_for_gate

    fixer = next(iter(fixers_for_gate(gate_name)), None)
    if fixer is None:
        return None
    return SuggestedFix(tool=fixer.tool, args=fixer.args)


def _finding_for_gate_detail(outcome: GateOutcome, detail: str) -> Finding:
    cleaned = detail.strip()
    severity = "warning" if outcome.status == "EMPTY" or cleaned.startswith("WARN: ") else "error"
    description = (
        cleaned.removeprefix("FAIL: ").removeprefix("WARN: ").removeprefix("BLOCKED: ").strip()
        or outcome.summary
    )
    return Finding(
        id=stable_finding_id("gate", outcome.name, outcome.status, description),
        severity=severity,
        location=outcome.name,
        description=description,
        suggested_fix=_fix_for_gate(outcome.name),
    )


def _gate_findings(outcome: GateOutcome) -> list[Finding]:
    actionable = [
        detail
        for detail in outcome.details
        if outcome.status != "PASS" or detail.strip().startswith(("FAIL: ", "WARN: ", "BLOCKED: "))
    ]
    if outcome.status != "PASS" and not actionable:
        actionable = [outcome.summary]
    return [_finding_for_gate_detail(outcome, detail) for detail in actionable]


def _gate_report(outcome: GateOutcome) -> VerdictReport:
    findings = _gate_findings(outcome)
    verdict = VerdictReport.verdict_for([finding.severity for finding in findings])
    if verdict == "PASS":
        verdict = _gate_status_verdict(outcome.status)
    next_action = "Proceed to the next gate."
    if outcome.status != "PASS":
        fixer = _fix_for_gate(outcome.name)
        next_action = (
            f"Call {fixer.tool} and re-run this gate."
            if fixer is not None
            else "Inspect this gate and re-run it after remediation."
        )
    return VerdictReport(
        text=_format_gate(outcome),
        summary=outcome.summary,
        verdict=verdict,
        findings=findings,
        next_action=next_action,
        metadata={"gate": outcome.name, "status": outcome.status, "details": outcome.details},
    )


def _drc_report_payload(
    path: Path,
    report: dict[str, object] | None,
    error: str | None,
    *,
    save_report: bool,
) -> VerdictReport:
    if report is None:
        message = f"DRC failed: {error or 'unknown error'}"
        return VerdictReport(
            text=message,
            summary="DRC report is unavailable.",
            verdict="FAIL",
            findings=[
                Finding(
                    id=stable_finding_id("drc", "unavailable", error or "unknown"),
                    severity="error",
                    location=str(path),
                    description=message,
                    suggested_fix=SuggestedFix(tool="run_drc", args={"save_report": True}),
                )
            ],
            next_action="Make kicad-cli/report generation available, then rerun run_drc().",
            metadata={"report_path": str(path), "available": False},
        )

    violations = _entries(report, "violations")
    unconnected = _entries(report, "unconnected_items")
    courtyard = _entries(report, "items_not_passing_courtyard")
    lines = [
        "DRC summary:",
        f"- Violations: {len(violations)}",
        f"- Unconnected items: {len(unconnected)}",
        f"- Courtyard issues: {len(courtyard)}",
    ]
    if violations:
        lines.append(_format_violations("Violations", violations))
    if save_report:
        lines.append(f"Saved report: {path}")
    findings = [_report_entry_finding("drc", entry, fix_tool="run_drc") for entry in violations]
    findings.extend(
        _report_entry_finding(
            "drc.unconnected",
            entry,
            default_severity="error",
            fix_tool="get_unconnected_nets",
        )
        for entry in unconnected
    )
    findings.extend(
        _report_entry_finding(
            "drc.courtyard",
            entry,
            default_severity="error",
            fix_tool="get_courtyard_violations",
        )
        for entry in courtyard
    )
    verdict = VerdictReport.verdict_for([finding.severity for finding in findings])
    return VerdictReport(
        text="\n".join(lines),
        summary=(
            "DRC is clean."
            if verdict == "PASS"
            else f"DRC reported {len(findings)} actionable finding(s)."
        ),
        verdict=verdict,
        findings=findings,
        next_action=(
            "No DRC action required."
            if verdict == "PASS"
            else "Fix DRC findings and rerun run_drc(save_report=True)."
        ),
        metadata={
            "report_path": str(path),
            "available": True,
            "violations": len(violations),
            "unconnected_items": len(unconnected),
            "courtyard_issues": len(courtyard),
        },
    )


def _erc_report_payload(
    path: Path,
    report: dict[str, object] | None,
    error: str | None,
    *,
    save_report: bool,
) -> VerdictReport:
    if report is None:
        message = f"ERC failed: {error or 'unknown error'}"
        return VerdictReport(
            text=message,
            summary="ERC report is unavailable.",
            verdict="FAIL",
            findings=[
                Finding(
                    id=stable_finding_id("erc", "unavailable", error or "unknown"),
                    severity="error",
                    location=str(path),
                    description=message,
                    suggested_fix=SuggestedFix(tool="run_erc", args={"save_report": True}),
                )
            ],
            next_action="Make kicad-cli/report generation available, then rerun run_erc().",
            metadata={"report_path": str(path), "available": False},
        )

    violations = _erc_violations(report)
    lines = ["ERC summary:", f"- Violations: {len(violations)}"]
    if violations:
        lines.append(_format_violations("Violations", violations))
    if save_report:
        lines.append(f"Saved report: {path}")
    findings = [_report_entry_finding("erc", entry, fix_tool="run_erc") for entry in violations]
    verdict = VerdictReport.verdict_for([finding.severity for finding in findings])
    return VerdictReport(
        text="\n".join(lines),
        summary=(
            "ERC is clean."
            if verdict == "PASS"
            else f"ERC reported {len(findings)} actionable finding(s)."
        ),
        verdict=verdict,
        findings=findings,
        next_action=(
            "No ERC action required."
            if verdict == "PASS"
            else "Fix ERC findings and rerun run_erc(save_report=True)."
        ),
        metadata={
            "report_path": str(path),
            "available": True,
            "violations": len(violations),
        },
    )


def _run_drc_report(report_name: str) -> tuple[Path, dict[str, object] | None, str | None]:
    pcb_file = _get_pcb_file()
    out_file = _ensure_output_dir() / report_name

    cfg = get_config()
    capabilities = get_cli_capabilities(cfg.kicad_cli)
    drc_flags: list[str] = []
    if capabilities.supports_drc_severity_all:
        drc_flags.append("--severity-all")
    if capabilities.supports_drc_exit_code_violations:
        drc_flags.append("--exit-code-violations")

    code, _, stderr = _run_cli_variants(
        [
            [
                "pcb",
                "drc",
                "--output",
                str(out_file),
                "--format",
                "json",
                *drc_flags,
                str(pcb_file),
            ],
            [
                "pcb",
                "drc",
                "--input",
                str(pcb_file),
                "--output",
                str(out_file),
                "--format",
                "json",
                *drc_flags,
            ],
        ]
    )
    if not out_file.exists():
        return out_file, None, stderr if code != 0 else "DRC report was not produced."
    return out_file, _load_report(out_file), None


def _run_erc_report(report_name: str) -> tuple[Path, dict[str, object] | None, str | None]:
    sch_file = _get_sch_file()
    out_file = _ensure_output_dir() / report_name
    code, _, stderr = _run_cli_variants(
        [
            [
                "sch",
                "erc",
                "--output",
                str(out_file),
                "--format",
                "json",
                "--severity-all",
                "--exit-code-violations",
                str(sch_file),
            ],
            [
                "sch",
                "erc",
                "--input",
                str(sch_file),
                "--output",
                str(out_file),
                "--format",
                "json",
                "--severity-all",
                "--exit-code-violations",
            ],
        ]
    )
    if not out_file.exists():
        return out_file, None, stderr if code != 0 else "ERC report was not produced."
    return out_file, _load_report(out_file), None


def _format_gate(outcome: GateOutcome) -> str:
    lines = [f"{outcome.name} quality gate: {outcome.status}", f"- {outcome.summary}"]
    for detail in outcome.details:
        lines.append(f"- {detail}")
    return "\n".join(lines)


def _gate_outcome_payload(outcome: GateOutcome) -> GateOutcomePayload:
    return GateOutcomePayload(
        name=outcome.name,
        status=outcome.status,
        summary=outcome.summary,
        details=outcome.details,
    )


def _board_footprint_references() -> tuple[set[str], str, str | None]:
    try:
        return (
            {
                footprint.reference_field.text.value
                for footprint in get_board().get_footprints()
                if footprint.reference_field.text.value
            },
            "IPC",
            None,
        )
    except (KiCadConnectionError, OSError):
        from .board_file import _parse_board_footprint_blocks

        try:
            board_text = _get_pcb_file().read_text(encoding="utf-8", errors="ignore")
        except OSError as exc:
            return set(), "file", str(exc)
        return set(_parse_board_footprint_blocks(board_text)), "file", None


def _footprint_parity_outcome() -> GateOutcome:
    from .schematic import parse_schematic_file, project_schematic_files

    cfg = get_config()
    if cfg.sch_file is None or cfg.pcb_file is None:
        return GateOutcome(
            name="Footprint parity",
            status="BLOCKED",
            summary="Both schematic and PCB files must be configured first.",
        )

    schematic_files = project_schematic_files()
    schematic_refs: set[str] = set()
    for sch_file in schematic_files:
        schematic = parse_schematic_file(sch_file)
        schematic_refs.update(
            str(symbol["reference"])
            for symbol in schematic["symbols"]
            if str(symbol["reference"]).strip()
            and not str(symbol["reference"]).startswith("#")
            and str(symbol["footprint"]).strip()
        )
    board_refs, source, error = _board_footprint_references()
    if error is not None:
        return GateOutcome(
            name="Footprint parity",
            status="BLOCKED",
            summary=f"PCB references were unavailable via {source} mode ({error}).",
        )

    missing_on_board = sorted(schematic_refs - board_refs)
    missing_in_schematic = sorted(board_refs - schematic_refs)
    status: GateStatus = "PASS" if not missing_on_board and not missing_in_schematic else "FAIL"
    details = [
        f"Schematic files scanned: {len(schematic_files)}",
        f"Schematic refs with footprints: {len(schematic_refs)}",
        f"PCB footprint refs ({source}): {len(board_refs)}",
        f"Missing on board: {len(missing_on_board)}",
        f"Missing in schematic: {len(missing_in_schematic)}",
    ]
    if missing_on_board:
        details.append("Missing on board refs: " + ", ".join(missing_on_board[:20]))
    if missing_in_schematic:
        details.append("Missing in schematic refs: " + ", ".join(missing_in_schematic[:20]))
    return GateOutcome(
        name="Footprint parity",
        status=status,
        summary="PCB and schematic references are aligned."
        if status == "PASS"
        else "Schematic and PCB references are out of sync.",
        details=details,
    )


def _evaluate_pcb_transfer_gate() -> GateOutcome:
    from .board_file import _parse_board_footprint_blocks

    collect_schematic_components, export_schematic_net_map = _pcb_transfer_helpers()

    cfg = get_config()
    if cfg.sch_file is None or cfg.pcb_file is None:
        return GateOutcome(
            name="PCB transfer",
            status="BLOCKED",
            summary="Both schematic and PCB files must be configured first.",
        )

    try:
        components, issues = collect_schematic_components()
    except ValueError as exc:
        return GateOutcome(
            name="PCB transfer",
            status="BLOCKED",
            summary=str(exc),
        )
    if issues:
        return GateOutcome(
            name="PCB transfer",
            status="FAIL",
            summary="Schematic component metadata is not stable enough for pad-net transfer.",
            details=issues[:12],
        )

    expected_map, note = export_schematic_net_map()
    if note:
        return GateOutcome(
            name="PCB transfer",
            status="BLOCKED",
            summary=note,
        )
    if not expected_map:
        return GateOutcome(
            name="PCB transfer",
            status="BLOCKED",
            summary="The schematic did not export any named pad nets to compare against the PCB.",
        )

    try:
        board_text = cfg.pcb_file.read_text(encoding="utf-8", errors="ignore")
    except OSError as exc:
        return GateOutcome(
            name="PCB transfer",
            status="BLOCKED",
            summary=f"Could not read the PCB file ({exc}).",
        )

    footprints = _parse_board_footprint_blocks(board_text)
    component_refs = {str(component["reference"]) for component in components}
    missing_refs: list[str] = []
    mismatches: list[str] = []
    matched_pads = 0
    total_expected_pads = 0

    for reference in sorted(component_refs):
        expected_for_ref = sorted(
            (pad_number, net_name)
            for (ref, pad_number), net_name in expected_map.items()
            if ref == reference and net_name
        )
        if not expected_for_ref:
            continue
        entry = footprints.get(reference)
        if entry is None:
            missing_refs.append(reference)
            total_expected_pads += len(expected_for_ref)
            continue

        actual_pad_nets = cast(dict[str, str], entry.get("pad_nets", {}))
        for pad_number, expected_net in expected_for_ref:
            total_expected_pads += 1
            actual_net = actual_pad_nets.get(pad_number, "")
            if not actual_net:
                mismatches.append(f"{reference}.{pad_number}: missing net '{expected_net}' on PCB.")
                continue
            if actual_net != expected_net:
                mismatches.append(
                    f"{reference}.{pad_number}: PCB has '{actual_net}', expected '{expected_net}'."
                )
                continue
            matched_pads += 1

    if total_expected_pads == 0:
        return GateOutcome(
            name="PCB transfer",
            status="BLOCKED",
            summary="No expected named pads were available for transfer comparison.",
        )

    coverage_pct = round((matched_pads / total_expected_pads) * 100, 1)
    status: GateStatus = "PASS" if not missing_refs and not mismatches else "FAIL"
    details = [
        f"Expected named pad nets: {total_expected_pads}",
        f"Matched pad nets on PCB: {matched_pads}",
        f"Transfer coverage: {coverage_pct}%",
        f"Missing footprint refs on PCB: {len(missing_refs)}",
        f"Pad-net mismatches: {len(mismatches)}",
    ]
    if missing_refs:
        details.append("Missing footprint refs: " + ", ".join(missing_refs[:20]))
    details.extend(f"FAIL: {item}" for item in mismatches[:12])
    return GateOutcome(
        name="PCB transfer",
        status=status,
        summary="Named schematic pad nets match the PCB footprint pads."
        if status == "PASS"
        else "Named schematic pad nets did not transfer cleanly to the PCB.",
        details=details,
    )


def _evaluate_schematic_gate() -> GateOutcome:
    from .schematic import _build_connectivity_groups, parse_schematic_file

    _, report, error = _run_erc_report("schematic_quality_gate.json")
    if report is None:
        return GateOutcome(
            name="Schematic",
            status="BLOCKED",
            summary=f"ERC report was unavailable ({error or 'unknown error'}).",
        )

    cfg = get_config()
    ignored_empty_sheets: set[str] = set()
    if cfg.sch_file is not None:
        ignored_empty_sheets = _empty_child_sheet_ids(cfg.sch_file)
    raw_violations = _erc_violations(report)
    violations = _erc_violations(report, ignored_empty_sheets)
    ignored_violation_count = len(raw_violations) - len(violations)
    details = [f"ERC violations: {len(violations)}"]
    if ignored_violation_count:
        details.append(
            f"Ignored empty child-sheet ERC violations: {ignored_violation_count}"
        )
    if cfg.sch_file is not None:
        try:
            data = parse_schematic_file(cfg.sch_file)
            groups = _build_connectivity_groups(cfg.sch_file)
            orphan_groups = [
                group
                for group in groups
                if len(cast(list[dict[str, object]], group["pins"])) == 1
                and not cast(list[str], group["names"])
            ]
            details.extend(
                [
                    f"Symbols: {len(data['symbols'])}",
                    f"Power symbols: {len(data['power_symbols'])}",
                    f"Wires: {len(data['wires'])}",
                    f"Labels: {len(data['labels'])}",
                    f"Connectivity groups: {len(groups)}",
                    f"Unnamed single-pin groups: {len(orphan_groups)}",
                ]
            )
        except (OSError, ValueError) as exc:
            details.append(f"Connectivity summary unavailable ({exc})")

    status: GateStatus = "PASS" if not violations else "FAIL"
    if violations:
        details.append(f"Violation types: {_type_breakdown(violations)}")
    return GateOutcome(
        name="Schematic",
        status=status,
        summary="ERC is clean." if status == "PASS" else "ERC reported blocking issues.",
        details=details,
    )


def _sheet_contracts(sch_file: Path) -> list[dict[str, object]]:
    from ..utils.sexpr import _extract_block, _unescape_sexpr_string

    content = sch_file.read_text(encoding="utf-8", errors="ignore")
    contracts: list[dict[str, object]] = []
    for match in re.finditer(r"\(sheet(?=\s)", content):
        block, _ = _extract_block(content, match.start())
        if not block:
            continue
        name_match = re.search(r'\(property\s+"Sheetname"\s+"((?:\\.|[^"\\])*)"', block)
        file_match = re.search(r'\(property\s+"Sheetfile"\s+"((?:\\.|[^"\\])*)"', block)
        if file_match is None:
            continue
        pin_names = [
            _unescape_sexpr_string(value)
            for value in re.findall(r'\(pin\s+"((?:\\.|[^"\\])*)"\s+\w+', block)
        ]
        contracts.append(
            {
                "name": _unescape_sexpr_string(name_match.group(1))
                if name_match is not None
                else Path(_unescape_sexpr_string(file_match.group(1))).stem,
                "filename": _unescape_sexpr_string(file_match.group(1)),
                "pins": sorted(pin_names),
            }
        )
    return contracts


def _hierarchical_labels(sch_file: Path) -> set[str]:
    from ..utils.sexpr import _unescape_sexpr_string

    content = sch_file.read_text(encoding="utf-8", errors="ignore")
    return {
        _unescape_sexpr_string(match.group(1))
        for match in re.finditer(r'\(hierarchical_label\s+"((?:\\.|[^"\\])*)"', content)
    }


def _empty_child_sheet_ids(top_file: Path) -> set[str]:
    from .schematic import parse_schematic_file

    ignored: set[str] = set()
    try:
        contracts = _sheet_contracts(top_file)
    except OSError:
        return ignored

    for contract in contracts:
        filename = str(contract.get("filename", ""))
        if not filename:
            continue
        child_path = top_file.parent / filename
        if not child_path.exists():
            continue
        try:
            data = parse_schematic_file(child_path)
        except (OSError, RuntimeError, ValueError):
            continue
        item_count = (
            len(cast(list[object], data.get("symbols", [])))
            + len(cast(list[object], data.get("power_symbols", [])))
            + len(cast(list[object], data.get("wires", [])))
            + len(cast(list[object], data.get("labels", [])))
        )
        if item_count != 0:
            continue
        name = str(contract.get("name", ""))
        for candidate in {name, filename, child_path.name, child_path.stem}:
            normalized = _normalize_erc_sheet_id(candidate)
            if normalized:
                ignored.add(normalized)
    return ignored


def _evaluate_schematic_connectivity_gate() -> GateOutcome:
    from .schematic import _build_connectivity_groups, parse_schematic_file

    try:
        top_file = _get_sch_file()
    except ValueError as exc:
        return GateOutcome(
            name="Schematic connectivity",
            status="BLOCKED",
            summary=str(exc),
        )

    pages: list[tuple[str, Path]] = [("Top level", top_file)]
    blocked: list[str] = []
    failures: list[str] = []
    page_summaries: list[str] = []
    try:
        contracts = _sheet_contracts(top_file)
    except OSError as exc:
        return GateOutcome(
            name="Schematic connectivity",
            status="BLOCKED",
            summary=f"Top-level sheet contract data was unavailable ({exc}).",
        )

    for contract in contracts:
        child_path = top_file.parent / str(contract["filename"])
        pages.append((str(contract["name"]), child_path))
        if not child_path.exists():
            blocked.append(f"Child sheet '{contract['name']}' is missing: {child_path.name}.")
            continue
        try:
            child_labels = _hierarchical_labels(child_path)
        except OSError as exc:
            blocked.append(
                f"Child sheet '{contract['name']}' could not be read for contract checks ({exc})."
            )
            continue

        top_pins = set(cast(list[str], contract["pins"]))
        if top_pins != child_labels:
            missing_on_top = sorted(child_labels - top_pins)
            missing_in_child = sorted(top_pins - child_labels)
            mismatch = [f"Hierarchy contract mismatch for '{contract['name']}'."]
            if missing_on_top:
                mismatch.append("top missing " + ", ".join(missing_on_top[:12]))
            if missing_in_child:
                mismatch.append("child missing " + ", ".join(missing_in_child[:12]))
            failures.append("; ".join(mismatch))

    dangling_labels = 0
    zero_wire_pages = 0
    unnamed_single_pin_groups = 0
    isolated_footprint_symbols = 0
    matched_component_contracts = 0
    contract_violations = 0

    for page_name, page_path in pages:
        if not page_path.exists():
            continue
        try:
            data = parse_schematic_file(page_path)
            groups = _build_connectivity_groups(page_path)
        except (OSError, RuntimeError, ValueError) as exc:
            blocked.append(f"{page_name}: connectivity data was unavailable ({exc}).")
            continue

        symbol_count = len(data["symbols"]) + len(data["power_symbols"])
        label_count = len(data["labels"])
        wire_count = len(data["wires"])
        page_summaries.append(
            f"{page_name}: {symbol_count} symbol(s), {label_count} label(s), {wire_count} wire(s)"
        )

        if wire_count == 0 and (symbol_count >= 2 or label_count >= 3):
            zero_wire_pages += 1
            failures.append(
                f"{page_name}: has {symbol_count} symbol(s) and {label_count} label(s) but 0 wires."
            )

        label_only_groups = [
            group
            for group in groups
            if group["names"] and not group["pins"] and len(group["points"]) == 1
        ]
        dangling_labels += len(label_only_groups)
        for group in label_only_groups[:8]:
            failures.append(
                f"{page_name}: unattached label/group at {group['points'][0]} -> "
                + ", ".join(group["names"][:4])
            )

        unnamed_groups = [
            group for group in groups if not group["names"] and len(group["pins"]) == 1
        ]
        unnamed_single_pin_groups += len(unnamed_groups)
        for group in unnamed_groups[:8]:
            pin = cast(dict[str, str], group["pins"][0])
            failures.append(
                f"{page_name}: unnamed single-pin group at {group['points'][0]} -> "
                f"{pin['reference']}:{pin['pin']}"
            )

        for symbol in cast(list[dict[str, object]], data["symbols"]):
            footprint = str(symbol.get("footprint", "")).strip()
            lib_id = str(symbol.get("lib_id", "")).strip()
            if not footprint:
                continue
            reference = str(symbol.get("reference", "")).strip()
            component_contract = find_component_contract(lib_id=lib_id, footprint=footprint)
            if component_contract is not None:
                matched_component_contracts += 1
            relevant_groups = [
                group
                for group in groups
                if any(
                    str(pin["reference"]) == reference
                    for pin in cast(list[dict[str, object]], group["pins"])
                )
            ]
            meaningful = any(group["names"] or len(group["pins"]) > 1 for group in relevant_groups)
            if not meaningful:
                isolated_footprint_symbols += 1
                failures.append(
                    f"{page_name}: {reference} has footprint '{footprint}' but no meaningful "
                    "net/power connectivity."
                )
            if component_contract is None:
                continue
            group_names_upper = {
                str(name).upper()
                for group in relevant_groups
                for name in cast(list[str], group["names"])
            }
            missing_groups = [
                "/".join(options)
                for options in component_contract.required_net_groups
                if not any(option.upper() in group_names_upper for option in options)
            ]
            if missing_groups:
                contract_violations += 1
                failures.append(
                    f"{page_name}: {reference} matched contract '{component_contract.key}' "
                    f"but is missing required nets: {', '.join(missing_groups)}."
                )

    hierarchy_mismatches = sum("Hierarchy contract mismatch" in item for item in failures)
    details = [f"Pages analysed: {len(pages)}"]
    details.extend(page_summaries[:12])
    details.extend(
        [
            f"Dangling label groups: {dangling_labels}",
            f"Zero-wire pages: {zero_wire_pages}",
            f"Unnamed single-pin groups: {unnamed_single_pin_groups}",
            f"Isolated footprint symbols: {isolated_footprint_symbols}",
            f"Hierarchy contract mismatches: {hierarchy_mismatches}",
            f"Matched component contracts: {matched_component_contracts}",
            f"Component contract violations: {contract_violations}",
        ]
    )
    if blocked:
        details.extend(f"BLOCKED: {item}" for item in blocked[:12])
        return GateOutcome(
            name="Schematic connectivity",
            status="BLOCKED",
            summary="Connectivity checks could not complete for every sheet.",
            details=details,
        )
    if failures:
        details.extend(f"FAIL: {item}" for item in failures[:20])
        return GateOutcome(
            name="Schematic connectivity",
            status="FAIL",
            summary=(
                "Connectivity smells suggest the schematic is not ready for PCB or release work."
            ),
            details=details,
        )
    return GateOutcome(
        name="Schematic connectivity",
        status="PASS",
        summary="Connectivity structure looks consistent across the active schematic set.",
        details=details,
    )


def _evaluate_pre_sync_gate() -> GateOutcome:
    """Validate that schematic state is safe to transfer into PCB footprints."""
    outcomes = [_evaluate_schematic_gate(), _evaluate_schematic_connectivity_gate()]
    blocking = [outcome for outcome in outcomes if outcome.status != "PASS"]
    if blocking:
        details: list[str] = []
        for outcome in blocking:
            details.append(f"{outcome.name} quality gate: {outcome.status}")
            details.append(outcome.summary)
            details.extend(outcome.details[:6])
        return GateOutcome(
            name="Pre-sync",
            status="FAIL",
            summary=(
                "Schematic checks must pass before PCB sync to avoid transferring "
                "a stale or broken netlist."
            ),
            details=details,
        )
    return GateOutcome(
        name="Pre-sync",
        status="PASS",
        summary="Schematic is ready for PCB sync.",
        details=["ERC/connectivity blockers: 0"],
    )


def _evaluate_pcb_gate() -> GateOutcome:
    _, report, error = _run_drc_report("pcb_quality_gate.json")
    if report is None:
        return GateOutcome(
            name="PCB",
            status="BLOCKED",
            summary=f"DRC report was unavailable ({error or 'unknown error'}).",
        )

    violations = _entries(report, "violations")
    unconnected = _entries(report, "unconnected_items")
    courtyard = _entries(report, "items_not_passing_courtyard")
    blocking_count = len(violations) + len(unconnected) + len(courtyard)
    status: GateStatus = "PASS" if blocking_count == 0 else "FAIL"
    details = [
        f"DRC violations: {len(violations)}",
        f"Unconnected items: {len(unconnected)}",
        f"Courtyard issues: {len(courtyard)}",
    ]
    if violations:
        details.append(f"DRC types: {_type_breakdown(violations)}")
    return GateOutcome(
        name="PCB",
        status=status,
        summary="PCB passes DRC, unconnected, and courtyard checks."
        if status == "PASS"
        else "PCB still has blocking physical-rule issues.",
        details=details,
    )


def _nearest_edge_distance(
    entry: dict[str, object],
    frame: tuple[float, float, float, float],
) -> float | None:
    if entry["x_mm"] is None or entry["y_mm"] is None:
        return None
    min_x, min_y, max_x, max_y = frame
    x_mm = float(cast(float, entry["x_mm"]))
    y_mm = float(cast(float, entry["y_mm"]))
    width_mm = float(cast(float, entry["width_mm"]))
    height_mm = float(cast(float, entry["height_mm"]))
    return min(
        x_mm - (width_mm / 2) - min_x,
        max_x - (x_mm + (width_mm / 2)),
        y_mm - (height_mm / 2) - min_y,
        max_y - (y_mm + (height_mm / 2)),
    )


def _entry_center(entry: dict[str, object]) -> tuple[float, float] | None:
    if entry["x_mm"] is None or entry["y_mm"] is None:
        return None
    return float(cast(float, entry["x_mm"])), float(cast(float, entry["y_mm"]))


def _bbox_gap_mm(left_entry: dict[str, object], right_entry: dict[str, object]) -> float | None:
    left_center = _entry_center(left_entry)
    right_center = _entry_center(right_entry)
    if left_center is None or right_center is None:
        return None
    left_x, left_y = left_center
    right_x, right_y = right_center
    left_w = float(cast(float, left_entry["width_mm"]))
    left_h = float(cast(float, left_entry["height_mm"]))
    right_w = float(cast(float, right_entry["width_mm"]))
    right_h = float(cast(float, right_entry["height_mm"]))
    gap_x = abs(left_x - right_x) - ((left_w + right_w) / 2.0)
    gap_y = abs(left_y - right_y) - ((left_h + right_h) / 2.0)
    return max(max(gap_x, 0.0), max(gap_y, 0.0))


def _group_spread_mm(
    refs: list[str],
    footprints: dict[str, dict[str, object]],
) -> tuple[float, list[str]]:
    present_refs = [
        reference
        for reference in refs
        if reference in footprints and _entry_center(footprints[reference]) is not None
    ]
    if len(present_refs) < 2:
        return 0.0, present_refs
    max_spread = 0.0
    for index, left_ref in enumerate(present_refs):
        left_center = _entry_center(footprints[left_ref])
        if left_center is None:
            continue
        for right_ref in present_refs[index + 1 :]:
            right_center = _entry_center(footprints[right_ref])
            if right_center is None:
                continue
            max_spread = max(
                max_spread,
                math.hypot(left_center[0] - right_center[0], left_center[1] - right_center[1]),
            )
    return max_spread, present_refs


def _manhattan_mst_length(points: list[tuple[float, float]]) -> float:
    """Approximate a ratsnest length using Manhattan-distance MST wiring."""
    if len(points) < 2:
        return 0.0

    visited = {0}
    total = 0.0
    while len(visited) < len(points):
        best_distance: float | None = None
        best_index: int | None = None
        for left_index in visited:
            left_point = points[left_index]
            for right_index, right_point in enumerate(points):
                if right_index in visited:
                    continue
                distance = abs(left_point[0] - right_point[0]) + abs(left_point[1] - right_point[1])
                if best_distance is None or distance < best_distance:
                    best_distance = distance
                    best_index = right_index
        if best_distance is None or best_index is None:
            break
        visited.add(best_index)
        total += best_distance
    return total


def _placement_analysis() -> tuple[PlacementAnalysis | None, GateOutcome | None]:
    from .board_file import (
        _board_frame_mm,
        _normalize_board_content,
        _parse_board_footprint_blocks,
        _placement_boxes_overlap,
    )
    from .design_intent_state import ProjectDesignIntent, resolve_design_intent

    try:
        content = _normalize_board_content(
            _get_pcb_file().read_text(encoding="utf-8", errors="ignore")
        )
    except OSError as exc:
        return None, GateOutcome(
            name="Placement",
            status="BLOCKED",
            summary=f"PCB file could not be read ({exc}).",
        )

    footprints = _parse_board_footprint_blocks(content)
    if not footprints:
        return None, GateOutcome(
            name="Placement",
            status="BLOCKED",
            summary="No PCB footprints were found to evaluate.",
        )

    try:
        intent = resolve_design_intent().resolved
    except ValueError:
        intent = ProjectDesignIntent()

    min_x, min_y, max_x, max_y = _board_frame_mm(content, footprints)
    frame = (min_x, min_y, max_x, max_y)
    board_width_mm = max_x - min_x
    board_height_mm = max_y - min_y
    board_area_mm2 = max(board_width_mm * board_height_mm, 1.0)

    missing_position = [
        reference
        for reference, entry in footprints.items()
        if entry["x_mm"] is None or entry["y_mm"] is None
    ]
    overlaps: list[str] = []
    outside: list[str] = []
    connector_edge_violations: list[str] = []
    decoupling_distance_violations: list[str] = []
    keepout_violations: list[str] = []
    power_tree_violations: list[str] = []
    sensor_cluster_violations: list[str] = []
    analog_digital_violations: list[str] = []
    warnings: list[str] = []

    items = sorted(footprints.items())
    footprint_area_mm2 = sum(
        float(entry["width_mm"]) * float(entry["height_mm"]) for entry in footprints.values()
    )
    density_pct = round((footprint_area_mm2 / board_area_mm2) * 100.0, 2)
    board_diagonal = math.hypot(board_width_mm, board_height_mm)

    for index, (left_ref, left_entry) in enumerate(items):
        if left_entry["x_mm"] is None or left_entry["y_mm"] is None:
            continue
        left_x = float(left_entry["x_mm"])
        left_y = float(left_entry["y_mm"])
        left_w = float(left_entry["width_mm"])
        left_h = float(left_entry["height_mm"])
        if (
            left_x - (left_w / 2) < min_x
            or left_x + (left_w / 2) > max_x
            or left_y - (left_h / 2) < min_y
            or left_y + (left_h / 2) > max_y
        ):
            outside.append(left_ref)
        for right_ref, right_entry in items[index + 1 :]:
            if right_entry["x_mm"] is None or right_entry["y_mm"] is None:
                continue
            if _placement_boxes_overlap(
                left_x,
                left_y,
                left_w,
                left_h,
                float(right_entry["x_mm"]),
                float(right_entry["y_mm"]),
                float(right_entry["width_mm"]),
                float(right_entry["height_mm"]),
                0.0,
            ):
                overlaps.append(f"{left_ref}/{right_ref}")

    checked_connectors = 0
    for reference in intent.connector_refs:
        entry = footprints.get(reference)
        if entry is None:
            connector_edge_violations.append(f"Connector intent ref '{reference}' is missing.")
            continue
        checked_connectors += 1
        distance = _nearest_edge_distance(entry, frame)
        if distance is None:
            connector_edge_violations.append(
                f"Connector '{reference}' has no resolved placement to evaluate."
            )
            continue
        if distance > 5.0:
            connector_edge_violations.append(
                f"Connector '{reference}' is {distance:.2f} mm from the nearest edge."
            )

    checked_decoupling_pairs = 0
    for pair in intent.decoupling_pairs:
        ic_entry = footprints.get(pair.ic_ref)
        if ic_entry is None:
            decoupling_distance_violations.append(
                f"Decoupling IC ref '{pair.ic_ref}' is missing on the board."
            )
            continue
        if ic_entry["x_mm"] is None or ic_entry["y_mm"] is None:
            decoupling_distance_violations.append(
                f"Decoupling IC ref '{pair.ic_ref}' has no resolved placement."
            )
            continue
        checked_decoupling_pairs += 1
        cap_distances: list[float] = []
        missing_caps: list[str] = []
        for cap_ref in pair.cap_refs:
            cap_entry = footprints.get(cap_ref)
            if cap_entry is None:
                missing_caps.append(cap_ref)
                continue
            if cap_entry["x_mm"] is None or cap_entry["y_mm"] is None:
                missing_caps.append(cap_ref)
                continue
            cap_distances.append(
                math.hypot(
                    float(ic_entry["x_mm"]) - float(cap_entry["x_mm"]),
                    float(ic_entry["y_mm"]) - float(cap_entry["y_mm"]),
                )
            )
        if missing_caps:
            decoupling_distance_violations.append(
                f"{pair.ic_ref}: missing or unresolved decoupling caps -> "
                + ", ".join(missing_caps[:12])
            )
        if cap_distances and min(cap_distances) > pair.max_distance_mm:
            decoupling_distance_violations.append(
                f"{pair.ic_ref}: nearest decoupling cap is {min(cap_distances):.2f} mm away "
                f"(limit {pair.max_distance_mm:.2f} mm)."
            )

    checked_keepouts = 0
    for region in intent.rf_keepout_regions:
        checked_keepouts += 1
        for reference, entry in footprints.items():
            if entry["x_mm"] is None or entry["y_mm"] is None:
                continue
            if _placement_boxes_overlap(
                float(entry["x_mm"]),
                float(entry["y_mm"]),
                float(entry["width_mm"]),
                float(entry["height_mm"]),
                region.x_mm,
                region.y_mm,
                region.w_mm,
                region.h_mm,
                0.0,
            ):
                keepout_violations.append(f"{reference} overlaps RF keepout '{region.name}'.")

    checked_power_tree_refs = 0
    present_power_tree: list[str] = []
    for reference in intent.power_tree_refs:
        entry = footprints.get(reference)
        if entry is None:
            power_tree_violations.append(f"Power-tree intent ref '{reference}' is missing.")
            continue
        if _entry_center(entry) is None:
            power_tree_violations.append(
                f"Power-tree intent ref '{reference}' has no resolved placement."
            )
            continue
        checked_power_tree_refs += 1
        present_power_tree.append(reference)
    for left_ref, right_ref in zip(present_power_tree, present_power_tree[1:], strict=False):
        left_center = _entry_center(footprints[left_ref])
        right_center = _entry_center(footprints[right_ref])
        if left_center is None or right_center is None:
            continue
        step_distance = math.hypot(
            left_center[0] - right_center[0],
            left_center[1] - right_center[1],
        )
        if step_distance > board_diagonal * 0.75:
            power_tree_violations.append(
                f"Power-tree step '{left_ref} -> {right_ref}' spans {step_distance:.2f} mm."
            )
        elif step_distance > board_diagonal * 0.5:
            warnings.append(
                f"Power-tree step '{left_ref} -> {right_ref}' spans {step_distance:.2f} mm."
            )

    checked_sensor_cluster_refs = 0
    missing_sensor_refs = [
        reference
        for reference in intent.sensor_cluster_refs
        if reference not in footprints or _entry_center(footprints[reference]) is None
    ]
    if missing_sensor_refs:
        sensor_cluster_violations.append(
            "Sensor-cluster refs missing or unresolved: " + ", ".join(missing_sensor_refs[:12])
        )
    sensor_cluster_spread, present_sensor_refs = _group_spread_mm(
        intent.sensor_cluster_refs,
        footprints,
    )
    checked_sensor_cluster_refs = len(present_sensor_refs)
    if checked_sensor_cluster_refs >= 2:
        if sensor_cluster_spread > board_diagonal * 0.6:
            sensor_cluster_violations.append(
                f"Sensor cluster spreads {sensor_cluster_spread:.2f} mm across the board."
            )
        elif sensor_cluster_spread > board_diagonal * 0.35:
            warnings.append(
                f"Sensor cluster spreads {sensor_cluster_spread:.2f} mm across the board."
            )

    analog_refs = [
        reference
        for reference in intent.analog_refs
        if reference in footprints and _entry_center(footprints[reference]) is not None
    ]
    digital_refs = [
        reference
        for reference in intent.digital_refs
        if reference in footprints and _entry_center(footprints[reference]) is not None
    ]
    checked_analog_refs = len(analog_refs)
    checked_digital_refs = len(digital_refs)
    nearest_mixed_gap: tuple[float, str, str] | None = None
    for analog_ref in analog_refs:
        analog_entry = footprints[analog_ref]
        for digital_ref in digital_refs:
            digital_entry = footprints[digital_ref]
            gap = _bbox_gap_mm(analog_entry, digital_entry)
            if gap is None:
                continue
            candidate = (gap, analog_ref, digital_ref)
            if nearest_mixed_gap is None or candidate[0] < nearest_mixed_gap[0]:
                nearest_mixed_gap = candidate
    if nearest_mixed_gap is not None:
        gap, analog_ref, digital_ref = nearest_mixed_gap
        if gap < 1.0:
            analog_digital_violations.append(
                "Analog ref "
                f"'{analog_ref}' is only {gap:.2f} mm away from digital ref "
                f"'{digital_ref}'."
            )
        elif gap < 3.0:
            warnings.append(
                "Analog ref "
                f"'{analog_ref}' is only {gap:.2f} mm away from digital ref "
                f"'{digital_ref}'."
            )

    if density_pct > 70.0:
        warnings.append(f"Footprint density is high ({density_pct:.2f}%).")
    elif density_pct < 5.0 and len(footprints) >= 6:
        warnings.append(f"Footprint density is sparse ({density_pct:.2f}%).")

    placed_x = [float(entry["x_mm"]) for entry in footprints.values() if entry["x_mm"] is not None]
    placed_y = [float(entry["y_mm"]) for entry in footprints.values() if entry["y_mm"] is not None]
    if len(placed_x) >= 2 and len(placed_y) >= 2:
        footprint_span_x = max(placed_x) - min(placed_x)
        footprint_span_y = max(placed_y) - min(placed_y)
        if len(footprints) >= 6 and (
            footprint_span_x > board_width_mm * 0.7 or footprint_span_y > board_height_mm * 0.7
        ):
            warnings.append("Placement spans most of the board; clustering looks weak.")

    critical_net_proxy_mm = 0.0
    for net_name in intent.critical_nets:
        refs = sorted(
            reference
            for reference, entry in footprints.items()
            if net_name in cast(list[str], entry.get("net_names", []))
            and entry["x_mm"] is not None
            and entry["y_mm"] is not None
        )
        if len(refs) < 2:
            continue
        points = [
            (
                float(cast(float, footprints[reference]["x_mm"])),
                float(cast(float, footprints[reference]["y_mm"])),
            )
            for reference in refs
        ]
        critical_net_proxy_mm += _manhattan_mst_length(points)
        max_spread = 0.0
        for index, left_ref in enumerate(refs):
            left_entry = footprints[left_ref]
            for right_ref in refs[index + 1 :]:
                right_entry = footprints[right_ref]
                max_spread = max(
                    max_spread,
                    math.hypot(
                        float(left_entry["x_mm"]) - float(right_entry["x_mm"]),
                        float(left_entry["y_mm"]) - float(right_entry["y_mm"]),
                    ),
                )
        if max_spread > board_diagonal * 0.6:
            warnings.append(
                f"Critical net '{net_name}' spans {max_spread:.2f} mm across the board."
            )

    critical_net_proxy_density = round(
        critical_net_proxy_mm / max(board_area_mm2 / 1000.0, 1.0),
        2,
    )
    if critical_net_proxy_density > 80.0:
        warnings.append(
            "Critical nets require a long Manhattan ratsnest relative to board area "
            f"({critical_net_proxy_density:.2f} mm per 1000 mm^2)."
        )

    thermal_hotspot_refs = [
        reference
        for reference in intent.thermal_hotspots
        if reference in footprints and _entry_center(footprints[reference]) is not None
    ]
    thermal_proximity_sum = 0.0
    for index, left_ref in enumerate(thermal_hotspot_refs):
        left_center = _entry_center(footprints[left_ref])
        if left_center is None:
            continue
        for right_ref in thermal_hotspot_refs[index + 1 :]:
            right_center = _entry_center(footprints[right_ref])
            if right_center is None:
                continue
            distance = max(
                math.hypot(left_center[0] - right_center[0], left_center[1] - right_center[1]),
                0.5,
            )
            thermal_proximity_sum += 1.0 / distance
    if thermal_hotspot_refs and thermal_proximity_sum > max(len(thermal_hotspot_refs) - 1, 1) * 0.2:
        warnings.append(
            f"Thermal hotspots are clustered tightly (proximity sum {thermal_proximity_sum:.3f})."
        )

    hard_failures: list[str] = []
    if missing_position:
        hard_failures.append("Missing positions: " + ", ".join(missing_position[:20]))
    if overlaps:
        hard_failures.append("Overlap refs: " + ", ".join(overlaps[:20]))
    if outside:
        hard_failures.append("Outside-board refs: " + ", ".join(outside[:20]))
    hard_failures.extend(connector_edge_violations)
    hard_failures.extend(decoupling_distance_violations)
    hard_failures.extend(keepout_violations)
    hard_failures.extend(power_tree_violations)
    hard_failures.extend(sensor_cluster_violations)
    hard_failures.extend(analog_digital_violations)

    score = 100
    score -= min(len(overlaps) * 20, 40)
    score -= min(len(outside) * 20, 40)
    score -= min(len(connector_edge_violations) * 15, 30)
    score -= min(len(decoupling_distance_violations) * 15, 30)
    score -= min(len(keepout_violations) * 15, 30)
    score -= min(len(power_tree_violations) * 15, 30)
    score -= min(len(sensor_cluster_violations) * 15, 30)
    score -= min(len(analog_digital_violations) * 15, 30)
    score -= min(len(warnings) * 5, 20)
    score -= min(int(round(thermal_proximity_sum * 10.0)), 10)
    score -= min(int(critical_net_proxy_density // 20), 10)

    return (
        PlacementAnalysis(
            footprint_count=len(footprints),
            board_width_mm=board_width_mm,
            board_height_mm=board_height_mm,
            board_area_mm2=board_area_mm2,
            footprint_area_mm2=footprint_area_mm2,
            density_pct=density_pct,
            score=max(score, 0),
            hard_failures=hard_failures,
            warnings=warnings,
            checked_connectors=checked_connectors,
            checked_decoupling_pairs=checked_decoupling_pairs,
            checked_keepouts=checked_keepouts,
            checked_power_tree_refs=checked_power_tree_refs,
            checked_analog_refs=checked_analog_refs,
            checked_digital_refs=checked_digital_refs,
            checked_sensor_cluster_refs=checked_sensor_cluster_refs,
            critical_net_proxy_mm=round(critical_net_proxy_mm, 2),
            critical_net_proxy_density=critical_net_proxy_density,
            checked_thermal_hotspot_refs=len(thermal_hotspot_refs),
            thermal_proximity_sum=round(thermal_proximity_sum, 4),
        ),
        None,
    )


def _format_placement_score(analysis: PlacementAnalysis) -> str:
    lines = [
        f"Placement score: {analysis.score}/100",
        f"- Footprints analysed: {analysis.footprint_count}",
        f"- Board frame: {analysis.board_width_mm:.2f} x {analysis.board_height_mm:.2f} mm",
        f"- Density: {analysis.density_pct:.2f}%",
        f"- Connector checks: {analysis.checked_connectors}",
        f"- Decoupling pair checks: {analysis.checked_decoupling_pairs}",
        f"- RF keepout checks: {analysis.checked_keepouts}",
        f"- Power-tree refs checked: {analysis.checked_power_tree_refs}",
        f"- Analog refs checked: {analysis.checked_analog_refs}",
        f"- Digital refs checked: {analysis.checked_digital_refs}",
        f"- Sensor-cluster refs checked: {analysis.checked_sensor_cluster_refs}",
        f"- Critical-net Manhattan proxy: {analysis.critical_net_proxy_mm:.2f} mm",
        f"- Critical-net proxy density: {analysis.critical_net_proxy_density:.2f} mm per 1000 mm^2",
        f"- Thermal hotspot refs checked: {analysis.checked_thermal_hotspot_refs}",
        f"- Thermal hotspot proximity: {analysis.thermal_proximity_sum:.4f}",
        f"- Hard failures: {len(analysis.hard_failures)}",
        f"- Warnings: {len(analysis.warnings)}",
    ]
    lines.extend(f"- FAIL: {item}" for item in analysis.hard_failures[:12])
    lines.extend(f"- WARN: {item}" for item in analysis.warnings[:12])
    return "\n".join(lines)


def _evaluate_pcb_placement_gate() -> GateOutcome:
    analysis, blocked = _placement_analysis()
    if blocked is not None:
        return blocked
    if analysis is None:
        raise RuntimeError("Placement analysis unexpectedly returned no result.")

    status: GateStatus = "PASS" if not analysis.hard_failures else "FAIL"
    details = [
        f"Footprints analysed: {analysis.footprint_count}",
        f"Board frame: {analysis.board_width_mm:.2f} x {analysis.board_height_mm:.2f} mm",
        f"Density: {analysis.density_pct:.2f}%",
        f"Connector checks: {analysis.checked_connectors}",
        f"Decoupling pair checks: {analysis.checked_decoupling_pairs}",
        f"RF keepout checks: {analysis.checked_keepouts}",
        f"Power-tree refs checked: {analysis.checked_power_tree_refs}",
        f"Analog refs checked: {analysis.checked_analog_refs}",
        f"Digital refs checked: {analysis.checked_digital_refs}",
        f"Sensor-cluster refs checked: {analysis.checked_sensor_cluster_refs}",
        f"Critical-net Manhattan proxy: {analysis.critical_net_proxy_mm:.2f} mm",
        f"Critical-net proxy density: {analysis.critical_net_proxy_density:.2f} mm per 1000 mm^2",
        f"Thermal hotspot refs checked: {analysis.checked_thermal_hotspot_refs}",
        f"Thermal hotspot proximity: {analysis.thermal_proximity_sum:.4f}",
        f"Placement score: {analysis.score}/100",
    ]
    details.extend(f"FAIL: {item}" for item in analysis.hard_failures[:12])
    details.extend(f"WARN: {item}" for item in analysis.warnings[:12])
    return GateOutcome(
        name="Placement",
        status=status,
        summary="Footprint placement is geometrically and contextually sane."
        if status == "PASS"
        else "Footprint placement still violates hard physical or intent-aware checks.",
        details=details,
    )


def _evaluate_manufacturing_gate(
    *,
    manufacturer: str | None = None,
    tier: str | None = None,
) -> GateOutcome:
    from .design_intent_state import resolve_design_intent
    from .dfm import _dfm_check_lines, _load_profile, _selected_profile

    if manufacturer is None or tier is None:
        try:
            intent = resolve_design_intent().resolved
        except ValueError:
            intent = None
        if intent is not None:
            manufacturer = manufacturer or intent.manufacturer or None
            tier = tier or intent.manufacturer_tier or None
    profile = (
        _load_profile(manufacturer, tier)
        if manufacturer and tier
        else cast(dict[str, object], _selected_profile())
    )
    lines = _dfm_check_lines(
        cast(dict[str, object], profile),
        heading="Manufacturing quality gate:",
    )
    fail_lines = [line[8:] for line in lines if line.startswith("- FAIL: ")]
    warn_lines = [line[8:] for line in lines if line.startswith("- WARN: ")]
    status: GateStatus = "PASS" if not fail_lines else "FAIL"
    details = [f"Profile: {profile['manufacturer']} / {profile['tier']}"]
    details.extend(f"FAIL: {line}" for line in fail_lines[:12])
    details.extend(f"WARN: {line}" for line in warn_lines[:12])
    return GateOutcome(
        name="Manufacturing",
        status=status,
        summary="DFM checks passed."
        if status == "PASS"
        else f"DFM reported {len(fail_lines)} failing checks.",
        details=details,
    )


def _is_project_empty() -> bool:
    from .board_file import _edge_cuts_bounds, _parse_board_footprint_blocks
    from .schematic import parse_schematic_file, project_schematic_files

    # Check schematic
    try:
        sch_files = project_schematic_files()
        if sch_files:
            for sch_file in sch_files:
                if sch_file.exists():
                    data = parse_schematic_file(sch_file)
                    if (
                        data.get("symbols")
                        or data.get("power_symbols")
                        or data.get("wires")
                        or data.get("labels")
                    ):
                        return False
    except Exception:  # noqa: S110
        pass

    # Check PCB
    try:
        pcb_file = _get_pcb_file()
        if pcb_file.exists():
            content = pcb_file.read_text(encoding="utf-8", errors="ignore")
            footprints = _parse_board_footprint_blocks(content)
            if footprints:
                return False
            if _edge_cuts_bounds(content) is not None:
                return False
    except Exception:  # noqa: S110
        pass

    return True


def _empty_project_onboarding_outcome() -> GateOutcome:
    return GateOutcome(
        name="Project Onboarding",
        status="EMPTY",
        summary="Your KiCad Studio project is currently empty or newly created.",
        details=[
            "Suggested Onboarding Steps:",
            "1. Define your design intent by calling the 'project_set_design_intent' tool.",
            "2. Add schematic symbols, connect them with wires, and add labels.",
            "3. Place components onto the PCB and define the board outline.",
            "4. Re-run project_quality_gate to see your progress!",
        ],
    )


# The edit-impact categories that the bundled project gate can actually re-run. The
# remaining categories (signal_integrity, power, thermal, emc) are covered by separate
# analysis tools, not by this sign-off gate.
PROJECT_GATE_CATEGORIES: frozenset[str] = frozenset(
    {"schematic", "connectivity", "pcb", "manufacturing", "dfm"}
)


def _evaluate_project_gate(
    *,
    manufacturer: str | None = None,
    tier: str | None = None,
    only_categories: set[str] | frozenset[str] | None = None,
) -> list[GateOutcome]:
    """Evaluate the project gate. When ``only_categories`` is given, run only the
    evaluators whose edit-impact category is in that set (selective re-validation)."""
    if _is_project_empty():
        return [_empty_project_onboarding_outcome()]

    # (edit-impact category, evaluator) — order is the report order.
    evaluators: tuple[tuple[str, Callable[[], GateOutcome]], ...] = (
        ("schematic", _evaluate_schematic_gate),
        ("connectivity", _evaluate_schematic_connectivity_gate),
        ("connectivity", _evaluate_pre_sync_gate),
        ("pcb", _evaluate_pcb_gate),
        ("pcb", _evaluate_pcb_placement_gate),
        ("pcb", _evaluate_pcb_transfer_gate),
        (
            "manufacturing",
            lambda: _evaluate_manufacturing_gate(manufacturer=manufacturer, tier=tier),
        ),
        ("dfm", _footprint_parity_outcome),
    )
    return [
        evaluator()
        for category, evaluator in evaluators
        if only_categories is None or category in only_categories
    ]


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _signoff_provenance(intent: ProjectDesignIntent) -> dict[str, Any]:
    """Build deterministic sign-off provenance (no timestamps, so the hash is stable)."""
    cfg = get_config()
    caps = get_cli_capabilities(cfg.kicad_cli)
    intent_hash = hashlib.sha256(
        json.dumps(intent.model_dump(), sort_keys=True).encode()
    ).hexdigest()[:16]
    source_hashes = {
        label: _sha256_file(path)
        for label, path in (
            ("project", cfg.project_file),
            ("pcb", cfg.pcb_file),
            ("schematic", cfg.sch_file),
        )
        if path is not None and path.exists()
    }
    return {
        "kicad_mcp_version": __version__,
        "kicad_cli": str(cfg.kicad_cli),
        "kicad_cli_version": caps.version,
        "rule_profile": f"{cfg.profile}/{cfg.operating_mode}",
        "intent_hash": intent_hash,
        "source_hashes": source_hashes,
    }


def _render_project_gate_report(
    outcomes: list[GateOutcome],
    *,
    summary: str | None = None,
) -> str:
    status = _combined_status(outcomes)
    lines = [
        f"Project quality gate: {status}",
        summary
        or (
            "- This project is ready for the next stage."
            if status == "PASS"
            else "- Blocking issues remain. Do not treat this design as production-ready yet."
        ),
    ]
    if _design_intent_warning():
        lines.append("WARN: Design intent not set - placement scoring will use defaults.")
    lines.extend(_format_gate(outcome) for outcome in outcomes)
    return "\n\n".join(lines)


def _design_intent_warning() -> bool:
    try:
        from .design_intent_state import resolve_design_intent

        return resolve_design_intent().source == "none"
    except Exception:
        return False


def _project_gate_report_payload(
    outcomes: list[GateOutcome],
    *,
    summary: str | None = None,
) -> ProjectGateReportPayload:
    text = _render_project_gate_report(outcomes, summary=summary)
    status = _combined_status(outcomes)
    headline = summary or (
        "This project is ready for the next stage."
        if status == "PASS"
        else "Blocking issues remain. Do not treat this design as production-ready yet."
    )
    return ProjectGateReportPayload(
        text=text,
        status=status,
        summary=headline.lstrip("- ").strip(),
        outcomes=[_gate_outcome_payload(outcome) for outcome in outcomes],
    )


def _project_gate_verdict_report(
    outcomes: list[GateOutcome],
    *,
    summary: str | None = None,
) -> VerdictReport:
    text = _render_project_gate_report(outcomes, summary=summary)
    status = _combined_status(outcomes)
    headline = summary or (
        "This project is ready for the next stage."
        if status == "PASS"
        else "Blocking issues remain. Do not treat this design as production-ready yet."
    )
    findings = [finding for outcome in outcomes for finding in _gate_findings(outcome)]
    if _design_intent_warning():
        findings.append(
            Finding(
                id=stable_finding_id("gate", "project", "design-intent-missing"),
                severity="warning",
                location="Project design intent",
                description="Design intent is not set; placement scoring will use defaults.",
                suggested_fix=SuggestedFix(tool="project_set_design_intent", args={}),
            )
        )
    verdict = VerdictReport.verdict_for([finding.severity for finding in findings])
    if verdict == "PASS":
        verdict = _gate_status_verdict(status)
    first_blocker = next((outcome for outcome in outcomes if outcome.status != "PASS"), None)
    if first_blocker is None:
        next_action = "Proceed to export_manufacturing_package()."
    else:
        fixer = _fix_for_gate(first_blocker.name)
        next_action = (
            f"Call {fixer.tool} and re-run project_quality_gate()."
            if fixer is not None
            else "Fix the first blocking gate and re-run project_quality_gate()."
        )
    return VerdictReport(
        text=text,
        summary=headline.lstrip("- ").strip(),
        verdict=verdict,
        findings=findings,
        next_action=next_action,
        metadata={
            "status": status,
            "outcomes": [_gate_outcome_payload(outcome).model_dump() for outcome in outcomes],
        },
    )


def _placement_gate_report_payload() -> PlacementGateReportPayload:
    analysis, blocked = _placement_analysis()
    if blocked is not None:
        return PlacementGateReportPayload(
            text=_format_gate(blocked),
            status=blocked.status,
            summary=blocked.summary,
            hard_failures=blocked.details,
        )
    if analysis is None:
        raise RuntimeError("Placement analysis unexpectedly returned no result.")
    outcome = _evaluate_pcb_placement_gate()
    return PlacementGateReportPayload(
        text=_format_gate(outcome),
        status=outcome.status,
        summary=outcome.summary,
        score=analysis.score,
        footprint_count=analysis.footprint_count,
        checked_connectors=analysis.checked_connectors,
        checked_decoupling_pairs=analysis.checked_decoupling_pairs,
        checked_keepouts=analysis.checked_keepouts,
        checked_power_tree_refs=analysis.checked_power_tree_refs,
        checked_analog_refs=analysis.checked_analog_refs,
        checked_digital_refs=analysis.checked_digital_refs,
        checked_sensor_cluster_refs=analysis.checked_sensor_cluster_refs,
        hard_failures=analysis.hard_failures,
        warnings=analysis.warnings,
    )


def render_gate_by_name(
    gate_name: str,
    *,
    manufacturer: str | None = None,
    tier: str | None = None,
) -> str:
    """Render a single named gate or the full project gate as text."""
    normalized = gate_name.strip().lower().replace("-", "_")
    if normalized in {"project", "project_quality", "project_quality_gate"}:
        return _render_project_gate_report(
            _evaluate_project_gate(manufacturer=manufacturer, tier=tier)
        )
    if normalized in {"schematic", "schematic_quality", "schematic_quality_gate"}:
        return _format_gate(_evaluate_schematic_gate())
    if normalized in {
        "schematic_connectivity",
        "schematic_connectivity_gate",
        "connectivity",
    }:
        return _format_gate(_evaluate_schematic_connectivity_gate())
    if normalized in {"pcb", "pcb_quality", "pcb_quality_gate"}:
        return _format_gate(_evaluate_pcb_gate())
    if normalized in {"placement", "pcb_placement", "pcb_placement_quality_gate"}:
        return _format_gate(_evaluate_pcb_placement_gate())
    if normalized in {"transfer", "pcb_transfer", "pcb_transfer_quality_gate"}:
        return _format_gate(_evaluate_pcb_transfer_gate())
    if normalized in {"manufacturing", "manufacturing_quality_gate"}:
        return _format_gate(_evaluate_manufacturing_gate(manufacturer=manufacturer, tier=tier))
    if normalized in {"footprint_parity", "parity"}:
        return _format_gate(_footprint_parity_outcome())
    raise ValueError(
        "Unknown gate name. Use one of: project, schematic, schematic_connectivity, "
        "pcb, placement, transfer, manufacturing, footprint_parity."
    )


def _drc_state_path() -> Path:
    cfg = get_config()
    if cfg.project_dir is None:
        raise ValueError("No active project is configured.")
    target = cfg.project_dir / ".kicad-mcp"
    target.mkdir(parents=True, exist_ok=True)
    return target / "drc_rules_state.json"


def _load_drc_state() -> dict[str, object]:
    path = _drc_state_path()
    if not path.exists():
        payload: dict[str, object] = {"enabled": {}, "severity": {}}
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return payload
    return cast(dict[str, object], json.loads(path.read_text(encoding="utf-8")))


def _save_drc_state(payload: dict[str, object]) -> Path:
    path = _drc_state_path()
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def _rule_child_nodes(
    rule: SExprNode,
    child_name: str,
) -> list[SExprNode]:
    return [
        child for child in rule[2:] if isinstance(child, list) and child and child[0] == child_name
    ]


def _replace_rule_child(
    rule: SExprNode,
    child_name: str,
    replacement: SExprNode,
) -> SExprNode:
    updated: SExprNode = []
    replaced = False
    for child in rule:
        if isinstance(child, list) and child and child[0] == child_name and not replaced:
            updated.append(replacement)
            replaced = True
            continue
        if isinstance(child, list) and child and child[0] == child_name:
            continue
        updated.append(child)
    if not replaced:
        updated.append(replacement)
    return updated


def _rule_payload(rule: SExprNode, state: dict[str, object]) -> dict[str, object]:
    rule_name = str(rule[1]) if len(rule) > 1 and not isinstance(rule[1], list) else "unknown"
    condition_nodes = _rule_child_nodes(rule, "condition")
    constraint_nodes = _rule_child_nodes(rule, "constraint")
    severity_nodes = _rule_child_nodes(rule, "severity")
    enabled_state = cast(dict[str, bool], state.get("enabled", {}))
    severity_state = cast(dict[str, str], state.get("severity", {}))
    parsed_condition = (
        str(condition_nodes[0][1])
        if condition_nodes
        and len(condition_nodes[0]) > 1
        and not isinstance(condition_nodes[0][1], list)
        else ""
    )
    parsed_severity = (
        str(severity_nodes[0][1])
        if severity_nodes
        and len(severity_nodes[0]) > 1
        and not isinstance(severity_nodes[0][1], list)
        else "error"
    )
    effective_severity = severity_state.get(rule_name, parsed_severity)
    payload: dict[str, object] = {
        "name": rule_name,
        "condition": parsed_condition,
        "constraints": [
            str(child[1])
            for child in constraint_nodes
            if len(child) > 1 and not isinstance(child[1], list)
        ],
        "severity": effective_severity,
        "enabled": enabled_state.get(rule_name, parsed_severity != "ignore"),
    }
    return payload


def _coerce_constraint_value(value: float | str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value.strip()
    return f"{value}"


def _build_constraint_node(
    constraint_type: str,
    min_value: float | str | None,
    max_value: float | str | None,
) -> SExprNode:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", constraint_type):
        raise ValueError("constraint_type must be a simple KiCad rule atom such as clearance.")
    node: SExprNode = ["constraint", constraint_type]
    min_atom = _coerce_constraint_value(min_value)
    max_atom = _coerce_constraint_value(max_value)
    if min_atom is not None:
        node.append(["min", min_atom])
    if max_atom is not None:
        node.append(["max", max_atom])
    return node


def register(mcp: FastMCP) -> None:
    """Register validation tools."""

    @mcp.tool()
    @headless_compatible
    def drc_list_rules(include_custom: bool = True) -> str:
        """List known DRC rules from the active ``.kicad_dru`` file."""
        from .routing_rules import _load_rules_content, _rules_file_path

        built_in = [
            {"name": "clearance", "source": "built-in"},
            {"name": "track_width", "source": "built-in"},
            {"name": "via_diameter", "source": "built-in"},
            {"name": "hole_to_hole", "source": "built-in"},
        ]
        if not include_custom:
            return json.dumps({"rules": built_in}, indent=2)

        content = _load_rules_content(_rules_file_path())
        root, _version = parse_dru(content)
        state = _load_drc_state()
        custom = [_rule_payload(rule, state) for rule in iter_rule_nodes(root)]
        return json.dumps({"rules": [*built_in, *custom]}, indent=2)

    @mcp.tool()
    @headless_compatible
    def drc_rule_create(
        name: str,
        constraint_type: str,
        min_value: float | str | None = None,
        max_value: float | str | None = None,
        condition: str | None = None,
        severity: str = "error",
    ) -> str:
        """Create or update a custom DRC rule in the active ``.kicad_dru`` file."""
        from .routing_rules import _load_rules_content, _rules_file_path

        if not name.strip():
            raise ValueError("Rule name must not be empty.")
        if not re.fullmatch(r"[a-z_]+", severity.casefold()):
            raise ValueError("severity must be a simple KiCad severity atom such as error.")

        rule_node: SExprNode = [
            "rule",
            name,
            ["condition", condition or "A.Type != 'none'"],
            _build_constraint_node(constraint_type, min_value, max_value),
            ["severity", severity],
        ]
        path = _rules_file_path()
        root, version = parse_dru(_load_rules_content(path))
        upsert_rule(root, rule_node)
        path.write_text(dump_dru(root, version=version), encoding="utf-8")
        state = _load_drc_state()
        cast(dict[str, bool], state.setdefault("enabled", {}))[name] = True
        cast(dict[str, str], state.setdefault("severity", {}))[name] = severity
        _save_drc_state(state)
        return f"Custom DRC rule '{name}' written to {path}."

    @mcp.tool()
    @headless_compatible
    def drc_rule_delete(rule_name: str) -> str:
        """Delete a custom DRC rule from the active rules file."""
        from .routing_rules import _load_rules_content, _rules_file_path

        path = _rules_file_path()
        root, version = parse_dru(_load_rules_content(path))
        if not delete_rule(root, rule_name):
            raise ValueError(f"Rule '{rule_name}' was not found.")
        path.write_text(dump_dru(root, version=version), encoding="utf-8")
        state = _load_drc_state()
        cast(dict[str, bool], state.setdefault("enabled", {})).pop(rule_name, None)
        cast(dict[str, str], state.setdefault("severity", {})).pop(rule_name, None)
        _save_drc_state(state)
        return f"Deleted custom DRC rule '{rule_name}' from {path}."

    @mcp.tool()
    @headless_compatible
    def drc_rule_enable(rule_name: str, enabled: bool = True) -> str:
        """Enable or disable a custom DRC rule."""
        from .routing_rules import _load_rules_content, _rules_file_path

        path = _rules_file_path()
        root, version = parse_dru(_load_rules_content(path))
        rule = find_rule(root, rule_name)
        if rule is None:
            return f"Custom DRC rule '{rule_name}' was not found."

        state = _load_drc_state()
        severity_map = cast(dict[str, str], state.setdefault("severity", {}))
        enabled_map = cast(dict[str, bool], state.setdefault("enabled", {}))
        severity_nodes = _rule_child_nodes(rule, "severity")
        parsed_severity = (
            str(severity_nodes[0][1])
            if severity_nodes
            and len(severity_nodes[0]) > 1
            and not isinstance(severity_nodes[0][1], list)
            else "error"
        )
        existing_severity = severity_map.get(rule_name) or parsed_severity
        severity_map[rule_name] = existing_severity
        enabled_map[rule_name] = enabled

        replacement = _replace_rule_child(
            rule,
            "severity",
            ["severity", "ignore" if not enabled else existing_severity],
        )
        upsert_rule(root, replacement)
        path.write_text(dump_dru(root, version=version), encoding="utf-8")
        _save_drc_state(state)
        state_text = "enabled" if enabled else "disabled"
        return f"Custom DRC rule '{rule_name}' {state_text}."

    @mcp.tool()
    @headless_compatible
    def drc_export_rules(output_path: str | None = None) -> str:
        """Export the active custom DRC rules file for sharing or CI."""
        from .routing_rules import _rules_file_path

        source = _rules_file_path()
        cfg = get_config()
        target = (
            cfg.resolve_within_project(output_path, allow_absolute=False)
            if output_path
            else cfg.ensure_output_dir("drc") / source.name
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
        return f"Custom DRC rules exported to {target}."

    @mcp.tool()
    @headless_compatible
    def run_drc(save_report: bool = False) -> VerdictReport:
        """Run PCB design rule checks."""
        path, report, error = _run_drc_report("drc_report.json")
        return _drc_report_payload(path, report, error, save_report=save_report)

    @mcp.tool()
    @headless_compatible
    def run_erc(save_report: bool = False) -> VerdictReport:
        """Run schematic electrical rule checks."""
        path, report, error = _run_erc_report("erc_report.json")
        return _erc_report_payload(path, report, error, save_report=save_report)

    @mcp.tool()
    @headless_compatible
    def validate_design() -> str:
        """Run DRC and ERC and summarize readiness."""
        _, drc_report, drc_error = _run_drc_report("validate_drc.json")
        _, erc_report, erc_error = _run_erc_report("validate_erc.json")

        lines = ["Design validation summary:"]
        if drc_report is not None:
            lines.append(
                f"- DRC: {len(_entries(drc_report, 'violations'))} violations, "
                f"{len(_entries(drc_report, 'unconnected_items'))} unconnected items"
            )
        else:
            lines.append(f"- DRC: unavailable ({drc_error})")

        if erc_report is not None:
            lines.append(f"- ERC: {len(_erc_violations(erc_report))} violations")
        else:
            lines.append(f"- ERC: unavailable ({erc_error})")
        return "\n".join(lines)

    @mcp.tool()
    @headless_compatible
    def schematic_quality_gate() -> VerdictReport:
        """Evaluate whether the schematic is clean enough to proceed."""
        return _gate_report(_evaluate_schematic_gate())

    @mcp.tool()
    @headless_compatible
    def pcb_quality_gate() -> VerdictReport:
        """Evaluate whether the PCB is physically clean enough to proceed."""
        return _gate_report(_evaluate_pcb_gate())

    @mcp.tool()
    @headless_compatible
    def schematic_connectivity_gate() -> VerdictReport:
        """Evaluate whether schematic structure and hierarchy look electrically meaningful."""
        return _gate_report(_evaluate_schematic_connectivity_gate())

    @mcp.tool()
    @headless_compatible
    def pcb_placement_quality_gate() -> VerdictReport:
        """Evaluate whether footprint placement is overlap-free and inside the board frame."""
        return _gate_report(_evaluate_pcb_placement_gate())

    @mcp.tool()
    @headless_compatible
    def pcb_placement_quality_report() -> PlacementGateReportPayload:
        """Return a structured placement-quality report for capable MCP clients."""
        return _placement_gate_report_payload()

    @mcp.tool()
    @headless_compatible
    def pcb_transfer_quality_gate() -> VerdictReport:
        """Evaluate whether named schematic pad nets transferred cleanly onto PCB pads."""
        return _gate_report(_evaluate_pcb_transfer_gate())

    @mcp.tool()
    @headless_compatible
    def pcb_score_placement() -> str:
        """Score PCB placement quality and explain both hard failures and softer warnings."""
        analysis, blocked = _placement_analysis()
        if blocked is not None:
            return "\n".join(
                [
                    "Placement score: BLOCKED",
                    f"- {blocked.summary}",
                    *[f"- {detail}" for detail in blocked.details],
                ]
            )
        if analysis is None:
            raise RuntimeError("Placement analysis unexpectedly returned no result.")
        return _format_placement_score(analysis)

    @mcp.tool()
    @headless_compatible
    def manufacturing_quality_gate(
        manufacturer: str = "",
        tier: str = "",
    ) -> VerdictReport:
        """Evaluate manufacturing readiness against the active or requested DFM profile."""
        outcome = _evaluate_manufacturing_gate(
            manufacturer=manufacturer or None,
            tier=tier or None,
        )
        return _gate_report(outcome)

    @mcp.tool()
    @headless_compatible
    def project_quality_gate(
        manufacturer: str = "",
        tier: str = "",
    ) -> VerdictReport:
        """Run the full project quality gate across schematic, PCB, DFM, and parity checks."""
        outcomes = _evaluate_project_gate(
            manufacturer=manufacturer or None,
            tier=tier or None,
        )
        return _project_gate_verdict_report(outcomes)

    @mcp.tool()
    @headless_compatible
    def project_quality_gate_report(
        manufacturer: str = "",
        tier: str = "",
    ) -> ProjectGateReportPayload:
        """Return the full project gate in structured form for capable MCP clients."""
        outcomes = _evaluate_project_gate(
            manufacturer=manufacturer or None,
            tier=tier or None,
        )
        return _project_gate_report_payload(outcomes)

    @mcp.tool()
    @headless_compatible
    def project_signoff_report(manufacturer: str = "", tier: str = "") -> str:
        """Produce the single manufacturing sign-off report.

        Binds each declared design-intent requirement to the gate check(s) that
        would catch a violation, attaches the gate evidence and full provenance
        (engine versions, rule profile, intent and source hashes), and returns one
        PASS/FAIL verdict. A board with no declared intent is UNVERIFIED, not a
        silent PASS. ``export_manufacturing_package`` is hard-gated on the same
        underlying project gate, so a PASS here means the package will export.
        """
        from .project import load_design_intent
        from .signoff import build_signoff_report, render_signoff_report

        outcomes = _evaluate_project_gate(manufacturer=manufacturer or None, tier=tier or None)
        intent = load_design_intent()
        report = build_signoff_report(
            intent.model_dump(),
            outcomes,
            _signoff_provenance(intent),
        )
        return render_signoff_report(report)

    @mcp.tool()
    @headless_compatible
    def check_design_for_manufacture(jlcpcb: bool = True) -> str:
        """Run a lightweight DFM check using available DRC data."""
        from .dfm import _dfm_check_lines, _load_profile

        profile = _load_profile("JLCPCB" if jlcpcb else "PCBWay", "standard")
        heading = f"DFM check ({'JLCPCB' if jlcpcb else 'generic'} profile):"
        return "\n".join(_dfm_check_lines(profile, heading=heading))

    @mcp.tool()
    @headless_compatible
    def get_unconnected_nets() -> str:
        """Return only unconnected net issues from DRC."""
        _, report, error = _run_drc_report("unconnected.json")
        if report is None:
            return f"Unable to compute unconnected nets: {error or 'unknown error'}"

        entries = _entries(report, "unconnected_items")
        if not entries:
            return "No unconnected nets were reported."
        return _format_violations("Unconnected nets", entries)

    @mcp.tool()
    @headless_compatible
    def get_courtyard_violations() -> str:
        """Return only courtyard issues from DRC."""
        _, report, error = _run_drc_report("courtyard.json")
        if report is None:
            return f"Unable to compute courtyard issues: {error or 'unknown error'}"

        entries = _entries(report, "items_not_passing_courtyard")
        if not entries:
            return "No courtyard violations were reported."
        return _format_violations("Courtyard violations", entries)

    @mcp.tool()
    @headless_compatible
    def get_silk_to_pad_violations() -> str:
        """Return silkscreen overlap issues from DRC."""
        _, report, error = _run_drc_report("silk_to_pad.json")
        if report is None:
            return f"Unable to compute silk-to-pad issues: {error or 'unknown error'}"

        entries = [
            entry
            for entry in _entries(report, "violations")
            if "silk" in str(entry.get("description", "")).lower()
            and "pad" in str(entry.get("description", "")).lower()
        ]
        if not entries:
            return "No silk-to-pad violations were reported."
        return _format_violations("Silk-to-pad violations", entries)

    @mcp.tool()
    @headless_compatible
    def validate_footprints_vs_schematic() -> str:
        """Compare PCB footprint references against the schematic symbol references."""
        outcome = _footprint_parity_outcome()
        lines = [
            "Footprint versus schematic comparison:",
            f"- Status: {outcome.status}",
            f"- {outcome.summary}",
        ]
        lines.extend(f"- {detail}" for detail in outcome.details)
        return "\n".join(lines)

    # ── FAZ 5.1 — DRC Exclusion tools ──────────────────────────────────

    def _drc_exclusions_path() -> Path:
        cfg = get_config()
        if cfg.project_dir is None:
            raise ValueError("No active project is configured.")
        target = cfg.project_dir / ".kicad-mcp"
        target.mkdir(parents=True, exist_ok=True)
        return target / "drc_exclusions.json"

    def _load_drc_exclusions() -> dict[str, object]:
        path = _drc_exclusions_path()
        if not path.exists():
            payload: dict[str, object] = {"exclusions": []}
            path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            return payload
        return cast(dict[str, object], json.loads(path.read_text(encoding="utf-8")))

    def _save_drc_exclusions(payload: dict[str, object]) -> Path:
        path = _drc_exclusions_path()
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return path

    @mcp.tool()
    @headless_compatible
    def drc_list_exclusions() -> str:
        """List all DRC violation exclusions stored for the active project.

        Returns a JSON array of exclusions, each with a 'uuid' (violation
        identifier), 'reason', and 'created' timestamp.
        """
        state = _load_drc_exclusions()
        exclusions = cast(list[dict[str, object]], state.get("exclusions", []))
        if not exclusions:
            return json.dumps({"exclusions": [], "count": 0}, indent=2)
        return json.dumps({"exclusions": exclusions, "count": len(exclusions)}, indent=2)

    @mcp.tool()
    @headless_compatible
    def drc_add_exclusion(reason: str = "Reviewed — not actionable.") -> str:
        """Add DRC exclusions for the current violation set.

        Runs DRC, lists all violations, and asks the user to pick which UUIDs
        to exclude.  Because MCP tools cannot interactively prompt, this tool
        excludes ALL current DRC violations and records a reason string.

        Use ``drc_list_exclusions`` afterward to review what was excluded.
        """
        _, report, error = _run_drc_report("drc_add_exclusion.json")
        if report is None:
            return f"Could not run DRC: {error or 'unknown error'}"
        violations = _entries(report, "violations")
        if not violations:
            return "No DRC violations found — nothing to exclude."

        state = _load_drc_exclusions()
        existing_uuids = {
            str(excl.get("uuid", ""))
            for excl in cast(list[dict[str, object]], state.get("exclusions", []))
        }
        exclusions = cast(list[dict[str, object]], state.setdefault("exclusions", []))
        now = datetime.now(UTC).isoformat()
        added = 0
        for violation in violations:
            uuid = str(violation.get("uuid", ""))
            if not uuid or uuid in existing_uuids:
                continue
            exclusions.append(
                {
                    "uuid": uuid,
                    "reason": reason,
                    "created": now,
                    "description": str(violation.get("description", "")),
                }
            )
            existing_uuids.add(uuid)
            added += 1

        _save_drc_exclusions(state)
        return f"Added {added} DRC exclusion(s). Total exclusions stored: {len(exclusions)}."

    @mcp.tool()
    @headless_compatible
    def drc_remove_exclusion(uuid: str) -> str:
        """Remove a single DRC exclusion by its violation UUID.

        Use ``drc_list_exclusions`` to retrieve the UUID of the exclusion to remove.
        """
        state = _load_drc_exclusions()
        exclusions = cast(list[dict[str, object]], state.get("exclusions", []))
        before = len(exclusions)
        state["exclusions"] = [excl for excl in exclusions if str(excl.get("uuid", "")) != uuid]
        removed = before - len(cast(list[dict[str, object]], state["exclusions"]))
        if removed == 0:
            return f"No exclusion found with UUID '{uuid}'."
        _save_drc_exclusions(state)
        return f"Removed 1 DRC exclusion (UUID: {uuid})."

    @mcp.tool()
    @headless_compatible
    def drc_validate_exclusions() -> str:
        """Validate that stored DRC exclusions still cover active violations.

        Re-runs DRC and reports which previously excluded violations are
        still present (valid) and which have been resolved (stale).
        """
        state = _load_drc_exclusions()
        exclusions = cast(list[dict[str, object]], state.get("exclusions", []))
        if not exclusions:
            return "No DRC exclusions stored for the active project."

        _, report, error = _run_drc_report("drc_validate_exclusions.json")
        if report is None:
            return f"Could not run DRC: {error or 'unknown error'}"
        active_uuids = {str(v.get("uuid", "")) for v in _entries(report, "violations")}

        valid = []
        stale = []
        for excl in exclusions:
            uuid = str(excl.get("uuid", ""))
            if uuid in active_uuids:
                valid.append(excl)
            else:
                stale.append(excl)

        return json.dumps(
            {
                "total_exclusions": len(exclusions),
                "valid_exclusions": len(valid),
                "stale_exclusions": len(stale),
                "active_violations": len(active_uuids),
                "valid": valid[:20],
                "stale": stale[:20],
            },
            indent=2,
        )

    # ── FAZ 5.2 — ERC Rule Severity tools ──────────────────────────────

    _erc_rule_names: list[str] = [
        "power_pin_not_driven",
        "pin_not_connected",
        "pin_to_pin_warning",
        "unresolved_variable",
        "missing_input_pin_connection",
        "missing_power_pin_connection",
        "missing_power_symbol",
        "bus_conflict",
        "label_conflict",
        "global_label_conflict",
        "hierarchical_label_conflict",
        "duplicate_reference",
        "invalid_reference",
        "extra_units",
        "no_connect_connected",
    ]

    def _erc_severity_path() -> Path:
        cfg = get_config()
        if cfg.project_dir is None:
            raise ValueError("No active project is configured.")
        target = cfg.project_dir / ".kicad-mcp"
        target.mkdir(parents=True, exist_ok=True)
        return target / "erc_severity.json"

    def _load_erc_severity() -> dict[str, str]:
        path = _erc_severity_path()
        if not path.exists():
            payload: dict[str, str] = {rule: "error" for rule in _erc_rule_names}
            path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            return payload
        return cast(dict[str, str], json.loads(path.read_text(encoding="utf-8")))

    def _save_erc_severity(payload: dict[str, str]) -> Path:
        path = _erc_severity_path()
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return path

    @mcp.tool()
    @headless_compatible
    def erc_list_rules() -> str:
        """List known ERC rules and their current severity levels.

        Severity levels are: ``error``, ``warning``, or ``ignore``.
        """
        severity_map = _load_erc_severity()
        payload = {
            "rules": [
                {"name": name, "severity": severity_map.get(name, "error")}
                for name in _erc_rule_names
            ]
        }
        return json.dumps(payload, indent=2)

    @mcp.tool()
    @headless_compatible
    def erc_set_rule_severity(rule_name: str, severity: str) -> str:
        """Override the severity of an ERC rule.

        Parameters
        ----------
        rule_name : str
            Name of the ERC rule (use ``erc_list_rules`` to see available names).
        severity : str
            One of ``error``, ``warning``, or ``ignore``.
        """
        severity_lower = severity.casefold().strip()
        if severity_lower not in {"error", "warning", "ignore"}:
            raise ValueError("Severity must be one of: error, warning, ignore.")
        if rule_name not in _erc_rule_names:
            raise ValueError(
                f"Unknown ERC rule '{rule_name}'. Available rules: {', '.join(_erc_rule_names)}"
            )
        state = _load_erc_severity()
        state[rule_name] = severity_lower
        _save_erc_severity(state)
        return f"ERC rule '{rule_name}' severity set to '{severity_lower}'."

    @mcp.tool()
    @headless_compatible
    def erc_reset_rules(rule_name: str | None = None) -> str:
        """Reset one or all ERC rule severities back to their default (``error``).

        Parameters
        ----------
        rule_name : str | None
            Specific rule to reset, or omit to reset all rules.
        """
        state = _load_erc_severity()
        if rule_name:
            if rule_name not in _erc_rule_names:
                raise ValueError(
                    f"Unknown ERC rule '{rule_name}'. Available rules: {', '.join(_erc_rule_names)}"
                )
            state[rule_name] = "error"
            _save_erc_severity(state)
            return f"ERC rule '{rule_name}' reset to default severity (error)."
        for name in _erc_rule_names:
            state[name] = "error"
        _save_erc_severity(state)
        return f"All {len(_erc_rule_names)} ERC rules reset to default severity (error)."
