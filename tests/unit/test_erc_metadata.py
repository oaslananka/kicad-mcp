import pytest
from kicad_mcp.tools.validation import _erc_violations, _report_entry_finding
from kicad_mcp.models.verdict import Finding, SuggestedFix


def test_finding_metadata_extraction():
    entry = {
        "type": "err_type",
        "description": "an error",
        "severity": "error",
        "sheet_path": "/Sheet1/",
        "items": [
            {"uuid": "1234", "ref": "R1", "pin": "1", "net": "GND", "position": [10.0, 20.0]},
            {"uuid": "5678", "ref": "C1", "pin": "2", "position": [30.0, 40.0]},
        ],
    }

    finding = _report_entry_finding("erc", entry, fix_tool="run_erc")
    assert finding.metadata["sheet_path"] == "/Sheet1/"
    assert finding.metadata["refs"] == ["R1", "C1"]
    assert finding.metadata["pins"] == ["1", "2"]
    assert finding.metadata["nets"] == ["GND"]
    assert finding.metadata["uuids"] == ["1234", "5678"]
    assert finding.metadata["positions"] == [[10.0, 20.0], [30.0, 40.0]]


def test_erc_violations_preserves_sheet_path():
    report = {
        "sheets": [
            {
                "path": "/Subsheet/",
                "name": "Subsheet",
                "violations": [{"type": "err_type", "description": "an error"}],
            }
        ]
    }

    violations = _erc_violations(report)
    assert len(violations) == 1
    assert violations[0]["sheet_path"] == "/Subsheet/"

    # Check that name is used as fallback if path is absent
    report2 = {
        "sheets": [
            {
                "name": "AnotherSheet",
                "violations": [
                    {
                        "type": "err_type2",
                    }
                ],
            }
        ]
    }
    violations2 = _erc_violations(report2)
    assert len(violations2) == 1
    assert violations2[0]["sheet_path"] == "AnotherSheet"
