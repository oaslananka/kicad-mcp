"""KiCad MCP Pro server entrypoint."""
# mypy: disable-error-code=untyped-decorator

from __future__ import annotations

import asyncio
import contextlib
import inspect
import io
import json
import os
import secrets
import sys
import threading
import time
from collections import deque
from collections.abc import Callable, Iterable, Iterator
from pathlib import Path
from typing import Any, TextIO, cast

import anyio
import click
import structlog
import typer
from mcp import types as mcp_types
from mcp.server.auth.provider import AccessToken
from mcp.server.auth.settings import AuthSettings
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.server.lowlevel.helper_types import ReadResourceContents
from mcp.types import Icon, ToolAnnotations
from pydantic import AnyUrl
from starlette.applications import Starlette
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse, Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send
from typer.models import OptionInfo

from . import __version__
from .capabilities import AccessTier, RuntimeRequirement, all_protocol_metadata
from .capabilities import get as get_capability_record
from .compatibility import MCP_PROTOCOL_VERSION
from .config import LOOPBACK_HOSTS, KiCadMCPConfig, get_config, reset_config
from .connection import KiCadConnectionError, get_board
from .diagnostics import (
    DiagnosticReport,
    build_doctor_report,
    build_health_report,
    diagnostic_report_json,
    write_diagnostic_bundle,
)
from .discovery import ensure_studio_project_watcher, find_kicad_version
from .i18n import SERVER_DESCRIPTION, localize, option_help
from .ipc.capabilities import KiCadIpcCapabilityState, get_ipc_capability_state
from .operating_modes import (
    OperatingMode,
    active_operating_mode,
    denial_message,
    filter_tools_for_mode,
    is_tool_allowed_in_mode,
)
from .tools import router
from .tools.fixers import validate_callable_imports
from .tools.metadata import get_tool_metadata, infer_tool_annotations
from .tools.router import EXPERIMENTAL_TOOL_NAMES, available_profiles, categories_for_profile
from .utils import telemetry as otel
from .utils.logging import setup_logging
from .wellknown import get_wellknown_metadata

logger = structlog.get_logger(__name__)
app = typer.Typer(help=localize(SERVER_DESCRIPTION))
tools_app = typer.Typer(help=localize("Inspect registered MCP tools."))
mcp_config_app = typer.Typer(help=localize("Generate MCP client configuration snippets."))
app.add_typer(tools_app, name="tools")
app.add_typer(mcp_config_app, name="mcp-config")
DOCTOR_BUNDLE_OPTION = cast(
    Path | None,
    typer.Option(
        None,
        "--bundle",
        file_okay=True,
        dir_okay=False,
        writable=True,
        resolve_path=True,
        help=option_help("Write a redacted diagnostic zip bundle to this path."),
    ),
)
AnyFunction = Callable[..., object]


class _ThreadAwareStdout:
    """Route stdout writes by thread while preserving protocol stdout for stdio."""

    def __init__(self, default: TextIO) -> None:
        """Store the default stream used by threads without an override."""
        self._default = default
        self._targets: dict[int, TextIO] = {}
        self._lock = threading.Lock()

    @contextlib.contextmanager
    def redirected_current_thread(self, target: TextIO) -> Iterator[None]:
        """Temporarily route only the current thread to a different stream."""
        thread_id = threading.get_ident()
        with self._lock:
            self._targets[thread_id] = target
        try:
            yield
        finally:
            with self._lock:
                self._targets.pop(thread_id, None)

    def _target(self) -> TextIO:
        """Return the active stream for the calling thread."""
        with self._lock:
            return self._targets.get(threading.get_ident(), self._default)

    def write(self, text: str) -> int:
        """Write text to the calling thread's active stream."""
        return self._target().write(text)

    def flush(self) -> None:
        """Flush the calling thread's active stream."""
        self._target().flush()

    def isatty(self) -> bool:
        """Return whether the calling thread's active stream is a TTY."""
        return self._target().isatty()

    def fileno(self) -> int:
        """Return the file descriptor for the calling thread's active stream."""
        return self._target().fileno()

    def __getattr__(self, name: str) -> object:
        """Delegate stream attributes such as encoding to the default stream."""
        return getattr(self._default, name)


def _ensure_thread_aware_stdout() -> _ThreadAwareStdout:
    """Install a thread-aware stdout proxy if one is not already active."""
    if isinstance(sys.stdout, _ThreadAwareStdout):
        return sys.stdout
    proxy = _ThreadAwareStdout(sys.stdout)
    sys.stdout = cast(TextIO, proxy)
    return proxy


@contextlib.contextmanager
def _redirect_current_thread_stdout_to_stderr() -> Iterator[None]:
    """Route stdout writes from the current thread to stderr."""
    stdout = sys.stdout
    if isinstance(stdout, _ThreadAwareStdout):
        with stdout.redirected_current_thread(sys.stderr):
            yield
        return
    with contextlib.redirect_stdout(sys.stderr):
        yield


HEAVY_TOOL_NAMES: frozenset[str] = frozenset(
    {
        "run_drc",
        "run_erc",
        "validate_design",
        "schematic_quality_gate",
        "schematic_connectivity_gate",
        "pcb_quality_gate",
        "pcb_placement_quality_gate",
        "pcb_transfer_quality_gate",
        "manufacturing_quality_gate",
        "project_quality_gate",
        "project_quality_gate_report",
        "project_auto_fix_loop",
        "project_full_validation_loop",
        "check_design_for_manufacture",
        "export_gerber",
        "export_drill",
        "export_bom",
        "export_netlist",
        "export_spice_netlist",
        "export_pcb_pdf",
        "export_sch_pdf",
        "export_3d_step",
        "export_step",
        "export_stepz",
        "export_xao",
        "pcb_export_3d_pdf",
        "export_3d_render",
        "export_pick_and_place",
        "export_ipc2581",
        "export_odb",
        "export_svg",
        "export_dxf",
        "get_board_stats",
        "export_manufacturing_package",
        "route_export_dsn",
        "route_autoroute_freerouting",
        "route_import_ses",
        "route_tune_time_domain",
    }
)
CLI_FAILURE_TOOL_NAMES: frozenset[str] = frozenset(
    {
        "run_drc",
        "run_erc",
        "export_gerber",
        "export_drill",
        "export_bom",
        "export_netlist",
        "export_spice_netlist",
        "export_pcb_pdf",
        "export_sch_pdf",
        "export_3d_step",
        "export_step",
        "export_stepz",
        "export_xao",
        "pcb_export_3d_pdf",
        "export_3d_render",
        "export_pick_and_place",
        "export_ipc2581",
        "export_odb",
        "export_svg",
        "export_dxf",
        "get_board_stats",
    }
)
_TOOL_LIMITERS: dict[str, anyio.CapacityLimiter] = {}
_TOOL_LIMITERS_LOCK = threading.Lock()
_METRICS_LOCK = threading.Lock()
_TOOL_CALL_COUNTS: dict[tuple[str, str], int] = {}
_TOOL_LATENCIES_MS: dict[str, deque[float]] = {}
IPC_CAPABILITY_CACHE_TTL_SEC = 1.0


def _tool_limiter(tool_name: str) -> anyio.CapacityLimiter | None:
    if tool_name not in HEAVY_TOOL_NAMES:
        return None
    with _TOOL_LIMITERS_LOCK:
        limiter = _TOOL_LIMITERS.get(tool_name)
        if limiter is None:
            limiter = anyio.CapacityLimiter(2)
            _TOOL_LIMITERS[tool_name] = limiter
        return limiter


def _record_tool_metric(tool_name: str, status: str, elapsed_ms: float) -> None:
    with _METRICS_LOCK:
        key = (tool_name, status)
        _TOOL_CALL_COUNTS[key] = _TOOL_CALL_COUNTS.get(key, 0) + 1
        samples = _TOOL_LATENCIES_MS.setdefault(tool_name, deque(maxlen=256))
        samples.append(elapsed_ms)


