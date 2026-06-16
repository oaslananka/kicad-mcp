"""Verified security controls (work order P5-T2, K8).

These lock the controls in docs/security/threat-model.md so they cannot silently
regress: the server never shells out, kicad-cli is invoked as an argv list (so a path
argument is never shell-interpreted), and user-supplied paths cannot escape the
workspace.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from kicad_mcp.errors import UnsafePathError
from kicad_mcp.path_safety import relative_subpath, resolve_under

SRC = Path(__file__).resolve().parents[2] / "src" / "kicad_mcp"
_SHELL_EXEC = re.compile(
    r"shell\s*=\s*True|\bos\.system\s*\(|\bos\.popen\s*\(|subprocess\.getoutput\s*\("
)


def test_no_shell_execution_anywhere_in_src() -> None:
    """The server must never invoke a shell — kicad-cli runs as an argv list, so user
    paths and names cannot be interpreted as shell commands (CLI-injection control)."""
    offenders = [
        str(py.relative_to(SRC))
        for py in SRC.rglob("*.py")
        if _SHELL_EXEC.search(py.read_text(encoding="utf-8", errors="ignore"))
    ]
    assert not offenders, f"shell execution found (injection risk): {offenders}"


def test_resolve_under_blocks_parent_traversal(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    with pytest.raises(UnsafePathError):
        resolve_under(root, "../../etc/passwd")
    with pytest.raises(UnsafePathError):
        resolve_under(root, str(root.parent / "outside.txt"))


def test_resolve_under_allows_paths_inside_root(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    resolved = resolve_under(root, "output/gerber")
    assert str(resolved).startswith(str(root.resolve()))


def test_relative_subpath_blocks_traversal_and_absolute() -> None:
    with pytest.raises(UnsafePathError):
        relative_subpath("../escape")
    with pytest.raises(UnsafePathError):
        relative_subpath(str(SRC))  # a platform-absolute path must be rejected
    assert relative_subpath("a/b").parts == ("a", "b")


def test_kicad_cli_is_invoked_as_argv_list(fake_cli: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """_run_cli must pass [binary, *args]; never a shell string."""
    import kicad_mcp.tools.export_support as export_support
    from kicad_mcp.config import reset_config

    reset_config()
    captured: dict[str, object] = {}

    class _Result:
        returncode = 0
        stdout = ""
        stderr = ""

    def fake_run(cmd, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003
        captured["cmd"] = cmd
        captured["shell"] = kwargs.get("shell", False)
        return _Result()

    monkeypatch.setattr(export_support.subprocess, "run", fake_run)
    export_support._run_cli("pcb", "export", "gerber", "; rm -rf /")

    cmd = captured["cmd"]
    assert isinstance(cmd, list), "kicad-cli must be invoked with an argv list"
    assert cmd[0] == str(fake_cli)
    # The injection-looking argument is a plain argv element, never shell-interpreted.
    assert cmd[-1] == "; rm -rf /"
    assert captured["shell"] is False
