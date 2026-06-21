"""Unit tests for the KiCad companion-plugin context helpers (issue #157)."""

from __future__ import annotations

import json
import urllib.request

import pytest

from kicad_mcp.companion.context import (
    BoardInfo,
    StudioContextClient,
    build_studio_context,
    requires_confirmation,
)


def test_build_studio_context_maps_fields() -> None:
    info = BoardInfo(
        file_name="/proj/board.kicad_pcb",
        file_type="pcb",
        project_root="/proj",
        project_file="/proj/board.kicad_pro",
        selected_reference="U3",
        selected_net="VBUS",
        cursor=(12.5, 34.0),
        drc_errors=("clearance", "unconnected"),
    )
    args = build_studio_context(info)
    assert args["active_file"] == "/proj/board.kicad_pcb"
    assert args["file_type"] == "pcb"
    assert args["selected_reference"] == "U3"
    assert args["selected_net"] == "VBUS"
    assert args["cursor_position"] == {"x": 12.5, "y": 34.0}
    assert args["drc_errors"] == ["clearance", "unconnected"]
    assert args["snapshot"] == {"projectRoot": "/proj", "projectFile": "/proj/board.kicad_pro"}


def test_build_studio_context_omits_empty_fields() -> None:
    args = build_studio_context(BoardInfo(file_name="x.kicad_sch", file_type="schematic"))
    assert args == {"file_type": "schematic", "active_file": "x.kicad_sch"}


def test_build_studio_context_normalizes_unknown_file_type() -> None:
    args = build_studio_context(BoardInfo(file_type="gerber"))
    assert args["file_type"] == "other"


def test_requires_confirmation() -> None:
    assert requires_confirmation("move_footprint") is True
    assert requires_confirmation("apply_patch") is True
    assert requires_confirmation("read_board") is False


def test_client_builds_jsonrpc_body() -> None:
    client = StudioContextClient()
    body = client.build_request_body({"file_type": "pcb"})
    assert body["method"] == "tools/call"
    assert body["params"]["name"] == "studio_push_context"
    assert body["params"]["arguments"] == {"file_type": "pcb"}


def test_client_builds_generic_tool_call_body() -> None:
    client = StudioContextClient()
    body = client.build_tool_call_body("sch_render_png", {"sheet": "Power"}, request_id=7)
    assert body["id"] == 7
    assert body["method"] == "tools/call"
    assert body["params"]["name"] == "sch_render_png"
    assert body["params"]["arguments"] == {"sheet": "Power"}


def test_client_rejects_non_loopback_url() -> None:
    with pytest.raises(ValueError, match="loopback"):
        StudioContextClient("https://example.com")


def test_client_push_posts_to_mcp_endpoint() -> None:
    captured: dict[str, object] = {}
    closed: list[bool] = []

    class _FakeResponse:
        def read(self) -> bytes:
            return json.dumps({"result": {"status": "ok"}}).encode("utf-8")

        def close(self) -> None:
            closed.append(True)

    def fake_opener(request: urllib.request.Request) -> _FakeResponse:
        captured["url"] = request.full_url
        captured["method"] = request.get_method()
        captured["body"] = json.loads(request.data.decode("utf-8"))  # type: ignore[union-attr]
        captured["auth"] = request.headers.get("Authorization")
        captured["accept"] = request.headers.get("Accept")
        return _FakeResponse()

    client = StudioContextClient(
        "http://127.0.0.1:9999",
        "/mcp",
        auth_token="secret",  # noqa: S106 - test fixture, not a real credential
        opener=fake_opener,
    )
    result = client.push({"file_type": "pcb", "active_file": "b.kicad_pcb"})

    assert result == {"result": {"status": "ok"}}
    assert captured["url"] == "http://127.0.0.1:9999/mcp"
    assert captured["method"] == "POST"
    assert captured["auth"] == "Bearer secret"
    # MCP Streamable HTTP rejects a JSON-only Accept header with HTTP 400.
    accept = str(captured["accept"])
    assert "application/json" in accept and "text/event-stream" in accept
    body = captured["body"]
    assert body["params"]["name"] == "studio_push_context"  # type: ignore[index]
    assert body["params"]["arguments"]["active_file"] == "b.kicad_pcb"  # type: ignore[index]
    assert closed == [True], "the HTTP response must be closed after reading"


def test_client_render_and_highlight_helpers_call_expected_tools() -> None:
    bodies: list[dict[str, object]] = []

    class _FakeResponse:
        def read(self) -> bytes:
            return json.dumps({"result": "ok"}).encode("utf-8")

        def close(self) -> None:
            pass

    def fake_opener(request: urllib.request.Request) -> _FakeResponse:
        bodies.append(json.loads(request.data.decode("utf-8")))  # type: ignore[union-attr]
        return _FakeResponse()

    client = StudioContextClient(opener=fake_opener)

    assert client.request_render_artifact(sheet="Power") == {"result": "ok"}
    assert client.request_highlight_net("VBUS") == {"result": "ok"}

    assert bodies[0]["params"]["name"] == "sch_render_png"  # type: ignore[index]
    assert bodies[0]["params"]["arguments"] == {"sheet": "Power"}  # type: ignore[index]
    assert bodies[1]["params"]["name"] == "pcb_highlight_net"  # type: ignore[index]
    assert bodies[1]["params"]["arguments"] == {"net_name": "VBUS"}  # type: ignore[index]
