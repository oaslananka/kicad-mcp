"""Starlette app factories for the KiCad MCP Pro web dashboard."""

from __future__ import annotations

from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware

from .routes import web_routes


def create_app(*, debug: bool = False) -> Starlette:
    """Create the dashboard API app used by tests and standalone tooling."""
    app = Starlette(debug=debug, routes=web_routes)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:3334", "http://localhost:3334"],
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )
    return app


def create_test_app() -> Starlette:
    """Return a deterministic ASGI app for pytest/httpx route tests."""
    return create_app(debug=True)
