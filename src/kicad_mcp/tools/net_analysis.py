"""Net analysis tools: net statistics, net inspector, and board stats CLI wrapper.

FAZ 6.1 — pcb_get_net_statistics
FAZ 6.2 — pcb_net_inspector
FAZ 6.3 — pcb_export_stats
"""

from __future__ import annotations

import json
import logging
from typing import Any

from mcp.server.fastmcp import FastMCP

from ..connection import KiCadConnectionError, get_board
from ..utils.units import nm_to_mm
from .export_support import _get_pcb_file
from .metadata import headless_compatible


def _collect_nets_from_board() -> list[dict[str, Any]]:
    """Collect net data from a live KiCad IPC connection."""
    try:
        board = get_board()
        nets = board.get_nets()
    except (KiCadConnectionError, OSError, AttributeError) as exc:
        raise RuntimeError(f"Could not retrieve nets from live board: {exc}") from exc

    result: list[dict[str, Any]] = []
    for net in nets:
        net_info = {
            "code": getattr(net, "code", None) or 0,
            "name": getattr(net, "name", "") or "",
            "class_name": getattr(net, "class_name", "") or "",
        }
        try:
            net_info["track_count"] = len(board.get_tracks_for_net(net.code))  # type: ignore[attr-defined]
        except Exception:
            net_info["track_count"] = 0
        try:
            net_info["via_count"] = len(board.get_vias_for_net(net.code))  # type: ignore[attr-defined]
        except Exception:
            net_info["via_count"] = 0
        try:
            net_info["pad_count"] = len(board.get_pads_for_net(net.code))  # type: ignore[attr-defined]
        except Exception:
            net_info["pad_count"] = 0
        # Total track length
        total_length_mm = 0.0
        try:
            for track in board.get_tracks_for_net(net.code):  # type: ignore[attr-defined]
                length = getattr(track, "length", None)
                if length is not None:
                    total_length_mm += nm_to_mm(length)
        except Exception:
            logging.exception("Failed to get track length for net %s", getattr(net, "name", "?"))
        net_info["total_track_length_mm"] = round(total_length_mm, 4)
        result.append(net_info)
    return result


def _collect_nets_from_file() -> list[dict[str, Any]]:
    """Collect net data by parsing the PCB file as S-expression text."""
    from .board_file import _normalize_board_content

    content = _normalize_board_content(_get_pcb_file().read_text(encoding="utf-8", errors="ignore"))
    nets: list[dict[str, Any]] = []
    seen_codes: set[int] = set()
    for match in __import__("re").finditer(r'\(net\s+(\d+)\s+"((?:\\.|[^"\\])*)"', content):
        code = int(match.group(1))
        name = match.group(2)
        if code in seen_codes:
            continue
        seen_codes.add(code)
        nets.append({"code": code, "name": name, "class_name": ""})
    return nets


def _nets() -> list[dict[str, Any]]:
    try:
        return _collect_nets_from_board()
    except (RuntimeError, KiCadConnectionError):
        return _collect_nets_from_file()


def register(mcp: FastMCP) -> None:
    """Register net analysis tools."""

    @mcp.tool()
    @headless_compatible
    def pcb_get_net_statistics() -> str:
        """Return statistical data about all nets in the active PCB.

        Includes per-net counts of tracks, vias, pads, and total track length
        (mm).  Uses an active KiCad IPC connection when available; falls back
        to file-level net enumeration.
        """
        nets = _nets()
        if not nets:
            return json.dumps({"nets": [], "count": 0, "summary": {}}, indent=2)

        lengths = [
            float(net.get("total_track_length_mm", 0))
            for net in nets
            if "total_track_length_mm" in net
        ]
        summary: dict[str, object] = {
            "total_nets": len(nets),
            "nets_with_tracks": sum(1 for net in nets if net.get("track_count", 0) > 0),
            "nets_with_vias": sum(1 for net in nets if net.get("via_count", 0) > 0),
            "nets_with_pads": sum(1 for net in nets if net.get("pad_count", 0) > 0),
        }
        if lengths:
            summary["min_track_length_mm"] = round(min(lengths), 4)
            summary["max_track_length_mm"] = round(max(lengths), 4)
            summary["total_track_length_mm"] = round(sum(lengths), 4)

        return json.dumps(
            {"nets": nets[:200], "count": len(nets), "summary": summary},
            indent=2,
        )

    @mcp.tool()
    @headless_compatible
    def pcb_net_inspector(net_name: str) -> str:
        """Inspect every detail about a specific net in the PCB.

        Parameters
        ----------
        net_name : str
            The exact net name to inspect (e.g. ``GND``, ``+3V3``, ``USB_DP``).
        """
        nets = _nets()
        matches = [n for n in nets if n.get("name", "") == net_name]
        if not matches:
            available = ", ".join(sorted(set(n.get("name", "") for n in nets[:100])))
            return f"Net '{net_name}' was not found in the PCB. Sample nets: {available}"

        net = matches[0]
        net_code = int(net.get("code", -1))

        # Collect footprint pads on this net
        pads_on_net: list[dict[str, object]] = []
        try:
            board = get_board()
            for footprint in board.get_footprints():
                for pad in footprint.get_pads():  # type: ignore[attr-defined]
                    if pad.net and pad.net.code == net_code:
                        pads_on_net.append(
                            {
                                "reference": footprint.reference_field.text.value,
                                "pad": pad.number,
                                "layer": str(pad.layer),
                            }
                        )
        except Exception:
            # File fallback — parse footprint pad nets
            from .board_file import _normalize_board_content

            content = _normalize_board_content(
                _get_pcb_file().read_text(encoding="utf-8", errors="ignore")
            )
            for fp_match in __import__("re").finditer(
                r"\(footprint\s+.*?\)",
                content,
                __import__("re").DOTALL,
            ):
                block = fp_match.group()
                ref_m = __import__("re").search(r'\(property\s+"Reference"\s+"([^"]*)"', block)
                if not ref_m:
                    continue
                for pad_m in __import__("re").finditer(
                    r'\(pad\s+"([^"]*)"\s+\w+\s+\(net\s+' + str(net_code) + r'\s+"[^"]*"\)',
                    block,
                ):
                    pads_on_net.append(
                        {
                            "reference": ref_m.group(1),
                            "pad": pad_m.group(1),
                            "layer": "unknown",
                        }
                    )

        payload: dict[str, object] = {
            "net_name": net_name,
            "net_code": net_code,
            "class_name": net.get("class_name", ""),
            "track_count": net.get("track_count", 0),
            "via_count": net.get("via_count", 0),
            "pad_count": net.get("pad_count", 0),
            "total_track_length_mm": net.get("total_track_length_mm", 0),
            "footprint_pads": pads_on_net[:100],
        }
        return json.dumps(payload, indent=2)
