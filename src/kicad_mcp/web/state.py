"""Shared mutable state between server.py and web routes.

Centralises metrics, server handle, and start-time references so that
both the MCP server and the HTTP dashboard API endpoints share the same
in-memory state without circular imports.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from typing import Any

_METRICS_LOCK: threading.Lock = threading.Lock()
_TOOL_CALL_COUNTS: dict[tuple[str, str], int] = {}
_TOOL_LATENCIES_MS: dict[str, deque[float]] = {}
_server_start_time: float = time.time()
_server_handle: Any = None


def set_server_handle(handle: Any) -> None:  # noqa: ANN401
    """Store a reference to the active MCP server for tool discovery."""
    global _server_handle
    _server_handle = handle


def get_server_handle() -> Any:  # noqa: ANN401
    """Return the stored server handle (``_SyncServerHandle`` or ``KiCadFastMCP``)."""
    return _server_handle


def reset_start_time() -> None:
    """Reset the server start time (e.g. after a restart)."""
    global _server_start_time
    _server_start_time = time.time()


def get_start_time() -> float:
    """Return the monotonic server start timestamp."""
    return _server_start_time


def get_metrics_snapshot() -> dict[str, object]:
    """Return a JSON-safe snapshot of all tool metrics.

    Safe to call from any thread.
    """
    with _METRICS_LOCK:
        call_counts: dict[str, dict[str, int]] = {}
        for (tool, status), count in _TOOL_CALL_COUNTS.items():
            tool_entry = call_counts.setdefault(tool, {})
            tool_entry[status] = tool_entry.get(status, 0) + count

        latencies: dict[str, object] = {}
        for tool, samples in _TOOL_LATENCIES_MS.items():
            ordered = sorted(samples)
            latencies[tool] = {
                "count": len(samples),
                "p50": _percentile_from_sorted(ordered, 0.50),
                "p95": _percentile_from_sorted(ordered, 0.95),
                "p99": _percentile_from_sorted(ordered, 0.99),
                "min": ordered[0] if ordered else 0.0,
                "max": ordered[-1] if ordered else 0.0,
            }

    return {
        "call_counts": call_counts,
        "latencies_ms": latencies,
        "total_calls": sum(t.get("ok", 0) + t.get("error", 0) for t in call_counts.values()),
        "total_errors": sum(t.get("error", 0) for t in call_counts.values()),
    }


def reset_metrics() -> None:
    """Clear all tool call counters and latency samples.

    Used by tests to prevent cross-test pollution of module-level state.
    """
    global _TOOL_CALL_COUNTS, _TOOL_LATENCIES_MS  # noqa: PLW0603
    with _METRICS_LOCK:
        _TOOL_CALL_COUNTS.clear()
        _TOOL_LATENCIES_MS.clear()


def _percentile_from_sorted(ordered: list[float], percentile: float) -> float:
    if not ordered:
        return 0.0
    index = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * percentile))))
    return ordered[index]
