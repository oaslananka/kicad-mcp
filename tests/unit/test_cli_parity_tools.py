"""Unit tests for CLI parity / export wrapper tools (FAZ 2)."""

from __future__ import annotations

import pytest

from kicad_mcp.tools.export_support import _run_cli_variants
from kicad_mcp.tools.export import _safe_output_filename


def test_safe_output_filename_valid() -> None:
    name = _safe_output_filename("output.csv", default_name="out.csv")
    assert name == "output.csv"


def test_safe_output_filename_rejects_path() -> None:
    with pytest.raises(ValueError, match="directory"):
        _safe_output_filename("../escape.csv", default_name="out.csv")


def test_safe_output_filename_rejects_absolute() -> None:
    with pytest.raises(ValueError, match="absolute|relative"):
        _safe_output_filename("C:\\Windows\\file.csv", default_name="out.csv")


def test_safe_output_filename_empty_rejected() -> None:
    with pytest.raises(ValueError, match="empty"):
        _safe_output_filename("  ", default_name="out.csv")


def test_run_cli_variants_missing_binary() -> None:
    code, stdout, stderr = _run_cli_variants(
        [["/nonexistent/binary", "arg"]],
    )
    assert code != 0
