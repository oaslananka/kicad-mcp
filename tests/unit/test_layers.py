from __future__ import annotations

from pathlib import Path

import pytest
from kipy.proto.board.board_types_pb2 import BoardLayer

from kicad_mcp.tools.pcb import _board_file_layers, _file_backed_layers
from kicad_mcp.utils.layers import resolve_layer, resolve_layer_name


def test_layer_alias_resolution() -> None:
    assert resolve_layer_name("F.Cu") == "F_Cu"
    assert resolve_layer_name("In30.Cu") == "In30_Cu"


def test_resolve_layer_returns_board_layer_value() -> None:
    layer = resolve_layer("F.Cu")
    inner = resolve_layer("In30.Cu")

    assert isinstance(layer, int)
    assert layer == BoardLayer.BL_F_Cu
    assert inner == BoardLayer.Value("BL_In30_Cu")


def test_resolve_layer_rejects_unknown_layer() -> None:
    try:
        resolve_layer("Not.A.Layer")
    except ValueError as exc:
        assert "Unknown layer" in str(exc)
    else:
        raise AssertionError("resolve_layer() should reject invalid layers")


def test_board_file_layers_default_fallback() -> None:
    minimal_pcb = '(kicad_pcb (version 20260206) (generator_version "10.0"))'
    layers = _board_file_layers(minimal_pcb)

    assert len(layers) > 0
    assert any(layer["name"] == "F.Cu" for layer in layers)
    assert any(layer["name"] == "B.Cu" for layer in layers)
    assert any(layer["name"] == "Edge.Cuts" for layer in layers)


def test_file_backed_layers_uses_kicad_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    minimal_pcb = "(kicad_pcb (version 20260206))"
    dummy_diagnostics = [
        "Diagnostics:",
        "- Source: file-backed",
        "- Fallback status: using file-backed .kicad_pcb parser",
    ]
    monkeypatch.setattr(
        "kicad_mcp.tools.pcb._load_file_backed_board",
        lambda exc: (Path("dummy.kicad_pcb"), minimal_pcb, dummy_diagnostics),
    )
    from kicad_mcp.connection import KiCadConnectionError

    result = _file_backed_layers(KiCadConnectionError("test"))

    assert "using KiCad defaults" in result
    assert "F.Cu" in result
    assert "B.Cu" in result
