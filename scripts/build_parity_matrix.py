"""Build the KiCad capability-parity artifacts (work order P0-T4).

Source of truth: ``docs/compatibility/capability-parity-matrix.yaml``.

Generates:
  * ``src/kicad_mcp/parity_matrix_data.py`` — embedded copy the runtime tool reads
    (no YAML dependency at runtime, mirroring ``kicad_mcp.compatibility``).
  * ``docs/compatibility/capability-parity.generated.md`` — human-readable view.

Usage:
  uv run python scripts/build_parity_matrix.py            # write artifacts
  uv run python scripts/build_parity_matrix.py --check    # fail on drift (CI)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml

from kicad_mcp.parity import coverage_summary, opportunities

ROOT = Path(__file__).resolve().parents[1]
YAML_PATH = ROOT / "docs" / "compatibility" / "capability-parity-matrix.yaml"
PY_PATH = ROOT / "src" / "kicad_mcp" / "parity_matrix_data.py"
MD_PATH = ROOT / "docs" / "compatibility" / "capability-parity.generated.md"


def load_matrix() -> dict[str, Any]:
    return yaml.safe_load(YAML_PATH.read_text(encoding="utf-8"))


def render_python(matrix: dict[str, Any]) -> str:
    raw = json.dumps(matrix, indent=2, ensure_ascii=False)
    return (
        '"""Embedded capability-parity matrix. GENERATED — do not edit by hand.\n'
        "\n"
        "Synchronized from docs/compatibility/capability-parity-matrix.yaml by\n"
        "scripts/build_parity_matrix.py. Regenerate with:\n"
        "    uv run python scripts/build_parity_matrix.py\n"
        '"""\n'
        "\n"
        "from __future__ import annotations\n"
        "\n"
        "import json\n"
        "from typing import Any\n"
        "\n"
        '_RAW = r"""\n'
        f"{raw}\n"
        '"""\n'
        "\n"
        "CAPABILITY_PARITY_MATRIX: dict[str, Any] = json.loads(_RAW)\n"
    )


def _pct(value: float) -> str:
    return f"{value:.1f}%"


def render_markdown(matrix: dict[str, Any]) -> str:
    summary = coverage_summary(matrix)
    overall = summary["overall"]
    lines: list[str] = [
        "# KiCad Capability Parity (generated)",
        "",
        "Machine-generated from `docs/compatibility/capability-parity-matrix.yaml`. "
        "Refresh with `uv run python scripts/build_parity_matrix.py`.",
        "",
        f"KiCad baseline: `{summary['kicad_baseline']}` · Updated: {summary['updated']}",
        "",
        (
            f"**Overall: {overall['covered']} / {overall['denominator']} "
            f"programmatically-reachable capabilities driven = {_pct(overall['coverage_pct'])}** "
            f"({overall['partial']} partial, {overall['gap']} gap; "
            f"{overall['gui_only_no_api']} GUI-only with no KiCad API, excluded from the "
            "denominator)."
        ),
        "",
        "## Coverage by domain",
        "",
        "| Domain | Coverage | Covered | Partial | Gap | GUI-only (no API) |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for name, stats in summary["domains"].items():
        lines.append(
            f"| `{name}` | {_pct(stats['coverage_pct'])} | {stats['covered']} | "
            f"{stats['partial']} | {stats['gap']} | {stats['gui_only_no_api']} |"
        )
    lines.append(
        f"| **Overall** | **{_pct(overall['coverage_pct'])}** | {overall['covered']} | "
        f"{overall['partial']} | {overall['gap']} | {overall['gui_only_no_api']} |"
    )

    opps = opportunities(matrix)
    lines.extend(["", "## Closeable surface (gap, then partial)", ""])
    if opps:
        lines.append("| Domain | Capability | Status | Channel | MCP tool | Notes |")
        lines.append("|---|---|---|---|---|---|")
        for row in opps:
            tool = f"`{row['mcp_tool']}`" if row["mcp_tool"] else "—"
            notes = row["notes"].replace("|", "\\|")
            lines.append(
                f"| `{row['domain']}` | {row['capability']} | `{row['status']}` | "
                f"`{row['kicad_channel']}` | {tool} | {notes} |"
            )
    else:
        lines.append("No open gaps or partials.")

    lines.extend(["", "## Full matrix", ""])
    for name, info in matrix["domains"].items():
        lines.append(f"### `{name}`")
        lines.append("")
        lines.append(str(info.get("description", "")))
        lines.append("")
        lines.append("| Capability | Channel | MCP tool | Status | KiCad | Notes |")
        lines.append("|---|---|---|---|---|---|")
        for cap in info["capabilities"]:
            tool = f"`{cap['mcp_tool']}`" if cap["mcp_tool"] else "—"
            notes = (cap["notes"] or "").replace("|", "\\|")
            lines.append(
                f"| {cap['capability']} | `{cap['kicad_channel']}` | {tool} | "
                f"`{cap['status']}` | {cap['kicad_version_introduced']} | {notes} |"
            )
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the capability-parity artifacts.")
    parser.add_argument("--check", action="store_true", help="Fail if committed artifacts drift.")
    args = parser.parse_args(argv)

    matrix = load_matrix()
    py_text = render_python(matrix)
    md_text = render_markdown(matrix)

    py_drift = not PY_PATH.is_file() or PY_PATH.read_text(encoding="utf-8") != py_text
    md_drift = not MD_PATH.is_file() or MD_PATH.read_text(encoding="utf-8") != md_text

    if args.check:
        if py_drift or md_drift:
            stale = [
                str(path.relative_to(ROOT))
                for path, drift in ((PY_PATH, py_drift), (MD_PATH, md_drift))
                if drift
            ]
            print(f"capability-parity drift detected: {', '.join(stale)}", file=sys.stderr)
            print("Run: uv run python scripts/build_parity_matrix.py", file=sys.stderr)
            return 1
        print("capability-parity artifacts OK")
        return 0

    PY_PATH.write_text(py_text, encoding="utf-8", newline="\n")
    MD_PATH.write_text(md_text, encoding="utf-8", newline="\n")
    print(f"wrote {PY_PATH.relative_to(ROOT)}")
    print(f"wrote {MD_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
