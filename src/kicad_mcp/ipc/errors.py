"""IPC-specific error types for KiCad live API integration."""

from __future__ import annotations

from ..errors import KiCadMcpError, KiCadNotRunningError


class KiCadIpcError(KiCadMcpError):
    """Base error for KiCad IPC discovery and live capability checks."""

    code = "KICAD_IPC_ERROR"
    hint = "Inspect KiCad IPC configuration and run kicad_doctor for diagnostics."
    retryable = True


class KiCadIpcUnavailableError(KiCadNotRunningError):
    """Raised when the KiCad IPC API cannot be reached."""

    code = "KICAD_IPC_UNAVAILABLE"
    hint = "Start KiCad, enable the IPC API server, and verify the socket/token settings."
    retryable = True
