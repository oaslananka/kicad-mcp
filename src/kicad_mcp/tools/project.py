"""Project setup and discovery tools."""

from __future__ import annotations

import json
import math
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal

import structlog
from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from .. import __version__
from ..config import get_config
from ..connection import KiCadConnectionError, get_kicad, reset_connection
from ..discovery import find_kicad_version, find_recent_projects, scan_project_dir
from ..models.component_contracts import find_component_contract
from ..models.intent import (
    ComplianceTarget,
    CostTarget,
    InterfaceSpec,
    MechanicalConstraint,
    PowerRailSpec,
    ThermalEnvelope,
)
from ..path_safety import assert_within
from ..prompts.workflows import render_professional_circuit_design_prompt
from ..utils.cache import clear_ttl_cache, ttl_cache
from .design_intent_state import (
    DecouplingPairIntent,
    ProjectDesignIntent,
    ProjectDesignSpec,
    ProjectSpecResolution,
    ProjectSpecSource,
    RFKeepoutIntent,
    set_design_intent_resolver,
)
from .fixers import fixers_for_gate, sampling_prompt_for_gate
from .metadata import headless_compatible
from .router import TOOL_CATEGORIES, available_profiles

logger = structlog.get_logger(__name__)
__all__ = [
    "DecouplingPairIntent",
    "ProjectDesignIntent",
    "ProjectDesignSpec",
    "ProjectSpecResolution",
    "ProjectSpecSource",
    "RFKeepoutIntent",
    "resolve_design_intent",
]

PROJECT_SPEC_DIRNAME = ".kicad-mcp"
PROJECT_SPEC_FILENAME = "project_spec.json"
LEGACY_DESIGN_INTENT_FILENAME = "design_intent.json"
DEFAULT_INFERRED_DECOUPLING_DISTANCE_MM = 6.0
_REPORTED_LEGACY_INTENT_PATHS: set[Path] = set()


class ScanDirectoryInput(BaseModel):
    """Directory scan parameters."""

    path: str = Field(min_length=1, max_length=1000)


class CreateProjectInput(BaseModel):
    """New project creation parameters."""

    path: str = Field(min_length=1, max_length=1000)
    name: str = Field(min_length=1, max_length=120)


class ProjectSpecPayload(BaseModel):
    """Structured design-spec payload returned to capable MCP clients."""

    text: str
    source: ProjectSpecSource = "none"
    path: str = ""
    explicit: ProjectDesignSpec = Field(default_factory=ProjectDesignSpec)
    inferred: ProjectDesignSpec = Field(default_factory=ProjectDesignSpec)
    resolved: ProjectDesignSpec = Field(default_factory=ProjectDesignSpec)
    notes: list[str] = Field(default_factory=list)


class ProjectSpecValidationPayload(BaseModel):
    """Structured project-spec validation payload."""

    text: str
    valid: bool
    issues: list[str] = Field(default_factory=list)


class ProjectNextActionPayload(BaseModel):
    """Structured next-action recommendation derived from the project gate."""

    text: str
    status: str
    gate: str = ""
    reason: str = ""
    suggested_tool: str = ""


class AutoFixAction(BaseModel):
    """One step in the auto-fix loop action plan."""

    gate: str
    status: str
    auto_fixed: bool = False
    auto_fix_description: str = ""
    agent_tool: str = ""
    agent_description: str = ""
    sampling_guidance: str = ""


class AutoFixLoopPayload(BaseModel):
    """Structured result returned by project_auto_fix_loop."""

    text: str
    gate_status: str
    iterations_used: int = 0
    actions: list[AutoFixAction] = Field(default_factory=list)
    remaining_issues: int = 0
    ready_for_release: bool = False


class DesignReportPayload(BaseModel):
    """Comprehensive design-status report combining intent, gates, and recommended actions."""

    text: str
    gate_status: str
    intent_source: ProjectSpecSource = "none"
    power_rails_count: int = 0
    interfaces_count: int = 0
    compliance_count: int = 0
    has_mechanical_constraint: bool = False
    next_tool: str = ""


def _render_project_info() -> str:
    cfg = get_config()
    cli_status = "found" if cfg.kicad_cli.exists() else "missing"
    return "\n".join(
        [
            "Current project configuration:",
            f"- Project directory: {cfg.project_dir or '(not set)'}",
            f"- Project file: {cfg.project_file or '(not set)'}",
            f"- Resolved project: {cfg.project_file or '(not set)'}",
            f"- PCB file: {cfg.pcb_file or '(not set)'}",
            f"- Schematic file: {cfg.sch_file or '(not set)'}",
            f"- Output directory: {cfg.output_dir or '(not set)'}",
            f"- KiCad CLI: {cfg.kicad_cli} ({cli_status})",
            f"- Server profile: {cfg.profile}",
            f"- Experimental tools: {cfg.enable_experimental_tools}",
        ]
    )


def _new_project_files(project_dir: Path, name: str) -> tuple[Path, Path, Path]:
    project_file = project_dir / f"{name}.kicad_pro"
    pcb_file = project_dir / f"{name}.kicad_pcb"
    sch_file = project_dir / f"{name}.kicad_sch"
    return project_file, pcb_file, sch_file


def _project_spec_dir() -> Path:
    cfg = get_config()
    if cfg.project_dir is None:
        raise ValueError(
            "No project is configured. "
            "Call kicad_set_project() or kicad_create_new_project() first."
        )
    return cfg.project_dir / PROJECT_SPEC_DIRNAME


def _project_spec_path() -> Path:
    return _project_spec_dir() / PROJECT_SPEC_FILENAME


def _legacy_design_intent_path() -> Path:
    cfg = get_config()
    if cfg.project_dir is None:
        raise ValueError(
            "No project is configured. "
            "Call kicad_set_project() or kicad_create_new_project() first."
        )
    output_dir = cfg.output_dir or (cfg.project_dir / "output")
    return output_dir / LEGACY_DESIGN_INTENT_FILENAME


def _normalized_unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        cleaned = item.strip()
        if not cleaned:
            continue
        key = cleaned.casefold()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(cleaned)
    return ordered


def _normalize_design_intent(intent: ProjectDesignIntent) -> ProjectDesignIntent:
    return ProjectDesignIntent.model_validate(
        {
            # v1 fields
            "connector_refs": _normalized_unique(intent.connector_refs),
            "decoupling_pairs": [
                {
                    "ic_ref": pair.ic_ref.strip(),
                    "cap_refs": _normalized_unique(pair.cap_refs),
                    "max_distance_mm": pair.max_distance_mm,
                }
                for pair in intent.decoupling_pairs
            ],
            "critical_nets": _normalized_unique(intent.critical_nets),
            "power_tree_refs": _normalized_unique(intent.power_tree_refs),
            "analog_refs": _normalized_unique(intent.analog_refs),
            "digital_refs": _normalized_unique(intent.digital_refs),
            "sensor_cluster_refs": _normalized_unique(intent.sensor_cluster_refs),
            "rf_keepout_regions": [region.model_dump() for region in intent.rf_keepout_regions],
            "manufacturer": intent.manufacturer.strip(),
            "manufacturer_tier": intent.manufacturer_tier.strip(),
            "functional_spacing_mm": intent.functional_spacing_mm,
            "thermal_hotspots": _normalized_unique(intent.thermal_hotspots),
            "critical_frequencies_mhz": intent.critical_frequencies_mhz,
            # v2 fields — pass through as-is (already validated by Pydantic)
            "power_rails": [rail.model_dump() for rail in intent.power_rails],
            "interfaces": [iface.model_dump() for iface in intent.interfaces],
            "mechanical": intent.mechanical.model_dump(),
            "compliance": [c.model_dump() for c in intent.compliance],
            "cost": intent.cost.model_dump(),
            "thermal": intent.thermal.model_dump(),
        }
    )


