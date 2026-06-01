"""Real KiCad CLI smoke tests.

These tests intentionally skip unless a real ``kicad-cli`` executable is
discoverable from ``KICAD_MCP_KICAD_CLI``, ``KICAD_CLI_PATH``, ``PATH``, or the
project's existing discovery/configuration layer. They are not subprocess mocks;
CI should run them only in a KiCad 10-capable environment.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from kicad_mcp.config import get_config, reset_config

KICAD_MAJOR_VERSION = 10


def _candidate_cli_paths() -> list[Path]:
    """Return ordered KiCad CLI candidates from env, PATH, then project discovery."""
    candidates: list[Path] = []
    for env_name in ("KICAD_MCP_KICAD_CLI", "KICAD_CLI_PATH"):
        raw_path = os.environ.get(env_name, "").strip()
        if raw_path:
            candidates.append(Path(raw_path).expanduser())

    discovered = shutil.which("kicad-cli")
    if discovered:
        candidates.append(Path(discovered))

    try:
        reset_config()
        candidates.append(get_config().kicad_cli)
    except Exception:  # noqa: S110
        pass

    deduplicated: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate)
        if key not in seen:
            deduplicated.append(candidate)
            seen.add(key)
    return deduplicated


@pytest.fixture(scope="session")
def kicad_cli_path() -> Path:
    """Return the configured/discovered KiCad CLI path or skip when unavailable."""
    for cli_path in _candidate_cli_paths():
        if cli_path.exists() and cli_path.is_file():
            return cli_path
    searched = ", ".join(str(path) for path in _candidate_cli_paths()) or "<none>"
    pytest.skip(f"kicad-cli not found via env, PATH, or discovery. Candidates: {searched}")
    raise RuntimeError("pytest.skip() returned unexpectedly")


def _run_kicad_cli(
    cli_path: Path,
    *args: str,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run kicad-cli and return a completed process with captured text output."""
    return subprocess.run(
        [str(cli_path), *args],
        cwd=cwd,
        text=True,
        capture_output=True,
        timeout=60,
        check=False,
    )


def _combined_output(result: subprocess.CompletedProcess[str]) -> str:
    return "\n".join(part for part in (result.stdout, result.stderr) if part)


def _write_minimal_project(project_dir: Path) -> Path:
    """Create a deterministic minimal KiCad project with an empty board file."""
    project_dir.mkdir(parents=True, exist_ok=True)
    project_file = project_dir / "smoke.kicad_pro"
    board_file = project_dir / "smoke.kicad_pcb"
    project_file.write_text(
        """
{
  "board": {
    "design_settings": {
      "defaults": {},
      "diff_pair_dimensions": [],
      "drc_exclusions": [],
      "rules": {}
    }
  },
  "meta": {
    "filename": "smoke.kicad_pro",
    "version": 1
  },
  "net_settings": {
    "classes": [],
    "meta": {
      "version": 3
    },
    "nets": []
  }
}
""".strip()
        + "\n",
        encoding="utf-8",
    )
    board_file.write_text(
        """
(kicad_pcb
  (version 20240108)
  (generator "kicad-mcp-pro-smoke")
  (general)
  (paper "A4")
  (layers
    (0 "F.Cu" signal)
    (31 "B.Cu" signal)
    (44 "Edge.Cuts" user)
  )
  (setup (pad_to_mask_clearance 0))
)
""".strip()
        + "\n",
        encoding="utf-8",
    )
    return board_file


def test_kicad_cli_version_is_discoverable(kicad_cli_path: Path) -> None:
    """Verify that the discovered binary is a KiCad 10 CLI."""
    result = _run_kicad_cli(kicad_cli_path, "version")
    output = _combined_output(result)

    assert result.returncode == 0, output
    match = re.search(r"\b(\d+)\.\d+(?:\.\d+)?\b", output)
    assert match is not None, output
    assert int(match.group(1)) == KICAD_MAJOR_VERSION, output


def test_kicad_cli_exports_board_stats_without_gui(kicad_cli_path: Path, tmp_path: Path) -> None:
    """Run a GUI-free CLI export path against a minimal board fixture."""
    project_dir = tmp_path / "project"
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    board_file = _write_minimal_project(project_dir)
    stats_file = artifacts_dir / "board_stats.txt"

    result = _run_kicad_cli(
        kicad_cli_path,
        "pcb",
        "export",
        "stats",
        "--output",
        str(stats_file),
        str(board_file),
        cwd=project_dir,
    )
    output = _combined_output(result)
    (artifacts_dir / "kicad-cli-stdout.log").write_text(result.stdout, encoding="utf-8")
    (artifacts_dir / "kicad-cli-stderr.log").write_text(result.stderr, encoding="utf-8")

    assert result.returncode == 0, output
    assert stats_file.exists(), output
    assert stats_file.stat().st_size > 0, output
