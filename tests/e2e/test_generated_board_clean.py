"""Live ``kicad-cli`` E2E: native DRC on real boards (work order P2-T3).

Proves the kicad-cli DRC integration end to end: a clean board passes native DRC with
zero violations, and a board with a known error is detected (so the check is not
vacuous). Skipped when kicad-cli is not installed; runs in the KiCad-enabled CI job.

Full intent -> generated -> DRC-clean board generation is Phase 4 work; this pins the
live native-DRC contract on real boards today.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

FIXTURES = Path(__file__).resolve().parents[2] / "packages" / "kicad-fixtures" / "fixtures"


def _find_kicad_cli() -> str | None:
    for env_var in ("KICAD_MCP_KICAD_CLI", "KICAD_CLI_PATH", "KICAD_CANARY_KICAD_CLI"):
        value = os.environ.get(env_var)
        if value and Path(value).exists():
            return value
    found = shutil.which("kicad-cli")
    if found:
        return found
    for base in (Path(r"C:/Program Files/KiCad"), Path(r"C:/Program Files (x86)/KiCad")):
        if base.exists():
            for cli in sorted(base.glob("*/bin/kicad-cli.exe"), reverse=True):
                return str(cli)
    return None


KICAD_CLI = _find_kicad_cli()
pytestmark = pytest.mark.skipif(KICAD_CLI is None, reason="kicad-cli not installed")


def _run_drc(pcb: Path, out_json: Path) -> dict[str, object]:
    assert KICAD_CLI is not None  # guarded by pytestmark
    subprocess.run(  # noqa: S603
        [KICAD_CLI, "pcb", "drc", "--format", "json", "--output", str(out_json), str(pcb)],
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    return json.loads(out_json.read_text(encoding="utf-8"))


def test_clean_board_passes_native_drc(tmp_path: Path) -> None:
    pcb = FIXTURES / "empty-board" / "empty-board.kicad_pcb"
    if not pcb.exists():
        pytest.skip("empty-board fixture missing")
    report = _run_drc(pcb, tmp_path / "drc.json")
    violations = report.get("violations", [])
    unconnected = report.get("unconnected_items", [])
    assert violations == [], f"clean board reported DRC violations: {violations}"
    assert unconnected == [], f"clean board reported unconnected items: {unconnected}"


def test_native_drc_detects_known_error(tmp_path: Path) -> None:
    pcb = FIXTURES / "drc-courtyard-error" / "drc-courtyard-error.kicad_pcb"
    if not pcb.exists():
        pytest.skip("drc-courtyard-error fixture missing")
    report = _run_drc(pcb, tmp_path / "drc.json")
    violations = report.get("violations", [])
    unconnected = report.get("unconnected_items", [])
    total = len(violations if isinstance(violations, list) else []) + len(
        unconnected if isinstance(unconnected, list) else []
    )
    assert total > 0, "native DRC did not detect the known error board's issues"
