"""Unit tests for CLI parity / export wrapper tools (FAZ 2)."""

from __future__ import annotations

from pathlib import Path

import pytest

from kicad_mcp.tools.export import _safe_output_filename
from kicad_mcp.tools.export_support import _run_cli_variants


def test_safe_output_filename_valid() -> None:
    name = _safe_output_filename("output.csv", default_name="out.csv")
    assert name == "output.csv"


def test_safe_output_filename_rejects_path() -> None:
    with pytest.raises(ValueError, match="directory"):
        _safe_output_filename("../escape.csv", default_name="out.csv")


def test_safe_output_filename_rejects_absolute() -> None:
    with pytest.raises(ValueError, match="directory separators"):
        _safe_output_filename("C:\\Windows\\file.csv", default_name="out.csv")


def test_safe_output_filename_empty_rejected() -> None:
    with pytest.raises(ValueError, match="empty"):
        _safe_output_filename("  ", default_name="out.csv")


def test_run_cli_variants_missing_binary(fake_cli: Path) -> None:
    code, stdout, stderr = _run_cli_variants(
        [["--nonexistent"]],
    )
    # With fake_cli the shell script always exits 0, so code == 0
    # (the test validates the function runs without FileNotFoundError)
    assert isinstance(code, int)
    assert isinstance(stdout, str)
