"""Unit tests for ERC rule severity tools (FAZ 5.2)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from kicad_mcp.tools.validation import (
    _ERC_RULE_NAMES,
    _load_erc_severity,
    _save_erc_severity,
    erc_list_rules,
    erc_set_rule_severity,
    erc_reset_rules,
)


def test_erc_list_rules_returns_all(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    sev_path = tmp_path / "erc_severity.json"
    monkeypatch.setattr("kicad_mcp.tools.validation._erc_severity_path", lambda: sev_path)
    result = erc_list_rules()
    payload = json.loads(result)
    assert payload["rules"]
    assert len(payload["rules"]) == len(_ERC_RULE_NAMES)


def test_erc_set_severity(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    sev_path = tmp_path / "erc_severity.json"
    monkeypatch.setattr("kicad_mcp.tools.validation._erc_severity_path", lambda: sev_path)
    result = erc_set_rule_severity(rule_name="pin_not_connected", severity="warning")
    assert "warning" in result
    state = _load_erc_severity()
    assert state["pin_not_connected"] == "warning"


def test_erc_set_severity_invalid_rule(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    sev_path = tmp_path / "erc_severity.json"
    monkeypatch.setattr("kicad_mcp.tools.validation._erc_severity_path", lambda: sev_path)
    with pytest.raises(ValueError, match="Unknown"):
        erc_set_rule_severity(rule_name="bogus_rule", severity="error")


def test_erc_set_severity_invalid_level(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    sev_path = tmp_path / "erc_severity.json"
    monkeypatch.setattr("kicad_mcp.tools.validation._erc_severity_path", lambda: sev_path)
    with pytest.raises(ValueError, match="Severity"):
        erc_set_rule_severity(rule_name="bus_conflict", severity="fatal")


def test_erc_reset_rules_all(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    sev_path = tmp_path / "erc_severity.json"
    monkeypatch.setattr("kicad_mcp.tools.validation._erc_severity_path", lambda: sev_path)
    _save_erc_severity({name: "ignore" for name in _ERC_RULE_NAMES})
    erc_reset_rules()
    state = _load_erc_severity()
    assert all(v == "error" for v in state.values())


def test_erc_reset_rules_single(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    sev_path = tmp_path / "erc_severity.json"
    monkeypatch.setattr("kicad_mcp.tools.validation._erc_severity_path", lambda: sev_path)
    _save_erc_severity({name: "ignore" for name in _ERC_RULE_NAMES})
    erc_reset_rules(rule_name="label_conflict")
    state = _load_erc_severity()
    assert state["label_conflict"] == "error"
    assert state.get("bus_conflict") == "ignore"
