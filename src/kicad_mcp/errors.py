"""Typed error model for KiCad MCP Pro."""

from __future__ import annotations

from typing import TypedDict


class ErrorPayload(TypedDict):
    """Stable machine-readable error payload."""

    code: str
    message: str
    hint: str
    retryable: bool


class KiCadMcpError(Exception):
    """Base class for stable KiCad MCP domain errors."""

    code = "KICAD_MCP_ERROR"
    hint = "Inspect the request, project configuration, and diagnostics output."
    retryable = False

    def to_payload(self) -> ErrorPayload:
        """Return a stable JSON-serializable error payload."""
        return {
            "code": self.code,
            "message": str(self),
            "hint": self.hint,
            "retryable": self.retryable,
        }


class KiCadNotRunningError(KiCadMcpError):
    """Raised when KiCad IPC is not reachable."""

    code = "KICAD_NOT_RUNNING"
    hint = "Start KiCad and enable the IPC API server, or run doctor for diagnostics."
    retryable = True


class KiCadConnectionTimeoutError(KiCadNotRunningError):
    """Raised when KiCad IPC connection attempts time out."""

    code = "KICAD_CONNECTION_TIMEOUT"
    hint = "Increase KICAD_MCP_TIMEOUT_MS or verify that the KiCad IPC API is responding."
    retryable = True


class KiCadVersionMismatchError(KiCadMcpError):
    """Raised when the detected KiCad version is unsupported."""

    code = "KICAD_VERSION_MISMATCH"
    hint = "Install a supported KiCad version or check the compatibility matrix."
    retryable = False


class KiCadProjectNotFoundError(KiCadMcpError):
    """Raised when a configured KiCad project cannot be found."""

    code = "KICAD_PROJECT_NOT_FOUND"
    hint = "Set KICAD_MCP_PROJECT_DIR or call kicad_set_project() with an existing project."
    retryable = False


class KiCadBoardNotOpenError(KiCadMcpError):
    """Raised when KiCad is reachable but no board is open."""

    code = "KICAD_BOARD_NOT_OPEN"
    hint = "Open a .kicad_pcb file in KiCad or set the active project before using board tools."
    retryable = True


class UnsafePathError(KiCadMcpError, ValueError):
    """Raised when a requested path escapes the configured workspace."""

    code = "UNSAFE_PATH"
    hint = "Use a relative path inside KICAD_MCP_WORKSPACE_ROOT or the active project."
    retryable = False


class ToolValidationError(KiCadMcpError, ValueError):
    """Raised when a tool request is invalid before touching external state."""

    code = "TOOL_VALIDATION_ERROR"
    hint = "Correct the tool arguments and retry."
    retryable = False


class ExternalToolUnavailableError(KiCadMcpError):
    """Raised when a required external executable is unavailable."""

    code = "EXTERNAL_TOOL_UNAVAILABLE"
    hint = "Install the required executable or configure its path explicitly."
    retryable = False


def error_payload(exc: BaseException) -> ErrorPayload:
    """Map an arbitrary exception to the stable error payload shape."""
    if isinstance(exc, KiCadMcpError):
        return exc.to_payload()
    return {
        "code": "INTERNAL_ERROR",
        "message": str(exc) or exc.__class__.__name__,
        "hint": "Run doctor for diagnostics and retry with corrected configuration.",
        "retryable": False,
    }
