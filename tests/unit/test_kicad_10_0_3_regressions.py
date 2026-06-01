from __future__ import annotations

import json
from pathlib import Path

from kicad_mcp.tools import validation

REPO_ROOT = Path(__file__).resolve().parents[2]
EXPECTED_ROOT = REPO_ROOT / "packages" / "kicad-fixtures" / "expected"
FIXTURE_ID = "kicad-10-0-3-regressions"


def _expected_report(name: str) -> dict[str, object]:
    path = EXPECTED_ROOT / FIXTURE_ID / name
    return json.loads(path.read_text(encoding="utf-8"))


def test_kicad_10_0_3_drc_report_shape_keeps_status_metadata_parseable() -> None:
    report = _expected_report("drc-report.json")

    violations = validation._entries(report, "violations")

    assert report["metadata"] == {
        "elapsedSeconds": 0.42,
        "kicadVersion": "10.0.3",
        "regression": "drc_elapsed_or_status_output_parsing",
        "statusText": "DRC completed; elapsed=00:00:00.42",
    }
    assert len(violations) == 1
    assert "DRC status and elapsed-time output" in str(violations[0]["message"])
    assert "DRC status and elapsed-time output" in validation._format_violations(
        "Violations",
        [{"severity": violations[0]["severity"], "description": violations[0]["message"]}],
    )


def test_kicad_10_0_3_erc_report_shape_flattens_sheet_violations() -> None:
    report = _expected_report("erc-report.json")

    violations = validation._erc_violations(report)

    assert len(violations) == 2
    assert {entry["severity"] for entry in violations} == {"warning"}
    assert any(entry.get("type") == "sheet_output_shape" for entry in violations)
