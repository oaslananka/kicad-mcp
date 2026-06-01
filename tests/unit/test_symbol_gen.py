"""Unit tests for the KiCad symbol generator."""

from __future__ import annotations

import re

import pytest

from kicad_mcp.utils.symbol_gen import PinSpec, generate_symbol


def _is_balanced(sexpr: str) -> bool:
    depth = 0
    in_str = False
    escaped = False
    for ch in sexpr:
        if in_str:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth < 0:
                return False
    return depth == 0


def _count_pins(sexpr: str) -> int:
    return len(re.findall(r"\(pin\s+", sexpr))


def _simple_pins(n: int = 4) -> list[PinSpec]:
    half = n // 2
    pins = []
    for i in range(half):
        pins.append(PinSpec(i + 1, f"IN{i}", "input", "left"))
    for i in range(n - half):
        pins.append(PinSpec(half + i + 1, f"OUT{i}", "output", "right"))
    return pins


# ---------------------------------------------------------------------------
# Basic generation
# ---------------------------------------------------------------------------


def test_simple_8pin_symbol_has_correct_pin_count() -> None:
    pins = _simple_pins(8)
    sym = generate_symbol("TEST_IC", pins)
    assert _count_pins(sym) == 8


def test_symbol_is_balanced_parens() -> None:
    pins = _simple_pins(8)
    sym = generate_symbol("TEST_IC", pins)
    assert _is_balanced(sym)


def test_symbol_contains_name() -> None:
    pins = _simple_pins(4)
    sym = generate_symbol("MY_CHIP", pins)
    assert "MY_CHIP" in sym


def test_symbol_contains_reference_prefix() -> None:
    pins = _simple_pins(4)
    sym = generate_symbol("MY_CHIP", pins, reference_prefix="Q")
    assert '"Q"' in sym or "'Q'" in sym or "Q" in sym


def test_symbol_contains_footprint_hint() -> None:
    pins = _simple_pins(4)
    sym = generate_symbol("MY_CHIP", pins, footprint_hint="Package_SO:SOIC-8")
    assert "Package_SO:SOIC-8" in sym


def test_symbol_contains_datasheet() -> None:
    pins = _simple_pins(4)
    sym = generate_symbol("MY_CHIP", pins, datasheet="https://example.com/ds.pdf")
    assert "https://example.com/ds.pdf" in sym


# ---------------------------------------------------------------------------
# Pin placement sides
# ---------------------------------------------------------------------------


def test_all_four_sides() -> None:
    pins = [
        PinSpec(1, "LEFT", "input", "left"),
        PinSpec(2, "RIGHT", "output", "right"),
        PinSpec(3, "TOP", "passive", "top"),
        PinSpec(4, "BOTTOM", "power_in", "bottom"),
    ]
    sym = generate_symbol("FOUR_SIDES", pins)
    assert _count_pins(sym) == 4
    assert _is_balanced(sym)


# ---------------------------------------------------------------------------
# Pin types
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "pin_type",
    [
        "input",
        "output",
        "bidirectional",
        "passive",
        "power_in",
        "power_out",
        "no_connect",
        "open_collector",
    ],
)
def test_valid_pin_types(pin_type: str) -> None:
    pins = [PinSpec(1, "P", pin_type, "left")]  # type: ignore[arg-type]
    sym = generate_symbol("TEST", pins)
    assert pin_type in sym
    assert _is_balanced(sym)


# ---------------------------------------------------------------------------
# Multi-unit symbols
# ---------------------------------------------------------------------------


def test_two_unit_symbol() -> None:
    pins = [
        PinSpec(1, "A_IN", "input", "left", unit=1),
        PinSpec(2, "A_OUT", "output", "right", unit=1),
        PinSpec(3, "B_IN", "input", "left", unit=2),
        PinSpec(4, "B_OUT", "output", "right", unit=2),
    ]
    sym = generate_symbol("DUAL", pins, unit_count=2)
    assert _count_pins(sym) == 4
    assert _is_balanced(sym)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_empty_pin_list() -> None:
    """An empty pin list should produce a valid (if minimal) symbol."""
    sym = generate_symbol("EMPTY", [])
    assert _is_balanced(sym)


def test_single_pin_symbol() -> None:
    pins = [PinSpec(1, "SIG", "passive", "left")]
    sym = generate_symbol("ONE_PIN", pins)
    assert _count_pins(sym) == 1
    assert _is_balanced(sym)


def test_large_pin_count() -> None:
    pins = [
        PinSpec(i + 1, f"P{i}", "bidirectional", "left" if i < 64 else "right") for i in range(128)
    ]
    sym = generate_symbol("LARGE_IC", pins)
    assert _count_pins(sym) == 128
    assert _is_balanced(sym)
