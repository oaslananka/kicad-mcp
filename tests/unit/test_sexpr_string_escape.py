"""String-level S-expression escape/unescape round trip (work order P2-T2, K6).

This is a *string escaping* round trip, not a file round trip. It was previously named
``test_sexpr_property.py::test_sexpr_roundtrip``, which misleadingly implied it proved
schematic-file fidelity. Real file round-trip fidelity is covered by
``tests/integration/test_roundtrip_fidelity.py``.
"""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from kicad_mcp.utils.sexpr import _sexpr_string, _unescape_sexpr_string


@given(st.text(min_size=0, max_size=200))
def test_sexpr_string_escape_roundtrip(s: str) -> None:
    encoded = _sexpr_string(s)
    decoded = _unescape_sexpr_string(encoded[1:-1])

    assert decoded == s.replace("\r\n", "\n").replace("\r", "\n")
