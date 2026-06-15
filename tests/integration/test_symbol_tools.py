"""Integration tests for KiCad symbol tools."""

from __future__ import annotations

from pathlib import Path

import pytest

from kicad_mcp.server import build_server
from tests.conftest import call_tool_text


@pytest.mark.anyio
async def test_sym_export_fails_without_project(sample_project: Path, monkeypatch) -> None:
    """sym_export should fail when no project file is configured."""
    monkeypatch.setenv("KICAD_MCP_PROJECT_DIR", "")
    server = build_server("full")

    result = await call_tool_text(server, "sym_export", {})
    assert "No project file configured" in result


@pytest.mark.anyio
async def test_sym_export_runs_cli_variants(sample_project: Path, monkeypatch) -> None:
    """sym_export should attempt CLI export and report success."""
    commands: list[list[str]] = []

    def fake_run_cli_variants(variants: list[list[str]]) -> tuple[int, str, str]:
        commands.append(variants[0])
        out_file = Path(variants[0][variants[0].index("--output") + 1])
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_text("svg", encoding="utf-8")
        return (0, "", "")

    monkeypatch.setattr("kicad_mcp.tools.symbol._run_cli_variants", fake_run_cli_variants)
    server = build_server("full")
    await call_tool_text(server, "kicad_set_project", {"project_dir": str(sample_project)})

    result = await call_tool_text(server, "sym_export", {"format": "svg"})
    assert "Symbol exported to" in result
    assert commands


@pytest.mark.anyio
async def test_sym_export_reports_cli_failure(sample_project: Path, monkeypatch) -> None:
    """sym_export should report failure when CLI returns non-zero."""

    def fake_run_cli_variants(variants: list[list[str]]) -> tuple[int, str, str]:
        return (1, "", "export error")

    monkeypatch.setattr("kicad_mcp.tools.symbol._run_cli_variants", fake_run_cli_variants)
    server = build_server("full")
    await call_tool_text(server, "kicad_set_project", {"project_dir": str(sample_project)})

    result = await call_tool_text(server, "sym_export", {"format": "pdf"})
    assert "Symbol export failed" in result
    assert "export error" in result


@pytest.mark.anyio
async def test_sym_export_svg_requires_input_file(sample_project: Path) -> None:
    """sym_export_svg should require input_file parameter."""
    server = build_server("full")
    await call_tool_text(server, "kicad_set_project", {"project_dir": str(sample_project)})

    result = await call_tool_text(server, "sym_export_svg", {"input_file": ""})
    assert "input_file parameter is required" in result


@pytest.mark.anyio
async def test_sym_export_svg_fails_for_missing_file(sample_project: Path) -> None:
    """sym_export_svg should report when input file does not exist."""
    server = build_server("full")
    await call_tool_text(server, "kicad_set_project", {"project_dir": str(sample_project)})

    result = await call_tool_text(
        server, "sym_export_svg", {"input_file": "nonexistent.kicad_sym"}
    )
    assert "Input symbol library file not found" in result


@pytest.mark.anyio
async def test_sym_export_svg_runs_cli(sample_project: Path, monkeypatch) -> None:
    """sym_export_svg should invoke kicad-cli with correct flags."""
    commands: list[list[str]] = []

    def fake_run_cli(*cmd: str) -> tuple[int, str, str]:
        commands.append(list(cmd))
        return (0, "", "")

    monkeypatch.setattr("kicad_mcp.tools.symbol._run_cli", fake_run_cli)
    server = build_server("full")
    await call_tool_text(server, "kicad_set_project", {"project_dir": str(sample_project)})

    # Copy symbol file into project so resolve_under accepts it
    sym_file = sample_project / "Device.kicad_sym"
    sym_file.write_text(
        sample_project.parent.joinpath("symbols", "Device.kicad_sym").read_text(
            encoding="utf-8"
        ),
        encoding="utf-8",
    )
    result = await call_tool_text(
        server,
        "sym_export_svg",
        {
            "input_file": str(sym_file),
            "symbol": "R",
            "theme": "default",
            "black_and_white": True,
            "include_hidden_pins": True,
            "include_hidden_fields": True,
        },
    )

    assert "Symbol SVG exported successfully" in result
    assert commands
    cmd = commands[0]
    assert "sym" in cmd
    assert "export" in cmd
    assert "svg" in cmd
    assert "--symbol" in cmd
    assert "R" in cmd
    assert "--theme" in cmd
    assert "default" in cmd
    assert "--black-and-white" in cmd
    assert "--include-hidden-pins" in cmd
    assert "--include-hidden-fields" in cmd


@pytest.mark.anyio
async def test_sym_export_svg_reports_failure(sample_project: Path, monkeypatch) -> None:
    """sym_export_svg should report CLI failure."""

    def fake_run_cli(*cmd: str) -> tuple[int, str, str]:
        return (1, "stdout msg", "stderr msg")

    monkeypatch.setattr("kicad_mcp.tools.symbol._run_cli", fake_run_cli)
    server = build_server("full")
    await call_tool_text(server, "kicad_set_project", {"project_dir": str(sample_project)})

    sym_file = sample_project / "Device.kicad_sym"
    sym_file.write_text(
        sample_project.parent.joinpath("symbols", "Device.kicad_sym").read_text(
            encoding="utf-8"
        ),
        encoding="utf-8",
    )
    result = await call_tool_text(
        server, "sym_export_svg", {"input_file": str(sym_file)}
    )
    assert "Symbol SVG export failed" in result


