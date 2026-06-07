"""Server-Sent Events helpers for dashboard log streaming.

The route module owns subscriber registration for backward compatibility with
existing tests.  This module provides the spec-facing import surface:
``push_log(record)`` and ``log_event_stream(request)``.
"""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator

from starlette.requests import Request

from .routes import _sse_log_generator
from .routes import push_log as _push_log


def push_log(record: dict[str, object]) -> None:
    """Push a log record into the dashboard SSE stream."""
    level = str(record.get("level", "INFO"))
    event = str(record.get("event", record.get("message", "")))
    rest = {k: v for k, v in record.items() if k not in {"level", "event", "message"}}
    _push_log(level, event, **rest)


async def log_event_stream(request: Request) -> AsyncGenerator[bytes]:
    """Yield dashboard log events as SSE bytes."""
    async for event in _sse_log_generator():
        if await request.is_disconnected():
            break
        # Existing generator emits string SSE frames; normalize to bytes.
        if event.startswith("data: "):
            raw = event.removeprefix("data: ").strip()
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                payload = {"event": raw}
            yield f"event: log\ndata: {json.dumps(payload, default=str)}\n\n".encode()
        else:
            yield event.encode()
