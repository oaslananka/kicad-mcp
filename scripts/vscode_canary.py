#!/usr/bin/env python3
"""Generate VS Code canary lanes from repository compatibility metadata."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml

MCP_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = MCP_ROOT


def _read_compatibility_matrix() -> dict[str, Any]:
    data = yaml.safe_load((REPO_ROOT / "compatibility.yaml").read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise TypeError("compatibility.yaml must contain a YAML mapping")
    return data


def _vscode_value(vscode: dict[str, Any], key: str) -> str:
    value = vscode.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"compatibility metadata missing vscode.{key}")
    return value


def _channel_version(value: str, channel: str) -> str:
    return channel if value == "current" else value


def build_canary_matrix(compatibility: dict[str, Any]) -> dict[str, list[dict[str, object]]]:
    """Return GitHub Actions matrix lanes derived from VS Code compatibility metadata."""
    vscode = compatibility.get("vscode")
    if not isinstance(vscode, dict):
        raise ValueError("compatibility metadata missing vscode mapping")

    return {
        "include": [
            {
                "id": "vscode-stable",
                "state": "primary",
                "version": _channel_version(_vscode_value(vscode, "stable"), "stable"),
                "continue_on_error": False,
            },
            {
                "id": "vscode-minimum",
                "state": "supported",
                "version": _vscode_value(vscode, "minimum"),
                "continue_on_error": False,
            },
            {
                "id": "vscode-insiders",
                "state": "prerelease",
                "version": _channel_version(_vscode_value(vscode, "insiders"), "insiders"),
                "continue_on_error": True,
            },
        ]
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("matrix",))
    args = parser.parse_args(argv)

    if args.command == "matrix":
        print(json.dumps(build_canary_matrix(_read_compatibility_matrix()), separators=(",", ":")))
        return 0

    parser.error(f"Unsupported command {args.command!r}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
