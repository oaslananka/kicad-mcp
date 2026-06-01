from __future__ import annotations

from types import SimpleNamespace

import pytest

from kicad_mcp.utils.units import _coord_nm, mil_to_mm, mm_to_mil, mm_to_nm, nm_to_mm


def test_mm_to_nm_roundtrip() -> None:
    assert nm_to_mm(mm_to_nm(1.5)) == pytest.approx(1.5)


def test_mm_to_nm_precision() -> None:
    assert mm_to_nm(0.001) == 1000


def test_mil_conversions_and_coord_reader() -> None:
    assert mm_to_mil(mil_to_mm(100.0)) == pytest.approx(100.0)
    assert _coord_nm(SimpleNamespace(x_nm=123, y_nm=456), "x") == 123
    assert _coord_nm(SimpleNamespace(x=789, y=321), "y") == 321