def _percentile(samples: deque[float], percentile: float) -> float:
    if not samples:
        return 0.0
    ordered = sorted(samples)
    index = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * percentile))))
    return ordered[index]


def _label_value(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _clean_tool_error(exc: BaseException) -> str:
    message = str(exc)
    prefix = "Error executing tool "
    if message.startswith(prefix) and ": " in message:
        return message.split(": ", 1)[1]
    return message


def _tool_error_code(message: str, *, tool_name: str = "") -> str:
    lowered = message.casefold()
    if "operating mode" in lowered and "requires" in lowered:
        return "MODE_FORBIDDEN"
    if "timed out" in lowered or "timeout" in lowered:
        return "CLI_TIMEOUT"
    if "kicad-cli" in lowered:
        return "CLI_UNAVAILABLE"
    if "manufacturing export blocked" in lowered or "quality gate" in lowered:
        return "VALIDATION_FAILED"
    if (
        "no pcb file" in lowered
        or "no schematic file" in lowered
        or "invalid output path" in lowered
    ):
        return "CONFIGURATION_ERROR"
    if tool_name in CLI_FAILURE_TOOL_NAMES:
        return "CLI_COMMAND_FAILED"
    return "TOOL_EXECUTION_FAILED"


def _tool_error_hint(message: str) -> str:
    lowered = message.casefold()
    if "operating mode" in lowered and "requires" in lowered:
        return (
            "Start kicad-mcp-pro with --mode write, --mode manufacturing, "
            "or --mode experimental as appropriate."
        )
    if "no pcb file" in lowered or "no schematic file" in lowered:
        return "Call kicad_set_project() or set the relevant KICAD_MCP_*_FILE variable."
    if "kicad-cli" in lowered:
        return "Install KiCad or set KICAD_MCP_KICAD_CLI to the kicad-cli executable."
    if "quality gate" in lowered or "hard-blocked" in lowered:
        return "Read kicad://project/fix_queue, resolve blocking gate issues, then rerun the tool."
    if "unknown tool" in lowered:
        return "Check kicad_list_tool_categories() and kicad_get_tools_in_category()."
    return "Inspect the structured error and retry after correcting the request or project state."


def _structured_tool_error_from_message(
    message: str,
    *,
    tool_name: str = "",
) -> mcp_types.CallToolResult:
    code = _tool_error_code(message, tool_name=tool_name)
    payload = {
        "error_code": code,
        "message": message,
        "hint": _tool_error_hint(message),
    }
    return mcp_types.CallToolResult(
        isError=True,
        structuredContent=payload,
        content=[
            mcp_types.TextContent(
                type="text",
                text=(f"{payload['error_code']}: {payload['message']}\nHint: {payload['hint']}"),
            )
        ],
    )


def _structured_tool_error(exc: BaseException, *, tool_name: str = "") -> mcp_types.CallToolResult:
    return _structured_tool_error_from_message(_clean_tool_error(exc), tool_name=tool_name)


def _result_text(result: object) -> str:
    if isinstance(result, mcp_types.CallToolResult):
        return _result_text(result.content)
    if isinstance(result, list):
        return "\n".join(
            str(getattr(item, "text", item))
            for item in result
            if getattr(item, "text", item) is not None
        )
    if isinstance(result, tuple) and result:
        return _result_text(result[0])
    return str(result)


def _tool_failure_message(tool_name: str, result: object) -> str | None:
    text = _result_text(result).strip()
    lowered = text.casefold()
    first_line = lowered.splitlines()[0] if lowered else ""
    if tool_name == "export_manufacturing_package" and lowered.startswith(
        "manufacturing export blocked"
    ):
        return text
    if tool_name == "export_manufacturing_package" and (
        "hard-blocked" in lowered or "project quality gate: fail" in lowered
    ):
        return text
    if tool_name in CLI_FAILURE_TOOL_NAMES and (
        " failed:" in lowered or " failed." in lowered or " is unavailable:" in lowered
    ):
        return text
    if (
        " failed:" in first_line
        or first_line.endswith(" failed.")
        or " is unavailable:" in first_line
        or first_line.startswith("invalid output path:")
    ):
        return text
    return None


def _status_from_result(result: object) -> tuple[str, str | None]:
    if isinstance(result, mcp_types.CallToolResult):
        if result.isError:
            structured = result.structuredContent or {}
            return "error", str(structured.get("error_code", "TOOL_ERROR"))
        # ToolResult-returning tools embed ok=False inside structuredContent.result
        # rather than setting isError; surface those as errors for metrics/audit.
        structured = result.structuredContent or {}
        inner = structured.get("result")
        if isinstance(inner, dict) and not inner.get("ok", True):
            return "error", "TOOL_RESULT_FAILURE"
    return "ok", None


def _audit_tool_call(
    *,
    tool_name: str,
    arguments: dict[str, object],
    status: str,
    elapsed_ms: float,
    error_code: str | None,
) -> None:
    if get_config().transport == "stdio":
        return
    logger.info(
        "tool_call_audit",
        tool=tool_name,
        status=status,
        duration_ms=round(elapsed_ms, 3),
        argument_keys=sorted(arguments),
        error_code=error_code,
    )


def _log_tool_call_started(tool_name: str, arguments: dict[str, object]) -> None:
    logger.info(
        "tool_call_started",
        tool=tool_name,
        argument_keys=sorted(arguments),
    )


def _log_tool_call_finished(
    tool_name: str,
    *,
    status: str,
    elapsed_ms: float,
    error_code: str | None,
) -> None:
    logger.info(
        "tool_call_finished",
        tool=tool_name,
        status=status,
        latency_ms=round(elapsed_ms, 3),
        error_code=error_code,
    )


class _SyncServerHandle:
    """Compatibility wrapper that exposes sync-friendly discovery helpers."""

    def __init__(self, server: FastMCP) -> None:
        self._server = server

    def list_tools(self) -> object:
        """Return tool metadata synchronously when called outside an event loop."""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self._server.list_tools())
        sync_list = getattr(self._server, "list_tools_sync", None)
        if callable(sync_list):
            return sync_list()

        result: list[object] = []
        error: BaseException | None = None

        def _runner() -> None:
            nonlocal result, error
            try:
                result = list(asyncio.run(self._server.list_tools()))
            except Exception as exc:  # pragma: no cover - defensive bridge
                error = exc

        thread = threading.Thread(target=_runner, name="kicad-mcp-list-tools", daemon=True)
        thread.start()
        thread.join()
        if error is not None:
            raise error
        return result

    def __getattr__(self, name: str) -> object:
        return getattr(self._server, name)


class _StaticTokenVerifier:
    """Simple bearer-token verifier for local HTTP bridge deployments."""

    def __init__(self, expected_token: str) -> None:
        self._expected_token = expected_token

    async def verify_token(self, token: str) -> AccessToken | None:
        if secrets.compare_digest(token, self._expected_token):
            return AccessToken(token=token, client_id="kicad-studio", scopes=["mcp"])
        return None

    def rotate(self, token: str) -> None:
        """Replace the accepted bearer token without restarting the server."""
        self._expected_token = token


def _tool_requires_ipc(tool_name: str) -> bool:
    record = get_capability_record(tool_name)
    if record is not None and record.runtime is RuntimeRequirement.KICAD_IPC:
        return True
    metadata = get_tool_metadata(tool_name)
    return bool(metadata and metadata.requires_kicad_running)


