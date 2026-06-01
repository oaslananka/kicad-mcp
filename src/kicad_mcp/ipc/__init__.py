"""KiCad IPC client, discovery, and capability helpers."""

from .capabilities import (
    REQUIRED_LIVE_EDITING_TOOLS,
    KiCadIpcCapabilityState,
    get_ipc_capability_state,
)
from .client import KiCadIpcClient
from .discovery import KiCadIpcDiscovery, KiCadIpcEndpoint
from .errors import KiCadIpcError, KiCadIpcUnavailableError

__all__ = [
    "REQUIRED_LIVE_EDITING_TOOLS",
    "KiCadIpcCapabilityState",
    "KiCadIpcClient",
    "KiCadIpcDiscovery",
    "KiCadIpcEndpoint",
    "KiCadIpcError",
    "KiCadIpcUnavailableError",
    "get_ipc_capability_state",
]
