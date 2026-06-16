"""Component derating and AVL checks (work order P4-T3)."""

from __future__ import annotations

import pytest

from kicad_mcp.utils.derating import avl_check, derating_check


def test_capacitor_within_derating_passes() -> None:
    # 12V on a 25V cap = 48% utilization, well under the 80% limit.
    result = derating_check("capacitor", "voltage", rated_value=25.0, operating_value=12.0)
    assert result.verdict == "PASS"
    assert result.utilization == pytest.approx(0.48)


def test_capacitor_over_derating_fails() -> None:
    # 22V on a 25V cap = 88% > 80% derating limit -> reliability FAIL.
    result = derating_check("capacitor", "voltage", rated_value=25.0, operating_value=22.0)
    assert result.verdict == "FAIL"
    assert "derating limit" in result.summary


def test_overstress_beyond_absolute_rating_fails() -> None:
    result = derating_check("capacitor", "voltage", rated_value=16.0, operating_value=18.0)
    assert result.verdict == "FAIL"
    assert "overstress" in result.summary.lower()


def test_close_to_limit_warns() -> None:
    # 0.75 utilization is within 90% of the 0.80 limit -> WARN (little margin).
    result = derating_check("resistor", "power", rated_value=1.0, operating_value=0.58)
    assert result.verdict == "WARN"


def test_unknown_kind_raises() -> None:
    with pytest.raises(ValueError, match="No derating policy"):
        derating_check("unobtanium", "flux", rated_value=1.0, operating_value=0.1)


def test_avl_pass_and_fail() -> None:
    assert avl_check("Murata", ["Murata", "TDK"])[0] == "PASS"
    fail_verdict, fail_summary = avl_check("Shenzhen Knockoff Co", ["Murata", "TDK"])
    assert fail_verdict == "FAIL"
    assert "NOT on the approved-vendor list" in fail_summary


def test_avl_unconfigured_warns() -> None:
    assert avl_check("Murata", [])[0] == "WARN"