def _load_design_intent_from_path(path: Path) -> ProjectDesignIntent:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("design_intent_load_failed", path=str(path), error=str(exc))
        return ProjectDesignIntent()
    return _normalize_design_intent(ProjectDesignIntent.model_validate(payload))


def _load_saved_design_intent() -> tuple[
    ProjectDesignIntent,
    Path | None,
    ProjectSpecSource,
    list[str],
]:
    notes: list[str] = []
    path = _project_spec_path()
    if path.exists():
        return _load_design_intent_from_path(path), path, "project_spec", notes

    legacy_path = _legacy_design_intent_path()
    if legacy_path.exists():
        if legacy_path not in _REPORTED_LEGACY_INTENT_PATHS:
            _REPORTED_LEGACY_INTENT_PATHS.add(legacy_path)
            logger.info("legacy_design_intent_loaded", path=str(legacy_path))
        notes.append(
            "Loaded legacy output/design_intent.json. "
            "Run project_set_design_intent() to migrate it into .kicad-mcp/project_spec.json."
        )
        return (
            _load_design_intent_from_path(legacy_path),
            legacy_path,
            "legacy_design_intent",
            notes,
        )

    return ProjectDesignIntent(), None, "none", notes


def load_design_intent() -> ProjectDesignIntent:
    """Load the explicitly saved project design intent/spec, if any."""
    intent, _, _, _ = _load_saved_design_intent()
    return intent


def _persist_project_spec(intent: ProjectDesignIntent) -> Path:
    """Persist the normalized project spec to the canonical project_spec.json path."""
    path = _project_spec_path()
    normalized = _normalize_design_intent(intent)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(normalized.model_dump(), indent=2), encoding="utf-8")
    return path


def save_design_intent(intent: ProjectDesignIntent) -> Path:
    """Persist the normalized project design spec inside the project root."""
    return _persist_project_spec(intent)


def _render_design_intent(intent: ProjectDesignIntent) -> str:
    lines = ["Project design spec:"]
    lines.append(
        "- Connector refs: "
        + (", ".join(intent.connector_refs) if intent.connector_refs else "(none)")
    )
    lines.append(
        "- Critical nets: "
        + (", ".join(intent.critical_nets) if intent.critical_nets else "(none)")
    )
    lines.append(
        "- Power-tree refs: "
        + (", ".join(intent.power_tree_refs) if intent.power_tree_refs else "(none)")
    )
    lines.append(
        "- Analog refs: " + (", ".join(intent.analog_refs) if intent.analog_refs else "(none)")
    )
    lines.append(
        "- Digital refs: " + (", ".join(intent.digital_refs) if intent.digital_refs else "(none)")
    )
    lines.append(
        "- Sensor cluster refs: "
        + (", ".join(intent.sensor_cluster_refs) if intent.sensor_cluster_refs else "(none)")
    )
    lines.append(
        "- Manufacturer: "
        + (
            f"{intent.manufacturer} / {intent.manufacturer_tier}"
            if intent.manufacturer or intent.manufacturer_tier
            else "(none)"
        )
    )
    lines.append(f"- Functional spacing: {intent.functional_spacing_mm:.2f} mm")
    lines.append(
        "- Thermal hotspots: "
        + (", ".join(intent.thermal_hotspots) if intent.thermal_hotspots else "(none)")
    )
    lines.append(
        "- Critical frequencies: "
        + (
            ", ".join(f"{frequency:.2f} MHz" for frequency in intent.critical_frequencies_mhz)
            if intent.critical_frequencies_mhz
            else "(none)"
        )
    )
    lines.append(f"- Decoupling pairs: {len(intent.decoupling_pairs)}")
    for pair in intent.decoupling_pairs[:10]:
        lines.append(
            f"  {pair.ic_ref} <- {', '.join(pair.cap_refs)} (max {pair.max_distance_mm:.2f} mm)"
        )
    lines.append(f"- RF keepout regions: {len(intent.rf_keepout_regions)}")
    for region in intent.rf_keepout_regions[:10]:
        lines.append(
            f"  {region.name}: center=({region.x_mm:.2f}, {region.y_mm:.2f}) "
            f"size=({region.w_mm:.2f} x {region.h_mm:.2f}) mm"
        )

    # v2 fields
    if intent.power_rails:
        lines.append(f"- Power rails: {len(intent.power_rails)}")
        for rail in intent.power_rails[:12]:
            lines.append(
                f"  {rail.name}: {rail.voltage_v}V / {rail.current_max_a}A"
                + (f" via {rail.source_ref}" if rail.source_ref else "")
            )
    if intent.interfaces:
        lines.append(f"- Interfaces: {len(intent.interfaces)}")
        for iface in intent.interfaces[:10]:
            impedance = (
                f"  {iface.impedance_target_ohm}ohm" + (" diff" if iface.differential else "")
                if iface.impedance_target_ohm is not None
                else ""
            )
            lines.append(f"  {iface.kind}{impedance}")
    if intent.compliance:
        lines.append("- Compliance: " + ", ".join(c.kind for c in intent.compliance))
    if intent.cost.unit_cost_usd_max is not None:
        lines.append(f"- Cost target: <${intent.cost.unit_cost_usd_max:.2f}/unit")
    if intent.mechanical.max_height_mm is not None:
        lines.append(f"- Max height: {intent.mechanical.max_height_mm:.1f} mm")
    lines.append(
        f"- Thermal: {intent.thermal.ambient_c}°C ambient, "
        f"max {intent.thermal.max_component_c}°C component"
    )
    return "\n".join(lines)


def _entry_center(entry: dict[str, Any]) -> tuple[float, float] | None:
    x_mm = entry.get("x_mm")
    y_mm = entry.get("y_mm")
    if x_mm is None or y_mm is None:
        return None
    return float(x_mm), float(y_mm)


def _distance_mm(left: dict[str, Any], right: dict[str, Any]) -> float:
    left_center = _entry_center(left)
    right_center = _entry_center(right)
    if left_center is None or right_center is None:
        return math.inf
    return math.hypot(left_center[0] - right_center[0], left_center[1] - right_center[1])


