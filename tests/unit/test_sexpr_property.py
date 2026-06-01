from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from kicad_mcp.utils.sexpr import _sexpr_string, _unescape_sexpr_string


@given(st.text(min_size=0, max_size=200))
def test_sexpr_roundtrip(s: str) -> None:
    encoded = _sexpr_string(s)
    decoded = _unescape_sexpr_string(encoded[1:-1])

    assert decoded == s.replace("\r\n", "\n").replace("\r", "\n")
