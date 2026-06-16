"""Bridge daemon rate-limiting (work order P5-T5, threat model K8).

The bridge previously processed unbounded inbound messages, leaving the 24-bit
pairing code open to brute force and the proxy open to floods. These tests pin the
token-bucket budget and the pairing throttle.
"""

from __future__ import annotations

import asyncio

from kicad_mcp.bridge import (
    RATE_LIMIT_ERROR_CODE,
    BridgeState,
    TokenBucket,
    _route_message,
)


class _Clock:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t

    def advance(self, delta: float) -> None:
        self.t += delta


def _state(**overrides: object) -> BridgeState:
    state = BridgeState(pairing_code="ABC123", port=9090, target_url="http://127.0.0.1:9090")
    for key, value in overrides.items():
        setattr(state, key, value)
    return state


def test_token_bucket_allows_burst_then_refills() -> None:
    clock = _Clock()
    bucket = TokenBucket(capacity=3, refill_per_second=1.0, time_fn=clock)
    assert [bucket.allow() for _ in range(3)] == [True, True, True]
    assert bucket.allow() is False  # burst exhausted
    clock.advance(2.0)  # refill two tokens
    assert bucket.allow() is True
    assert bucket.allow() is True
    assert bucket.allow() is False


def test_route_message_enforces_general_rate_limit() -> None:
    clock = _Clock()
    state = _state(rate_limiter=TokenBucket(capacity=2, refill_per_second=0.0, time_fn=clock))

    first = asyncio.run(_route_message(state, {"method": "bridge.ping", "id": 1}))
    second = asyncio.run(_route_message(state, {"method": "bridge.ping", "id": 2}))
    blocked = asyncio.run(_route_message(state, {"method": "bridge.ping", "id": 3}))

    assert first is not None and first["result"]["pong"] is True  # type: ignore[index]
    assert second is not None
    assert blocked is not None and blocked["error"]["code"] == RATE_LIMIT_ERROR_CODE  # type: ignore[index]
    assert state.rate_limited_count == 1
    assert state.request_count == 2  # blocked request is not counted as served


def test_pairing_brute_force_is_throttled() -> None:
    clock = _Clock()
    state = _state(
        rate_limiter=TokenBucket(capacity=1000, refill_per_second=0.0, time_fn=clock),
        pair_limiter=TokenBucket(capacity=3, refill_per_second=0.0, time_fn=clock),
    )

    for i in range(3):
        resp = asyncio.run(
            _route_message(state, {"method": "bridge.pair", "id": i, "params": {"code": "WRONG"}})
        )
        assert resp is not None and resp["error"]["message"] == "Invalid pairing code"  # type: ignore[index]

    throttled = asyncio.run(
        _route_message(state, {"method": "bridge.pair", "id": 99, "params": {"code": "WRONG"}})
    )
    assert throttled is not None
    assert throttled["error"]["code"] == RATE_LIMIT_ERROR_CODE  # type: ignore[index]
    assert state.paired is False
