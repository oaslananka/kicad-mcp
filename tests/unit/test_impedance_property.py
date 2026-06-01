from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from kicad_mcp.utils.impedance import trace_impedance


@given(
    width_mm=st.floats(min_value=0.05, max_value=10.0),
    height_mm=st.floats(min_value=0.05, max_value=5.0),
    er=st.floats(min_value=2.0, max_value=12.0),
)
def test_impedance_always_positive(width_mm: float, height_mm: float, er: float) -> None:
    result, _effective_er = trace_impedance(
        width_mm,
        height_mm,
        er,
        trace_type="microstrip",
    )
    assert result > 0
