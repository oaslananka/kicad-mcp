#!/usr/bin/env python3
"""Verify that kicad-mcp-pro is installed and the MCP server starts."""

import json
import shutil
import subprocess
import sys


def main() -> int:
    """Run verification checks and return exit code."""
    checks = 0
    passed = 0

    # Check 1: Package importable
    checks += 1
    try:
        import kicad_mcp  # noqa: F401

        print(f"✓ kicad-mcp-pro v{kicad_mcp.__version__} is importable")
        passed += 1
    except ImportError as e:
        print(f"✗ kicad-mcp-pro not importable: {e}")

    executable = shutil.which("kicad-mcp-pro")

    # Check 2: CLI runs
    checks += 1
    if executable is None:
        print("✗ kicad-mcp-pro not found")
    else:
        try:
            result = subprocess.run(
                [executable, "version", "--json"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                data = json.loads(result.stdout)
                print(
                    f"✓ CLI works: v{data['package']['version']}, profile={data['mcp']['profile']}"
                )
                passed += 1
            else:
                print(f"✗ CLI error: {result.stderr[:200]}")
        except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError) as e:
            print(f"✗ CLI check failed: {e}")

    # Check 3: Doctor runs
    checks += 1
    if executable is None:
        print("✗ kicad-mcp-pro not found")
    else:
        try:
            result = subprocess.run(
                [executable, "doctor", "--json"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                data = json.loads(result.stdout)
                print(
                    f"✓ Doctor report: status={data['status']}, tools={data['tools']['tool_count']}"
                )
                passed += 1
            else:
                print(f"✗ Doctor error: {result.stderr[:200]}")
        except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError) as e:
            print(f"✗ Doctor check failed: {e}")

    print(f"\n{passed}/{checks} checks passed")
    return 0 if passed == checks else 1


if __name__ == "__main__":
    sys.exit(main())
