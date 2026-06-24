#!/usr/bin/env python3
"""
Validate MCP configuration files for all supported agents.

Usage:
    python validate-mcp-config.py                     # validate all
    python validate-mcp-config.py --agent claude-code  # specific agent
    python validate-mcp-config.py --path /path/to/config.json
"""

import argparse
import json
import sys
import tomllib
from pathlib import Path


def validate_json_config(path: Path) -> list[str]:
    """Validate a JSON MCP config file."""
    errors = []
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        return [f"Invalid JSON: {e}"]

    # Claude Code / Cursor format
    if "mcpServers" in data:
        for name, server in data["mcpServers"].items():
            if isinstance(server, dict):
                if "command" not in server and "url" not in server and "httpUrl" not in server:
                    errors.append(f"{name}: missing command/url/httpUrl")
    # VS Code format
    if "servers" in data:
        for name, server in data["servers"].items():
            if isinstance(server, dict):
                if "command" not in server and "url" not in server:
                    errors.append(f"{name}: missing command/url")
    return errors


def validate_toml_config(path: Path) -> list[str]:
    """Validate a TOML MCP config file (Codex format)."""
    errors = []
    try:
        data = tomllib.loads(path.read_text())
    except Exception as e:
        return [f"Invalid TOML: {e}"]

    for section, values in data.items():
        if section.startswith("mcp_servers."):
            if isinstance(values, dict):
                if "command" not in values and "args" not in values:
                    errors.append(f"{section}: missing command/args")
    return errors


def validate_opencode_config(path: Path) -> list[str]:
    """Validate an OpenCode config file."""
    errors = []
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        return [f"Invalid JSON: {e}"]

    mcp = data.get("mcp", {})
    for name, server in mcp.items():
        if isinstance(server, dict):
            if server.get("type") == "local" and "command" not in server:
                errors.append(f"mcp.{name}: local type missing command")
            elif server.get("type") == "remote" and "url" not in server:
                errors.append(f"mcp.{name}: remote type missing url")
    return errors


def validate_vscode_config(path: Path) -> list[str]:
    """Validate VS Code MCP config."""
    errors = []
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        return [f"Invalid JSON: {e}"]

    servers = data.get("servers", {})
    for name, server in servers.items():
        if isinstance(server, dict):
            server_type = server.get("type", "stdio")
            if server_type == "stdio" and "command" not in server:
                errors.append(f"servers.{name}: stdio type missing command")
            elif server_type == "http" and "url" not in server:
                errors.append(f"servers.{name}: http type missing url")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate MCP configuration files")
    parser.add_argument("--agent", help="Validate config for specific agent")
    parser.add_argument("--path", help="Validate a specific config file")
    args = parser.parse_args()

    config_checks = {}

    if args.path:
        path = Path(args.path)
        if not path.exists():
            print(f"File not found: {path}")
            return 1
        errors = validate_json_config(path)
        config_checks[path.name] = (path, errors)
    elif args.agent:
        agent = args.agent.lower()
        val = {"codex": validate_toml_config, "opencode": validate_opencode_config}
        formatters = {"json": validate_json_config, "toml": validate_toml_config}

        paths = {
            "claude-code": Path(".mcp.json"),
            "codex": Path.home() / ".codex" / "config.toml",
            "gemini": Path.home() / ".gemini" / "settings.json",
            "antigravity": Path.home() / ".gemini" / "config" / "mcp_config.json",
            "opencode": Path("opencode.json"),
            "cursor": Path(".cursor") / "mcp.json",
            "vscode": Path(".vscode") / "mcp.json",
            "claude-desktop": Path.home() / ".config" / "Claude" / "claude_desktop_config.json",
        }
        path = paths.get(agent)
        if path and path.exists():
            validator = val.get(agent, formatters.get("json"))
            errors = validator(path) if validator else validate_json_config(path)
            config_checks[agent] = (path, errors)
        else:
            print(f"No config found for agent: {agent}")
            return 1
    else:
        # Validate all common example files
        example_dirs = [
            Path("integrations/claude-code/.mcp.json.example"),
            Path("integrations/codex/config.toml.example"),
            Path("integrations/gemini-cli/settings.example.json"),
            Path("integrations/antigravity/mcp_config.example.json"),
            Path("integrations/opencode/opencode.example.json"),
            Path("integrations/cursor/mcp.example.json"),
            Path("integrations/vscode/mcp.example.json"),
            Path("integrations/claude-desktop/claude_desktop_config.example.json"),
        ]
        for ex_path in example_dirs:
            full = Path.cwd() / ex_path
            if full.exists():
                if full.suffix == ".toml":
                    errors = validate_toml_config(full)
                else:
                    errors = validate_json_config(full)
                config_checks[ex_path.name] = (full, errors)

    all_ok = True
    for name, (path, errors) in config_checks.items():
        if errors:
            print(f"✗ {name} ({path}):")
            for err in errors:
                print(f"    - {err}")
            all_ok = False
        else:
            print(f"✓ {name}: valid")

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
