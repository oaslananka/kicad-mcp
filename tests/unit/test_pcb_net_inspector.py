"""Unit tests for net analysis tools (FAZ 6.1–6.3).
Tools: pcb_get_net_statistics, pcb_net_inspector, pcb_export_stats.
"""

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
        '(kicad_pcb (version 20250316) (net 0 "") (net 1 "GND") (net 2 "+3V3"))\n',
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
        '(kicad_pcb (version 20250316) (net 0 "") (net 1 "CLK") (net 2 "D0"))\n',
        encoding="utf-8",
    )
    monkeypatch.setattr("kicad_mcp.tools.net_analysis._get_pcb_file", lambda: pcb_file)
    result = _nets()
    assert len(result) >= 1


class _DeprecatedCodeNet:
    def __init__(self, name: str) -> None:
        self.name = name
        self.class_name = "Default"

    @property
    def code(self) -> int:  # pragma: no cover - should never be touched
        raise AssertionError("deprecated net code was accessed")


class _NetObject:
    def __init__(self, net_name: str, *, length: int = 0) -> None:
        self.net = type("NetRef", (), {"name": net_name})()
        self.length = length


class _BoardByName:
    def get_nets(self):  # type: ignore[no-untyped-def]
        return [_DeprecatedCodeNet("GND")]

    def get_tracks(self):  # type: ignore[no-untyped-def]
        return [_NetObject("GND", length=1_000_000)]

    def get_vias(self):  # type: ignore[no-untyped-def]
        return [_NetObject("GND")]

    def get_pads(self):  # type: ignore[no-untyped-def]
        return [_NetObject("GND")]


def test_collect_nets_from_board_uses_net_names_not_deprecated_codes(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from kicad_mcp.tools.net_analysis import _collect_nets_from_board

    monkeypatch.setattr("kicad_mcp.tools.net_analysis.get_board", lambda: _BoardByName())

    nets = _collect_nets_from_board()

    assert nets == [
        {
            "code": None,
            "name": "GND",
            "class_name": "Default",
            "track_count": 1,
            "via_count": 1,
            "pad_count": 1,
            "total_track_length_mm": 1.0,
        }
    ]