def _ipc_runtime_allows_tool(tool_name: str, state: KiCadIpcCapabilityState) -> bool:
    if not _tool_requires_ipc(tool_name):
        return True
    if tool_name in state.operations:
        return state.tool_available(tool_name)

    record = get_capability_record(tool_name)
    tier = record.tier if record is not None else AccessTier.WRITE
    if tool_name.startswith("pcb_"):
        return state.live_pcb_read if tier is AccessTier.READ else state.live_pcb_write
    if tool_name.startswith("sch_"):
        return state.live_schematic_read if tier is AccessTier.READ else state.live_schematic_write
    return state.reachable


def _filter_ipc_runtime_tools(
    tools: list[mcp_types.Tool],
    state: KiCadIpcCapabilityState | None = None,
) -> list[mcp_types.Tool]:
    state = state or get_ipc_capability_state()
    return [tool for tool in tools if _ipc_runtime_allows_tool(tool.name, state)]


class KiCadFastMCP(FastMCP):
    """FastMCP extension that auto-infers tool annotations and adds CORS support."""

    allow_experimental_tools: bool = False
    allowed_tool_names: set[str] | None = None
    filter_runtime_tools: bool = True
    operating_mode: OperatingMode = OperatingMode.READONLY
    _lazy_registration: Callable[[], None] | None = None
    _lazy_registration_complete: bool = False
    _lazy_registration_error: BaseException | None = None
    _lazy_registration_lock: threading.Lock
    _lazy_registration_thread: threading.Thread | None = None
    _telemetry_catalog_hash: str | None = None
    _telemetry_kicad_version: str | None = None
    _ipc_capability_state: KiCadIpcCapabilityState | None = None
    _ipc_capability_checked_at: float = 0.0

    def set_lazy_registration(self, register: Callable[[], None]) -> None:
        """Defer heavy tool/resource registration until after stdio initialize can bind."""
        self._lazy_registration = register
        self._lazy_registration_complete = False
        self._lazy_registration_error = None
        self._lazy_registration_lock = threading.Lock()
        self._lazy_registration_thread = None

    def start_lazy_registration_background(self) -> None:
        """Begin deferred registration without blocking process startup."""
        if self._lazy_registration is None or self._lazy_registration_complete:
            return
        if getattr(self, "_lazy_registration_thread", None) is not None:
            return

        thread = threading.Thread(
            target=self.ensure_registered,
            name="kicad-mcp-register-tools",
            daemon=True,
        )
        self._lazy_registration_thread = thread
        thread.start()

    def ensure_registered(self) -> None:
        """Materialize deferred tools, resources, and prompts exactly once."""
        register = self._lazy_registration
        if register is None:
            return
        if self._lazy_registration_complete:
            return
        lock = getattr(self, "_lazy_registration_lock", None)
        if lock is None:
            lock = threading.Lock()
            self._lazy_registration_lock = lock
        with lock:
            if self._lazy_registration_complete:
                return
            if self._lazy_registration_error is not None:
                raise self._lazy_registration_error
            try:
                with _redirect_current_thread_stdout_to_stderr():
                    register()
            except Exception as exc:
                self._lazy_registration_error = exc
                raise
            self._lazy_registration_complete = True

    async def _ensure_registered_async(self) -> None:
        await anyio.to_thread.run_sync(self.ensure_registered)

    def tool(
        self,
        name: str | None = None,
        title: str | None = None,
        description: str | None = None,
        annotations: ToolAnnotations | None = None,
        icons: list[Icon] | None = None,
        meta: dict[str, object] | None = None,
        structured_output: bool | None = None,
    ) -> Callable[[AnyFunction], AnyFunction]:
        def decorator(func: AnyFunction) -> AnyFunction:
            merged = infer_tool_annotations(name or func.__name__, explicit=annotations)
            published_description = description
            if published_description is None:
                published_description = inspect.getdoc(func) or None
            if published_description is not None:
                words = [word for word in published_description.replace("-", " ").split() if word]
                if len(words) < 10:
                    published_description = (
                        f"{published_description.rstrip()} This KiCad MCP Pro tool "
                        "supports production EDA automation workflows for MCP clients."
                    )
            return super(KiCadFastMCP, self).tool(
                name=name,
                title=title,
                description=published_description,
                annotations=merged or None,
                icons=icons,
                meta=meta,
                structured_output=structured_output,
            )(func)

        return decorator

    def _filter_tools(self, tools: list[mcp_types.Tool]) -> list[mcp_types.Tool]:
        allowed_tool_names = getattr(self, "allowed_tool_names", None)
        if allowed_tool_names is not None:
            tools = [tool for tool in tools if tool.name in allowed_tool_names]
        mode = getattr(self, "operating_mode", active_operating_mode())
        tools = filter_tools_for_mode(tools, mode)
        if getattr(self, "filter_runtime_tools", True):
            tools = _filter_ipc_runtime_tools(tools, self._runtime_ipc_capability_state())
        if mode is OperatingMode.EXPERIMENTAL:
            return tools
        if (
            getattr(self, "allow_experimental_tools", False)
            or get_config().enable_experimental_tools
        ):
            return tools
        return [
            tool for tool in tools if getattr(tool, "name", None) not in EXPERIMENTAL_TOOL_NAMES
        ]

    def _runtime_ipc_capability_state(self) -> KiCadIpcCapabilityState:
        """Return a short-lived KiCad IPC capability snapshot for discovery filtering."""
        now = time.monotonic()
        cached = getattr(self, "_ipc_capability_state", None)
        checked_at = getattr(self, "_ipc_capability_checked_at", 0.0)
        if cached is None or now - checked_at > IPC_CAPABILITY_CACHE_TTL_SEC:
            cached = get_ipc_capability_state()
            self._ipc_capability_state = cached
            self._ipc_capability_checked_at = now
        return cached

    def list_tools_sync(self) -> list[mcp_types.Tool]:
        """List filtered tools without needing to drive an asyncio event loop."""
        self.ensure_registered()
        tools = self._tool_manager.list_tools()
        rendered = [
            mcp_types.Tool(
                name=info.name,
                title=info.title,
                description=info.description,
                inputSchema=info.parameters,
                outputSchema=info.output_schema,
                annotations=info.annotations,
                icons=info.icons,
                _meta=info.meta,
            )
            for info in tools
        ]
        return self._filter_tools(rendered)

    def streamable_http_app(self) -> Starlette:
        app = super().streamable_http_app()
        cfg = get_config()
        app.add_middleware(_StreamableHttpContractMiddleware)
        if cfg.legacy_sse:
            sse_routes = self.sse_app().routes
            existing_paths = {getattr(route, "path", None) for route in app.routes}
            for route in sse_routes:
                route_path = getattr(route, "path", None)
                if route_path in {"/sse", "/messages"} and route_path not in existing_paths:
                    app.routes.append(route)
                    existing_paths.add(route_path)
        origins = cfg.cors_origin_list
        if origins:
            app.add_middleware(
                CORSMiddleware,
                allow_origins=origins,
                allow_methods=["GET", "POST", "OPTIONS"],
                allow_headers=[
                    "Authorization",
                    "Content-Type",
                    "MCP-Protocol-Version",
                    "MCP-Session-Id",
                ],
            )
            app.add_middleware(_OriginValidationMiddleware)
        return app

    async def list_tools(self) -> list[mcp_types.Tool]:
        """Hide experimental tools from discovery unless explicitly enabled."""
        await self._ensure_registered_async()
        tools = await super().list_tools()
        return self._filter_tools(tools)

    async def list_resources(self) -> list[mcp_types.Resource]:
        """Materialize resources before discovery when stdio startup was deferred."""
        await self._ensure_registered_async()
        return await super().list_resources()

    async def list_resource_templates(self) -> list[mcp_types.ResourceTemplate]:
        """Materialize resource templates before discovery when startup was deferred."""
        await self._ensure_registered_async()
        return await super().list_resource_templates()

    async def read_resource(self, uri: AnyUrl | str) -> Iterable[ReadResourceContents]:
        """Materialize resources before reading them when startup was deferred."""
        await self._ensure_registered_async()
        return await super().read_resource(uri)

    async def list_prompts(self) -> list[mcp_types.Prompt]:
        """Materialize prompts before discovery when stdio startup was deferred."""
        await self._ensure_registered_async()
        return await super().list_prompts()

    async def get_prompt(
        self,
        name: str,
        arguments: dict[str, Any] | None = None,
    ) -> mcp_types.GetPromptResult:
        """Materialize prompts before rendering them when startup was deferred."""
        await self._ensure_registered_async()
        return await super().get_prompt(name, arguments)

    def _telemetry_tool_catalog_hash(self) -> str:
        if self._telemetry_catalog_hash is not None:
            return self._telemetry_catalog_hash
        catalog_hash = otel.tool_catalog_hash(tool.name for tool in self.list_tools_sync())
        self._telemetry_catalog_hash = catalog_hash
        return catalog_hash

    def _telemetry_kicad_major_minor(self) -> str | None:
        if self._telemetry_kicad_version is not None:
            return self._telemetry_kicad_version or None
        version = otel.kicad_cli_major_minor(find_kicad_version(get_config().kicad_cli))
        self._telemetry_kicad_version = version or ""
        return version

    def _telemetry_context_attributes(self) -> dict[str, object]:
        if not otel.telemetry_enabled():
            return {}
        return {
            "protocol_version": MCP_PROTOCOL_VERSION,
            "tool_catalog_hash": self._telemetry_tool_catalog_hash(),
            "kicad_cli_version": self._telemetry_kicad_major_minor() or "unknown",
        }

    async def call_tool(  # type: ignore[override]
        self,
        name: str,
        arguments: dict[str, Any],
    ) -> object:
        """Call a tool with metrics, audit logging, rate limits, and structured errors."""
        started = time.perf_counter()
        status = "ok"
        error_code: str | None = None
        limiter = _tool_limiter(name)
        result: object
        _log_tool_call_started(name, arguments)
        with otel.tool_span(name) as span:
            try:
                await self._ensure_registered_async()
                mode = getattr(self, "operating_mode", active_operating_mode())
                if not is_tool_allowed_in_mode(name, mode):
                    result = _structured_tool_error_from_message(
                        denial_message(name, mode),
                        tool_name=name,
                    )
                    status, error_code = _status_from_result(result)
                    return result
                if limiter is None:
                    result = await super().call_tool(name, arguments)
                else:
                    async with limiter:
                        result = await super().call_tool(name, arguments)
                failure_message = _tool_failure_message(name, result)
                if failure_message is not None:
                    result = _structured_tool_error_from_message(failure_message, tool_name=name)
                status, error_code = _status_from_result(result)
                return result
            except ToolError as exc:
                result = _structured_tool_error(exc, tool_name=name)
                status, error_code = _status_from_result(result)
                otel.record_error_event(
                    "mcp.tool_error",
                    exc,
                    {
                        "tool": name,
                        "error_code": error_code or type(exc).__name__,
                        **self._telemetry_context_attributes(),
                    },
                )
                return result
            except Exception as exc:
                status = "error"
                error_code = type(exc).__name__
                otel.record_error_event(
                    "mcp.tool_error",
                    exc,
                    {
                        "tool": name,
                        "error_code": error_code,
                        **self._telemetry_context_attributes(),
                    },
                )
                raise
            finally:
                elapsed_ms = (time.perf_counter() - started) * 1000.0
                _record_tool_metric(name, status, elapsed_ms)
                otel.record_tool_invocation(name, status, elapsed_ms / 1000.0)
                otel.record_runtime_event(
                    "mcp.tool_call",
                    {
                        "tool": name,
                        "status": status,
                        "elapsed_ms": round(elapsed_ms, 2),
                        "error_code": error_code or "",
                        **self._telemetry_context_attributes(),
                    },
                )
                otel.finish_tool_span(span, status=status, error_code=error_code)
                _log_tool_call_finished(
                    name,
                    status=status,
                    elapsed_ms=elapsed_ms,
                    error_code=error_code,
                )
                _audit_tool_call(
                    tool_name=name,
                    arguments=arguments,
                    status=status,
                    elapsed_ms=elapsed_ms,
                    error_code=error_code,
                )


