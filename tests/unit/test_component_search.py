from __future__ import annotations

import io

import pytest

from kicad_mcp.utils.component_search import (
    DEFAULT_USER_AGENT,
    ComponentRecord,
    DigiKeyClient,
    JLCSearchClient,
    NexarClient,
    RateLimiter,
    _plain_text_lines,
    _request_json,
    normalize_lcsc_code,
)


def test_normalize_lcsc_code_accepts_bare_digits() -> None:
    assert normalize_lcsc_code("25804") == "C25804"
    assert normalize_lcsc_code(25804) == "C25804"
    assert normalize_lcsc_code("C17414") == "C17414"


def test_jlcsearch_search_parses_component_records(monkeypatch) -> None:
    monkeypatch.setattr(
        "kicad_mcp.utils.component_search._request_json",
        lambda url, params: {
            "components": [
                {
                    "lcsc": 25804,
                    "mfr": "0603WAF1002T5E",
                    "package": "0603",
                    "description": "10k resistor",
                    "stock": 37165617,
                    "price": 0.000842857,
                    "is_basic": True,
                    "is_preferred": False,
                }
            ]
        },
    )

    result = JLCSearchClient().search("10k resistor")

    assert len(result) == 1
    assert result[0].lcsc_code == "C25804"
    assert result[0].mpn == "0603WAF1002T5E"
    assert result[0].is_basic is True


def test_jlcsearch_get_part_prefers_exact_lcsc_match(monkeypatch) -> None:
    records = [
        ComponentRecord(
            source="jlcsearch",
            lcsc_code="C17414",
            mpn="0805W8F1002T5E",
            package="0805",
            description="10k resistor",
            stock=100,
            price=0.0016,
            is_basic=True,
            is_preferred=False,
        ),
        ComponentRecord(
            source="jlcsearch",
            lcsc_code="C25804",
            mpn="0603WAF1002T5E",
            package="0603",
            description="10k resistor",
            stock=100,
            price=0.0008,
            is_basic=True,
            is_preferred=False,
        ),
    ]
    monkeypatch.setattr(
        "kicad_mcp.utils.component_search.JLCSearchClient.search",
        lambda self, keyword, **kwargs: records,
    )
    monkeypatch.setattr(
        "kicad_mcp.utils.component_search.JLCSearchClient._search_jlcpcb_public",
        lambda self, keyword, *, limit: [],
    )

    part = JLCSearchClient().get_part("25804")

    assert part is not None
    assert part.lcsc_code == "C25804"


def test_request_json_rejects_non_https_urls() -> None:
    with pytest.raises(ValueError, match="Only https"):
        _request_json("http://example.com/search", {"q": "10k"})


def test_request_json_builds_expected_request(monkeypatch) -> None:
    seen: dict[str, object] = {}

    class FakeResponse(io.StringIO):
        def __enter__(self) -> FakeResponse:
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            _ = (exc_type, exc, tb)

    def fake_urlopen(request, timeout: int):
        seen["url"] = request.full_url
        seen["user_agent"] = request.headers["User-agent"]
        seen["timeout"] = timeout
        return FakeResponse('{"components": []}')

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    payload = _request_json("https://example.com/search", {"q": "10k", "limit": 5, "empty": ""})

    assert payload == {"components": []}
    assert seen["url"] == "https://example.com/search?q=10k&limit=5"
    assert seen["user_agent"] == DEFAULT_USER_AGENT
    assert seen["timeout"] == 20


def test_jlcsearch_get_part_falls_back_to_exact_mpn_only(monkeypatch) -> None:
    records = [
        ComponentRecord(
            source="jlcsearch",
            lcsc_code="C11111",
            mpn="ABC-123",
            package="SOT-23",
            description="driver",
            stock=5,
            price=None,
            is_basic=False,
            is_preferred=False,
        ),
        ComponentRecord(
            source="jlcsearch",
            lcsc_code="C22222",
            mpn="XYZ-999",
            package="SOT-23",
            description="driver",
            stock=5,
            price=None,
            is_basic=False,
            is_preferred=False,
        ),
    ]
    monkeypatch.setattr(
        "kicad_mcp.utils.component_search.JLCSearchClient.search",
        lambda self, keyword, **kwargs: records,
    )
    monkeypatch.setattr(
        "kicad_mcp.utils.component_search.JLCSearchClient._search_jlcpcb_public",
        lambda self, keyword, *, limit: [],
    )

    assert JLCSearchClient().get_part("abc-123").mpn == "ABC-123"
    assert JLCSearchClient().get_part("unmatched") is None

    monkeypatch.setattr(
        "kicad_mcp.utils.component_search.JLCSearchClient.search",
        lambda self, keyword, **kwargs: [],
    )
    assert JLCSearchClient().get_part("unmatched") is None


