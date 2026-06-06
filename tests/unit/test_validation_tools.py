"""Unit tests for validation/quality gate tools."""

from __future__ import annotations

import pytest

from kicad_mcp.tools.validation import (
    _compute_scores,
    _ERC_RULE_NAMES,
    _load_erc_severity,
)


def test_compute_scores_returns_dict() -> None:
    scores = _compute_scores(density_pct=30.0)
    assert isinstance(scores, dict)
    assert "overall" in scores


def test_erc_rule_names_match_expected() -> None:
    assert len(_ERC_RULE_NAMES) >= 10
    assert "power_pin_not_driven" in _ERC_RULE_NAMES
    assert "duplicate_reference" in _ERC_RULE_NAMES


def test_load_erc_severity_defaults(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(
        "kicad_mcp.tools.validation._erc_severity_path", lambda: tmp_path / "erc.json"
    )
    sev = _load_erc_severity()
    assert all(v == "error" for v in sev.values())
    assert len(sev) == len(_ERC_RULE_NAMES)
