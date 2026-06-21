from __future__ import annotations

from pathlib import Path

from kicad_mcp import diagnostics

REQ_KEY = "required" "-version"


def _checkout(tmp_path: Path) -> Path:
    checkout = tmp_path / "kicad-mcp"
    checkout.mkdir()
    return checkout


def _requirement(value: str) -> str:
    return f'{REQ_KEY} = "{value}"\n'


def test_config_requirement_reads_tool_file_first(tmp_path: Path) -> None:
    checkout = _checkout(tmp_path)
    (checkout / "uv.toml").write_text(_requirement("0.10.8"), encoding="utf-8")
    (checkout / "pyproject.toml").write_text(
        f'[tool.uv]\n{_requirement(">=0.11,<0.12")}',
        encoding="utf-8",
    )

    assert diagnostics._required_uv_version(checkout) == "0.10.8"


def test_config_requirement_falls_back_to_pyproject_tool_table(tmp_path: Path) -> None:
    checkout = _checkout(tmp_path)
    (checkout / "uv.toml").write_text('preview = true\n', encoding="utf-8")
    (checkout / "pyproject.toml").write_text(
        f'[tool.uv]\n{_requirement(">=0.10,<0.12")}',
        encoding="utf-8",
    )

    assert diagnostics._required_uv_version(checkout) == ">=0.10,<0.12"


def test_config_check_accepts_range_specifier(tmp_path: Path, monkeypatch) -> None:
    checkout = _checkout(tmp_path)
    (checkout / "uv.toml").write_text(_requirement(">=0.10,<0.12"), encoding="utf-8")
    monkeypatch.setattr(
        diagnostics,
        "_detect_uv_version",
        lambda: ("0.11.19", "/usr/bin/uv"),
    )

    check = diagnostics._uv_version_check(checkout)

    assert check is not None
    assert check.status == "ok"
    assert "satisfies checkout requirement >=0.10,<0.12" in check.message


def test_config_check_reports_exact_pin_mismatch(tmp_path: Path, monkeypatch) -> None:
    checkout = _checkout(tmp_path)
    (checkout / "uv.toml").write_text(_requirement("0.10.8"), encoding="utf-8")
    monkeypatch.setattr(
        diagnostics,
        "_detect_uv_version",
        lambda: ("0.11.19", "C:/tools/uv.exe"),
    )

    check = diagnostics._uv_version_check(checkout)

    assert check is not None
    assert check.status == "warn"
    assert "Checkout requires uv 0.10.8" in check.message
    assert "uv self update 0.10.8" in check.hint


def test_config_requirement_handles_invalid_and_missing_config(tmp_path: Path) -> None:
    checkout = _checkout(tmp_path)
    assert diagnostics._required_uv_version(checkout) is None

    (checkout / "uv.toml").write_text(f'{REQ_KEY} = 123\n', encoding="utf-8")
    assert diagnostics._required_uv_version(checkout) is None

    (checkout / "uv.toml").write_text(f'{REQ_KEY} = [\n', encoding="utf-8")
    (checkout / "pyproject.toml").write_text(
        f'[tool.uv]\n{_requirement("0.10.8")}',
        encoding="utf-8",
    )
    assert diagnostics._required_uv_version(checkout) == "0.10.8"