def test_jlcsearch_public_detail_fallback_parses_extended_lcsc_code(monkeypatch) -> None:
    monkeypatch.setattr(
        "kicad_mcp.utils.component_search._request_json",
        lambda _url, _params: {"components": []},
    )

    html = """
    <html><head><title>SSI2164 | JLCPCB Assembly | New Arrivals | JLCPCB</title></head>
    <body>
    <h1>SSI2164</h1><p>Extended</p>
    <div>MFR.Part #</div><div>SSI2164</div>
    <div>JLCPCB Part #</div><div>C9900088938</div>
    <div>Package</div><div>SOIC-16</div>
    <div>Description</div><div>SOIC-16 New Arrivals ROHS</div>
    <div>In Stock: 0</div><div>1+ $0.0365</div>
    </body></html>
    """
    monkeypatch.setattr(
        "kicad_mcp.utils.component_search.JLCSearchClient._request_text",
        lambda self, url, params=None: html,
    )

    part = JLCSearchClient().get_part("C9900088938")

    assert part is not None
    assert part.lcsc_code == "C9900088938"
    assert part.mpn == "SSI2164"
    assert part.package == "SOIC-16"
    assert part.is_basic is False


def test_plain_text_lines_ignores_script_tags_with_spaced_end_tags() -> None:
    lines = _plain_text_lines(
        """
        <html>
          <script>dangerousText()</script >
          <style>.hidden { color: red; }</style >
          <body><h1>SSI2164</h1><p>C9900088938</p></body>
        </html>
        """
    )

    assert "SSI2164" in lines
    assert "C9900088938" in lines
    assert all("dangerousText" not in line for line in lines)
    assert all("hidden" not in line for line in lines)


def test_optional_search_clients_raise_clear_messages(monkeypatch) -> None:
    monkeypatch.delenv("NEXAR_CLIENT_ID", raising=False)
    monkeypatch.delenv("NEXAR_CLIENT_SECRET", raising=False)
    with pytest.raises(RuntimeError, match="NEXAR_CLIENT_ID"):
        NexarClient().search("accelerometer")
    with pytest.raises(RuntimeError, match="NEXAR_CLIENT_ID"):
        NexarClient().get_part("C12345")

    monkeypatch.delenv("DIGIKEY_CLIENT_ID", raising=False)
    monkeypatch.delenv("DIGIKEY_CLIENT_SECRET", raising=False)
    with pytest.raises(RuntimeError, match="DIGIKEY_CLIENT_ID"):
        DigiKeyClient().search("buzzer")
    with pytest.raises(RuntimeError, match="detail lookups require authenticated deployment"):
        DigiKeyClient().get_part("C12345")


class _FakeNexarTransport:
    """Scripted OAuth + GraphQL transport for hermetic NexarClient tests."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def __call__(self, url: str, body: bytes, headers: dict[str, str]) -> dict[str, object]:
        self.calls.append(url)
        if url.endswith("/connect/token"):
            assert b"client_credentials" in body
            return {"access_token": "tok-123", "expires_in": 3600}
        assert headers.get("Authorization") == "Bearer tok-123"
        return {
            "data": {
                "supSearchMpn": {
                    "results": [
                        {
                            "part": {
                                "mpn": "STM32F103C8T6",
                                "manufacturer": {"name": "STMicroelectronics"},
                                "shortDescription": "ARM Cortex-M3 MCU",
                                "totalAvail": 4200,
                                "medianPrice1000": {"price": 1.83},
                                "specs": [
                                    {
                                        "attribute": {"name": "Case/Package"},
                                        "displayValue": "LQFP-48",
                                    }
                                ],
                            }
                        }
                    ]
                }
            }
        }


def test_nexar_search_parses_records_with_injected_transport() -> None:
    transport = _FakeNexarTransport()
    client = NexarClient(client_id="id", client_secret="secret", transport=transport)  # noqa: S106
    records = client.search("STM32F103", limit=5)

    assert len(records) == 1
    record = records[0]
    assert record.source == "nexar"
    assert record.mpn == "STM32F103C8T6"
    assert record.package == "LQFP-48"
    assert record.stock == 4200
    assert record.price == 1.83
    # OAuth token fetched, then the GraphQL query issued.
    assert transport.calls[0].endswith("/connect/token")
    assert transport.calls[1].endswith("/graphql")


def test_nexar_token_is_cached_across_searches() -> None:
    transport = _FakeNexarTransport()
    client = NexarClient(client_id="id", client_secret="secret", transport=transport)  # noqa: S106
    client.search("a")
    client.search("b")
    # One token call, two graphql calls — the token is reused, not re-fetched.
    assert transport.calls.count("https://identity.nexar.com/connect/token") == 1
    assert transport.calls.count("https://api.nexar.com/graphql") == 2


def test_nexar_graphql_errors_surface_as_runtime_error() -> None:
    def transport(url: str, body: bytes, headers: dict[str, str]) -> dict[str, object]:
        if url.endswith("/connect/token"):
            return {"access_token": "t", "expires_in": 3600}
        return {"errors": [{"message": "rate limit exceeded"}]}

    client = NexarClient(client_id="id", client_secret="secret", transport=transport)  # noqa: S106
    with pytest.raises(RuntimeError, match="Nexar GraphQL error: rate limit exceeded"):
        client.search("anything")


def test_rate_limiter_waits_when_window_is_full(monkeypatch) -> None:
    timeline = iter([0.0, 0.0, 0.1, 0.1, 0.2, 1.3, 1.3])
    slept: list[float] = []

    monkeypatch.setattr("kicad_mcp.utils.component_search.time.monotonic", lambda: next(timeline))
    monkeypatch.setattr("kicad_mcp.utils.component_search.time.sleep", slept.append)

    limiter = RateLimiter(max_calls=2, period_seconds=1.0)
    limiter.acquire()
    limiter.acquire()
    limiter.acquire()

    assert slept and slept[0] > 0.0
