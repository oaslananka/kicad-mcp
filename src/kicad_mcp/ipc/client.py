"""Thin KiCad IPC client wrapper around the repository session adapter."""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

from ..connection import get_board, get_kicad
from ..errors import KiCadMcpError
from .errors import KiCadIpcUnavailableError

ClientFactory = Callable[[], object]
BoardFactory = Callable[[], object]


class KiCadIpcClient:
    """Expose small, stable operations used by capability discovery and live tools."""

    def __init__(
        self,
        *,
        client_factory: ClientFactory = get_kicad,
        board_factory: BoardFactory = get_board,
    ) -> None:
        self._client_factory = client_factory
        self._board_factory = board_factory

    def connect(self) -> object:
        """Return the active KiCad IPC client."""
        return self._client_factory()

    def probe(self) -> dict[str, object]:
        """Probe the running KiCad IPC API without exposing credentials."""
        try:
            client = self.connect()
            version = _call_optional(client, "get_version")
            api_version = _call_optional(client, "get_api_version")
            ping = getattr(client, "ping", None)
            if callable(ping):
                ping()
        except KiCadIpcUnavailableError:
            raise
        except KiCadMcpError as exc:
            raise KiCadIpcUnavailableError(_first_line(exc)) from exc
        except Exception as exc:
            raise KiCadIpcUnavailableError(
                f"Failed to connect to KiCad IPC: {_first_line(exc)}"
            ) from exc
        return {
            "connected": True,
            "version": _stringify_version(version),
            "apiVersion": _stringify_version(api_version),
        }

    def board(self) -> object:
        """Return the active board object from KiCad."""
        return self._board_factory()

    def has_open_schematic(self) -> bool:
        """Return whether KiCad reports an open schematic document through IPC."""
        client = self.connect()
        get_open_documents = getattr(client, "get_open_documents", None)
        if not callable(get_open_documents):
            return False
        try:
            from kipy.proto.common import types as common_types
        except Exception as exc:  # pragma: no cover - optional kipy boundary
            raise KiCadIpcUnavailableError(
                "KiCad IPC document type bindings are unavailable."
            ) from exc
        try:
            return bool(get_open_documents(common_types.DOCTYPE_SCHEMATIC))
        except Exception:
            return False


def _call_optional(client: object, method_name: str) -> object | None:
    method = getattr(client, method_name, None)
    if not callable(method):
        return None
    return cast(object | None, method())


def _stringify_version(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    major = getattr(value, "major", None)
    minor = getattr(value, "minor", None)
    patch = getattr(value, "patch", None)
    if isinstance(major, int):
        if isinstance(minor, int) and isinstance(patch, int):
            return f"{major}.{minor}.{patch}"
        if isinstance(minor, int):
            return f"{major}.{minor}"
        return str(major)
    return str(value)


def _first_line(exc: BaseException) -> str:
    return str(exc).splitlines()[0] or exc.__class__.__name__