class _StreamableHttpContractMiddleware:
    """Normalize the public Streamable HTTP contract before FastMCP handles it."""

    _SESSION_CACHE_LIMIT = 256

    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self._session_ids: set[str] = set()
        self._session_order: deque[str] = deque()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        cfg = get_config()
        method = scope.get("method")
        if scope["type"] != "http" or scope.get("path") != cfg.mount_path:
            await self.app(scope, receive, send)
            return

        headers = _scope_headers(scope)
        if method == "DELETE":
            session_id = headers.get("mcp-session-id", "")
            delete_response_status: int | None = None

            async def delete_request_send(message: Message) -> None:
                nonlocal delete_response_status
                if message["type"] == "http.response.start":
                    status_value = message.get("status")
                    delete_response_status = status_value if isinstance(status_value, int) else None
                await send(message)

            with otel.mcp_request_span(
                http_method=str(method),
                mount_path=cfg.mount_path,
                session_present=bool(session_id),
            ) as request_span:
                with structlog.contextvars.bound_contextvars(mcp_session_id=session_id or None):
                    await self.app(scope, receive, delete_request_send)
                otel.finish_mcp_request_span(request_span, status_code=delete_response_status)
            if session_id:
                self._forget_session(session_id)
                logger.info("mcp_session_destroyed", mcp_session_id=session_id)
            return
        if method != "POST":
            await self.app(scope, receive, send)
            return

        body, replay_receive = await _buffer_request_body(receive)

        # Let FastMCP's auth layer preserve its existing 401/403 error shape.
        if cfg.auth_token and not secrets.compare_digest(
            _scope_bearer_token(headers), cfg.auth_token
        ):
            await self.app(scope, replay_receive, send)
            return

        rpc_id, rpc_method = _json_rpc_metadata(body)
        post_response_status: int | None = None
        original_send = send

        async def post_request_send(message: Message) -> None:
            nonlocal post_response_status
            if message["type"] == "http.response.start":
                status_value = message.get("status")
                post_response_status = status_value if isinstance(status_value, int) else None
            await original_send(message)

        send = post_request_send
        if rpc_method == "initialize":
            logger.info(
                "mcp_transport_initialize",
                request_id=rpc_id,
                mcp_session_id=headers.get("mcp-session-id") or None,
            )
        if not _accept_header_includes(headers.get("accept", ""), "application/json"):
            await _streamable_http_error_response(
                code=-32003,
                message=(
                    "Bad Request: Accept header must include application/json and "
                    "text/event-stream."
                ),
                rpc_id=rpc_id,
                status_code=400,
                scope=scope,
                receive=replay_receive,
                send=send,
            )
            return
        if not _accept_header_includes(headers.get("accept", ""), "text/event-stream"):
            await _streamable_http_error_response(
                code=-32003,
                message=(
                    "Bad Request: Accept header must include application/json and "
                    "text/event-stream."
                ),
                rpc_id=rpc_id,
                status_code=400,
                scope=scope,
                receive=replay_receive,
                send=send,
            )
            return

        protocol_version = headers.get("mcp-protocol-version")
        if protocol_version and protocol_version != MCP_PROTOCOL_VERSION:
            await _streamable_http_error_response(
                code=-32002,
                message=(
                    f"Unsupported MCP-Protocol-Version: {protocol_version}. "
                    f"Expected {MCP_PROTOCOL_VERSION}."
                ),
                rpc_id=rpc_id,
                status_code=400,
                scope=scope,
                receive=replay_receive,
                send=send,
            )
            return

        session_id = headers.get("mcp-session-id", "")
        if cfg.stateful_http and rpc_method and rpc_method != "initialize":
            if not session_id:
                await _streamable_http_error_response(
                    code=-32000,
                    message="Bad Request: Missing MCP-Session-Id header.",
                    rpc_id=rpc_id,
                    status_code=400,
                    scope=scope,
                    receive=replay_receive,
                    send=send,
                )
                return
            if not self._has_session(session_id):
                await _streamable_http_error_response(
                    code=-32001,
                    message="Session not found for MCP-Session-Id.",
                    rpc_id=rpc_id,
                    status_code=404,
                    scope=scope,
                    receive=replay_receive,
                    send=send,
                )
                return

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                response_session_id = _message_header(message, "mcp-session-id")
                if response_session_id:
                    self._remember_session(response_session_id)
                    logger.info(
                        "mcp_session_created",
                        request_id=rpc_id,
                        mcp_session_id=response_session_id,
                    )
            await send(message)

        with otel.mcp_request_span(
            http_method=str(method),
            mount_path=cfg.mount_path,
            session_present=bool(session_id),
        ) as request_span:
            otel.annotate_mcp_request(request_span, rpc_method=rpc_method)
            with structlog.contextvars.bound_contextvars(
                request_id=rpc_id,
                mcp_session_id=session_id or None,
            ):
                await self.app(scope, replay_receive, send_wrapper)
            otel.finish_mcp_request_span(request_span, status_code=post_response_status)

    def _has_session(self, session_id: str) -> bool:
        return session_id in self._session_ids

    def _remember_session(self, session_id: str) -> None:
        if session_id in self._session_ids:
            return
        if len(self._session_order) >= self._SESSION_CACHE_LIMIT:
            self._session_ids.discard(self._session_order.popleft())
            otel.record_session_delta(-1)
        self._session_order.append(session_id)
        self._session_ids.add(session_id)
        otel.record_session_delta(1)

    def _forget_session(self, session_id: str) -> None:
        if session_id in self._session_ids:
            self._session_ids.discard(session_id)
            otel.record_session_delta(-1)
        with contextlib.suppress(ValueError):
            self._session_order.remove(session_id)


