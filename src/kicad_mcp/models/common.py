"""Shared structural protocols used across KiCad tool modules."""

from __future__ import annotations

from typing import Protocol


class _PositionLike(Protocol):
    x_nm: int
    y_nm: int


class _TextValueLike(Protocol):
    value: str


class _TextFieldLike(Protocol):
    text: _TextValueLike


class _NetLike(Protocol):
    name: str


class _FootprintLike(Protocol):
    reference_field: _TextFieldLike
    value_field: _TextFieldLike
    position: object
    layer: int


class _PadLike(Protocol):
    parent: _FootprintLike
    number: str | int
    position: _PositionLike
    net: _NetLike


__all__ = [
    "_FootprintLike",
    "_NetLike",
    "_PadLike",
    "_PositionLike",
    "_TextFieldLike",
    "_TextValueLike",
]
