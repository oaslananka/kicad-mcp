"""Hybrid bridge daemon — local-to-remote MCP proxy.

Allows remote clients (ChatGPT app, Claude.ai) to reach a local
kicad-mcp-pro server through a WebSocket tunnel.

Usage:
    kicad-mcp bridge start            # start with random pairing code
    kicad-mcp bridge start --port 9090 --code SECRET
    kicad-mcp bridge status           # check if bridge is running
    kicad-mcp bridge stop             # stop bridge
"""

from __future__ import annotations

import asyncio
import json
import os
import secrets
import signal
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import structlog
import typer

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Public API called by server.py
# ---------------------------------------------------------------------------


def bridge_start(port: int = 9090, code: str = "", daemon: bool = False) -> None:
    """Start the bridge daemon (entry point called from server.py)."""
    from .setup import _check_kicad_mcp_available

    pairing_code = code if code else _generate_pairing_code()
    state = BridgeState(
        pairing_code=pairing_code,
        port=port,
        target_url=f"http://127.0.0.1:{port}",
    )

    if daemon:
        _start_daemon(state)
        return

    typer.echo("\nKiCad MCP Bridge Daemon")
    typer.echo(f"  Port:         {port}")
    typer.echo(f"  Pairing Code: {pairing_code}")
    typer.echo(f"  Local MCP:    {'available' if _check_kicad_mcp_available() else 'not found'}")
    example = (
        f'{{"jsonrpc":"2.0","method":"bridge.pair","params":{{"code":"{pairing_code}"}},"id":1}}'
    )
    typer.echo(f"\n  To pair, send: {example}")
    typer.echo("\n  Press Ctrl+C to stop.\n")

    try:
        asyncio.run(_bridge_server(state))
    except KeyboardInterrupt:
        typer.echo("\nBridge stopped.")
    except Exception as exc:
        typer.echo(f"Bridge error: {exc}", err=True)
        raise typer.Exit(code=1) from exc


def bridge_status() -> None:
    """Check bridge status (entry point called from server.py)."""
    pid_path = _bridge_pid_path()
    if not pid_path.exists():
        typer.echo("Bridge is not running.")
        return
    pid = pid_path.read_text().strip()
    import socket

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2)
        s.connect(("127.0.0.1", DEFAULT_BRIDGE_PORT))
        s.close()
        typer.echo(f"Bridge is running (PID: {pid}, port: {DEFAULT_BRIDGE_PORT})")
    except (ConnectionRefusedError, OSError):
        typer.echo(f"PID file exists ({pid}) but bridge is not responding.")
        typer.echo("Run 'kicad-mcp bridge stop' to clean up.")