@pytest.mark.anyio
async def test_sym_upgrade_dry_run_without_input_uses_sch_file(
    sample_project: Path,
) -> None:
    """sym_upgrade dry_run should use configured schematic file when input omitted."""
    server = build_server("full")
    await call_tool_text(server, "kicad_set_project", {"project_dir": str(sample_project)})

    result = await call_tool_text(server, "sym_upgrade", {"dry_run": True})
    assert "Dry run: Would upgrade symbol library" in result
    assert "force=False" in result


@pytest.mark.anyio
async def test_sym_upgrade_dry_run_with_force(sample_project: Path) -> None:
    """sym_upgrade dry_run should report force flag."""
    server = build_server("full")
    await call_tool_text(server, "kicad_set_project", {"project_dir": str(sample_project)})

    result = await call_tool_text(
        server, "sym_upgrade", {"dry_run": True, "force": True}
    )
    assert "force=True" in result


@pytest.mark.anyio
async def test_sym_upgrade_fails_without_project_or_input() -> None:
    """sym_upgrade should fail when no project or input file is available."""
    server = build_server("full")

    result = await call_tool_text(server, "sym_upgrade", {})
    assert "No input file provided and no schematic configured" in result


@pytest.mark.anyio
async def test_sym_upgrade_runs_cli(sample_project: Path, monkeypatch) -> None:
    """sym_upgrade should invoke kicad-cli and report success."""

    def fake_run_cli(*cmd: str) -> tuple[int, str, str]:
        return (0, "", "")

    monkeypatch.setattr("kicad_mcp.tools.symbol._run_cli", fake_run_cli)
    server = build_server("full")
    await call_tool_text(server, "kicad_set_project", {"project_dir": str(sample_project)})

    sym_file = sample_project / "symbols" / "Device.kicad_sym"
    result = await call_tool_text(
        server, "sym_upgrade", {"input_file": str(sym_file), "dry_run": False}
    )
    assert "Symbol library upgraded and saved" in result


@pytest.mark.anyio
async def test_sym_upgrade_reports_cli_failure(sample_project: Path, monkeypatch) -> None:
    """sym_upgrade should report CLI failure."""

    def fake_run_cli(*cmd: str) -> tuple[int, str, str]:
        return (1, "", "upgrade error")

    monkeypatch.setattr("kicad_mcp.tools.symbol._run_cli", fake_run_cli)
    server = build_server("full")
    await call_tool_text(server, "kicad_set_project", {"project_dir": str(sample_project)})

    sym_file = sample_project / "symbols" / "Device.kicad_sym"
    result = await call_tool_text(
        server, "sym_upgrade", {"input_file": str(sym_file), "dry_run": False}
    )
    assert "Symbol upgrade failed" in result
    assert "upgrade error" in result


@pytest.mark.anyio
async def test_sym_upgrade_with_output_file(sample_project: Path, monkeypatch) -> None:
    """sym_upgrade should use custom output path when provided."""
    server = build_server("full")
    await call_tool_text(server, "kicad_set_project", {"project_dir": str(sample_project)})

    result = await call_tool_text(
        server,
        "sym_upgrade",
        {"input_file": "Device.kicad_sym", "output_file": "upgraded.kicad_sym", "dry_run": True},
    )
    assert "upgraded.kicad_sym" in result


@pytest.mark.anyio
async def test_sym_export_svg_unsafe_input_path(sample_project: Path, monkeypatch) -> None:
    """sym_export_svg should reject unsafe input paths."""
    from kicad_mcp import path_safety

    original_resolve = path_safety.resolve_under

    def raising_resolve(*args: object, **kwargs: object) -> Path:
        raise ValueError("unsafe path")

    monkeypatch.setattr(path_safety, "resolve_under", raising_resolve)
    server = build_server("full")
    await call_tool_text(server, "kicad_set_project", {"project_dir": str(sample_project)})

    result = await call_tool_text(
        server, "sym_export_svg", {"input_file": "../unsafe.kicad_sym"}
    )
    assert "Unsafe input file path" in result

    monkeypatch.setattr(path_safety, "resolve_under", original_resolve)


@pytest.mark.anyio
async def test_sym_export_svg_unsafe_output_dir(sample_project: Path, monkeypatch) -> None:
    """sym_export_svg should reject unsafe output directories."""
    from kicad_mcp import path_safety

    original_resolve = path_safety.resolve_under

    call_count = 0

    def selective_resolve(*args: object, **kwargs: object) -> Path:
        nonlocal call_count
        call_count += 1
        # First call is for input_file, second for output_dir
        if call_count >= 2:
            raise ValueError("unsafe dir")
        return original_resolve(*args, **kwargs)

    monkeypatch.setattr(path_safety, "resolve_under", selective_resolve)
    server = build_server("full")
    await call_tool_text(server, "kicad_set_project", {"project_dir": str(sample_project)})

    sym_file = sample_project / "Device.kicad_sym"
    sym_file.write_text(
        sample_project.parent.joinpath("symbols", "Device.kicad_sym").read_text(
            encoding="utf-8"
        ),
        encoding="utf-8",
    )
    result = await call_tool_text(
        server,
        "sym_export_svg",
        {"input_file": str(sym_file), "output_dir": "../unsafe"},
    )
    assert "Unsafe output directory" in result

    monkeypatch.setattr(path_safety, "resolve_under", original_resolve)
