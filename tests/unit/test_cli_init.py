"""Tests for kicad_mcp.cli_init module (interactive setup wizard)."""

from __future__ import annotations

import json
from pathlib import Path

from kicad_mcp.cli_init import (
    MCP_CLIENT_CONFIGS,
    _generate_mcp_config,
    _resolve_config_path,
    _write_kicad_mcp_config,
    _write_mcp_config,
)

# ---------------------------------------------------------------------------
# MCP_CLIENT_CONFIGS
# ---------------------------------------------------------------------------


class TestMcpClientConfigs:
    def test_all_clients_have_three_platforms(self) -> None:
        for client, paths in MCP_CLIENT_CONFIGS.items():
            assert "windows" in paths, f"{client} missing windows"
            assert "darwin" in paths, f"{client} missing darwin"
            assert "linux" in paths, f"{client} missing linux"

    def test_all_config_paths_are_strings(self) -> None:
        for client, paths in MCP_CLIENT_CONFIGS.items():
            for platform_key, path in paths.items():
                assert isinstance(path, str), f"{client}/{platform_key} not a string"
                assert path.strip(), f"{client}/{platform_key} is empty"


# ---------------------------------------------------------------------------
# _resolve_config_path
# ---------------------------------------------------------------------------


class TestResolveConfigPath:
    def test_unknown_client_returns_none(self) -> None:
        assert _resolve_config_path("nonexistent-client") is None

    def test_known_client_returns_path(self) -> None:
        path = _resolve_config_path("claude-desktop")
        assert path is not None
        assert isinstance(path, Path)
        # Path should be absolute after expandvars/expanduser
        assert str(path).startswith("/") or (":" in str(path)[:3])  # unix or windows


# ---------------------------------------------------------------------------
# _generate_mcp_config
# ---------------------------------------------------------------------------


class TestGenerateMcpConfig:
    def test_http_transport(self) -> None:
        result = _generate_mcp_config("streamable-http", 3334)
        mcp = result["mcpServers"]["kicad-mcp-pro"]
        assert mcp["command"] == "uvx"
        assert "streamable-http" in mcp["args"]
        assert mcp["env"] == {}

    def test_stdio_transport(self) -> None:
        result = _generate_mcp_config("stdio", 3334)
        mcp = result["mcpServers"]["kicad-mcp-pro"]
        assert mcp["command"] == "uvx"
        assert "stdio" not in mcp["args"]  # stdio uses just the package name

    def test_custom_version(self) -> None:
        result = _generate_mcp_config("streamable-http", 8080, version="4.0.0")
        mcp = result["mcpServers"]["kicad-mcp-pro"]
        assert any("4.0.0" in arg for arg in mcp["args"])

    def test_output_is_valid_json(self) -> None:
        result = _generate_mcp_config("streamable-http", 3334)
        # Should be serializable
        json.dumps(result)
        assert "mcpServers" in result


# ---------------------------------------------------------------------------
# _write_mcp_config
# ---------------------------------------------------------------------------


class TestWriteMcpConfig:
    def test_unknown_client_returns_none(self) -> None:
        result = _write_mcp_config("nonexistent", {"mcpServers": {}})
        assert result is None

    def test_creates_new_file(self, tmp_path: Path) -> None:
        # Point config to a temp location by patching
        import kicad_mcp.cli_init as cli_init

        orig_resolve = cli_init._resolve_config_path

        def mock_resolve(client: str) -> Path | None:
            return tmp_path / "config.json"

        cli_init._resolve_config_path = mock_resolve
        try:
            snippet = _generate_mcp_config("streamable-http", 3334)
            result = _write_mcp_config("cursor", snippet)
            assert result is not None
            assert result.exists()
            data = json.loads(result.read_text(encoding="utf-8"))
            assert "mcpServers" in data
            assert "kicad-mcp-pro" in data["mcpServers"]
        finally:
            cli_init._resolve_config_path = orig_resolve

    def test_merges_existing_file(self, tmp_path: Path) -> None:
        import kicad_mcp.cli_init as cli_init

        orig_resolve = cli_init._resolve_config_path

        config_path = tmp_path / "config.json"
        config_path.write_text(
            json.dumps({"mcpServers": {"existing-agent": {"command": "npx"}}}, indent=2),
            encoding="utf-8",
        )

        def mock_resolve(client: str) -> Path | None:
            return config_path

        cli_init._resolve_config_path = mock_resolve
        try:
            snippet = _generate_mcp_config("streamable-http", 3334)
            result = _write_mcp_config("cursor", snippet)
            assert result is not None
            data = json.loads(result.read_text(encoding="utf-8"))
            assert "existing-agent" in data["mcpServers"]
            assert "kicad-mcp-pro" in data["mcpServers"]
        finally:
            cli_init._resolve_config_path = orig_resolve


# ---------------------------------------------------------------------------
# _write_kicad_mcp_config
# ---------------------------------------------------------------------------


class TestWriteKicadMcpConfig:
    def test_writes_config(self, tmp_path: Path) -> None:
        output = tmp_path / "kicad-mcp" / "config.json"
        kicad_path = Path("/usr/local/bin/kicad-cli")  # noqa: S108
        result = _write_kicad_mcp_config(kicad_path, "streamable-http", 3334, output=output)
        assert result == output
        assert output.exists()
        data = json.loads(output.read_text(encoding="utf-8"))
        assert data["kicad_path"] == str(kicad_path)
        assert data["transport"] == "streamable-http"
        assert data["port"] == 3334

    def test_default_path_uses_home_dir(self) -> None:
        kicad_path = Path("/usr/local/bin/kicad-cli")  # noqa: S108
        result = _write_kicad_mcp_config(kicad_path, "stdio", 0)
        expected = Path.home() / ".kicad-mcp" / "config.json"
        assert result == expected
        assert result.exists()
        result.unlink()
        # Clean up parent if empty
        result.parent.rmdir()
