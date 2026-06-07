# KiCad MCP Pro

[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/oaslananka/kicad-mcp)
[![PyPI - Version](https://img.shields.io/pypi/v/kicad-mcp-pro)](https://pypi.org/project/kicad-mcp-pro/)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/kicad-mcp-pro)](https://pypi.org/project/kicad-mcp-pro/)
[![npm - Version](https://img.shields.io/npm/v/kicad-mcp-pro)](https://www.npmjs.com/package/kicad-mcp-pro)
[![CI](https://github.com/oaslananka/kicad-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/oaslananka/kicad-mcp/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/oaslananka/kicad-mcp/badge)](https://securityscorecards.dev/viewer/?uri=github.com/oaslananka/kicad-mcp)

<!-- mcp-name: io.github.oaslananka/kicad-mcp-pro -->

Canonical repository: https://github.com/oaslananka/kicad-mcp

- PyPI: `kicad-mcp-pro`
- npm wrapper: `kicad-mcp-pro`
- MCP Registry name: `io.github.oaslananka/kicad-mcp-pro`
- Version: `3.8.0`

KiCad MCP Pro is a Model Context Protocol server for KiCad EDA workflows. It exposes tools, resources, and prompts for schematic, PCB, validation, DFM, and manufacturing export automation.

Telemetry and error reporting are disabled by default. Opt-in OpenTelemetry
configuration and privacy rules are documented in
[`docs/configuration.md`](docs/configuration.md#opentelemetry) in [`docs/telemetry.md`](docs/telemetry.md).

## Quick Start

### Desktop App

Download the latest installer from the
[GitHub releases page](https://github.com/oaslananka/kicad-mcp/releases/latest).
The Tauri desktop app starts the Python dashboard server automatically and opens
the GUI at `http://127.0.0.1:3334/ui`.

### CLI

```bash
uvx kicad-mcp-pro init
uvx kicad-mcp-pro tray
uvx kicad-mcp-pro dashboard --open
uvx kicad-mcp-pro --transport streamable-http --port 3334
```

### Web Dashboard

```bash
uvx kicad-mcp-pro dashboard --host 127.0.0.1 --port 3334 --open
# http://127.0.0.1:3334/ui
```

## Transports

KiCad MCP Pro supports `stdio` and Streamable HTTP. Streamable HTTP is served at
`/mcp` by default and can be moved with `KICAD_MCP_MOUNT_PATH`.

```bash
uvx kicad-mcp-pro@3.8.0 --transport streamable-http --host 127.0.0.1 --port 3334
```

Streamable HTTP clients must send:

- `Accept: application/json, text/event-stream`
- `Content-Type: application/json`
- `MCP-Protocol-Version: 2025-11-25` after initialization
- `MCP-Session-Id` on follow-up requests when `KICAD_MCP_STATEFUL_HTTP=1`

By default Streamable HTTP is stateless, so ChatGPT-style connectors can
initialize and call `tools/list` without a session-header injection proxy. Set
`KICAD_MCP_STATEFUL_HTTP=1` to require session IDs after `initialize`.

The deprecated HTTP+SSE fallback routes are disabled by default. Set
`KICAD_MCP_LEGACY_SSE=1` only for older clients that cannot use Streamable HTTP.

## Install

```bash
corepack pnpm run dev:doctor -- --ci
uvx kicad-mcp-pro@3.8.0 --help
npx kicad-mcp-pro@3.8.0 --help
```

For source checkouts, `corepack pnpm run dev:doctor` validates Node, pnpm,
Python, uv, MCP server CLI startup/version reporting, fixture corpus, protocol
schemas, common development ports, and optional Cloudflare tunnel tooling.

## Package Metadata

The canonical metadata source of truth is `server.json`, which defines the MCP server contract. It is synchronized with `pyproject.toml` and verified in CI via `pnpm run metadata:check`.
