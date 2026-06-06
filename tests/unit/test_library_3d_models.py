"""Unit tests for 3D model management tools (FAZ 7)."""

from __future__ import annotations

from kicad_mcp.tools.three_d_models import (
    _find_3d_model_refs,
    _find_footprint_file,
    _search_3d_model_files,
)


def test_find_footprint_file_not_found(tmp_path) -> None:  # type: ignore[no-untyped-def]
    fp = _find_footprint_file("Missing", "Nonexistent")
    assert fp is None


def test_find_3d_model_refs_empty() -> None:
    refs = _find_3d_model_refs("(footprint (version 20250316))\n")
    assert refs == []


def test_find_3d_model_refs_single() -> None:
    text = '(footprint (version 20250316) (model "package.3dshapes/R.step"))\n'
    refs = _find_3d_model_refs(text)
    assert len(refs) == 1
    assert "R.step" in refs[0]["path"]


def test_search_3d_models_empty(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr("kicad_mcp.tools.three_d_models._footprint_3d_dir", lambda: tmp_path)
    results = _search_3d_model_files("R_0805")
    assert results == []
