"""Unit tests for DRC exclusion tools (FAZ 5.1)."""

from __future__ import annotations

import json

from kicad_mcp.tools.validation import (
    _load_drc_exclusions,
    _save_drc_exclusions,
    drc_list_exclusions,
    drc_remove_exclusion,
)


def test_drc_exclusions_empty(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    excls_path = tmp_path / "drc_exclusions.json"
    monkeypatch.setattr("kicad_mcp.tools.validation._drc_exclusions_path", lambda: excls_path)
    state = _load_drc_exclusions()
    assert state.get("exclusions", []) == []


def test_drc_list_exclusions_empty(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    excls_path = tmp_path / "drc_exclusions.json"
    monkeypatch.setattr("kicad_mcp.tools.validation._drc_exclusions_path", lambda: excls_path)
    result = drc_list_exclusions()
    payload = json.loads(result)
    assert payload["count"] == 0


def test_drc_save_and_reload(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    excls_path = tmp_path / "drc_exclusions.json"
    monkeypatch.setattr("kicad_mcp.tools.validation._drc_exclusions_path", lambda: excls_path)
    state = {"exclusions": [{"uuid": "abc-123", "reason": "ok", "created": "2026-01-01"}]}
    _save_drc_exclusions(state)
    loaded = _load_drc_exclusions()
    assert len(loaded["exclusions"]) == 1
    assert loaded["exclusions"][0]["uuid"] == "abc-123"


def test_drc_remove_exclusion_nonexistent(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    excls_path = tmp_path / "drc_exclusions.json"
    monkeypatch.setattr("kicad_mcp.tools.validation._drc_exclusions_path", lambda: excls_path)
    result = drc_remove_exclusion(uuid="nobody")
    assert "No exclusion found" in result
