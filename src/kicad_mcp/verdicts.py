"""Shared three-level verdict helper for analysis gates (work order P1-T3).

A gate that can only return PASS or WARN is not a gate — it can never block a bad
design. These helpers give every gate a real ``FAIL`` band: PASS within budget, WARN
in a marginal band, FAIL once the value clearly exceeds the budget.
"""

from __future__ import annotations

from typing import Literal

Verdict = Literal["PASS", "WARN", "FAIL"]

# A value above ``pass_max`` but at or below ``warn_max`` is marginal (WARN). The
# default marginal band is one budget wide, so FAIL triggers at 2x the budget.
DEFAULT_FAIL_MULTIPLIER = 2.0


def three_level_verdict(value: float, *, pass_max: float, warn_max: float) -> Verdict:
    """Classify ``value`` against a soft (``pass_max``) and hard (``warn_max``) limit.

    * ``value <= pass_max`` -> ``PASS`` (within budget)
    * ``pass_max < value <= warn_max`` -> ``WARN`` (marginal)
    * ``value > warn_max`` -> ``FAIL`` (clearly over budget)
    """
    if value <= pass_max:
        return "PASS"
    if value <= warn_max:
        return "WARN"
    return "FAIL"


def warn_max_from(pass_max: float, *, multiplier: float = DEFAULT_FAIL_MULTIPLIER) -> float:
    """Return the FAIL threshold (``warn_max``) derived from a budget ``pass_max``."""
    return pass_max * multiplier
