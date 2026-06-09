# MCP Transport

kicad-mcp-pro supports local MCP workflows through stdio and Streamable HTTP. The extension uses
the transport configured in its MCP profile and validates server-info before calling tools.

## Streamable HTTP

Use Streamable HTTP when a client needs a stable local endpoint, session handling, bearer-token
authentication, or integration with ChatGPT-style connectors.

```bash
uv run --project packages/mcp-server --all-extras kicad-mcp-pro --transport streamable-http --host 127.0.0.1 --port 3334
```

The default MCP path is `/mcp`. Set `KICAD_MCP_MOUNT_PATH` when a client or
reverse proxy requires a different endpoint such as `/custom-mcp`.

Clients must send each JSON-RPC request, response, or notification as a new
HTTP `POST` request to the configured endpoint. Every Streamable HTTP request
must include `Accept: application/json, text/event-stream` and JSON requests
must include `Content-Type: application/json`.

After `initialize`, clients must include `MCP-Protocol-Version: 2025-11-25` on
follow-up requests. Stateful deployments also return `MCP-Session-Id` from
`initialize`; clients must echo that value on `notifications/initialized`,
`tools/list`, `tools/call`, and later requests. Missing stateful session IDs
return HTTP 400 with a structured JSON-RPC error, and unknown session IDs return
HTTP 404 with a structured JSON-RPC error.

The default local mode is stateless Streamable HTTP. This allows ChatGPT-style
connectors to initialize, send `notifications/initialized`, list tools, and call
tools without a session-header injection proxy. Set `KICAD_MCP_STATEFUL_HTTP=1`
only when the deployment needs server-side HTTP session tracking.

Deprecated HTTP+SSE routes are disabled by default. Set
`KICAD_MCP_LEGACY_SSE=1` only for old clients that cannot speak Streamable HTTP;
the compatibility routes are exposed alongside `/mcp` as `/sse` and
`/messages`.

Transport conformance coverage lives in
`packages/mcp-server/tests/unit/test_mcp_protocol_contract.py` and runs through:

```bash
corepack pnpm run test:contract
```

## stdio

Use stdio when the MCP client launches the server process directly and keeps it bound to the local
client session.

```bash
uv run --project packages/mcp-server --all-extras kicad-mcp-pro --transport stdio
```

## Compatibility

Protocol and capability expectations are generated in [MCP API reference](api-reference.md). Runtime
support boundaries are tracked in the [runtime matrix](../status/runtime-matrix.md).
