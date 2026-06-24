from __future__ import annotations

import pytest

from scripts import security_local


def test_required_paths_reports_all_missing_required_tools(monkeypatch, capsys) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(security_local, "_which", lambda _command: None)

    with pytest.raises(SystemExit) as exc:
        security_local._required_paths()

    assert exc.value.code == 127
    stderr = capsys.readouterr().err
    assert "gitleaks is required" in stderr
    assert "actionlint is required" in stderr
    assert "zizmor is required" in stderr


def test_required_paths_returns_all_tool_paths(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(security_local, "_which", lambda command: f"/tools/{command}")

    assert security_local._required_paths() == {
        "gitleaks": "/tools/gitleaks",
        "actionlint": "/tools/actionlint",
        "zizmor": "/tools/zizmor",
    }