def _critical_nets_from_entries(entries: dict[str, dict[str, Any]]) -> list[str]:
    priority_tokens = ("USB", "CLK", "ETH", "PCIE", "HDMI", "RF", "ANT", "DDR")
    critical: set[str] = set()
    for entry in entries.values():
        for net_name in entry.get("net_names", []):
            candidate = str(net_name).strip()
            if candidate and any(token in candidate.upper() for token in priority_tokens):
                critical.add(candidate)
    return sorted(critical)


def _component_category(reference: str, entry: dict[str, Any]) -> str:
    footprint_name = str(entry.get("name", "")).strip()
    value_name = str(entry.get("value", "")).strip()
    contract = find_component_contract(footprint=footprint_name)
    if contract is not None:
        category = contract.category
        if category in {"mcu", "mcu_module"}:
            return "mcu"
        if category == "sensor":
            return "sensor"
        if category == "connector":
            return "connector"
        if category == "regulator":
            return "regulator"
        if category == "analog":
            return "analog"
        if category in {"memory", "interface"}:
            return "digital"

    upper_ref = reference.upper()
    upper_name = footprint_name.upper()
    upper_value = value_name.upper()
    if upper_ref.startswith("J") or "CONNECTOR" in upper_name or "USB" in upper_name:
        return "connector"
    if upper_ref.startswith("C") or "CAPACITOR" in upper_name:
        return "capacitor"
    if "SENSOR" in upper_name or "SENSOR" in upper_value:
        return "sensor"
    if any(token in upper_name for token in ("BME280", "ADXL", "MPU6050", "LIS3DH")):
        return "sensor"
    if any(token in upper_name for token in ("ESP32", "RP2040", "STM32", "NRF")):
        return "mcu"
    if "MCU" in upper_value:
        return "mcu"
    if "REGULATOR" in upper_name or "BUCK" in upper_value or "LDO" in upper_value:
        return "regulator"
    if upper_ref.startswith("U") and any(
        token in upper_name
        for token in ("QFP", "QFN", "BGA", "SOIC", "DFN", "LGA", "MODULE", "DIP")
    ):
        return "ic"
    return ""


def _infer_design_intent_from_board() -> tuple[ProjectDesignIntent, list[str]]:
    from .board_file import _normalize_board_content, _parse_board_footprint_blocks

    cfg = get_config()
    if cfg.pcb_file is None or not cfg.pcb_file.exists():
        return ProjectDesignIntent(), ["No PCB file was available for design-spec inference."]

    try:
        content = _normalize_board_content(
            cfg.pcb_file.read_text(encoding="utf-8", errors="ignore")
        )
    except OSError as exc:
        return ProjectDesignIntent(), [f"PCB file could not be read for inference ({exc})."]

    footprints = _parse_board_footprint_blocks(content)
    if not footprints:
        return (
            ProjectDesignIntent(),
            ["No PCB footprints were available for design-spec inference."],
        )

    categories = {
        reference: _component_category(reference, entry) for reference, entry in footprints.items()
    }
    connector_refs = sorted(
        reference for reference, category in categories.items() if category == "connector"
    )
    sensor_cluster_refs = sorted(
        reference for reference, category in categories.items() if category == "sensor"
    )
    analog_refs = sorted(
        reference for reference, category in categories.items() if category == "analog"
    )
    digital_refs = sorted(
        reference for reference, category in categories.items() if category in {"digital", "mcu"}
    )
    power_tree_refs = sorted(
        (
            reference
            for reference, category in categories.items()
            if category in {"connector", "regulator", "mcu"}
        ),
        key=lambda reference: (
            float(footprints[reference].get("x_mm", 0.0) or 0.0),
            reference,
        ),
    )

    capacitor_refs = [
        reference for reference, category in categories.items() if category == "capacitor"
    ]
    ic_candidates = [
        reference
        for reference, category in categories.items()
        if category in {"analog", "digital", "ic", "mcu", "regulator", "sensor"}
        or reference.upper().startswith("U")
    ]
    decoupling_pairs: list[dict[str, Any]] = []
    for reference in sorted(ic_candidates):
        if not capacitor_refs:
            continue
        nearest_caps = sorted(
            capacitor_refs,
            key=lambda capacitor_ref: _distance_mm(
                footprints[reference], footprints[capacitor_ref]
            ),
        )[:1]
        if nearest_caps:
            decoupling_pairs.append(
                {
                    "ic_ref": reference,
                    "cap_refs": nearest_caps,
                    "max_distance_mm": DEFAULT_INFERRED_DECOUPLING_DISTANCE_MM,
                }
            )

    notes = [
        f"Inferred {len(connector_refs)} connector refs from PCB footprints.",
        f"Inferred {len(decoupling_pairs)} decoupling pair candidates from PCB placement.",
        f"Inferred {len(sensor_cluster_refs)} sensor refs from PCB footprints.",
        f"Inferred {len(power_tree_refs)} power-tree refs from PCB placement order.",
    ]
    return (
        _normalize_design_intent(
            ProjectDesignIntent(
                connector_refs=connector_refs,
                decoupling_pairs=decoupling_pairs,
                critical_nets=_critical_nets_from_entries(footprints),
                power_tree_refs=power_tree_refs,
                analog_refs=analog_refs,
                digital_refs=digital_refs,
                sensor_cluster_refs=sensor_cluster_refs,
            )
        ),
        notes,
    )


def _merge_design_intent(
    explicit: ProjectDesignIntent,
    inferred: ProjectDesignIntent,
) -> ProjectDesignIntent:
    return _normalize_design_intent(
        ProjectDesignIntent(
            # v1 — explicit wins, fall back to inferred
            connector_refs=explicit.connector_refs or inferred.connector_refs,
            decoupling_pairs=explicit.decoupling_pairs or inferred.decoupling_pairs,
            critical_nets=explicit.critical_nets or inferred.critical_nets,
            power_tree_refs=explicit.power_tree_refs or inferred.power_tree_refs,
            analog_refs=explicit.analog_refs or inferred.analog_refs,
            digital_refs=explicit.digital_refs or inferred.digital_refs,
            sensor_cluster_refs=explicit.sensor_cluster_refs or inferred.sensor_cluster_refs,
            rf_keepout_regions=explicit.rf_keepout_regions or inferred.rf_keepout_regions,
            manufacturer=explicit.manufacturer or inferred.manufacturer,
            manufacturer_tier=explicit.manufacturer_tier or inferred.manufacturer_tier,
            functional_spacing_mm=explicit.functional_spacing_mm,
            thermal_hotspots=explicit.thermal_hotspots,
            critical_frequencies_mhz=explicit.critical_frequencies_mhz,
            # v2 — explicit only (inference does not produce these)
            power_rails=explicit.power_rails,
            interfaces=explicit.interfaces,
            mechanical=explicit.mechanical,
            compliance=explicit.compliance,
            cost=explicit.cost,
            thermal=explicit.thermal,
        )
    )


