"""Unit tests for SPICE model assignment tools (FAZ 4)."""

from __future__ import annotations

import pytest

from kicad_mcp.tools.simulation import (
    sim_assign_spice_model,
    sim_list_spice_libraries,
    sim_validate_spice_setup,
)


def test_list_spice_libraries_default(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
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
    result = sim_list_spice_libraries()
    assert "default.lib" in result or "libraries" in result.lower()


def test_validate_spice_setup_without_project() -> None:
    result = sim_validate_spice_setup()
    assert result is not None


def test_assign_model_rejects_nonexistent_model() -> None:
    with pytest.raises((ValueError, FileNotFoundError)):
        sim_assign_spice_model(
            reference="Q1",
            model_path="/nonexistent/model.lib",
            model_name="2N3904",
        )
