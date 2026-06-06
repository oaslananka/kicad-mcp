"""Unit tests for jobset tools (FAZ 2.1)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from kicad_mcp.tools.jobset import list_templates, run_jobset


def test_list_templates_no_jobsets(tmp_path: Path) -> None:
    with patch("kicad_mcp.tools.jobset._jobset_dir", return_value=tmp_path):
        result = list_templates()
        assert "No" in result or "0" in result or "templates" in result.lower()


def test_run_jobset_missing_file() -> None:
    with pytest.raises((ValueError, FileNotFoundError)):
        run_jobset(jobset_path="/nonexistent/jobset.json")
