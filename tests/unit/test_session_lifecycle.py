"""Unit tests for KiCadSession TTL caching, retry backoff, and error escalation."""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import pytest

from kicad_mcp.errors import (
    IpcDisconnectedError,
    KiCadConnectionTimeoutError,
)
from kicad_mcp.kicad.session import KiCadSession, SessionConfig


@dataclass
class FakeConfig:
    """Minimal SessionConfig for testing."""

    kicad_socket_path: Path | None = None
    kicad_token: str | None = None
    ipc_connection_timeout: float = 10.0
    ipc_retries: int = 2
    ipc_cache_ttl: float = 5.0


class _FakeClient:
    """A stub KiCad IPC client that can track connect/disconnect."""

    def __init__(self, *, fail_count: int = 0) -> None:
        self.fail_count = fail_count
        self._call_count = 0
        self.closed = False

    def close(self) -> None:
        self.closed = True


def _dummy_sleep(_: float) -> None:
    """No-op sleep for deterministic tests."""


def _make_session(
    *,
    client_factory: Callable[..., object] | None = None,
    config: SessionConfig | None = None,
    sleep: Callable[[float], None] = _dummy_sleep,
) -> KiCadSession:
    if client_factory is None:
        client_factory = _FakeClient
    cfg = config or FakeConfig()

    def _config_factory() -> SessionConfig:
        return cfg

    return KiCadSession(
        client_factory=client_factory,
        config_factory=_config_factory,
        sleep=sleep,
    )


# ---------------------------------------------------------------------------
# Basic connect / cached response
# ---------------------------------------------------------------------------


def test_connect_returns_client() -> None:
    session = _make_session()
    client = session.client()
    assert isinstance(client, _FakeClient)
    assert client.closed is False


def test_connect_is_cached_within_ttl() -> None:
    factory_call_count = 0

    def factory() -> _FakeClient:
        nonlocal factory_call_count
        factory_call_count += 1
        return _FakeClient()

    session = _make_session(client_factory=factory)
    c1 = session.client()
    c2 = session.client()
    assert c1 is c2  # same object
    assert factory_call_count == 1


def test_reset_clears_cache() -> None:
    session = _make_session()
    c1 = session.client()
    session.reset()
    c2 = session.client()
    assert c1 is not c2
    assert c1.closed is True  # closed by reset


# ---------------------------------------------------------------------------
# TTL expiry — cache reconnection
# ---------------------------------------------------------------------------


class _MonotonicClock:
    """Simulate time.monotonic() for deterministic TTL tests."""

    def __init__(self, start: float = 0.0) -> None:
        self._now = start

    def advance(self, delta: float) -> None:
        self._now += delta

    def __call__(self) -> float:
        return self._now


def test_ttl_expiry_triggers_reconnect() -> None:
    """When TTL expires the session must close and reconnect."""
    clock = _MonotonicClock()
    factory_call_count = 0

    def factory() -> _FakeClient:
        nonlocal factory_call_count
        factory_call_count += 1
        return _FakeClient()

    config = FakeConfig(ipc_cache_ttl=5.0)
    session = _make_session(client_factory=factory, config=config)

    # Override time.monotonic with clock
    setattr(session, "_last_connect_time", 0.0)  # ensure no time bias

    # First call connects
    with pytest.MonkeyPatch().context() as mp:
        mp.setattr(time, "monotonic", clock)
        c1 = session.client()
        assert factory_call_count == 1

        clock.advance(3.0)  # still within TTL
        session.client()
        assert factory_call_count == 1  # no new connect

        clock.advance(3.0)  # now past 5s TTL (total 6s)
        c2 = session.client()
        assert factory_call_count == 2  # triggered reconnect
        assert c1 is not c2
        assert c1.closed is True


# ---------------------------------------------------------------------------
# Retry backoff
# ---------------------------------------------------------------------------


def test_retry_success_after_transient_failures() -> None:
    """Factory fails N times then succeeds; retry must recover."""
    attempt_log: list[int] = []

    def factory() -> _FakeClient:
        attempt = len(attempt_log) + 1
        attempt_log.append(attempt)
        if attempt <= 2:  # first 2 calls fail
            raise ConnectionError("KiCad busy")
        return _FakeClient()

    session = _make_session(
        client_factory=factory,
        config=FakeConfig(ipc_retries=3),
    )
    client = session.client()
    assert isinstance(client, _FakeClient)
    assert len(attempt_log) == 3  # fail/fail/succeed


def test_retry_exhaustion_raises_ipc_disconnected() -> None:
    """All retries exhausted → IpcDisconnectedError."""
    attempt_log: list[int] = []

    def factory() -> _FakeClient:
        attempt_log.append(len(attempt_log) + 1)
        raise ConnectionError("KiCad not reachable")

    session = _make_session(
        client_factory=factory,
        config=FakeConfig(ipc_retries=2),
    )

    with pytest.raises(IpcDisconnectedError) as exc_info:
        session.client()

    assert "not reachable after multiple retries" in str(exc_info.value)
    assert exc_info.value.code == "IPC_DISCONNECTED"
    assert exc_info.value.retryable is True
    assert len(attempt_log) == 3  # initial + 2 retries


def test_timeout_error_raises_connection_timeout() -> None:
    """Error with 'timeout' in message → KiCadConnectionTimeoutError."""

    def factory() -> _FakeClient:
        raise TimeoutError("timed out")

    session = _make_session(
        client_factory=factory,
        config=FakeConfig(ipc_retries=1),
    )

    with pytest.raises(KiCadConnectionTimeoutError) as exc_info:
        session.client()

    assert exc_info.value.code == "KICAD_CONNECTION_TIMEOUT"
    assert exc_info.value.retryable is True


# ---------------------------------------------------------------------------
# Exponential backoff values
# ---------------------------------------------------------------------------


def test_backoff_sequence() -> None:
    """Sleep is called with expected exponential backoff durations."""
    sleeps: list[float] = []

    def recording_sleep(duration: float) -> None:
        sleeps.append(duration)

    def factory() -> _FakeClient:
        raise ConnectionError("fail")

    session = _make_session(
        client_factory=factory,
        config=FakeConfig(ipc_retries=3),
        sleep=recording_sleep,
    )

    with pytest.raises(IpcDisconnectedError):
        session.client()

    # Retries=3 → 3 backoff steps: 0.5, 1.0, 2.0 (capped)
    assert sleeps == [0.5, 1.0, 2.0], f"Expected [0.5, 1.0, 2.0] got {sleeps}"


# ---------------------------------------------------------------------------
# reconnect after reset
# ---------------------------------------------------------------------------


def test_reconnect_after_reset() -> None:
    session = _make_session()
    c1 = session.client()
    session.reset()
    c2 = session.client()
    assert c1 is not c2
    assert c1.closed is True
    assert c2.closed is False
