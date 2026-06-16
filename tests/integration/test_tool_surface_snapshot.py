"""Golden snapshot of the public tool surface (work order P0-T3).

Captures every public tool's name, profile membership, and annotation flags so
that adding, removing, or renaming a tool — or changing its profile set or
annotations — produces a reviewable diff instead of silently altering the
agent-facing contract.

This is intentionally about the *surface* (names / profiles / annotations), not
docstrings; tool summaries are already covered by ``pnpm run docs:tools:check``.

To intentionally update the snapshot after a deliberate surface change::

    UPDATE_TOOL_SURFACE_SNAPSHOT=1 python -m pytest \
        tests/integration/test_tool_surface_snapshot.py

Then review the diff to ``data/tool_surface_snapshot.json`` before committing.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from kicad_mcp.tools.router import EXPERIMENTAL_TOOL_NAMES
from scripts.generate_tools_reference import collect_rows

SNAPSHOT_PATH = Path(__file__).with_name("data") / "tool_surface_snapshot.json"


def _current_surface() -> list[dict[str, object]]:
    surface: list[dict[str, object]] = []
    for row in collect_rows():
        surface.append(
            {
                "name": row.name,
                "profiles": list(row.profiles),
                "read_only": row.read_only,
                "destructive": row.destructive,
                "open_world": row.open_world,
                "idempotent": row.idempotent,
                "headless": row.headless,
                "requires_kicad_running": row.requires_kicad_running,
                "experimental": row.name in EXPERIMENTAL_TOOL_NAMES,
            }
        )
    surface.sort(key=lambda entry: str(entry["name"]))
    return surface


def _dump(surface: list[dict[str, object]]) -> str:
    return json.dumps(surface, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def test_tool_surface_matches_snapshot() -> None:
    current = _current_surface()

    if os.environ.get("UPDATE_TOOL_SURFACE_SNAPSHOT") == "1":
        SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
        SNAPSHOT_PATH.write_text(_dump(current), encoding="utf-8", newline="\n")

    assert SNAPSHOT_PATH.is_file(), (
        f"Missing snapshot {SNAPSHOT_PATH.name}. Regenerate with "
        "UPDATE_TOOL_SURFACE_SNAPSHOT=1 python -m pytest "
        "tests/integration/test_tool_surface_snapshot.py"
    )
    golden = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))

    if golden != current:
        golden_by_name = {str(entry["name"]): entry for entry in golden}
        current_by_name = {str(entry["name"]): entry for entry in current}
        added = sorted(set(current_by_name) - set(golden_by_name))
        removed = sorted(set(golden_by_name) - set(current_by_name))
        changed = sorted(
            name
            for name in set(current_by_name) & set(golden_by_name)
            if current_by_name[name] != golden_by_name[name]
        )
        raise AssertionError(
            "Public tool surface drifted from the golden snapshot.\n"
            f"  added: {added}\n"
            f"  removed: {removed}\n"
            f"  changed (profiles/annotations): {changed}\n"
            "If this is intentional, regenerate with "
            "UPDATE_TOOL_SURFACE_SNAPSHOT=1 python -m pytest "
            "tests/integration/test_tool_surface_snapshot.py and review the diff."
        )