async def _buffer_request_body(receive: Receive) -> tuple[bytes, Receive]:
    messages: list[Message] = []
    chunks: list[bytes] = []
    more_body = True
    while more_body:
        message = await receive()
        messages.append(message)
        if message["type"] != "http.request":
            break
        body = message.get("body", b"")
        if isinstance(body, bytes):
            chunks.append(body)
        more_body = bool(message.get("more_body", False))

    iterator = iter(messages)

    async def replay_receive() -> Message:
        return next(iterator, {"type": "http.request", "body": b"", "more_body": False})

    return b"".join(chunks), replay_receive


def _scope_headers(scope: Scope) -> dict[str, str]:
    headers: dict[str, str] = {}
    for key, value in scope.get("headers", []):
        name = key.decode("latin-1").casefold()
        decoded_value = value.decode("latin-1")
        if name in headers:
            headers[name] = f"{headers[name]}, {decoded_value}"
        else:
            headers[name] = decoded_value
    return headers


def _scope_bearer_token(headers: dict[str, str]) -> str:
    authorization = headers.get("authorization", "")
    prefix = "Bearer "
    if not authorization.startswith(prefix):
        return ""
    return authorization[len(prefix) :].strip()


def _accept_header_includes(value: str, media_type: str) -> bool:
    media_main, media_subtype = media_type.casefold().split("/", 1)
    for item in value.split(","):
        item_type = item.split(";", 1)[0].strip().casefold()
        if not item_type:
            continue
        if item_type == "*/*":
            return True
        if item_type == media_type:
            return True
        if item_type == f"{media_main}/*":
            return True
        if item_type == f"*/{media_subtype}":
            return True
    return False


def _json_rpc_metadata(body: bytes) -> tuple[object | None, str | None]:
    try:
        payload = json.loads(body.decode("utf-8"))
    except Exception:
        return None, None
    if not isinstance(payload, dict):
        return None, None
    rpc_id = payload.get("id")
    rpc_method = payload.get("method")
    return rpc_id, rpc_method if isinstance(rpc_method, str) else None


def _message_header(message: Message, header_name: str) -> str:
    expected = header_name.casefold().encode("latin-1")
    headers = message.get("headers", [])
    if not isinstance(headers, list):
        return ""
    for key, value in headers:
        if not isinstance(key, bytes) or not isinstance(value, bytes):
            continue
        if key.lower() == expected:
            return value.decode("latin-1")
    return ""


async def _streamable_http_error_response(
    *,
    code: int,
    message: str,
    rpc_id: object | None,
    status_code: int,
    scope: Scope,
    receive: Receive,
    send: Send,
) -> None:
    response = JSONResponse(
        {"jsonrpc": "2.0", "error": {"code": code, "message": message}, "id": rpc_id},
        status_code=status_code,
    )
    await response(scope, receive, send)


class _OriginValidationMiddleware(BaseHTTPMiddleware):
    """Reject cross-origin mutating requests that are not on the configured allowlist."""

    _MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
    _ROTATE_PATH = "/.well-known/mcp-server/token-rotate"

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        cfg = get_config()
        if (
            cfg.auth_token
            and request.method.upper() in self._MUTATING_METHODS
            and request.url.path in {cfg.mount_path, self._ROTATE_PATH}
        ):
            origin = request.headers.get("origin")
            if origin and origin not in cfg.cors_origin_list:
                return PlainTextResponse("Origin not allowed for this MCP server.", status_code=403)
        return await call_next(request)


def _server_base_url(cfg: KiCadMCPConfig) -> str:
    host = cfg.host if cfg.host not in {"0.0.0.0", "::"} else "127.0.0.1"  # noqa: S104
    return f"http://{host}:{cfg.port}"


def _bearer_token(request: Request) -> str:
    authorization = request.headers.get("authorization", "")
    prefix = "Bearer "
    if not authorization.startswith(prefix):
        return ""
    return authorization[len(prefix) :].strip()


def _is_loopback_host(host: str) -> bool:
    return host.strip().casefold() in LOOPBACK_HOSTS


def _validate_rotated_token(token: str) -> str | None:
    if len(token) < 32:
        return "new_token must be at least 32 characters."
    if len(set(token)) < 12:
        return "new_token must have higher entropy."
    return None


async def _request_is_authorized(
    request: Request,
    token_verifier: _StaticTokenVerifier | None,
) -> bool:
    if token_verifier is None:
        return False
    token = _bearer_token(request)
    return await token_verifier.verify_token(token) is not None


def _prometheus_metrics_payload() -> str:
    lines = [
        "# HELP kicad_mcp_tool_calls_total Total MCP tool calls observed by this process.",
        "# TYPE kicad_mcp_tool_calls_total counter",
    ]
    with _METRICS_LOCK:
        if not _TOOL_CALL_COUNTS:
            lines.append('kicad_mcp_tool_calls_total{tool="none",status="none"} 0')
        for (tool, status), count in sorted(_TOOL_CALL_COUNTS.items()):
            lines.append(
                "kicad_mcp_tool_calls_total"
                f'{{tool="{_label_value(tool)}",status="{_label_value(status)}"}} {count}'
            )

        lines.extend(
            [
                "# HELP kicad_mcp_tool_latency_p50_ms Sliding-window p50 tool latency in ms.",
                "# TYPE kicad_mcp_tool_latency_p50_ms gauge",
            ]
        )
        for tool, samples in sorted(_TOOL_LATENCIES_MS.items()):
            lines.append(
                "kicad_mcp_tool_latency_p50_ms"
                f'{{tool="{_label_value(tool)}"}} {_percentile(samples, 0.50):.3f}'
            )
        lines.extend(
            [
                "# HELP kicad_mcp_tool_latency_p95_ms Sliding-window p95 tool latency in ms.",
                "# TYPE kicad_mcp_tool_latency_p95_ms gauge",
            ]
        )
        for tool, samples in sorted(_TOOL_LATENCIES_MS.items()):
            lines.append(
                "kicad_mcp_tool_latency_p95_ms"
                f'{{tool="{_label_value(tool)}"}} {_percentile(samples, 0.95):.3f}'
            )
    lines.extend(
        [
            "# HELP kicad_mcp_active_sessions Active Streamable HTTP sessions.",
            "# TYPE kicad_mcp_active_sessions gauge",
            "kicad_mcp_active_sessions 0",
            "",
        ]
    )
    return "\n".join(lines)


