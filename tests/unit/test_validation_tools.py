"""Unit tests for validation/quality gate tools (FAZ 5)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from kicad_mcp.server import create_server
from kicad_mcp.tools import validation
from tests.conftest import call_tool_text


def _create_project(tmp_path: Path) -> Path:
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "demo.kicad_pro").write_text("{}", encoding="utf-8")
    (proj / "demo.kicad_pcb").write_text("", encoding="utf-8")
    (proj / "demo.kicad_sch").write_text("", encoding="utf-8")
    return proj


@pytest.mark.anyio
async def test_erc_list_rules_returns_expected(tmp_path: Path) -> None:
    proj = _create_project(tmp_path)
    server = create_server()
    await call_tool_text(server, "kicad_set_project", {"project_dir": str(proj)})
    result = await call_tool_text(server, "erc_list_rules", {})
    assert "power_pin_not_driven" in result
    assert "duplicate_reference" in result


@pytest.mark.anyio
async def test_erc_severity_defaults(tmp_path: Path) -> None:
    proj = _create_project(tmp_path)
    # Write a custom severity file before calling erc_list_rules
    sev_dir = proj / ".kicad-mcp"
    sev_dir.mkdir(parents=True, exist_ok=True)
    custom = {"power_pin_not_driven": "warning", "pin_not_connected": "ignore"}
    (sev_dir / "erc_severity.json").write_text(json.dumps(custom, indent=2), encoding="utf-8")
    server = create_server()
    await call_tool_text(server, "kicad_set_project", {"project_dir": str(proj)})
    result = await call_tool_text(server, "erc_list_rules", {})
    # The result should reflect our custom severity for at least one rule
    assert "warning" in result or "ignore" in result


def test_erc_report_payload_exposes_sheet_and_item_details(tmp_path: Path) -> None:
    report: dict[str, object] = {
        "sheets": [
            {
                "path": "/Power_USB_OR/",
                "uuid_path": "/root/power",
                "violations": [
                    {
                        "severity": "error",
                        "type": "pin_not_connected",
                        "description": "Pin not connected",
                        "items": [
                            {
                                "description": "Symbol U16 Pin 7 [WDI, Input, Line]",
                                "uuid": "uuid-pin-7",
                                "pos": {"x": 3.7592, "y": 1.6764},
                            }
                        ],
                    }
                ],
            },
            {
                "path": "/MCU/",
                "violations": [
                    {
                        "severity": "warning",
                        "type": "label_dangling",
                        "description": "Label connected to only one pin",
                        "items": [
                            {
                                "description": "Global Label 'WDT_FEED'",
                                "uuid": "uuid-label-wdt",
                                "pos": {"x": "37.084", "y": "16.764"},
                            }
                        ],
                    }
                ],
            },
        ]
    }

    payload = validation._erc_report_payload(
        tmp_path / "erc_report.json",
        report,
        None,
        save_report=False,
    )

    assert payload.metadata["violations"] == 2
    details = payload.metadata["violation_details"]
    assert isinstance(details, list)
    assert len(details) == 2
    assert payload.findings[0].location == "/Power_USB_OR/"
    assert payload.findings[1].location == "/MCU/"

    pin_detail = details[0]
    assert pin_detail["sheet_path"] == "/Power_USB_OR/"
    assert pin_detail["sheet_uuid_path"] == "/root/power"
    assert pin_detail["references"] == ["U16"]
    assert pin_detail["pins"] == ["U16.7"]
    pin_item = pin_detail["items"][0]
    assert pin_item["uuid"] == "uuid-pin-7"
    assert pin_item["kind"] == "symbol_pin"
    assert pin_item["reference"] == "U16"
    assert pin_item["pin"] == "7"
    assert pin_item["pin_name"] == "WDI"
    assert pin_item["electrical_type"] == "Input"
    assert pin_item["position_mm"] == {"x": 3.7592, "y": 1.6764}

    label_detail = details[1]
    assert label_detail["sheet_path"] == "/MCU/"
    assert label_detail["nets"] == ["WDT_FEED"]
    label_item = label_detail["items"][0]
    assert label_item["kind"] == "global_label"
    assert label_item["name"] == "WDT_FEED"
    assert label_item["net"] == "WDT_FEED"
    assert label_item["position_mm"] == {"x": 37.084, "y": 16.764}
