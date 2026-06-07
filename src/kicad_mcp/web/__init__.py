"""Web dashboard and API module for KiCad MCP Pro."""

from __future__ import annotations

from .app import create_app, create_test_app
from .events import log_event_stream, push_log
from .routes import router, setup_log_stream

__all__ = [
    "create_app",
    "create_test_app",
    "log_event_stream",
    "push_log",
    "router",
    "setup_log_stream",
]
