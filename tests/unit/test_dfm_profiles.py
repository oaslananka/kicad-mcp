"""Unit tests for DFM profile loading and validation (FAZ 12)."""

from __future__ import annotations

import json

import pytest

from kicad_mcp.tools.dfm import _load_profile, _profile_paths, pcbway_standard_profile


def test_profile_paths_returns_list() -> None:
    paths = _profile_paths()
    assert len(paths) >= 3  # at least the bundled profiles


def test_load_profiles_contain_required_keys() -> None:
    for path in _profile_paths():
        profile = _load_profile(path)
        assert "name" in profile
        assert "manufacturer" in profile
        assert "capabilities" in profile


def test_pcbway_standard_has_profile(pcbway_standard_profile) -> None:  # type: ignore[no-untyped-def]
    profile = pcbway_standard_profile
    assert profile is not None
    assert profile.get("manufacturer") == "PCBWay"


def test_unknown_profile_returns_error() -> None:
    from kicad_mcp.tools.dfm import dfm_load_manufacturer_profile

    result = dfm_load_manufacturer_profile("nonexistent_brand")
    assert "not found" in result.lower() or "error" in result.lower()