def resolve_design_intent() -> ProjectSpecResolution:
    """Resolve the saved and inferred design spec into a single view."""
    explicit, path, source, notes = _load_saved_design_intent()
    inferred, inference_notes = _infer_design_intent_from_board()
    resolved = _merge_design_intent(explicit, inferred)
    return ProjectSpecResolution(
        source=source,
        path=str(path) if path is not None else "",
        explicit=explicit,
        inferred=inferred,
        resolved=resolved,
        notes=[*notes, *inference_notes],
    )


set_design_intent_resolver(resolve_design_intent)


def validate_design_intent(intent: ProjectDesignIntent | None = None) -> list[str]:
    """Validate explicit or resolved design-spec references against the active board."""
    from .board_file import _normalize_board_content, _parse_board_footprint_blocks

    cfg = get_config()
    if cfg.pcb_file is None or not cfg.pcb_file.exists():
        return []

    try:
        board_text = _normalize_board_content(
            cfg.pcb_file.read_text(encoding="utf-8", errors="ignore")
        )
    except OSError as exc:
        return [f"PCB file could not be read while validating the design spec ({exc})."]

    references = set(_parse_board_footprint_blocks(board_text))
    candidate = intent or resolve_design_intent().resolved
    issues: list[str] = []
    for reference in candidate.connector_refs:
        if reference not in references:
            issues.append(f"Connector ref '{reference}' is not present on the PCB.")
    for reference in candidate.power_tree_refs:
        if reference not in references:
            issues.append(f"Power-tree ref '{reference}' is not present on the PCB.")
    for reference in candidate.analog_refs:
        if reference not in references:
            issues.append(f"Analog ref '{reference}' is not present on the PCB.")
    for reference in candidate.digital_refs:
        if reference not in references:
            issues.append(f"Digital ref '{reference}' is not present on the PCB.")
    for reference in candidate.sensor_cluster_refs:
        if reference not in references:
            issues.append(f"Sensor-cluster ref '{reference}' is not present on the PCB.")
    for pair in candidate.decoupling_pairs:
        if pair.ic_ref not in references:
            issues.append(f"Decoupling IC ref '{pair.ic_ref}' is not present on the PCB.")
        for reference in pair.cap_refs:
            if reference not in references:
                issues.append(f"Decoupling capacitor ref '{reference}' is not present on the PCB.")
    return issues


def _render_project_spec_resolution(resolution: ProjectSpecResolution) -> str:
    source_label = {
        "project_spec": ".kicad-mcp/project_spec.json",
        "legacy_design_intent": "legacy output/design_intent.json",
        "none": "(none)",
    }[resolution.source]
    lines = ["Project design spec resolution:"]
    lines.append(f"- Explicit source: {source_label}")
    lines.append(f"- Explicit path: {resolution.path or '(none)'}")
    if resolution.source == "none":
        lines.append(
            "- Warning: No design intent set. Call project_set_design_intent() "
            "to unlock full scoring."
        )
    lines.append(
        f"- Inferred connectors / decoupling / sensors: "
        f"{len(resolution.inferred.connector_refs)} / "
        f"{len(resolution.inferred.decoupling_pairs)} / "
        f"{len(resolution.inferred.sensor_cluster_refs)}"
    )
    for note in resolution.notes[:8]:
        lines.append(f"- Note: {note}")
    lines.append("")
    lines.append(_render_design_intent(resolution.resolved))
    return "\n".join(lines)


def _queue_reason_from_details(details: list[str], summary: str) -> str:
    ignored_prefixes = (
        "Footprints analysed:",
        "Board frame:",
        "Density:",
        "Connector checks:",
        "Decoupling pair checks:",
        "RF keepout checks:",
        "Power-tree refs checked:",
        "Analog refs checked:",
        "Digital refs checked:",
        "Sensor-cluster refs checked:",
        "Placement score:",
    )
    for detail in details:
        cleaned = detail.strip()
        if not cleaned or cleaned.startswith(ignored_prefixes):
            continue
        if cleaned.startswith("FAIL: "):
            return cleaned[6:]
        if cleaned.startswith("WARN: "):
            return cleaned[6:]
        if cleaned.startswith("BLOCKED: "):
            return cleaned[9:]
        return cleaned
    return summary


def _suggested_tool_for_gate(name: str) -> str:
    return {
        "Schematic": "run_erc()",
        "Schematic connectivity": "schematic_connectivity_gate()",
        "PCB": "run_drc()",
        "Placement": "pcb_score_placement()",
        "PCB transfer": "pcb_transfer_quality_gate()",
        "Manufacturing": "manufacturing_quality_gate()",
        "Footprint parity": "validate_footprints_vs_schematic()",
    }.get(name, "project_quality_gate()")


def _next_action_payload() -> ProjectNextActionPayload:
    from .validation import _evaluate_project_gate

    try:
        outcomes = _evaluate_project_gate()
    except Exception as exc:
        reason = f"Project quality gate could not be evaluated: {exc}"
        lines = [
            "Project next action:",
            "- Status: BLOCKED",
            "- Suggested tool: kicad_get_project_info()",
            f"- Reason: {reason}",
        ]
        return ProjectNextActionPayload(
            text="\n".join(lines),
            status="BLOCKED",
            reason=reason,
            suggested_tool="kicad_get_project_info()",
        )
    actionable = [outcome for outcome in outcomes if outcome.status != "PASS"]
    if not actionable:
        lines = [
            "Project next action:",
            "- Status: PASS",
            "- Suggested tool: export_manufacturing_package()",
            "- Reason: No blocking issues remain.",
        ]
        return ProjectNextActionPayload(
            text="\n".join(lines),
            status="PASS",
            reason="No blocking issues remain.",
            suggested_tool="export_manufacturing_package()",
        )

    actionable.sort(key=lambda outcome: (0 if outcome.status == "BLOCKED" else 1, outcome.name))
    target = actionable[0]
    reason = _queue_reason_from_details(target.details, target.summary)
    suggested_tool = _suggested_tool_for_gate(target.name)
    lines = [
        "Project next action:",
        f"- Status: {target.status}",
        f"- Gate: {target.name}",
        f"- Suggested tool: {suggested_tool}",
        f"- Reason: {reason}",
    ]
    return ProjectNextActionPayload(
        text="\n".join(lines),
        status=target.status,
        gate=target.name,
        reason=reason,
        suggested_tool=suggested_tool,
    )


