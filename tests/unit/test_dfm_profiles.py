"""Unit tests for DFM profile loading and validation (FAZ 12)."""

from __future__ import annotations

from pathlib import Path

import pytest

from kicad_mcp.tools.dfm import _available_profile_names, _load_profile


def test_available_profile_names() -> None:
    names = _available_profile_names()
    assert len(names) >= 3  # at least the bundled profiles


def test_load_profile_contains_required_keys() -> None:
    for name in _available_profile_names():
        manufacturer, tier = name.rsplit("_", 1)
        profile = _load_profile(manufacturer, tier)
        assert isinstance(profile, dict)
        if "entries" in profile:
            # Rotation-correction profiles have a different structure
            assert len(profile["entries"]) >= 1
        else:
            assert "manufacturer" in profile
            assert "tier" in profile
            assert "rules" in profile


def test_load_profile_unknown_raises() -> None:
    with pytest.raises(ValueError, match="Unknown DFM profile"):
        _load_profile("Nonexistent", "standard")


@pytest.mark.anyio
async def test_dfm_load_manufacturer_profile_not_found(
    sample_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("KICAD_MCP_OPERATING_MODE", "experimental")
    from kicad_mcp.server import create_server
    from tests.conftest import call_tool_text

    server = create_server()
    await call_tool_text(server, "kicad_set_project", {"project_dir": str(sample_project)})
    result = await call_tool_text(
        server, "dfm_load_manufacturer_profile", {"manufacturer": "nonexistent"}
    )
    assert "not found" in result.lower() or "error" in result.lower()
