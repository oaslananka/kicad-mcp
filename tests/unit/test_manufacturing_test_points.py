"""Unit tests for test point management tools (FAZ 8.1)."""

from __future__ import annotations

import json

from kicad_mcp.tools.test_points import (
    _collect_board_nets,
    _load_test_points,
    _save_test_points,
    pcb_list_test_points,
)


def test_test_points_empty(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(
        "kicad_mcp.tools.test_points._test_points_path", lambda: tmp_path / "tp.json"
    )
    state = _load_test_points()
    assert state["test_points"] == []


def test_save_and_load_test_point(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    tp_path = tmp_path / "tp.json"
    monkeypatch.setattr("kicad_mcp.tools.test_points._test_points_path", lambda: tp_path)
    state = {"test_points": [{"net_name": "GND", "x_mm": 10, "y_mm": 20, "diameter_mm": 1.0}]}
    _save_test_points(state)
    loaded = _load_test_points()
    assert len(loaded["test_points"]) == 1
    assert loaded["test_points"][0]["net_name"] == "GND"


def test_list_test_points_empty(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(
        "kicad_mcp.tools.test_points._test_points_path", lambda: tmp_path / "tp.json"
    )
    result = pcb_list_test_points()
    payload = json.loads(result)
    assert payload["count"] == 0


def test_collect_board_nets_file_fallback(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    pcb_file = tmp_path / "board.kicad_pcb"
    pcb_file.write_text(
        '(kicad_pcb (net 0 "") (net 1 "GND") (net 2 "+5V"))\n',
        encoding="utf-8",
    )
    monkeypatch.setattr("kicad_mcp.tools.test_points._get_pcb_file", lambda: pcb_file)
    nets = _collect_board_nets()
    names = {n["name"] for n in nets}
    assert "GND" in names
    assert "+5V" in names
