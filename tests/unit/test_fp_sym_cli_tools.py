"""Unit tests for footprint/symbol CLI export tools (FAZ 2.2–2.4)."""

from __future__ import annotations

import pytest

from kicad_mcp.tools.footprint import fp_export, fp_get_info
from kicad_mcp.tools.symbol import sym_export


def test_fp_export_rejects_invalid_format() -> None:
    with pytest.raises(ValueError, match="format"):
        fp_export(library="Lib", footprint="FP", format="invalid")


def test_fp_get_info_rejects_missing() -> None:
    with pytest.raises((ValueError, FileNotFoundError)):
        fp_get_info(library="Nonexistent", footprint="Missing")


def test_sym_export_rejects_invalid_format() -> None:
    with pytest.raises(ValueError, match="format"):
        sym_export(library="Lib", symbol="Sym", format="bogus")
