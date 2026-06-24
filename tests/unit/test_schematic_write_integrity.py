"""Schematic write-integrity guards (issue #193).

The transactional writer validates more than balanced parentheses: it refuses
output with duplicate element UUIDs, the classic silent-corruption signature of a
regex/string mutation that cloned a block instead of minting a fresh UUID.
"""

from __future__ import annotations

import pytest

from kicad_mcp.tools.schematic import _duplicate_uuids, _validate_schematic_text

_CLEAN = (
    '(kicad_sch (uuid "00000000-0000-0000-0000-000000000001")'
    ' (label "A" (at 0 0 0) (uuid "00000000-0000-0000-0000-000000000002"))'
    ' (label "B" (at 0 5 0) (uuid "00000000-0000-0000-0000-000000000003")))'
)
_DUPLICATE = (
    '(kicad_sch (uuid "00000000-0000-0000-0000-000000000001")'
    ' (label "A" (at 0 0 0) (uuid "00000000-0000-0000-0000-000000000002"))'
    ' (label "B" (at 0 5 0) (uuid "00000000-0000-0000-0000-000000000002")))'
)


def test_duplicate_uuids_detects_clones() -> None:
    assert _duplicate_uuids(_CLEAN) == set()
    assert _duplicate_uuids(_DUPLICATE) == {"00000000-0000-0000-0000-000000000002"}


def test_validate_accepts_clean_schematic() -> None:
    _validate_schematic_text(_CLEAN)  # must not raise


def test_validate_refuses_duplicate_uuids() -> None:
    with pytest.raises(ValueError, match="duplicate element UUIDs"):
        _validate_schematic_text(_DUPLICATE)


def test_validate_still_refuses_unbalanced_parens() -> None:
    with pytest.raises(ValueError, match="unbalanced parentheses"):
        _validate_schematic_text('(kicad_sch (uuid "x")')
