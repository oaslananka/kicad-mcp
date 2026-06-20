"""Lint public MCP tool contracts against router and metadata conventions."""

from __future__ import annotations

import asyncio
import sys
from typing import Any

from kicad_mcp.capabilities import AccessTier, all_records, metadata_coverage
from kicad_mcp.server import build_server


async def _tool_schemas() -> dict[str, dict[str, Any]]:
    server = build_server("agent_full")
    return {tool.name: dict(tool.inputSchema or {}) for tool in await server.list_tools()}


def _schema_properties(schema: dict[str, Any]) -> dict[str, Any]:
    properties = schema.get("properties", {})
    return properties if isinstance(properties, dict) else {}


async def lint() -> list[str]:
    """Return human-readable contract errors."""
    errors: list[str] = []
    coverage = metadata_coverage()
    if coverage["missing_tools"]:
        missing = ", ".join(str(name) for name in coverage["missing_tools"])
        errors.append(f"Missing capability metadata for routed tools: {missing}")

    records = all_records()
    read_only_profiles = {"beginner", "read_only_inspection"}
    for profile in read_only_profiles:
        server = build_server(profile)
        surfaced = {tool.name for tool in await server.list_tools()}
        for tool_name in surfaced:
            record = records.get(tool_name)
            if record is None:
                continue
            if record.tier in {AccessTier.WRITE, AccessTier.PUBLISH, AccessTier.HUMAN_ONLY}:
                errors.append(f"Read-only profile '{profile}' exposes mutating tool {tool_name}")

    schemas = await _tool_schemas()
    lib_search_components = _schema_properties(schemas.get("lib_search_components", {}))
    if "query" not in lib_search_components:
        errors.append("lib_search_components must expose preferred parameter 'query'.")
    if "keyword" not in lib_search_components:
        errors.append("lib_search_components must keep backward-compatible 'keyword'.")

    for name, record in records.items():
        if record.tier in {AccessTier.WRITE, AccessTier.PUBLISH, AccessTier.HUMAN_ONLY}:
            if not isinstance(record.supports_rollback, bool):
                errors.append(f"{name} must explicitly declare rollback support.")
            if not isinstance(record.supports_dry_run, bool):
                errors.append(f"{name} must explicitly declare dry-run support.")
    return errors


def main() -> int:
    errors = asyncio.run(lint())
    if errors:
        print("Tool contract lint failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("Tool contract lint passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