def _register_profile_components(
    server: KiCadFastMCP,
    enabled: set[str],
    cfg: KiCadMCPConfig,
) -> None:
    """Register all profile-specific MCP surfaces on an already-created server."""
    from .prompts import workflows
    from .resources import analysis, board_state, server_info, studio_context
    from .tools import (
        dfm,
        emc_compliance,
        export,
        library,
        manufacturing,
        pcb,
        power_integrity,
        project,
        routing,
        schematic,
        signal_integrity,
        simulation,
        validation,
        variants,
        version_control,
    )

    validate_callable_imports()

    router.register(server)
    project.register(server)

    if "pcb_read" in enabled or "pcb_write" in enabled:
        pcb.register(server)
    if "schematic" in enabled:
        schematic.register(server)
        variants.register(server)
    if "library" in enabled:
        library.register(server)
    if "export" in enabled or "release_export" in enabled:
        export.register(server, include_low_level_exports="export" in enabled)
    if "validation" in enabled:
        validation.register(server)
    if "dfm" in enabled:
        dfm.register(server)
    if "routing" in enabled:
        routing.register(server)
    if "power_integrity" in enabled:
        power_integrity.register(server)
    if "emc" in enabled:
        emc_compliance.register(server)
    if "signal_integrity" in enabled:
        signal_integrity.register(server)
    if "simulation" in enabled:
        simulation.register(server)
    if "version_control" in enabled:
        version_control.register(server)
    if "manufacturing" in enabled:
        manufacturing.register(server)

    analysis.register(server)
    board_state.register(server)
    server_info.register(server)
    studio_context.register(server)
    workflows.register(server)

    if cfg.studio_watch_dir is not None:
        ensure_studio_project_watcher(cfg.studio_watch_dir)


def build_server(profile: str | None = None, *, defer_registration: bool = False) -> FastMCP:
    """Build a FastMCP server instance for the active profile."""
    cfg = get_config()
    otel.ensure_telemetry_configured(cfg)
    cfg._validate_http_transport_security()
    selected_profile = profile or cfg.profile
    operating_mode = active_operating_mode(cfg)
    enabled = set(categories_for_profile(selected_profile))
    token_verifier = _StaticTokenVerifier(cfg.auth_token) if cfg.auth_token else None
    auth = None
    if cfg.auth_token:
        base_url = _server_base_url(cfg)
        auth = AuthSettings(
            issuer_url=base_url,
            resource_server_url=base_url,
            required_scopes=["mcp"],
        )

    server = KiCadFastMCP(
        name="kicad-mcp-pro",
        instructions=(
            "KiCad MCP Pro Server for project setup, schematic capture, PCB editing, "
            "validation, and manufacturing export. Start with kicad_get_version(), "
            "kicad_set_project(), and project_get_design_spec()."
        ),
        website_url="https://oaslananka.github.io/kicad-mcp",
        host=cfg.host,
        port=cfg.port,
        streamable_http_path=cfg.mount_path,
        mount_path=cfg.mount_path,
        log_level=cfg.log_level,
        json_response=True,
        stateless_http=not cfg.stateful_http,
        auth=auth,
        token_verifier=token_verifier,
    )
    server.operating_mode = operating_mode
    server.allow_experimental_tools = operating_mode is OperatingMode.EXPERIMENTAL
    server.allowed_tool_names = {
        tool_name for category in enabled for tool_name in router.TOOL_CATEGORIES[category]["tools"]
    }

    @server.custom_route("/.well-known/mcp-server", methods=["GET"], include_in_schema=False)
    async def _well_known_mcp(_request: Request) -> JSONResponse:
        return JSONResponse(get_wellknown_metadata())

    @server.custom_route("/well-known/mcp-server", methods=["GET"], include_in_schema=False)
    async def _well_known_mcp_compat(_request: Request) -> JSONResponse:
        return JSONResponse(get_wellknown_metadata())

    @server.custom_route(
        "/.well-known/mcp-server/token-rotate",
        methods=["POST"],
        include_in_schema=False,
    )
    async def _rotate_token(request: Request) -> JSONResponse:
        if token_verifier is None or not cfg.auth_token:
            return JSONResponse({"error": "Bearer token auth is not enabled."}, status_code=404)
        token = _bearer_token(request)
        if await token_verifier.verify_token(token) is None:
            return JSONResponse({"error": "Unauthorized."}, status_code=401)
        try:
            payload = await request.json()
        except Exception:
            return JSONResponse({"error": "Request body must be JSON."}, status_code=400)
        raw_token = payload.get("new_token") if isinstance(payload, dict) else None
        new_token = raw_token.strip() if isinstance(raw_token, str) else ""
        if not new_token:
            return JSONResponse({"error": "new_token must be a non-empty string."}, status_code=400)
        token_error = _validate_rotated_token(new_token)
        if token_error is not None:
            return JSONResponse({"error": token_error}, status_code=400)
        cfg.auth_token = new_token
        token_verifier.rotate(new_token)
        logger.info("security_token_rotated", transport=cfg.transport, host=cfg.host)
        return JSONResponse({"rotated": True})

    if cfg.enable_metrics:

        @server.custom_route("/metrics", methods=["GET"], include_in_schema=False)
        async def _metrics(request: Request) -> PlainTextResponse | JSONResponse:
            if not _is_loopback_host(cfg.host) and not await _request_is_authorized(
                request, token_verifier
            ):
                return JSONResponse({"error": "Unauthorized."}, status_code=401)
            return PlainTextResponse(
                _prometheus_metrics_payload(),
                media_type="text/plain; version=0.0.4",
            )

    def register() -> None:
        _register_profile_components(server, enabled, cfg)

    if defer_registration:
        server.set_lazy_registration(register)
    else:
        register()

    return server


def create_server(profile: str | None = None) -> _SyncServerHandle:
    """Backward-compatible helper used by benchmark and verification scripts."""
    return _SyncServerHandle(build_server(profile))


def _ipc_status_summary() -> str:
    try:
        get_board()
    except KiCadConnectionError as exc:
        return f"unavailable ({str(exc).splitlines()[0]})"
    return "connected (PCB editor available)"


def _print_startup_diagnostics(cfg: KiCadMCPConfig, *, probe_runtime: bool = True) -> None:
    """Emit a concise startup summary without writing directly to stdio transport."""
    if cfg.transport == "stdio" and cfg.auth_token:
        logger.warning(
            "stdio_auth_token_ignored",
            message="KICAD_MCP_AUTH_TOKEN has no effect when the server runs over stdio.",
        )
    kicad_version = "deferred" if not probe_runtime else find_kicad_version(cfg.kicad_cli)
    ipc_status = "deferred" if not probe_runtime else _ipc_status_summary()
    logger.info(
        "startup_diagnostics",
        profile=cfg.profile,
        operating_mode=active_operating_mode(cfg).value,
        kicad_cli=str(cfg.kicad_cli),
        kicad_version=kicad_version or "unknown",
        project_dir=str(cfg.project_dir) if cfg.project_dir else None,
        gate_mode="release-export-only",
        ipc_status=ipc_status,
    )


