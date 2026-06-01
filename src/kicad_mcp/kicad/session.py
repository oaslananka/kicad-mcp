"""Central KiCad IPC session adapter."""

from __future__ import annotations

import inspect
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Protocol, TypedDict

from ..errors import KiCadBoardNotOpenError, KiCadConnectionTimeoutError, KiCadNotRunningError


class LoggerLike(Protocol):
    """Small logging protocol used to avoid binding to a concrete logger type."""

    def debug(self, event: str, **kwargs: object) -> None:
        """Emit debug information."""

    def warning(self, event: str, **kwargs: object) -> None:
        """Emit warning information."""


class KiCadKwargs(TypedDict, total=False):
    """Keyword arguments supported by known kipy.KiCad constructors."""

    socket_path: str
    kicad_token: str
    client_name: str
    timeout_ms: int


KiCadClientFactory = Callable[..., object]


class SessionConfig(Protocol):
    """Configuration fields used by the session adapter."""

    kicad_socket_path: Path | None
    kicad_token: str | None
    ipc_connection_timeout: float
    ipc_retries: int


ConfigFactory = Callable[[], SessionConfig]
_BUSY_PATTERNS = (
    "busy",
    "cannot respond",
    "modal",
    "temporarily unavailable",
    "try again",
)


def _default_config() -> SessionConfig:
    from ..config import get_config

    return get_config()


def _is_busy_error(message: str) -> bool:
    lowered = message.casefold()
    return any(pattern in lowered for pattern in _BUSY_PATTERNS)


class KiCadSession:
    """Thread-safe lazy KiCad IPC session."""

    def __init__(
        self,
        *,
        client_factory: KiCadClientFactory,
        config_factory: ConfigFactory = _default_config,
        logger: LoggerLike | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._client_factory = client_factory
        self._config_factory = config_factory
        self._logger = logger
        self._sleep = sleep
        self._lock = threading.RLock()
        self._client: object | None = None

    def reset(self) -> None:
        """Close and clear the cached client."""
        with self._lock:
            if self._client is not None:
                close_fn = getattr(self._client, "close", None)
                if callable(close_fn):
                    try:
                        close_fn()
                    except Exception as exc:  # pragma: no cover - defensive cleanup
                        if self._logger is not None:
                            self._logger.debug("kicad_close_failed", error=str(exc))
            self._client = None

    def _constructor_params(self) -> set[str]:
        signature_target = getattr(self._client_factory, "__init__", self._client_factory)
        try:
            return set(inspect.signature(signature_target).parameters.keys()) - {"self"}
        except (TypeError, ValueError):
            return set()

    def build_kwargs(self) -> KiCadKwargs:
        """Build only the kwargs accepted by the active KiCad client factory."""
        cfg = self._config_factory()
        available = self._constructor_params()
        kwargs: KiCadKwargs = {}

        if "socket_path" in available and cfg.kicad_socket_path is not None:
            kwargs["socket_path"] = str(cfg.kicad_socket_path)
        if "kicad_token" in available and cfg.kicad_token is not None:
            kwargs["kicad_token"] = cfg.kicad_token
        if "client_name" in available:
            kwargs["client_name"] = "kicad-mcp"
        if "timeout_ms" in available:
            kwargs["timeout_ms"] = int(cfg.ipc_connection_timeout * 1000)
        return kwargs

    def client(self) -> object:
        """Return a connected KiCad client, retrying transient startup failures."""
        with self._lock:
            if self._client is not None:
                return self._client

            cfg = self._config_factory()
            attempts = max(1, cfg.ipc_retries + 1)
            kwargs = self.build_kwargs()
            last_error: BaseException | None = None
            for attempt in range(1, attempts + 1):
                if self._logger is not None:
                    self._logger.debug(
                        "kicad_connect",
                        attempt=attempt,
                        attempts=attempts,
                        kwargs=list(kwargs.keys()),
                    )
                try:
                    self._client = self._client_factory(**kwargs)
                    return self._client
                except Exception as exc:
                    last_error = exc
                    if self._logger is not None:
                        self._logger.warning(
                            "kicad_connect_failed",
                            attempt=attempt,
                            attempts=attempts,
                            error=str(exc),
                            socket_path=str(cfg.kicad_socket_path)
                            if cfg.kicad_socket_path
                            else None,
                        )
                    if attempt < attempts:
                        self._sleep(min(0.2 * attempt, 1.0))

            message = str(last_error or "KiCad IPC connection failed")
            if "timeout" in message.casefold() or "timed out" in message.casefold():
                raise KiCadConnectionTimeoutError(
                    "Could not connect to KiCad IPC API before the configured timeout."
                ) from last_error
            raise KiCadNotRunningError(
                "Could not connect to KiCad IPC API. Make sure KiCad is running and "
                "the IPC API server is enabled."
            ) from last_error

    def board(self) -> object:
        """Return the active KiCad board."""
        cfg = self._config_factory()
        attempts = max(1, cfg.ipc_retries + 1)
        last_error: BaseException | None = None
        try:
            client = self.client()
        except KiCadNotRunningError:
            raise
        get_board = getattr(client, "get_board", None)
        if not callable(get_board):
            raise KiCadBoardNotOpenError("KiCad client does not expose get_board().")

        for attempt in range(1, attempts + 1):
            try:
                return get_board()
            except Exception as exc:
                last_error = exc
                message = str(exc)
                if self._logger is not None:
                    self._logger.warning(
                        "kicad_get_board_failed",
                        attempt=attempt,
                        attempts=attempts,
                        error=message,
                    )
                if not _is_busy_error(message) or attempt >= attempts:
                    break
                self._sleep(min(0.2 * attempt, 1.0))

        message = str(last_error or "")
        if _is_busy_error(message):
            raise KiCadBoardNotOpenError(
                "KiCad GUI appears to be busy or modal and cannot respond to IPC requests "
                "right now. Try again, close any open KiCad dialog, or finish/save the "
                "current GUI operation before retrying."
            ) from last_error
        raise KiCadBoardNotOpenError(
            "KiCad IPC is reachable, but no PCB is open in the active KiCad session."
        ) from last_error

    def probe(self) -> dict[str, object]:
        """Return a small capability probe without leaking secrets."""
        client = self.client()
        get_version = getattr(client, "get_version", None)
        version = get_version() if callable(get_version) else None
        return {"connected": True, "version": version}
