"""Unit tests for net analysis tools (FAZ 6.1–6.3)."""

from __future__ import annotations

from kicad_mcp.tools.net_analysis import _collect_nets_from_file, _nets


def test_collect_nets_from_file_empty(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """A minimal PCB file with no nets should return an empty list."""
    pcb_file = tmp_path / "empty.kicad_pcb"
    pcb_file.write_text("(kicad_pcb (version 20250316))\n", encoding="utf-8")
    monkeypatch.setattr("kicad_mcp.tools.net_analysis._get_pcb_file", lambda: pcb_file)
    nets = _collect_nets_from_file()
    assert nets == []


def test_collect_nets_from_file_with_nets(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    pcb_file = tmp_path / "board.kicad_pcb"
    pcb_file.write_text(
        '(kicad_pcb (net 0 "") (net 1 "GND") (net 2 "+3V3"))\n',
        encoding="utf-8",
    )
    monkeypatch.setattr("kicad_mcp.tools.net_analysis._get_pcb_file", lambda: pcb_file)
    nets = _collect_nets_from_file()
    names = {n["name"] for n in nets}
    assert "GND" in names
    assert "+3V3" in names


def test_nets_uses_file_fallback_when_no_board(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    pcb_file = tmp_path / "board.kicad_pcb"
    pcb_file.write_text(
        '(kicad_pcb (net 0 "") (net 1 "CLK") (net 2 "D0"))\n',
        encoding="utf-8",
    )
    monkeypatch.setattr("kicad_mcp.tools.net_analysis._get_pcb_file", lambda: pcb_file)
    result = _nets()
    assert len(result) >= 1