def _apply_cli_env(
    transport: str | None = None,
    host: str | None = None,
    port: int | None = None,
    project_dir: str | None = None,
    log_level: str | None = None,
    log_format: str | None = None,
    log_file: str | None = None,
    profile: str | None = None,
    operating_mode: str | None = None,
    experimental: bool | None = None,
    telemetry: bool | None = None,
) -> None:
    cli_env = {
        "KICAD_MCP_TRANSPORT": transport,
        "KICAD_MCP_HOST": host,
        "KICAD_MCP_PORT": (
            str(port) if port is not None and not isinstance(port, OptionInfo) else None
        ),
        "KICAD_MCP_LOG_LEVEL": log_level,
        "KICAD_MCP_LOG_FORMAT": log_format,
        "KICAD_MCP_LOG_FILE": log_file,
        "KICAD_MCP_PROFILE": profile,
        "KICAD_MCP_OPERATING_MODE": operating_mode,
        "KICAD_MCP_PROJECT_DIR": project_dir,
    }
    for key, value in cli_env.items():
        if value is not None and not isinstance(value, OptionInfo):
            os.environ[key] = value
    if experimental is not None and not isinstance(experimental, OptionInfo):
        os.environ["KICAD_MCP_ENABLE_EXPERIMENTAL_TOOLS"] = "true" if experimental else "false"
        if experimental and operating_mode is None:
            os.environ["KICAD_MCP_OPERATING_MODE"] = "experimental"
    if telemetry is not None and not isinstance(telemetry, OptionInfo):
        os.environ["KICAD_MCP_TELEMETRY_ENABLED"] = "true" if telemetry else "false"


def _run_server_from_options(
    *,
    transport: str | None = None,
    host: str | None = None,
    port: int | None = None,
    project_dir: str | None = None,
    log_level: str | None = None,
    log_format: str | None = None,
    log_file: str | None = None,
    profile: str | None = None,
    operating_mode: str | None = None,
    experimental: bool | None = None,
    telemetry: bool | None = None,
) -> None:
    """Apply CLI overrides and start the MCP server."""
    _apply_cli_env(
        transport=transport,
        host=host,
        port=port,
        project_dir=project_dir,
        log_level=log_level,
        log_format=log_format,
        log_file=log_file,
        profile=profile,
        operating_mode=operating_mode,
        experimental=experimental,
        telemetry=telemetry,
    )
    with contextlib.redirect_stdout(sys.stderr):
        reset_config()
        cfg = get_config()
        otel.configure_telemetry(cfg)
        setup_logging(
            cfg.log_level,
            cfg.log_format,
            cfg.log_file,
            cfg.log_max_bytes,
            cfg.log_backup_count,
        )

        selected_transport = "stdio" if cfg.transport == "stdio" else "streamable-http"
        if cfg.transport == "sse":
            if cfg.legacy_sse:
                selected_transport = "sse"
                logger.warning(
                    "legacy_sse_enabled",
                    message="Legacy SSE transport is enabled for backward compatibility.",
                )
            else:
                logger.warning(
                    "legacy_sse_disabled",
                    message=(
                        "Ignoring KICAD_MCP_TRANSPORT=sse because KICAD_MCP_LEGACY_SSE is false."
                    ),
                )
        defer_registration = selected_transport == "stdio"
        server = build_server(cfg.profile, defer_registration=defer_registration)
        _print_startup_diagnostics(cfg, probe_runtime=not defer_registration)
        logger.info(
            "starting_kicad_mcp_pro",
            version=__version__,
            transport=selected_transport,
            profile=cfg.profile,
            operating_mode=active_operating_mode(cfg).value,
        )

    if selected_transport == "stdio":
        _ensure_thread_aware_stdout()
        server.run(transport="stdio")
        return

    if selected_transport == "sse":
        server.run(transport="sse", mount_path=cfg.mount_path)
        return

    server.run(transport="streamable-http", mount_path=cfg.mount_path)


@app.callback(invoke_without_command=True)
def main_callback(
    transport: str | None = typer.Option(
        None, help=option_help("Transport: stdio, http, sse, streamable-http")
    ),
    host: str | None = typer.Option(None, help=option_help("HTTP bind host")),
    port: int | None = typer.Option(None, help=option_help("HTTP bind port")),
    project_dir: str | None = typer.Option(
        None, help=option_help("Active KiCad project directory")
    ),
    log_level: str | None = typer.Option(None, help=option_help("Log level")),
    log_format: str | None = typer.Option(None, help=option_help("Log format: text or json")),
    log_file: str | None = typer.Option(None, help=option_help("Rotating log file path")),
    profile: str | None = typer.Option(
        None, help=f"Server profile: {', '.join(available_profiles())}"
    ),
    operating_mode: str | None = typer.Option(
        None,
        "--mode",
        help=option_help("Operating mode: readonly, write, manufacturing, experimental"),
    ),
    experimental: bool | None = typer.Option(None, help=option_help("Enable experimental tools")),
    telemetry: bool | None = typer.Option(
        None, "--telemetry/--no-telemetry", help=option_help("Enable OpenTelemetry export")
    ),
) -> None:
    """Start the KiCad MCP Pro server when no subcommand is supplied."""
    _apply_cli_env(
        transport=transport,
        host=host,
        port=port,
        project_dir=project_dir,
        log_level=log_level,
        log_format=log_format,
        log_file=log_file,
        profile=profile,
        operating_mode=operating_mode,
        experimental=experimental,
        telemetry=telemetry,
    )
    current_context = click.get_current_context(silent=True)
    if current_context is not None and current_context.invoked_subcommand is not None:
        return
    _run_server_from_options()


@app.command()
def serve(
    transport: str | None = typer.Option(
        None, help=option_help("Transport: stdio, http, sse, streamable-http")
    ),
    host: str | None = typer.Option(None, help=option_help("HTTP bind host")),
    port: int | None = typer.Option(None, help=option_help("HTTP bind port")),
    project_dir: str | None = typer.Option(
        None, help=option_help("Active KiCad project directory")
    ),
    log_level: str | None = typer.Option(None, help=option_help("Log level")),
    log_format: str | None = typer.Option(None, help=option_help("Log format: text or json")),
    log_file: str | None = typer.Option(None, help=option_help("Rotating log file path")),
    profile: str | None = typer.Option(
        None, help=f"Server profile: {', '.join(available_profiles())}"
    ),
    operating_mode: str | None = typer.Option(
        None,
        "--mode",
        help=option_help("Operating mode: readonly, write, manufacturing, experimental"),
    ),
    experimental: bool | None = typer.Option(None, help=option_help("Enable experimental tools")),
    telemetry: bool | None = typer.Option(
        None, "--telemetry/--no-telemetry", help=option_help("Enable OpenTelemetry export")
    ),
) -> None:
    """Start the MCP server explicitly."""
    _run_server_from_options(
        transport=transport,
        host=host,
        port=port,
        project_dir=project_dir,
        log_level=log_level,
        log_format=log_format,
        log_file=log_file,
        profile=profile,
        operating_mode=operating_mode,
        experimental=experimental,
        telemetry=telemetry,
    )


def _echo_report(report: DiagnosticReport, *, as_json: bool) -> None:
    if as_json:
        typer.echo(diagnostic_report_json(report, indent=2))
        return
    typer.echo(f"Status: {report.status}")
    for check in report.checks:
        suffix = f" Hint: {check.hint}" if check.hint else ""
        typer.echo(f"- {check.name}: {check.status} - {check.message}{suffix}")