def bridge_stop() -> None:
    """Stop the bridge daemon (entry point called from server.py)."""
    pid_path = _bridge_pid_path()
    if not pid_path.exists():
        typer.echo("Bridge is not running.")
        return
    pid = pid_path.read_text().strip()
    try:
        os.kill(int(pid), signal.SIGTERM)
        pid_path.unlink(missing_ok=True)
        typer.echo(f"Bridge (PID: {pid}) stopped.")
    except ProcessLookupError:
        typer.echo(f"Process {pid} not found. Cleaning up PID file.")
        pid_path.unlink(missing_ok=True)
    except Exception as exc:
        typer.echo(f"Error stopping bridge: {exc}", err=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

DEFAULT_BRIDGE_PORT = 9090
BRIDGE_PID_FILE = "bridge.pid"


def _bridge_pid_path() -> Path:
    """Return path to the bridge PID file in the config directory."""
    import platform

    if platform.system() == "Windows":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif platform.system() == "Darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / "kicad-mcp-pro" / BRIDGE_PID_FILE


def _generate_pairing_code() -> str:
    """Generate a 6-character alphanumeric pairing code."""
    return secrets.token_hex(3).upper()


# ---------------------------------------------------------------------------
# Bridge State
# ---------------------------------------------------------------------------


@dataclass
class BridgeState:
    """Runtime state of the bridge daemon."""

    pairing_code: str
    port: int
    target_url: str
    paired: bool = False
    paired_at: float | None = None
    request_count: int = 0
    error_count: int = 0
    start_time: float = field(default_factory=time.time)
    _ws_server: Any = None

    @property
    def uptime_seconds(self) -> float:
        return time.time() - self.start_time

    def to_dict(self) -> dict[str, object]:
        return {
            "pairing_code": self.pairing_code,
            "port": self.port,
            "target_url": self.target_url,
            "paired": self.paired,
            "paired_at": self.paired_at,
            "request_count": self.request_count,
            "error_count": self.error_count,
            "uptime_seconds": int(self.uptime_seconds),
        }


# ---------------------------------------------------------------------------
# WebSocket Bridge Server
# ---------------------------------------------------------------------------


async def _bridge_server(state: BridgeState) -> None:
    """Run the bridge WebSocket server that proxies to kicad-mcp-pro."""

    # Uses asyncio TCP streams — no WebSocket library dependency needed.
    # Using Python's built-in asyncio for the server
    async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        """Handle a single bridge client connection."""
        peer = writer.get_extra_info("peername")
        logger.info("bridge_client_connected", peer=peer)

        try:
            while True:
                data = await asyncio.wait_for(reader.readline(), timeout=300.0)
                if not data:
                    break

                try:
                    message = json.loads(data.decode("utf-8").strip())
                except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                    logger.warning("bridge_invalid_json", error=str(exc))
                    state.error_count += 1
                    continue

                # Handle the message
                response = await _route_message(state, message)
                if response is not None:
                    writer.write((json.dumps(response) + "\n").encode("utf-8"))
                    await writer.drain()
        except TimeoutError:
            logger.info("bridge_client_timeout", peer=peer)
        except ConnectionResetError:
            logger.info("bridge_client_reset", peer=peer)
        except Exception as exc:
            logger.error("bridge_client_error", error=str(exc))
            state.error_count += 1
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception as close_err:
                logger.debug("bridge_client_close_error", error=str(close_err))
            logger.info("bridge_client_disconnected", peer=peer)

    server = await asyncio.start_server(handle_client, host="127.0.0.1", port=state.port)
    state._ws_server = server

    logger.info(
        "bridge_started",
        port=state.port,
        pairing_code=state.pairing_code,
        target=state.target_url,
    )

    async with server:
        await server.serve_forever()


async def _route_message(
    state: BridgeState, message: dict[str, object]
) -> dict[str, object] | None:
    """Route an incoming JSON-RPC message to the local kicad-mcp server."""
    state.request_count += 1
    method = message.get("method", "")
    msg_id = message.get("id")

    # --- Bridge control methods ---
    if method == "bridge.pair":
        params = message.get("params", {})
        code = params.get("code", "") if isinstance(params, dict) else ""
        if code == state.pairing_code:
            state.paired = True
            state.paired_at = time.time()
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {"status": "paired", "port": state.port},
            }
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "error": {"code": -32001, "message": "Invalid pairing code"},
        }

    if method == "bridge.status":
        return {"jsonrpc": "2.0", "id": msg_id, "result": state.to_dict()}

    if method == "bridge.ping":
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {"pong": True, "uptime": state.uptime_seconds},
        }

    # --- Require pairing for proxied methods ---
    if not state.paired:
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "error": {
                "code": -32002,
                "message": "Not paired. Send bridge.pair first.",
            },
        }

    # --- Proxy to local kicad-mcp ---
    return await _proxy_to_local(state, message, msg_id)


async def _proxy_to_local(
    state: BridgeState, message: dict[str, object], msg_id: object
) -> dict[str, object] | None:
    """Proxy a tool call to the local kicad-mcp-pro server."""
    import httpx

    method = message.get("method", "")
    params = message.get("params", {}) or {}

    # Build an MCP JSON-RPC call for the local server
    local_payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": method, "arguments": params},
    }

    try:
        async with httpx.AsyncClient(base_url=state.target_url, timeout=30.0) as client:
            resp = await client.post("/mcp", json=local_payload)
            resp.raise_for_status()
            result = resp.json()
            return {"jsonrpc": "2.0", "id": msg_id, "result": result.get("result", result)}
    except httpx.RequestError as exc:
        state.error_count += 1
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "error": {"code": -32003, "message": f"Bridge proxy error: {exc}"},
        }


# ---------------------------------------------------------------------------
# Daemon helper
# ---------------------------------------------------------------------------


def _start_daemon(state: BridgeState) -> None:
    """Fork the bridge process into the background."""
    pid = os.fork() if hasattr(os, "fork") else 0
    if pid == 0:
        # Child process
        sys.stdin.close()
        try:
            asyncio.run(_bridge_server(state))
        except Exception as exc:
            logger.error("bridge_daemon_crashed", error=str(exc))
            sys.exit(1)
    else:
        # Parent process
        pid_path = _bridge_pid_path()
        pid_path.parent.mkdir(parents=True, exist_ok=True)
        pid_path.write_text(str(pid))
        typer.echo(f"Bridge daemon started (PID: {pid}, port: {state.port})")
        typer.echo(f"Pairing code: {state.pairing_code}")
        typer.echo("To stop: kicad-mcp bridge stop")
