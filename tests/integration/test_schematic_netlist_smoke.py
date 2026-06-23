from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from kicad_mcp.server import build_server
from tests.conftest import call_tool_text


@pytest.mark.anyio
@pytest.mark.slow
async def test_sch_build_circuit_exports_component_netlist_with_real_kicad_cli(
    tmp_path: Path,
) -> None:
    """Guard against visually valid schematics that disappear from KiCad netlists.

    The file writer can produce an SVG even when the placed-symbol S-expression is
    not accepted as a real component by KiCad's netlist exporter.  This smoke test
    uses the real KiCad CLI when it is installed and proves that a schematic built
    through sch_build_circuit contains at least one exported component.
    """

    kicad_cli = shutil.which("kicad-cli")
    if kicad_cli is None:
        pytest.skip("kicad-cli is not installed")

    project_root = tmp_path / "netlist-smoke"
    server = build_server("full")

    await call_tool_text(
        server,
        "kicad_create_new_project",
        {
            "path": str(project_root),
            "name": "SchSmoke",
            "confirm_overwrite": True,
        },
    )
    project_dir = project_root / "SchSmoke"
    schematic_path = project_dir / "SchSmoke.kicad_sch"

    await call_tool_text(
        server,
        "sch_build_circuit",
        {
            "symbols": [
                {
                    "library": "Device",
                    "symbol_name": "R",
                    "reference": "R1",
                    "value": "10k",
                    "footprint": "Resistor_SMD:R_0805_2012Metric",
                    "x_mm": 50.8,
                    "y_mm": 50.8,
                }
            ],
            "wires": [],
            "labels": [],
            "power_symbols": [],
            "nets": [],
            "auto_layout": False,
        },
    )

    netlist_path = project_dir / "SchSmoke.net"
    subprocess.run(
        [
            kicad_cli,
            "sch",
            "export",
            "netlist",
            str(schematic_path),
            "--output",
            str(netlist_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    netlist = netlist_path.read_text(encoding="utf-8", errors="replace")
    assert "(comp" in netlist
    assert '(ref "R1")' in netlist
    assert '(value "10k")' in netlist
    assert "(components)" not in netlist


@pytest.mark.anyio
@pytest.mark.slow
async def test_sch_build_circuit_custom_power_rail_exports_named_net(
    tmp_path: Path,
) -> None:
    """Custom rails such as +3V3_A must be labels, not fake power symbols."""

    kicad_cli = shutil.which("kicad-cli")
    if kicad_cli is None:
        pytest.skip("kicad-cli is not installed")

    project_root = tmp_path / "custom-rail-smoke"
    server = build_server("full")

    await call_tool_text(
        server,
        "kicad_create_new_project",
        {
            "path": str(project_root),
            "name": "CustomRailSmoke",
            "confirm_overwrite": True,
        },
    )
    project_dir = project_root / "CustomRailSmoke"
    schematic_path = project_dir / "CustomRailSmoke.kicad_sch"

    flag_ref = chr(35) + "FLG1"
    await call_tool_text(
        server,
        "sch_build_circuit",
        {
            "symbols": [
                {
                    "library": "Device",
                    "symbol_name": "R",
                    "reference": "R1",
                    "value": "10k",
                    "footprint": "Resistor_SMD:R_0603_1608Metric",
                },
                {
                    "library": "power",
                    "symbol_name": "PWR_FLAG",
                    "reference": flag_ref,
                    "value": "PWR_FLAG",
                    "footprint": "",
                },
            ],
            "wires": [],
            "labels": [],
            "power_symbols": [],
            "nets": [
                {"name": "+3V3_A", "endpoints": ["R1.1", f"{flag_ref}.1"]},
            ],
            "auto_layout": True,
        },
    )

    schematic = schematic_path.read_text(encoding="utf-8", errors="replace")
    assert 'lib_id "power:+3V3_A"' not in schematic
    assert 'global_label "+3V3_A"' in schematic

    netlist_path = project_dir / "CustomRailSmoke.net"
    subprocess.run(
        [
            kicad_cli,
            "sch",
            "export",
            "netlist",
            str(schematic_path),
            "--output",
            str(netlist_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    netlist = netlist_path.read_text(encoding="utf-8", errors="replace")
    assert '(name "+3V3_A")' in netlist
    assert '(ref "R1")' in netlist
