"""Embedded compatibility metadata synchronized from the repository matrix."""

from __future__ import annotations

from copy import deepcopy
from typing import Final

MCP_PROTOCOL_VERSION: Final = "2025-11-25"
MCP_TOOL_SCHEMA_VERSION: Final = "1.0"
PRIMARY_KICAD_VERSION: Final = "10.0.x"

COMPATIBILITY_MATRIX: Final[dict[str, object]] = {
    "schemaVersion": 1,
    "kicad": {
        "primary": PRIMARY_KICAD_VERSION,
        "supported": ["10.0.x", "9.x", "8.x"],
        "deprecated": ["9.x", "8.x"],
    },
    "mcp": {
        "protocolVersion": MCP_PROTOCOL_VERSION,
        "toolSchema": MCP_TOOL_SCHEMA_VERSION,
    },
    "products": {
        "kicad-studio": {
            "version": "1.0.0",
            "compatibleMcpPro": {
                "required": ">=3.5.2 <4.0.0",
                "recommended": ">=3.5.2 <4.0.0",
                "testedAgainst": "3.5.2",
            },
        },
        "kicad-mcp-pro": {
            "version": "3.9.0",
            "compatibleExtension": {
                "required": ">=1.0.0 <2.0.0",
                "testedAgainst": "1.0.0",
            },
        },
    },
}


def compatibility_summary() -> dict[str, object]:
    """Return a copy of compatibility metadata for discovery payloads."""
    return deepcopy(COMPATIBILITY_MATRIX)
