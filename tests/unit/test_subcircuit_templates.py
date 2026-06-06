"""Unit tests for subcircuit template instantiation (FAZ 13)."""

from __future__ import annotations

import pytest

from kicad_mcp.tools.schematic import sch_list_templates, sch_get_template_info


def test_list_templates_returns_list() -> None:
    result = sch_list_templates()
    assert "nrf52840" in result or "ws2812b" in result or "templates" in result.lower()


def test_get_template_info_exists() -> None:
    # The nrf52840_minimal template should exist
    result = sch_get_template_info("nrf52840_minimal")
    assert result is not None
    assert "nrf" in result.lower() or "not found" not in result.lower()


def test_get_template_info_missing() -> None:
    result = sch_get_template_info("nonexistent_template_xyz")
    assert "not found" in result.lower() or "error" in result.lower()
