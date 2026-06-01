from __future__ import annotations

from scripts.vscode_canary import build_canary_matrix


def test_vscode_canary_matrix_uses_compatibility_metadata() -> None:
    matrix = build_canary_matrix(
        {
            "vscode": {
                "minimum": "1.120.0",
                "stable": "current",
                "insiders": "current",
            }
        }
    )

    assert matrix == {
        "include": [
            {
                "id": "vscode-stable",
                "state": "primary",
                "version": "stable",
                "continue_on_error": False,
            },
            {
                "id": "vscode-minimum",
                "state": "supported",
                "version": "1.120.0",
                "continue_on_error": False,
            },
            {
                "id": "vscode-insiders",
                "state": "prerelease",
                "version": "insiders",
                "continue_on_error": True,
            },
        ]
    }


def test_vscode_canary_matrix_preserves_explicit_channel_versions() -> None:
    matrix = build_canary_matrix(
        {
            "vscode": {
                "minimum": "1.120.0",
                "stable": "1.116.0",
                "insiders": "1.117.0-insider",
            }
        }
    )

    assert matrix["include"][0]["version"] == "1.116.0"
    assert matrix["include"][2]["version"] == "1.117.0-insider"