def _emit_diagnostic_report(
    report: DiagnosticReport,
    *,
    as_json: bool,
    bundle_path: Path | None = None,
) -> None:
    if bundle_path is not None:
        write_diagnostic_bundle(report, bundle_path)
    _echo_report(report, as_json=as_json)


def _diagnostic_command(
    builder: Callable[[], DiagnosticReport],
    *,
    as_json: bool,
    bundle_path: Path | None = None,
) -> None:
    try:
        if as_json:
            with contextlib.redirect_stdout(io.StringIO()):
                report = builder()
        else:
            report = builder()
    except Exception as exc:
        message = str(exc)
        payload = {
            "ok": False,
            "status": "error",
            "error": {
                "code": "CONFIGURATION_ERROR",
                "message": message,
                "hint": "Fix malformed KiCad MCP configuration and retry.",
                "retryable": False,
            },
        }
        error = cast(dict[str, object], payload["error"])
        typer.echo(json.dumps(payload, indent=2) if as_json else str(error["message"]))
        raise typer.Exit(2) from exc
    _emit_diagnostic_report(report, as_json=as_json, bundle_path=bundle_path)
    if not report.ok:
        raise typer.Exit(1)


def _strict_diagnostic_exit_code(report: DiagnosticReport) -> int:
    if any(check.status == "error" for check in report.checks):
        return 2
    if any(check.name == "kicad_cli" and check.status == "warn" for check in report.checks):
        return 3
    if report.status == "degraded":
        return 1
    return 0


def _strict_diagnostic_command(
    builder: Callable[[], DiagnosticReport],
    *,
    as_json: bool,
    bundle_path: Path | None = None,
) -> None:
    try:
        if as_json:
            with contextlib.redirect_stdout(io.StringIO()):
                report = builder()
        else:
            report = builder()
    except Exception as exc:
        payload = {
            "ok": False,
            "status": "error",
            "error": {
                "code": "CONFIGURATION_ERROR",
                "message": str(exc),
                "hint": "Fix malformed KiCad MCP configuration and retry.",
                "retryable": False,
            },
        }
        error = cast(dict[str, object], payload["error"])
        typer.echo(json.dumps(payload, indent=2) if as_json else str(error["message"]))
        raise typer.Exit(2) from exc
    _emit_diagnostic_report(report, as_json=as_json, bundle_path=bundle_path)
    exit_code = _strict_diagnostic_exit_code(report)
    if exit_code:
        raise typer.Exit(exit_code)


@app.command()
def health(
    json_output: bool = typer.Option(
        False, "--json", help=option_help("Emit machine-readable JSON.")
    ),
) -> None:
    """Report fast package and configuration health without requiring KiCad IPC."""
    _diagnostic_command(build_health_report, as_json=json_output)


@app.command()
def doctor(
    json_output: bool = typer.Option(
        False, "--json", help=option_help("Emit machine-readable JSON.")
    ),
    bundle: Path | None = DOCTOR_BUNDLE_OPTION,
    strict: bool = typer.Option(
        False,
        "--strict",
        help=option_help("Use stable non-zero exit codes for degraded runtime states."),
    ),
) -> None:
    """Run deeper diagnostics without treating unavailable KiCad as fatal."""
    if strict:
        _strict_diagnostic_command(build_doctor_report, as_json=json_output, bundle_path=bundle)
        return
    _diagnostic_command(build_doctor_report, as_json=json_output, bundle_path=bundle)


def _tool_payload(tool: mcp_types.Tool) -> dict[str, object]:
    dumped = tool.model_dump(mode="json", exclude_none=True)
    return {
        "name": dumped.get("name"),
        "description": dumped.get("description", ""),
        "inputSchema": dumped.get("inputSchema", {}),
        "annotations": dumped.get("annotations", {}),
    }


@tools_app.command("list")
def list_tools_command(
    json_output: bool = typer.Option(False, "--json", help="Emit machine-readable JSON."),
    profile: str | None = typer.Option(
        None, help=f"Server profile: {', '.join(available_profiles())}"
    ),
    operating_mode: str | None = typer.Option(
        None,
        "--mode",
        help=option_help("Operating mode: readonly, write, manufacturing, experimental"),
    ),
) -> None:
    """List MCP tools available for the selected profile."""
    if profile is not None and profile not in available_profiles():
        raise typer.BadParameter(f"Unsupported profile: {profile}")
    previous_mode = os.environ.get("KICAD_MCP_OPERATING_MODE")
    if operating_mode is not None:
        os.environ["KICAD_MCP_OPERATING_MODE"] = operating_mode
        reset_config()
    with contextlib.redirect_stdout(io.StringIO()):
        try:
            server = build_server(profile, defer_registration=False)
        finally:
            if operating_mode is not None:
                if previous_mode is None:
                    os.environ.pop("KICAD_MCP_OPERATING_MODE", None)
                else:
                    os.environ["KICAD_MCP_OPERATING_MODE"] = previous_mode
                reset_config()
    sync_list = getattr(server, "list_tools_sync", None)
    if not callable(sync_list):
        raise typer.Exit(2)
    with contextlib.redirect_stdout(io.StringIO()):
        tools = sorted(
            cast(Callable[[], list[mcp_types.Tool]], sync_list)(), key=lambda tool: tool.name
        )
    payload = [_tool_payload(tool) for tool in tools]
    if json_output:
        typer.echo(json.dumps(payload, indent=2))
        return
    for tool in payload:
        typer.echo(str(tool["name"]))


@app.command("capabilities")
def capabilities_command(
    json_output: bool = typer.Option(False, "--json", help="Emit machine-readable JSON."),
) -> None:
    """List registered capability metadata."""
    payload = all_protocol_metadata()
    if json_output:
        typer.echo(json.dumps(payload, indent=2))
        return
    for record in payload:
        typer.echo(str(record["name"]))


def _client_config_payload(client: str) -> str:
    server_name = "kicad-mcp-pro"
    stdio_server = {"command": "uvx", "args": ["kicad-mcp-pro"]}
    if client in {"claude", "cursor"}:
        return json.dumps({"mcpServers": {server_name: stdio_server}}, indent=2)
    if client == "vscode":
        payload = {
            "servers": {
                server_name: {
                    "type": "stdio",
                    **stdio_server,
                }
            }
        }
        return json.dumps(payload, indent=2)
    if client == "codex":
        return "\n".join(
            [
                "[mcp_servers.kicad-mcp-pro]",
                'command = "uvx"',
                'args = ["kicad-mcp-pro"]',
            ]
        )
    raise typer.BadParameter(f"Unsupported client: {client}")


@mcp_config_app.command("generate")
def generate_mcp_config_command(
    client: str = typer.Option(
        ...,
        "--client",
        help="Client target: claude, cursor, vscode, or codex.",
    ),
) -> None:
    """Generate a minimal stdio MCP client configuration."""
    normalized = client.strip().casefold()
    if normalized not in {"claude", "cursor", "vscode", "codex"}:
        raise typer.BadParameter(f"Unsupported client: {client}")
    typer.echo(_client_config_payload(normalized))


@app.command("version")
def version_command(
    json_output: bool = typer.Option(False, "--json", help="Emit machine-readable JSON."),
) -> None:
    """Print package version information."""
    with contextlib.redirect_stdout(io.StringIO()):
        cfg = get_config()
    payload = {
        "package": {"name": "kicad-mcp-pro", "version": __version__},
        "mcp": {
            "transport_default": cfg.transport,
            "profile": cfg.profile,
            "operating_mode": active_operating_mode(cfg).value,
        },
        "python": {"version": sys.version.split()[0]},
    }
    typer.echo(json.dumps(payload, indent=2) if json_output else __version__)


def main() -> None:
    """CLI entrypoint used by the package script."""
    app()


if __name__ == "__main__":
    main()
