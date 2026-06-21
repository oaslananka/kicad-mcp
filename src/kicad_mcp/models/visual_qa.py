"""Headless visual-QA for schematics (issue #153).

Detects readability defects that ERC cannot catch — label collisions, off-sheet
items, title-block gaps and dense label fanout — directly from the ``.kicad_sch``
S-expression geometry, with no rendering dependency. When a PNG render
(``sch_render_png``, #115) is available it can be attached as evidence, but every
check here works purely from file geometry so the engine runs anywhere, including
fully headless CI.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

from .contract_verifier import extract_balanced_block

# Landscape paper extents (mm); portrait swaps width/height. Mirrors the table in
# tools/schematic.py but kept local so this pure module stays dependency-free.
PAPER_SIZES_MM: dict[str, tuple[float, float]] = {
    "A4": (297.0, 210.0),
    "A3": (420.0, 297.0),
    "A2": (594.0, 420.0),
    "A1": (841.0, 594.0),
    "A0": (1189.0, 841.0),
    "A": (279.4, 215.9),
    "B": (431.8, 279.4),
    "C": (558.8, 431.8),
    "D": (863.6, 558.8),
    "E": (1117.6, 863.6),
    "USLetter": (279.4, 215.9),
    "USLegal": (355.6, 215.9),
}
DEFAULT_PAPER = "A4"

_LEVEL_ORDER = {"PASS": 0, "INFO": 0, "WARN": 1, "FAIL": 2}

# Two labels closer than this are treated as visually overlapping.
LABEL_OVERLAP_TOLERANCE_MM = 1.0
# A label with this many close neighbours marks a dense, hard-to-read fanout.
DENSE_FANOUT_RADIUS_MM = 5.0
DENSE_FANOUT_NEIGHBOURS = 6


@dataclass(frozen=True, slots=True)
class VisualFinding:
    """A single readability finding with optional object ref/position."""

    level: str
    code: str
    message: str
    ref: str = ""
    x: float | None = None
    y: float | None = None

    def as_dict(self) -> dict[str, object]:
        data: dict[str, object] = {
            "level": self.level,
            "code": self.code,
            "message": self.message,
        }
        if self.ref:
            data["ref"] = self.ref
        if self.x is not None and self.y is not None:
            data["position"] = [self.x, self.y]
        return data


@dataclass(frozen=True, slots=True)
class LabelItem:
    text: str
    x: float
    y: float
    kind: str


@dataclass(frozen=True, slots=True)
class SymbolItem:
    reference: str
    lib_id: str
    x: float
    y: float


def parse_paper_extent(sch_text: str) -> tuple[float, float]:
    """Return the (width, height) of the sheet in millimetres."""

    match = re.search(r'\(paper\s+"([^"]+)"((?:\s+[\w.]+)*)\)', sch_text)
    if match is None:
        return PAPER_SIZES_MM[DEFAULT_PAPER]
    name = match.group(1)
    rest = match.group(2).split()
    numbers = [float(token) for token in rest if _is_number(token)]
    if name == "User" and len(numbers) >= 2:
        return numbers[0], numbers[1]
    width, height = PAPER_SIZES_MM.get(name, PAPER_SIZES_MM[DEFAULT_PAPER])
    if "portrait" in rest:
        width, height = height, width
    return width, height


def _is_number(token: str) -> bool:
    try:
        float(token)
    except ValueError:
        return False
    return True


def parse_labels(sch_text: str) -> list[LabelItem]:
    """Extract local/global/hierarchical labels with their positions."""

    patterns = {
        "local": r'\(label\s+"([^"]*)"\s+\(at\s+(-?[\d.]+)\s+(-?[\d.]+)',
        "global": r'\(global_label\s+"([^"]*)"\s+\(at\s+(-?[\d.]+)\s+(-?[\d.]+)',
        "hierarchical": r'\(hierarchical_label\s+"([^"]*)"\s+\(at\s+(-?[\d.]+)\s+(-?[\d.]+)',
    }
    labels: list[LabelItem] = []
    for kind, pattern in patterns.items():
        for match in re.finditer(pattern, sch_text):
            labels.append(
                LabelItem(match.group(1), float(match.group(2)), float(match.group(3)), kind)
            )
    return labels


def parse_symbols(sch_text: str) -> list[SymbolItem]:
    """Extract placed symbol instances with their reference and position."""

    symbols: list[SymbolItem] = []
    for match in re.finditer(r"\(symbol\s+\(lib_", sch_text):
        block = extract_balanced_block(sch_text, match.start())
        at_match = re.search(r"\(at\s+(-?[\d.]+)\s+(-?[\d.]+)", block)
        if at_match is None:
            continue
        lib_match = re.search(r'\(lib_id\s+"([^"]+)"', block)
        ref_match = re.search(r'\(property\s+"Reference"\s+"([^"]*)"', block)
        symbols.append(
            SymbolItem(
                reference=ref_match.group(1) if ref_match else "",
                lib_id=lib_match.group(1) if lib_match else "",
                x=float(at_match.group(1)),
                y=float(at_match.group(2)),
            )
        )
    return symbols


def detect_label_collisions(
    labels: list[LabelItem], tolerance_mm: float = LABEL_OVERLAP_TOLERANCE_MM
) -> list[VisualFinding]:
    """Flag pairs of labels whose anchor points are within ``tolerance_mm``."""

    findings: list[VisualFinding] = []
    for i in range(len(labels)):
        for j in range(i + 1, len(labels)):
            a = labels[i]
            b = labels[j]
            distance = math.hypot(a.x - b.x, a.y - b.y)
            if distance <= tolerance_mm:
                findings.append(
                    VisualFinding(
                        "WARN",
                        "label_overlap",
                        f"Labels '{a.text}' and '{b.text}' overlap (~{distance:.2f} mm apart).",
                        ref=a.text,
                        x=a.x,
                        y=a.y,
                    )
                )
    return findings


def detect_offsheet(
    symbols: list[SymbolItem],
    labels: list[LabelItem],
    extent: tuple[float, float],
) -> list[VisualFinding]:
    """Flag symbols/labels positioned outside the sheet boundary."""

    width, height = extent
    findings: list[VisualFinding] = []
    for symbol in symbols:
        if not (0.0 <= symbol.x <= width and 0.0 <= symbol.y <= height):
            name = symbol.reference or symbol.lib_id or "symbol"
            findings.append(
                VisualFinding(
                    "WARN",
                    "offsheet_symbol",
                    f"Symbol {name} is outside the {width:.0f}x{height:.0f} mm sheet "
                    f"(at {symbol.x:.1f}, {symbol.y:.1f}).",
                    ref=symbol.reference,
                    x=symbol.x,
                    y=symbol.y,
                )
            )
    for label in labels:
        if not (0.0 <= label.x <= width and 0.0 <= label.y <= height):
            findings.append(
                VisualFinding(
                    "WARN",
                    "offsheet_label",
                    f"Label '{label.text}' is outside the sheet (at {label.x:.1f}, {label.y:.1f}).",
                    ref=label.text,
                    x=label.x,
                    y=label.y,
                )
            )
    return findings


def detect_dense_fanout(
    labels: list[LabelItem],
    radius_mm: float = DENSE_FANOUT_RADIUS_MM,
    neighbours: int = DENSE_FANOUT_NEIGHBOURS,
) -> list[VisualFinding]:
    """Flag tight clusters of labels that are likely unreadable when rendered."""

    findings: list[VisualFinding] = []
    reported: set[int] = set()
    for i, anchor in enumerate(labels):
        if i in reported:
            continue
        close = [
            j
            for j, other in enumerate(labels)
            if j != i and math.hypot(anchor.x - other.x, anchor.y - other.y) <= radius_mm
        ]
        if len(close) >= neighbours:
            reported.update(close)
            reported.add(i)
            findings.append(
                VisualFinding(
                    "INFO",
                    "dense_label_fanout",
                    f"{len(close) + 1} labels cluster within {radius_mm:.0f} mm near "
                    f"({anchor.x:.1f}, {anchor.y:.1f}); rendering may be unreadable.",
                    x=anchor.x,
                    y=anchor.y,
                )
            )
    return findings


def check_title_block(sch_text: str) -> list[VisualFinding]:
    """Report missing title-block fields (title is WARN, others advisory)."""

    match = re.search(r"\(title_block\b", sch_text)
    if match is None:
        return [
            VisualFinding("WARN", "title_block_missing", "Schematic has no title block (advisory).")
        ]
    block = extract_balanced_block(sch_text, match.start())
    findings: list[VisualFinding] = []
    title = re.search(r'\(title\s+"([^"]*)"', block)
    if title is None or not title.group(1).strip():
        findings.append(VisualFinding("WARN", "title_block_title", "Title block has no title."))
    for field_name in ("rev", "date", "company"):
        field_match = re.search(rf'\({field_name}\s+"([^"]*)"', block)
        if field_match is None or not field_match.group(1).strip():
            findings.append(
                VisualFinding(
                    "INFO", f"title_block_{field_name}", f"Title block has no {field_name}."
                )
            )
    return findings


def rollup_status(findings: list[VisualFinding]) -> str:
    worst = 0
    for finding in findings:
        worst = max(worst, _LEVEL_ORDER.get(finding.level, 0))
    for level, rank in _LEVEL_ORDER.items():
        if rank == worst:
            return level
    return "PASS"


def run_visual_qa(sch_text: str, *, render_path: str = "") -> dict[str, object]:
    """Run every headless readability check and return a structured report."""

    extent = parse_paper_extent(sch_text)
    labels = parse_labels(sch_text)
    symbols = parse_symbols(sch_text)

    findings: list[VisualFinding] = []
    findings.extend(detect_label_collisions(labels))
    findings.extend(detect_offsheet(symbols, labels, extent))
    findings.extend(detect_dense_fanout(labels))
    findings.extend(check_title_block(sch_text))

    report: dict[str, object] = {
        "paper_mm": [extent[0], extent[1]],
        "symbol_count": len(symbols),
        "label_count": len(labels),
        "status": rollup_status(findings),
        "findings": [finding.as_dict() for finding in findings],
    }
    if render_path:
        report["render"] = render_path
    return report
