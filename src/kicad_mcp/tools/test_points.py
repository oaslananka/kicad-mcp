"""Test-point management for PCB manufacturing.

FAZ 8.1 — pcb_add_test_point, pcb_list_test_points,
         pcb_optimize_test_point_placement, pcb_check_test_coverage.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, cast

from mcp.server.fastmcp import FastMCP

from ..config import get_config
from ..connection import KiCadConnectionError, get_board
from ..utils.units import nm_to_mm
from .export_support import _get_pcb_file
from .metadata import headless_compatible


def _sidecar_dir() -> Path:
    cfg = get_config()
    if cfg.project_dir is None:
        raise ValueError(
            "No active project directory is configured.\n"
            "Resolution: call kicad_set_project('/absolute/path/to/project') first."
        )
    target = cfg.project_dir / ".kicad-mcp"
    target.mkdir(parents=True, exist_ok=True)
    return target


def _test_points_path() -> Path:
    return _sidecar_dir() / "test_points.json"


def _load_test_points() -> dict[str, Any]:
    path = _test_points_path()
    if not path.exists():
        return {"test_points": []}
    try:
        return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, OSError):
        return {"test_points": []}


def _save_test_points(state: dict[str, Any]) -> Path:
    path = _test_points_path()
    path.write_text(json.dumps(state, indent=2), encoding="utf-8")
    return path


def _collect_board_nets() -> list[dict[str, Any]]:
    """Collect net names and codes from the board (IPC or file fallback)."""
    try:
        board = get_board()
        nets = board.get_nets()
        return [
            {
                "code": getattr(n, "code", 0),
                "name": getattr(n, "name", ""),
            }
            for n in nets
        ]
    except (KiCadConnectionError, AttributeError, OSError):
        pass

    # File fallback
    try:
        content = _get_pcb_file().read_text(encoding="utf-8", errors="ignore")
        fallback_nets: list[dict[str, Any]] = []
        seen_codes: set[int] = set()
        for m in re.finditer(r'\(net\s+(\d+)\s+"((?:\\.|[^"\\])*)"', content):
            code = int(m.group(1))
            name = m.group(2)
            if code not in seen_codes:
                seen_codes.add(code)
                fallback_nets.append({"code": code, "name": name})
        return fallback_nets
    except (OSError, ValueError):
        return []


def register(mcp: FastMCP) -> None:
    """Register test-point management tools."""

    @mcp.tool()
    @headless_compatible
    def pcb_add_test_point(
        net_name: str, x_mm: float, y_mm: float, diameter_mm: float = 1.0
    ) -> str:
        """Register a test-point assignment for a net.

        Test points are stored as project-sidecar metadata and are applied
        during the manufacturing release flow.

        Parameters
        ----------
        net_name : str
            Target net name (e.g. ``GND``, ``+3V3``).
        x_mm : float
            X coordinate in mm.
        y_mm : float
            Y coordinate in mm.
        diameter_mm : float
            Pad diameter in mm (default 1.0).
        """
        nets = _collect_board_nets()
        net_names = {n["name"] for n in nets}
        if net_name not in net_names:
            hint = ", ".join(sorted(net_names)[:20])
            raise ValueError(f"Net '{net_name}' not found in board. Known nets: {hint}")

        state = _load_test_points()
        points = cast(list[dict[str, Any]], state.setdefault("test_points", []))
        points.append(
            {
                "net_name": net_name,
                "x_mm": x_mm,
                "y_mm": y_mm,
                "diameter_mm": diameter_mm,
            }
        )
        path = _save_test_points(state)
        return (
            f"Test point added for net '{net_name}' at ({x_mm}, {y_mm}) mm "
            f"with Ø{diameter_mm} mm. Saved to {path}."
        )

    @mcp.tool()
    @headless_compatible
    def pcb_list_test_points() -> str:
        """List all registered test points for the active project."""
        state = _load_test_points()
        points = cast(list[dict[str, Any]], state.get("test_points", []))
        return json.dumps({"test_points": points, "count": len(points)}, indent=2)

    @mcp.tool()
    @headless_compatible
    def pcb_optimize_test_point_placement() -> str:
        """Suggest optimal positions for test points on each registered net.

        Uses the board layout to find accessible pads/vias per net and
        scores them as candidate test points.
        """
        state = _load_test_points()
        points = cast(list[dict[str, Any]], state.get("test_points", []))
        existing_nets = {p["net_name"] for p in points}

        if not existing_nets:
            return (
                "No test points registered yet. Use pcb_add_test_point first. "
                "For unregistered nets, consider adding them manually."
            )

        suggestions: list[dict[str, Any]] = []
        try:
            board = get_board()
            for net_name in sorted(existing_nets):
                net_found = None
                for net in board.get_nets():
                    if getattr(net, "name", "") == net_name:
                        net_found = net
                        break
                if net_found is None:
                    continue

                net_code = getattr(net_found, "code", -1)
                candidates: list[dict[str, Any]] = []

                # Check existing pads on this net
                for fp in board.get_footprints():
                    for pad in fp.get_pads():  # type: ignore[attr-defined]
                        if hasattr(pad, "net") and pad.net and pad.net.code == net_code:
                            pos = getattr(pad, "position", None)
                            if pos:
                                candidates.append(
                                    {
                                        "type": "pad",
                                        "reference": getattr(fp, "reference", "?"),
                                        "pad_number": getattr(pad, "number", ""),
                                        "x_mm": round(nm_to_mm(pos.x), 4),
                                        "y_mm": round(nm_to_mm(pos.y), 4),
                                    }
                                )

                # Check vias on this net
                try:
                    for via in board.get_vias_for_net(net_code):  # type: ignore[attr-defined]
                        pos = getattr(via, "position", None)
                        if pos:
                            candidates.append(
                                {
                                    "type": "via",
                                    "x_mm": round(nm_to_mm(pos.x), 4),
                                    "y_mm": round(nm_to_mm(pos.y), 4),
                                    "diameter_mm": round(nm_to_mm(getattr(via, "drill", 0)), 4),
                                }
                            )
                except Exception:
                    logging.exception("Failed to suggest test point via via")

                suggestions.append(
                    {
                        "net_name": net_name,
                        "candidates": candidates[:20],
                        "candidate_count": len(candidates),
                    }
                )
        except (KiCadConnectionError, AttributeError, OSError) as exc:
            return (
                f"Could not optimize via live board ({exc}). "
                "Ensure KiCad is running with the PCB open, or use "
                "pcb_add_test_point with manual coordinates."
            )

        return json.dumps({"suggestions": suggestions}, indent=2)

    @mcp.tool()
    @headless_compatible
    def pcb_check_test_coverage() -> str:
        """Calculate test-point coverage: how many nets have test points assigned.

        Compares registered test points against all board nets.
        """
        nets = _collect_board_nets()
        all_net_names = {n["name"] for n in nets if n["name"]}

        # Filter out power/ground nets from coverage requirement
        power_nets = {"GND", "VCC", "+3V3", "+5V", "AGND", "DGND", "VIN", "VOUT", "PWR"}
        required_nets = all_net_names - power_nets

        state = _load_test_points()
        points = cast(list[dict[str, Any]], state.get("test_points", []))
        covered_nets = {p["net_name"] for p in points}

        uncovered = sorted(required_nets - covered_nets)
        covered = required_nets & covered_nets
        coverage_pct = round(len(covered) / len(required_nets) * 100, 1) if required_nets else 100.0

        return json.dumps(
            {
                "total_nets": len(all_net_names),
                "required_nets": len(required_nets),
                "covered_nets": len(covered),
                "coverage_pct": coverage_pct,
                "uncovered_nets": uncovered[:50],
                "test_points_registered": len(points),
            },
            indent=2,
        )
