from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from kicad_mcp.server import build_server
from tests.conftest import call_tool_text


@pytest.mark.anyio
async def test_manufacturing_panelize_error_paths(
    sample_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = build_server("manufacturing")
    await call_tool_text(server, "kicad_set_project", {"project_dir": str(sample_project)})

    monkeypatch.setattr("kicad_mcp.tools.manufacturing.shutil.which", lambda _name: None)
    missing = await call_tool_text(server, "mfg_panelize", {})
    assert "KiKit is not installed" in missing

    monkeypatch.setattr("kicad_mcp.tools.manufacturing.shutil.which", lambda _name: "kikit")
    invalid_layout = await call_tool_text(server, "mfg_panelize", {"layout": "radial"})
    invalid_size = await call_tool_text(server, "mfg_panelize", {"rows": 0, "cols": 2})

    assert "Invalid layout" in invalid_layout
    assert "rows and cols must both be >= 1" in invalid_size


@pytest.mark.anyio
async def test_manufacturing_panelize_success_and_process_failures(
    sample_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = build_server("manufacturing")
    await call_tool_text(server, "kicad_set_project", {"project_dir": str(sample_project)})
    monkeypatch.setattr("kicad_mcp.tools.manufacturing.shutil.which", lambda _name: "kikit")

    commands: list[list[str]] = []

    def ok_run(cmd: list[str], **_kwargs: object) -> SimpleNamespace:
        commands.append(cmd)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("kicad_mcp.tools.manufacturing.subprocess.run", ok_run)
    dry_run = await call_tool_text(server, "mfg_panelize", {"layout": "grid"})
    grid = await call_tool_text(
        server,
        "mfg_panelize",
        {"layout": "grid", "dry_run": False, "confirm": True},
    )
    mousebites = await call_tool_text(
        server,
        "mfg_panelize",
        {"layout": "mousebites", "dry_run": False, "confirm": True},
    )
    vcut = await call_tool_text(
        server,
        "mfg_panelize",
        {"layout": "vcut", "dry_run": False, "confirm": True},
    )

    assert "Dry run: panelization was not executed." in dry_run
    assert "Panel created:" in grid
    assert "Layout: grid" in grid
    assert "Layout: mousebites" in mousebites
    assert "Layout: vcut" in vcut
    assert any("mousebites" in " ".join(cmd) for cmd in commands)
    assert any("vcuts" in " ".join(cmd) for cmd in commands)

    monkeypatch.setattr(
        "kicad_mcp.tools.manufacturing.subprocess.run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=2, stdout="", stderr="bad panel"),
    )
    failed = await call_tool_text(
        server,
        "mfg_panelize",
        {"dry_run": False, "confirm": True},
    )
    assert "KiKit panelization failed" in failed
    assert "bad panel" in failed

    def timeout_run(*_args: object, **_kwargs: object) -> SimpleNamespace:
        raise subprocess.TimeoutExpired(cmd="kikit", timeout=120)

    monkeypatch.setattr("kicad_mcp.tools.manufacturing.subprocess.run", timeout_run)
    timed_out = await call_tool_text(
        server,
        "mfg_panelize",
        {"dry_run": False, "confirm": True},
    )
    assert "timed out" in timed_out


@pytest.mark.anyio
async def test_manufacturing_test_plan_manifest_and_cpl_rotation(
    sample_project: Path,
) -> None:
    server = build_server("manufacturing")
    await call_tool_text(server, "kicad_set_project", {"project_dir": str(sample_project)})
    await call_tool_text(
        server,
        "project_set_design_intent",
        {
            "critical_nets": ["USB_DP"],
            "power_rails": [{"name": "+3V3", "voltage_v": 3.3, "current_max_a": 1.0}],
            "interfaces": [{"kind": "usb2", "refs": ["J1"]}],
            "compliance": [{"kind": "ce_emc", "notes": "pre-scan"}],
        },
    )

    test_plan = await call_tool_text(
        server,
        "mfg_generate_test_plan",
        {"output_path": "bringup/test_plan.md"},
    )
    assert "Test plan saved" in test_plan
    assert "USB_DP" in test_plan
    assert "USB enumeration" in test_plan
    assert (sample_project / "bringup" / "test_plan.md").exists()

    output_dir = sample_project / "output"
    output_dir.mkdir(exist_ok=True)
    (output_dir / "demo-F_Cu.gbr").write_text("gerber", encoding="utf-8")
    (output_dir / "demo.drl").write_text("drill", encoding="utf-8")
    manifest = await call_tool_text(server, "mfg_generate_release_manifest", {})
    assert "Release manifest generated" in manifest
    assert (output_dir / "manifest.json").exists()
    assert (output_dir / "MANIFEST.txt").exists()

    cpl = sample_project / "output" / "demo_cpl.csv"
    cpl.write_text(
        "Ref,Val,Package,PosX,PosY,Rot,Side\nD1,LED,SOT-23-3,1,2,90,F\nR1,10k,R_0805,3,4,0,F\n",
        encoding="utf-8",
    )
    dry_run = await call_tool_text(
        server,
        "mfg_correct_cpl_rotations",
        {"cpl_csv_path": "output/demo_cpl.csv", "dry_run": True},
    )
    corrected = await call_tool_text(
        server,
        "mfg_correct_cpl_rotations",
        {"cpl_csv_path": "output/demo_cpl.csv", "dry_run": False, "confirm": True},
    )

    assert "Dry run" in dry_run
    assert "D1" in dry_run
    assert "CPL rotation corrections applied" in corrected
    assert (sample_project / "output" / "demo_cpl_jlcpcb_corrected.csv").exists()


@pytest.mark.anyio
async def test_manufacturing_import_support_and_import_cli(
    sample_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = build_server("manufacturing")
    await call_tool_text(server, "kicad_set_project", {"project_dir": str(sample_project)})

    caps = SimpleNamespace(
        supports_allegro_import=True,
        supports_pads_import=False,
        supports_geda_import=True,
        version="10.0.1",
    )
    monkeypatch.setattr("kicad_mcp.tools.manufacturing.get_cli_capabilities", lambda _cli: caps)
    supported = await call_tool_text(server, "mfg_check_import_support", {"format": "allegro"})
    unknown = await call_tool_text(server, "mfg_check_import_support", {"format": "eagle"})

    assert "Supported by detected CLI: yes" in supported
    assert "Detected KiCad version: 10.0.1" in supported
    assert "Supported import formats" in unknown

    allegro = sample_project / "legacy.brd"
    allegro.write_text("legacy", encoding="utf-8")

    def ok_variants(variants: list[list[str]]) -> tuple[int, str, str]:
        assert variants[0][:3] == ["pcb", "import", "allegro"]
        return 0, "imported", ""

    monkeypatch.setattr("kicad_mcp.tools.export._run_cli_variants", ok_variants)
    imported = await call_tool_text(
        server,
        "mfg_import_allegro",
        {"allegro_brd_path": "legacy.brd", "output_dir": "imports/allegro"},
    )
    assert "allegro import completed" in imported
    assert "Expected project file" in imported

    monkeypatch.setattr(
        "kicad_mcp.tools.export._run_cli_variants",
        lambda _variants: (2, "", "unsupported"),
    )
    failed = await call_tool_text(server, "mfg_import_pads", {"pads_pcb_path": "legacy.brd"})
    missing = await call_tool_text(server, "mfg_import_geda", {"geda_pcb_path": "missing.pcb"})
    assert "pads import failed" in failed
    assert "unsupported" in failed
    assert "Input file was not found" in missing
