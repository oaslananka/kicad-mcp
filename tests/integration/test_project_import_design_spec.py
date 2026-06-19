from __future__ import annotations

import json
from pathlib import Path

import pytest

from kicad_mcp.server import build_server
from tests.conftest import call_tool_payload, call_tool_text

_COMPLETE_SPEC = """---
design_intent:
  required_sheets:
    - Power_USB_OR
    - MCU_Service
  optional_sheets:
    - LoRa
  connector_refs: [J1, J2]
  critical_nets: [USB_DP, USB_DN, SPI_SCLK]
  power_tree_refs: [U3]
  sensor_cluster_refs: [J_SENS1, J_SENS2]
  manufacturer: JLCPCB
  manufacturer_tier: standard
  power_rails:
    - name: +3V3
      voltage_v: 3.3
      current_max_a: 1.0
      source_ref: U3
  interfaces:
    - kind: usb2
      refs: [J1, U1]
      differential: true
      impedance_target_ohm: 90
  mechanical:
    board_width_mm: 80
    board_height_mm: 50
    max_height_mm: 12
populate:
  - U1
  - U3
dnp:
  - U2
---
# Product prompt continues here.
"""


@pytest.mark.anyio
async def test_project_import_design_spec_dry_run_reports_conservative_yaml(
    sample_project: Path,
) -> None:
    server = build_server("full")
    await call_tool_text(server, "kicad_set_project", {"project_dir": str(sample_project)})

    payload = await call_tool_payload(
        server,
        "project_import_design_spec",
        {"markdown": _COMPLETE_SPEC, "dry_run": True, "strict": True},
    )

    assert isinstance(payload, dict)
    assert payload["valid"] is True
    assert payload["dry_run"] is True
    assert payload["wrote"] is False
    assert payload["missing"] == []
    assert payload["placeholders"] == []
    assert payload["parsed"]["required_sheets"] == ["Power_USB_OR", "MCU_Service"]
    assert payload["parsed"]["optional_sheets"] == ["LoRa"]
    assert payload["parsed"]["critical_nets"] == ["USB_DP", "USB_DN", "SPI_SCLK"]
    assert payload["extras"]["populate"] == ["U1", "U3"]
    assert payload["extras"]["dnp"] == ["U2"]
    assert not (sample_project / ".kicad-mcp" / "project_spec.json").exists()


@pytest.mark.anyio
async def test_project_import_design_spec_strict_reports_missing_and_placeholders(
    sample_project: Path,
) -> None:
    server = build_server("full")
    await call_tool_text(server, "kicad_set_project", {"project_dir": str(sample_project)})
    markdown = """---
design_intent:
  required_sheets:
    - {...}
  power_rails:
    - name: +3V3
      voltage_v: 3.3
      current_max_a: {...}
  mechanical:
    board_width_mm: {...}
---
"""

    payload = await call_tool_payload(
        server,
        "project_import_design_spec",
        {"markdown": markdown, "dry_run": True, "strict": True},
    )

    assert isinstance(payload, dict)
    assert payload["valid"] is False
    assert "mechanical.board_height_mm" in payload["missing"]
    assert "mechanical.board_width_mm" in payload["missing"]
    assert "power_rails[0].current_max_a" in payload["missing"]
    assert "required_sheets[0]" in payload["placeholders"]
    assert "power_rails[0].current_max_a" in payload["placeholders"]
    assert "mechanical.board_width_mm" in payload["placeholders"]


@pytest.mark.anyio
async def test_project_import_design_spec_writes_and_feeds_design_spec(
    sample_project: Path,
) -> None:
    server = build_server("full")
    await call_tool_text(server, "kicad_set_project", {"project_dir": str(sample_project)})

    payload = await call_tool_payload(
        server,
        "project_import_design_spec",
        {"markdown": _COMPLETE_SPEC, "dry_run": False, "strict": True},
    )
    spec = await call_tool_payload(server, "project_get_design_spec", {})

    assert isinstance(payload, dict)
    assert payload["wrote"] is True
    assert isinstance(spec, dict)
    assert spec["source"] == "project_spec"
    assert spec["resolved"]["required_sheets"] == ["Power_USB_OR", "MCU_Service"]
    assert spec["resolved"]["mechanical"]["board_width_mm"] == 80.0
    assert spec["resolved"]["power_rails"][0]["name"] == "+3V3"
    saved = json.loads((sample_project / ".kicad-mcp" / "project_spec.json").read_text())
    assert saved["required_sheets"] == ["Power_USB_OR", "MCU_Service"]


@pytest.mark.anyio
async def test_imported_required_sheet_drives_connectivity_gate(
    sample_project: Path,
) -> None:
    server = build_server("full")
    await call_tool_text(server, "kicad_set_project", {"project_dir": str(sample_project)})
    await call_tool_text(
        server,
        "sch_create_sheet",
        {"name": "Power_USB_OR", "filename": "power.kicad_sch", "x_mm": 40.64, "y_mm": 50.8},
    )
    await call_tool_text(
        server,
        "project_import_design_spec",
        {"markdown": _COMPLETE_SPEC, "dry_run": False, "strict": True},
    )

    result = await call_tool_text(server, "schematic_connectivity_gate", {})

    assert "Schematic connectivity quality gate: FAIL" in result
    assert "Required empty sheets: 1" in result
    assert "Required missing sheets: 1" in result
    assert "Sheet 'Power_USB_OR' is required by design intent" in result
    assert "Required sheet 'MCU_Service' is not present" in result