def register(mcp: FastMCP) -> None:
    """Register project management tools."""

    @mcp.tool()
    @headless_compatible
    def kicad_set_project(
        project_dir: str,
        pcb_file: str = "",
        sch_file: str = "",
        output_dir: str = "",
    ) -> str:
        """Set the active KiCad project directory and file paths."""
        cfg = get_config()
        project_path = Path(project_dir).expanduser().resolve()
        if not project_path.exists() or not project_path.is_dir():
            return "Project directory does not exist or is not a directory."

        scan = scan_project_dir(project_path)
        selected_pcb = Path(pcb_file).expanduser().resolve() if pcb_file else scan.get("pcb")
        selected_sch = Path(sch_file).expanduser().resolve() if sch_file else scan.get("schematic")
        selected_project = scan.get("project")
        if selected_project is not None and selected_pcb is None and selected_sch is None:
            return (
                "E_PROJECT_SCAN_INCOMPLETE: Found a .kicad_pro file but no matching "
                ".kicad_pcb or .kicad_sch file in the selected directory. "
                "Add at least one board or schematic file before activating this project."
            )
        selected_output = (
            Path(output_dir).expanduser().resolve() if output_dir else project_path / "output"
        )

        cfg.apply_project(
            project_path,
            project_file=selected_project,
            pcb_file=selected_pcb,
            sch_file=selected_sch,
            output_dir=selected_output,
        )
        clear_ttl_cache()
        reset_connection()
        return _render_project_info()

    @mcp.tool()
    @headless_compatible
    def kicad_get_project_info() -> str:
        """Show the currently configured KiCad project paths."""
        return _render_project_info()

    @mcp.tool()
    @headless_compatible
    def project_set_design_intent(
        connector_refs: list[str] | None = None,
        decoupling_pairs: list[dict[str, Any]] | None = None,
        critical_nets: list[str] | None = None,
        power_tree_refs: list[str] | None = None,
        analog_refs: list[str] | None = None,
        digital_refs: list[str] | None = None,
        sensor_cluster_refs: list[str] | None = None,
        rf_keepout_regions: list[dict[str, Any]] | None = None,
        manufacturer: str = "",
        manufacturer_tier: str = "",
        functional_spacing_mm: float | None = None,
        thermal_hotspots: list[str] | None = None,
        critical_frequencies_mhz: list[float] | None = None,
        # v2 parameters
        power_rails: list[dict[str, Any]] | None = None,
        interfaces: list[dict[str, Any]] | None = None,
        mechanical: dict[str, Any] | None = None,
        compliance: list[dict[str, Any]] | None = None,
        cost: dict[str, Any] | None = None,
        thermal: dict[str, Any] | None = None,
    ) -> str:
        """Call this FIRST to store design intent for placement, routing, and gates.

        v1 parameters (all boards): connector_refs, decoupling_pairs, critical_nets,
        power_tree_refs, analog_refs, digital_refs, sensor_cluster_refs, rf_keepout_regions,
        manufacturer, manufacturer_tier.

        v2 parameters (professional projects): power_rails (list of PowerRailSpec dicts),
        interfaces (list of InterfaceSpec dicts), mechanical (MechanicalConstraint dict),
        compliance (list of ComplianceTarget dicts), cost (CostTarget dict),
        thermal (ThermalEnvelope dict).
        """
        existing = load_design_intent()
        updated = ProjectDesignIntent(
            connector_refs=existing.connector_refs if connector_refs is None else connector_refs,
            decoupling_pairs=(
                existing.decoupling_pairs if decoupling_pairs is None else decoupling_pairs
            ),
            critical_nets=existing.critical_nets if critical_nets is None else critical_nets,
            power_tree_refs=(
                existing.power_tree_refs if power_tree_refs is None else power_tree_refs
            ),
            analog_refs=existing.analog_refs if analog_refs is None else analog_refs,
            digital_refs=existing.digital_refs if digital_refs is None else digital_refs,
            sensor_cluster_refs=(
                existing.sensor_cluster_refs if sensor_cluster_refs is None else sensor_cluster_refs
            ),
            rf_keepout_regions=(
                existing.rf_keepout_regions if rf_keepout_regions is None else rf_keepout_regions
            ),
            manufacturer=existing.manufacturer if not manufacturer else manufacturer,
            manufacturer_tier=(
                existing.manufacturer_tier if not manufacturer_tier else manufacturer_tier
            ),
            functional_spacing_mm=(
                existing.functional_spacing_mm
                if functional_spacing_mm is None
                else functional_spacing_mm
            ),
            thermal_hotspots=(
                existing.thermal_hotspots if thermal_hotspots is None else thermal_hotspots
            ),
            critical_frequencies_mhz=(
                existing.critical_frequencies_mhz
                if critical_frequencies_mhz is None
                else critical_frequencies_mhz
            ),
            # v2 fields
            power_rails=(
                existing.power_rails
                if power_rails is None
                else [PowerRailSpec.model_validate(r) for r in power_rails]
            ),
            interfaces=(
                existing.interfaces
                if interfaces is None
                else [InterfaceSpec.model_validate(i) for i in interfaces]
            ),
            mechanical=(
                existing.mechanical
                if mechanical is None
                else MechanicalConstraint.model_validate(mechanical)
            ),
            compliance=(
                existing.compliance
                if compliance is None
                else [ComplianceTarget.model_validate(c) for c in compliance]
            ),
            cost=(existing.cost if cost is None else CostTarget.model_validate(cost)),
            thermal=(
                existing.thermal if thermal is None else ThermalEnvelope.model_validate(thermal)
            ),
        )
        path = save_design_intent(updated)
        return (
            f"Stored project design spec at {path}.\n"
            f"{_render_design_intent(_normalize_design_intent(updated))}"
        )

    @mcp.tool()
    @headless_compatible
    @ttl_cache(ttl_seconds=2)
    def project_get_design_intent() -> str:
        """Show the persisted project design intent used by placement and release gates."""
        intent = load_design_intent()
        if intent == ProjectDesignIntent():
            return (
                "No explicit project design intent is stored yet.\n"
                "Use `project_get_design_spec()` to inspect the resolved "
                "explicit + inferred view.\n"
                f"{_render_design_intent(intent)}"
            )
        return _render_design_intent(intent)

    @mcp.tool()
    @headless_compatible
    def project_get_design_spec() -> ProjectSpecPayload:
        """Return the resolved project design spec with explicit and inferred fields."""
        resolution = resolve_design_intent()
        text = _render_project_spec_resolution(resolution)
        return ProjectSpecPayload(
            text=text,
            source=resolution.source,
            path=resolution.path,
            explicit=resolution.explicit,
            inferred=resolution.inferred,
            resolved=resolution.resolved,
            notes=resolution.notes,
        )

    @mcp.tool()
    @headless_compatible
    def project_infer_design_spec() -> ProjectSpecPayload:
        """Infer a design spec from the active PCB without writing it to disk."""
        inferred, notes = _infer_design_intent_from_board()
        resolution = ProjectSpecResolution(
            source="none",
            explicit=ProjectDesignIntent(),
            inferred=inferred,
            resolved=inferred,
            notes=notes,
        )
        return ProjectSpecPayload(
            text=_render_project_spec_resolution(resolution),
            source=resolution.source,
            path=resolution.path,
            explicit=resolution.explicit,
            inferred=resolution.inferred,
            resolved=resolution.resolved,
            notes=resolution.notes,
        )

    @mcp.tool()
    @headless_compatible
    def project_validate_design_spec() -> ProjectSpecValidationPayload:
        """Validate the resolved design spec against the active project PCB."""
        issues = validate_design_intent()
        lines = ["Project design spec validation:"]
        lines.append(f"- Valid: {'yes' if not issues else 'no'}")
        if issues:
            lines.extend(f"- {issue}" for issue in issues[:20])
        else:
            lines.append("- No reference mismatches were found.")
        return ProjectSpecValidationPayload(
            text="\n".join(lines),
            valid=not issues,
            issues=issues,
        )

    @mcp.tool()
    @headless_compatible
    def project_generate_design_prompt(
        circuit_description: str = "",
        target_fab: str = "",
    ) -> str:
        """Generate a professional workflow prompt tailored to the resolved project spec."""
        resolution = resolve_design_intent()
        intent = resolution.resolved
        mechanical = intent.mechanical
        board_size = (
            f"{mechanical.board_width_mm:g}x{mechanical.board_height_mm:g}"
            if mechanical.board_width_mm is not None and mechanical.board_height_mm is not None
            else "100x80"
        )
        fab = target_fab.strip()
        if not fab:
            manufacturer = (intent.manufacturer or "jlcpcb").strip().lower()
            tier = (intent.manufacturer_tier or "standard").strip().lower()
            fab = f"{manufacturer}_{tier}"
        notes = [
            "- Critical nets: "
            + (", ".join(intent.critical_nets) if intent.critical_nets else "(none)"),
            "- Power rails: "
            + (
                ", ".join(
                    f"{rail.name} {rail.voltage_v:g}V/{rail.current_max_a:g}A"
                    for rail in intent.power_rails
                )
                if intent.power_rails
                else "(none)"
            ),
            "- Interfaces: "
            + (
                ", ".join(
                    f"{iface.kind}"
                    + (
                        f" {iface.impedance_target_ohm:g}ohm"
                        if iface.impedance_target_ohm is not None
                        else ""
                    )
                    for iface in intent.interfaces
                )
                if intent.interfaces
                else "(none)"
            ),
            "- Thermal hotspots: "
            + (", ".join(intent.thermal_hotspots) if intent.thermal_hotspots else "(none)"),
        ]
        return render_professional_circuit_design_prompt(
            circuit_description=circuit_description or "KiCad project",
            board_size_mm=board_size,
            layer_count="2",
            target_fab=fab,
            design_notes="\n".join(notes),
        )

    @mcp.tool()
    @headless_compatible
    def project_get_next_action() -> ProjectNextActionPayload:
        """Return the next high-priority action derived from the current project gate."""
        return _next_action_payload()

    @mcp.tool()
    @headless_compatible
    async def project_auto_fix_loop(
        max_iterations: int = 5,
        ctx: Context[Any, Any, Any] | None = None,
    ) -> AutoFixLoopPayload:
        """Run the project quality gate and automatically apply server-side fixes.

        Each iteration:
        1. Evaluates all project quality gates.
        2. For **auto-applicable** gates (annotation, zone refill) — calls the
           underlying fix implementation directly on the server, then re-evaluates.
        3. For gates requiring **agent action** — returns the tool name and
           description so the agent can call it, then the agent must call this
           tool again to continue.

        The loop runs up to ``max_iterations`` times applying auto-fixes.  It
        stops early when all gates pass or when no further auto-fix is possible
        without agent involvement.

        Args:
            max_iterations: Maximum number of auto-fix + re-evaluate cycles to
                attempt before returning control to the agent (1–20).
        """
        import importlib

        from .gates import GateOutcome, _combined_status
        from .validation import _evaluate_project_gate

        max_iterations = max(1, min(max_iterations, 20))
        iterations_used = 0
        auto_fix_log: list[str] = []

        # ------------------------------------------------------------------ #
        # Helper: resolve a "tools.module:function" import string to callable  #
        # ------------------------------------------------------------------ #
        def _resolve_callable(import_str: str) -> Callable[[], object] | None:
            if not import_str:
                return None
            try:
                mod_path, func_name = import_str.rsplit(":", 1)
                full_mod = f"kicad_mcp.{mod_path}"
                mod = importlib.import_module(full_mod)
                candidate = getattr(mod, func_name, None)
                return candidate if callable(candidate) else None
            except Exception:
                return None

        async def _sample_guidance(outcome: GateOutcome) -> str:
            if ctx is None:
                return ""
            sample = getattr(ctx, "sample", None)
            if not callable(sample):
                return ""
            try:
                result = await sample(
                    messages=[
                        {
                            "role": "user",
                            "content": sampling_prompt_for_gate(
                                outcome.name,
                                outcome.summary,
                                outcome.details,
                            ),
                        }
                    ],
                    max_tokens=256,
                    system_prompt="You are a KiCad expert. Reply briefly and directly.",
                )
            except Exception:
                return ""

            content = getattr(result, "content", None)
            if isinstance(content, list) and content:
                return str(getattr(content[0], "text", "") or "")
            return ""

        async def _report_progress(progress: float, total: float, message: str) -> None:
            if ctx is None:
                return
            try:
                await ctx.report_progress(progress, total, message)
            except ValueError:
                return

        await _report_progress(0, 100, "Project quality gate is being evaluated...")

        outcomes = _evaluate_project_gate()
        iterations_used += 1

        for _iter in range(max_iterations - 1):  # -1 because we already ran once above
            # Find the first failing gate that has an auto-applicable fixer
            applied_any = False
            for outcome in outcomes:
                if outcome.status == "PASS":
                    continue
                fixers = fixers_for_gate(outcome.name)
                auto_fixer = next((f for f in fixers if f.auto_applicable), None)
                if auto_fixer is None:
                    continue
                fn = _resolve_callable(auto_fixer.callable_import)
                if fn is None:
                    continue
                try:
                    fix_result = fn()
                    auto_fix_log.append(
                        f"[iter {iterations_used}] Auto-fixed '{outcome.name}' "
                        f"via {auto_fixer.tool}: {fix_result}"
                    )
                    applied_any = True
                except Exception as exc:
                    auto_fix_log.append(
                        f"[iter {iterations_used}] Auto-fix '{auto_fixer.tool}' "
                        f"for '{outcome.name}' raised: {exc}"
                    )

            if not applied_any:
                break  # Nothing left for the server to do — hand off to agent

            # Re-evaluate after applying fixes
            progress = min(90, 10 + (iterations_used * 15))
            await _report_progress(
                progress,
                100,
                f"Re-evaluating quality gates after iteration {iterations_used}...",
            )
            outcomes = _evaluate_project_gate()
            iterations_used += 1

            if all(o.status == "PASS" for o in outcomes):
                break  # All gates green — done

        # ------------------------------------------------------------------ #
        # Build the final action list for the agent                           #
        # ------------------------------------------------------------------ #
        actions: list[AutoFixAction] = []
        for outcome in outcomes:
            if outcome.status == "PASS":
                continue
            fixers = fixers_for_gate(outcome.name)
            auto_fixer = next((f for f in fixers if f.auto_applicable), None)
            agent_fixer = next((f for f in fixers if not f.auto_applicable), None)
            sampling_guidance = await _sample_guidance(outcome)
            actions.append(
                AutoFixAction(
                    gate=outcome.name,
                    status=outcome.status,
                    auto_fixed=False,
                    auto_fix_description=(auto_fixer.description if auto_fixer is not None else ""),
                    agent_tool=(
                        (agent_fixer.tool if agent_fixer is not None else "")
                        or (auto_fixer.tool if auto_fixer is not None else "")
                    ),
                    agent_description=(
                        (agent_fixer.description if agent_fixer is not None else "")
                        or (auto_fixer.description if auto_fixer is not None else "")
                    ),
                    sampling_guidance=sampling_guidance,
                )
            )

        remaining = sum(1 for a in actions if not a.auto_fixed)
        ready = len(actions) == 0

        lines = [f"project_auto_fix_loop: {iterations_used}/{max_iterations} iteration(s) used."]
        if auto_fix_log:
            lines.append("Server-side auto-fixes applied:")
            lines.extend(f"  {entry}" for entry in auto_fix_log)
        if ready:
            lines.append("Status: PASS — all gates pass. Ready for manufacturing release.")
        else:
            lines.append(
                f"Status: {len(actions)} gate(s) still failing ({remaining} require agent action)."
            )
            for action in actions:
                lines.append(
                    f"  [AGENT] {action.gate}: call {action.agent_tool}() "
                    f"— {action.agent_description}"
                )
                if action.sampling_guidance:
                    lines.append(f"    Sampling guidance: {action.sampling_guidance}")
            lines.append("After applying the recommended tool, call project_auto_fix_loop() again.")

        combined = _combined_status(
            [
                GateOutcome(
                    name=o.name,
                    status=o.status,
                    summary=o.summary,
                    details=o.details,
                )
                for o in outcomes
            ]
        )

        await _report_progress(100, 100, "Project auto-fix loop completed.")

        return AutoFixLoopPayload(
            text="\n".join(lines),
            gate_status=combined,
            iterations_used=iterations_used,
            actions=actions,
            remaining_issues=remaining,
            ready_for_release=ready,
        )

    @mcp.tool()
    @headless_compatible
    def project_full_validation_loop(
        max_iterations: int = 5,
        fix_tier: Literal["auto_only", "suggest"] = "auto_only",
    ) -> AutoFixLoopPayload:
        """Run ERC/DRC/project gates in a bounded fix-and-rerun validation loop."""
        import importlib

        from .gates import GateOutcome, _combined_status
        from .validation import _evaluate_project_gate

        max_iterations = max(1, min(max_iterations, 20))
        outcomes = _evaluate_project_gate()
        fix_log: list[str] = []
        iterations_used = 1

        def _resolve_callable(import_str: str) -> Callable[[], object] | None:
            if not import_str:
                return None
            try:
                mod_path, func_name = import_str.rsplit(":", 1)
                module = importlib.import_module(f"kicad_mcp.{mod_path}")
                candidate = getattr(module, func_name, None)
                return candidate if callable(candidate) else None
            except Exception:
                return None

        while iterations_used < max_iterations:
            if all(outcome.status == "PASS" for outcome in outcomes):
                break
            blocker = next((outcome for outcome in outcomes if outcome.status != "PASS"), None)
            if blocker is None:
                break
            fixers = fixers_for_gate(blocker.name)
            auto_fixer = next((fixer for fixer in fixers if fixer.auto_applicable), None)
            if auto_fixer is None or fix_tier == "suggest":
                break
            fn = _resolve_callable(auto_fixer.callable_import)
            if fn is None:
                break
            try:
                fix_result = fn()
                fix_log.append(
                    f"[iter {iterations_used}] {blocker.name}: {auto_fixer.tool} -> {fix_result}"
                )
            except Exception as exc:
                fix_log.append(
                    f"[iter {iterations_used}] {blocker.name}: {auto_fixer.tool} raised {exc}"
                )
                break
            outcomes = _evaluate_project_gate()
            iterations_used += 1

        actions: list[AutoFixAction] = []
        for outcome in outcomes:
            if outcome.status == "PASS":
                continue
            fixers = fixers_for_gate(outcome.name)
            agent_fixer = next((fixer for fixer in fixers if not fixer.auto_applicable), None)
            auto_fixer = next((fixer for fixer in fixers if fixer.auto_applicable), None)
            chosen = agent_fixer or auto_fixer
            actions.append(
                AutoFixAction(
                    gate=outcome.name,
                    status=outcome.status,
                    auto_fixed=False,
                    auto_fix_description=auto_fixer.description if auto_fixer else "",
                    agent_tool=chosen.tool if chosen else "project_quality_gate",
                    agent_description=chosen.description if chosen else outcome.summary,
                )
            )

        combined = _combined_status(
            [
                GateOutcome(
                    name=outcome.name,
                    status=outcome.status,
                    summary=outcome.summary,
                    details=outcome.details,
                )
                for outcome in outcomes
            ]
        )
        lines = [
            f"project_full_validation_loop: {iterations_used}/{max_iterations} iteration(s) used.",
        ]
        if fix_log:
            lines.append("Auto-fixes applied:")
            lines.extend(f"  {entry}" for entry in fix_log)
        if not actions:
            lines.append("PASS after validation loop.")
        elif fix_tier == "suggest":
            lines.append("Suggested fixes:")
            lines.extend(
                f"  [SUGGEST] {action.gate}: call {action.agent_tool}() "
                f"- {action.agent_description}"
                for action in actions
            )
        else:
            lines.append("PARTIAL: remaining issues require agent or manual action.")
            lines.extend(
                f"  [REMAINING] {action.gate}: call {action.agent_tool}() "
                f"- {action.agent_description}"
                for action in actions
            )
        return AutoFixLoopPayload(
            text="\n".join(lines),
            gate_status=combined,
            iterations_used=iterations_used,
            actions=actions,
            remaining_issues=len(actions),
            ready_for_release=not actions,
        )

    @mcp.tool()
    @headless_compatible
    def project_gate_trend(gate_name: str, last_n: int = 10) -> str:
        """Return persisted quality-gate trend history for one gate."""
        from ..resources.gate_history import GateHistory

        history = GateHistory.for_active_project()
        payload = {
            "gate_name": gate_name,
            "history": history.trend(gate_name, max(1, min(last_n, 100))),
            "regressions": history.regression_check(),
        }
        return json.dumps(payload, indent=2, sort_keys=True)

    @mcp.tool()
    @headless_compatible
    def project_design_report() -> DesignReportPayload:
        """Generate a comprehensive design-status report.

        Combines intent summary, v2 spec richness, project gate evaluation, and
        a prioritised list of next steps into a single structured report.
        This is the recommended first call after opening a project to understand
        its current state.
        """
        from .gates import GateOutcome, _combined_status
        from .validation import _evaluate_project_gate

        resolution = resolve_design_intent()
        intent = resolution.resolved

        outcomes = _evaluate_project_gate()
        combined = _combined_status(
            [
                GateOutcome(
                    name=o.name,
                    status=o.status,
                    summary=o.summary,
                    details=o.details,
                )
                for o in outcomes
            ]
        )
        failing = [o for o in outcomes if o.status != "PASS"]

        lines = [
            "# Project Design Report",
            "",
            "## Design Intent",
            _render_design_intent(intent),
            "",
            f"## Gate Status: {combined}",
        ]
        if failing:
            lines.append(f"Failing gates ({len(failing)}):")
            for outcome in failing:
                fixers = fixers_for_gate(outcome.name)
                hint = fixers[0].tool if fixers else "project_quality_gate"
                lines.append(f"- [{outcome.status}] {outcome.name}: {outcome.summary}")
                lines.append(f"  -> Suggested: {hint}()")
        else:
            lines.append("All gates PASS — ready for export_manufacturing_package().")

        lines += [
            "",
            "## Resolution Notes",
            *[f"- {n}" for n in resolution.notes[:8]],
        ]

        next_tool = failing[0].name if failing else "export_manufacturing_package"
        if failing:
            fixers = fixers_for_gate(failing[0].name)
            next_tool = fixers[0].tool if fixers else "project_quality_gate"

        return DesignReportPayload(
            text="\n".join(lines),
            gate_status=combined,
            intent_source=resolution.source,
            power_rails_count=len(intent.power_rails),
            interfaces_count=len(intent.interfaces),
            compliance_count=len(intent.compliance),
            has_mechanical_constraint=(
                bool(intent.mechanical.mount_holes)
                or bool(intent.mechanical.connector_placement)
                or intent.mechanical.max_height_mm is not None
            ),
            next_tool=next_tool,
        )

    @mcp.tool()
    @headless_compatible
    def kicad_list_recent_projects() -> str:
        """List recently opened KiCad projects from KiCad's config files."""
        projects = find_recent_projects()
        if not projects:
            return "No recent KiCad projects were found on this machine."

        lines = [f"Found {len(projects)} recent project(s):"]
        for index, project in enumerate(projects, start=1):
            lines.append(f"{index}. {project}")
        lines.append("")
        lines.append("Call `kicad_set_project()` with one of these paths to activate it.")
        return "\n".join(lines)

    @mcp.tool()
    @headless_compatible
    def kicad_scan_directory(path: str) -> str:
        """Scan a directory and report any KiCad project files it contains."""
        payload = ScanDirectoryInput(path=path)
        directory = Path(payload.path).expanduser().resolve()
        if not directory.exists() or not directory.is_dir():
            return "The supplied path is not a directory."

        scan = scan_project_dir(directory)
        lines = [f"Scan results for {directory}:"]
        lines.append(f"- Project file: {scan['project'] or '(none)'}")
        lines.append(f"- PCB file: {scan['pcb'] or '(none)'}")
        lines.append(f"- Schematic file: {scan['schematic'] or '(none)'}")
        return "\n".join(lines)

    @mcp.tool()
    @headless_compatible
    def kicad_create_new_project(path: str, name: str, confirm_overwrite: bool = False) -> str:
        """Create a new minimal KiCad project structure and activate it."""
        payload = CreateProjectInput(path=path, name=name)
        cfg = get_config()
        base_dir = Path(payload.path).expanduser().resolve()
        if cfg.workspace_root is not None:
            assert_within(cfg.workspace, base_dir)
        project_dir = base_dir / payload.name
        if project_dir.exists() and any(project_dir.iterdir()) and not confirm_overwrite:
            return (
                "Refusing to create a project over an existing non-empty directory.\n"
                f"- Directory: {project_dir}\n"
                "Choose a new name/path or rerun with confirm_overwrite=true."
            )
        project_dir.mkdir(parents=True, exist_ok=True)

        project_file, pcb_file, sch_file = _new_project_files(project_dir, payload.name)
        project_file.write_text(
            json.dumps(
                {
                    "board": {"design_settings": {}},
                    "meta": {"filename": project_file.name, "version": 1},
                    "schematic": {"legacy_lib_dir": "", "page_layout_descr_file": ""},
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        pcb_file.write_text(
            '(kicad_pcb (version 20250316) (generator "kicad-mcp-pro"))\n',
            encoding="utf-8",
        )
        sch_file.write_text(
            (
                "(kicad_sch\n"
                "\t(version 20250316)\n"
                '\t(generator "kicad-mcp-pro")\n'
                f'\t(uuid "{uuid.uuid4()}")\n'
                '\t(paper "A4")\n'
                "\t(lib_symbols)\n"
                '\t(sheet_instances (path "/" (page "1")))\n'
                "\t(embedded_fonts no)\n"
                ")\n"
            ),
            encoding="utf-8",
        )

        cfg.apply_project(
            project_dir,
            project_file=project_file,
            pcb_file=pcb_file,
            sch_file=sch_file,
            output_dir=project_dir / "output",
        )
        reset_connection()
        return "\n".join(
            [
                f"Created project '{payload.name}' at {project_dir}.",
                f"- Project file: {project_file}",
                f"- PCB file: {pcb_file}",
                f"- Schematic file: {sch_file}",
            ]
        )

    @mcp.tool()
    @headless_compatible
    def kicad_get_version() -> str:
        """Get KiCad version information and current connection status."""
        cfg = get_config()
        lines = [f"# KiCad MCP Pro Server v{__version__}", f"CLI path: {cfg.kicad_cli}"]

        cli_version = find_kicad_version(cfg.kicad_cli)
        lines.append(f"CLI version: {cli_version or 'unavailable'}")

        try:
            from kipy.proto.common.types.base_types_pb2 import DocumentType

            kicad = get_kicad()
            lines.append(f"IPC version: {kicad.get_version()}")
            pcb_docs = kicad.get_open_documents(DocumentType.DOCTYPE_PCB)
            sch_docs = kicad.get_open_documents(DocumentType.DOCTYPE_SCHEMATIC)
            lines.append(f"Open PCB documents: {len(pcb_docs)}")
            lines.append(f"Open schematic documents: {len(sch_docs)}")
        except KiCadConnectionError as exc:
            lines.append(f"IPC connection: unavailable ({exc})")
        except Exception as exc:
            logger.debug("kicad_version_ipc_probe_failed", error=str(exc))
            lines.append("IPC connection: unavailable")

        lines.append("")
        lines.append("Use `kicad_set_project()` to configure an active project.")
        return "\n".join(lines)

    @mcp.tool()
    @headless_compatible
    def kicad_help() -> str:
        """Show a concise startup guide and all tool categories."""
        lines = [
            "# KiCad MCP Pro Quick Start",
            "",
            "1. Call `kicad_get_version()` to verify the runtime.",
            "2. Call `kicad_set_project()` or `kicad_create_new_project()`.",
            "3. Inspect `kicad://project/info` and `kicad://board/summary`.",
            "4. Call `kicad_list_tool_categories()` to discover the right tool family.",
            "",
            "Available categories:",
        ]
        for category, info in TOOL_CATEGORIES.items():
            lines.append(f"- `{category}`: {info['description']}")
        lines.append("")
        lines.append("Profiles:")
        lines.extend(f"- `{profile}`" for profile in available_profiles())
        return "\n".join(lines)
