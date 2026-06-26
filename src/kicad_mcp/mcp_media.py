"""Helpers for returning binary media through MCP tool results."""

from __future__ import annotations

import base64
import json
import mimetypes
from pathlib import Path
from typing import Any

from mcp.types import CallToolResult, ImageContent, TextContent


def text_tool_result(
    text: str,
    *,
    metadata: dict[str, Any] | None = None,
) -> CallToolResult:
    """Return a text-only MCP tool result with optional structured metadata."""
    return CallToolResult(
        isError=False,
        content=[TextContent(type="text", text=text)],
        structuredContent=metadata,
    )


def image_tool_result(
    image_path: Path,
    metadata: dict[str, Any],
    *,
    text: str | None = None,
) -> CallToolResult:
    """Return path metadata and a viewable image content block."""
    path = image_path.resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Image artifact does not exist: {path}")
    mime_type = mimetypes.guess_type(path.name)[0] or "image/png"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return CallToolResult(
        isError=False,
        content=[
            TextContent(type="text", text=text or json.dumps(metadata, indent=2)),
            ImageContent(type="image", data=encoded, mimeType=mime_type),
        ],
        structuredContent=metadata,
    )
