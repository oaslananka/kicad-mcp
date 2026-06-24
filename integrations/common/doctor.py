#!/usr/bin/env python3
"""
KiCad MCP Doctor — standalone diagnostics runner.

Usage:
    python doctor.py                          # full diagnostics
    python doctor.py --agent claude-code      # agent-specific checks
    python doctor.py --json                   # machine-readable output
    python doctor.py --bundle output.zip      # write diagnostic bundle
"""

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path


def check_uvx() -> tuple[bool, str]:
    """Check if uvx is available."""
    path = shutil.which("uvx")
    if path:
        return True, f"uvx found at {path}"
    return False, "uvx not found — install uv (https://docs.astral.sh/uv/)"


def check_kicad_cli() -> tuple[bool, str]:
    """Check if kicad-cli is available."""
    path = shutil.which("kicad-cli")
    if path:
        try:
            result = subprocess.run([path, "version"], capture_output=True, text=True, timeout=10)
            version = result.stdout.strip() or result.stderr.strip()
            return True, f"kicad-cli found: {version}"
        except (subprocess.TimeoutExpired, OSError):
            return True, f"kicad-cli found at {path} (version check failed)"
    return False, "kicad-cli not found — install KiCad"


def check_kicad_mcp_server() -> tuple[bool, str, dict | None]:
    """Check if kicad-mcp-pro starts and returns tools."""
    executable = shutil.which("kicad-mcp-pro")
    if executable is None:
        return False, "kicad-mcp-pro not found — install with: pipx install kicad-mcp-pro", None
    try:
        result = subprocess.run(
            [executable, "doctor", "--json"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            return (
                True,
                f"Server OK: status={data['status']}, tools={data['tools']['tool_count']}",
                data,
            )
        return False, f"Server error (exit {result.returncode}): {result.stderr[:200]}", None
    except json.JSONDecodeError as e:
        return False, f"Server JSON parse error: {e}", None
    except subprocess.TimeoutExpired:
        return False, "Server startup timeout (30s)", None


def check_project_dir() -> tuple[bool, str]:
    """Check if KICAD_MCP_PROJECT_DIR is set and valid."""
    project_dir = os.environ.get("KICAD_MCP_PROJECT_DIR")
    if not project_dir:
        return False, "KICAD_MCP_PROJECT_DIR not set"
    path = Path(project_dir)
    if not path.exists():
        return False, f"KICAD_MCP_PROJECT_DIR={project_dir} does not exist"
    kicad_pro = list(path.glob("*.kicad_pro"))
    if kicad_pro:
        return True, f"Project found: {kicad_pro[0].name}"
    return True, "Directory exists (no .kicad_pro file found — this is fine for analysis)"


def check_config_exists(agent: str | None = None) -> list[tuple[str, bool, str]]:
    """Check MCP config files for supported agents."""
    checks = []
    config_paths = {
        "claude-code": lambda: Path.cwd() / ".mcp.json",
        "codex": lambda: Path.home() / ".codex" / "config.toml",
        "gemini": lambda: Path.home() / ".gemini" / "settings.json",
        "antigravity": lambda: Path.home() / ".gemini" / "config" / "mcp_config.json",
        "opencode": lambda: Path.cwd() / "opencode.json",
        "cursor": lambda: Path.cwd() / ".cursor" / "mcp.json",
        "vscode": lambda: Path.cwd() / ".vscode" / "mcp.json",
        "claude-desktop": lambda: (
            Path(os.environ.get("APPDATA", "")) / "Claude" / "claude_desktop_config.json"
            if platform.system() == "Windows"
            else Path.home()
            / "Library"
            / "Application Support"
            / "Claude"
            / "claude_desktop_config.json"
            if platform.system() == "Darwin"
            else Path.home() / ".config" / "Claude" / "claude_desktop_config.json"
        ),
    }

    for name, path_fn in config_paths.items():
        if agent and name != agent:
            continue
        path = path_fn()
        exists = path.exists()
        if exists:
            checks.append((name, True, f"Config found at {path}"))
        else:
            checks.append((name, False, f"No config at {path}"))
    return checks


def check_python_version() -> tuple[bool, str]:
    """Check Python version meets requirements."""
    v = sys.version_info
    ok = v.major >= 3 and v.minor >= 10
    return ok, f"Python {v.major}.{v.minor}.{v.micro} ({'OK' if ok else 'need 3.10+'})"


def run(agent: str | None = None, json_output: bool = False) -> int:
    """Run all checks and return exit code."""
    checks = []

    # Python
    ok, msg = check_python_version()
    checks.append(("python_version", ok, msg))

    # uvx
    ok, msg = check_uvx()
    checks.append(("uvx", ok, msg))

    # kicad-cli
    ok, msg = check_kicad_cli()
    checks.append(("kicad_cli", ok, msg))

    # kicad-mcp-pro server
    ok, msg, data = check_kicad_mcp_server()
    checks.append(("kicad_mcp_server", ok, msg))

    # Project directory
    ok, msg = check_project_dir()
    checks.append(("project_dir", ok, msg))

    # Agent configs
    config_checks = check_config_exists(agent)
    checks.extend((name, ok, msg) for name, ok, msg in config_checks)

    # Results
    passed = sum(1 for _, ok, _ in checks if ok)
    failed = sum(1 for _, ok, _ in checks if not ok)

    if json_output:
        output = {
            "schemaVersion": "1.0.0",
            "timestamp": None,  # caller can fill
            "ok": failed == 0,
            "status": "ok" if failed == 0 else "error",
            "checks": [
                {"name": name, "status": "ok" if ok else "error", "message": msg}
                for name, ok, msg in checks
            ],
        }
        json.dump(output, sys.stdout, indent=2)
        print()
    else:
        print(f"\nKiCad MCP Doctor — {platform.node()}")
        print("=" * 50)
        for name, ok, msg in checks:
            status = "✓" if ok else "✗"
            print(f"  {status} {name}: {msg}")
        print(f"\n{passed}/{len(checks)} checks passed")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="KiCad MCP Doctor")
    parser.add_argument("--agent", help="Check specific agent config only")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--bundle", help="Write diagnostic bundle zip")
    args = parser.parse_args()

    sys.exit(run(agent=args.agent, json_output=args.json))
