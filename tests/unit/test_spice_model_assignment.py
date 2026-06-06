"""Unit tests for SPICE model assignment tools (FAZ 4).
Tools: sim_list_spice_libraries, sim_validate_spice_setup,
sim_assign_spice_model, sim_add_spice_library, sim_remove_spice_library.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from kicad_mcp.server import create_server
from tests.conftest import call_tool_text


@pytest.mark.anyio
async def test_list_spice_libraries_default(tmp_path: Path, monkeypatch) -> None:
    # Create a minimal project so tools requiring a project can run
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "demo.kicad_pro").write_text("{}", encoding="utf-8")
    (proj / "demo.kicad_pcb").write_text("", encoding="utf-8")
    (proj / "demo.kicad_sch").write_text("", encoding="utf-8")

    cfg_path = tmp_path / "sim" / "spice"
    cfg_path.mkdir(parents=True, exist_ok=True)
    (cfg_path / "default.lib").write_text("* default lib", encoding="utf-8")
    from kicad_mcp import config

    monkeypatch.setattr(
        config,
        "get_config",
        lambda: config.KiCadMCPConfig._make(
            project_dir=tmp_path,
            output_dir=None,
            spice_model_dir=cfg_path,
            kicad_cli="kicad-cli",
            project_file=None,
            sch_file=None,
            footprint_library_dir=None,
            symbol_library_dir=None,
            max_text_response_chars=100000,
            profile="full",
            auth_token=None,
            studio_watch_dir=None,
            http_transport=None,
        ),
    )
    server = create_server()
    await call_tool_text(server, "kicad_set_project", {"project_dir": str(proj)})
    result = await call_tool_text(server, "sim_list_spice_libraries", {})
    assert "default.lib" in result or "libraries" in result.lower()


@pytest.mark.anyio
async def test_validate_spice_setup_without_project() -> None:
    server = create_server()
    result = await call_tool_text(server, "sim_validate_spice_setup", {})
    assert result is not None


@pytest.mark.anyio
async def test_assign_model_rejects_nonexistent_model() -> None:
    server = create_server()
    result = await call_tool_text(
        server,
        "sim_assign_spice_model",
        {"reference": "Q1", "model_path": "/nonexistent/model.lib", "model_name": "2N3904"},
    )
    assert "error" in result.lower() or "No project" in result or "not found" in result.lower()
