"""Unit tests for variant extended tools (FAZ 10.2)."""

from __future__ import annotations

from pathlib import Path

import pytest

from kicad_mcp.tools.variants import (
    _load_state,
    _save_state,
    _variant_names,
    variant_clone,
    variant_delete,
    variant_get_component_status,
)


def test_variant_clone_creates_new(sample_project: Path) -> None:
    state = _load_state()
    assert "default" in state["variants"]

    # Add a variant to clone
    state["variants"]["v1"] = {"overrides": {}}
    _save_state(state)

    result = variant_clone(name="v1", new_name="v2")
    assert "v2" in result

    state = _load_state()
    assert "v2" in state["variants"]


def test_variant_clone_rejects_duplicate(sample_project: Path) -> None:
    state = _load_state()
    state["variants"]["dup"] = {"overrides": {}}
    _save_state(state)

    with pytest.raises(ValueError, match="already exists"):
        variant_clone(name="default", new_name="dup")


def test_variant_delete_removes(sample_project: Path) -> None:
    state = _load_state()
    state["variants"]["to_delete"] = {"overrides": {}}
    _save_state(state)

    assert "to_delete" in _variant_names(_load_state())
    result = variant_delete(name="to_delete")
    assert "Deleted" in result
    assert "to_delete" not in _variant_names(_load_state())


def test_variant_delete_rejects_default(sample_project: Path) -> None:
    with pytest.raises(ValueError, match="default"):
        variant_delete(name="default")


def test_variant_get_component_status_missing(sample_project: Path) -> None:
    with pytest.raises(ValueError, match="not found"):
        variant_get_component_status(variant="default", reference="ZZ99")
