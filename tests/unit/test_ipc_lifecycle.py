from __future__ import annotations

from collections.abc import Mapping

from kicad_mcp.errors import KiCadMcpError
from kicad_mcp.ipc.capabilities import get_ipc_capability_state


class MockCapabilityClient:
    def __init__(self) -> None:
        self.connected = False
        self.has_board = False
        self.has_schematic = False
        self.version = "KiCad 10.0.3"

    def probe(self) -> Mapping[str, object]:
        if not self.connected:
            raise KiCadMcpError("Connection refused")
        return {"connected": True, "version": self.version}

    def board(self) -> object:
        if not self.has_board:
            raise KiCadMcpError("No board open")
        return object()

    def has_open_schematic(self) -> bool:
        if not self.has_schematic:
            return False
        return True


def test_ipc_lifecycle_state_transitions() -> None:
    client = MockCapabilityClient()

    # 1. Startup / KiCad not running
    state1 = get_ipc_capability_state(
        client=client,
        probe_live_context=True,
    )
    assert state1.reachable is False
    assert state1.live_pcb_context is False
    assert state1.live_schematic_context is False
    assert (state1.live_pcb_context or state1.live_schematic_context) is False

    # 2. KiCad running, but no documents loaded
    client.connected = True
    state2 = get_ipc_capability_state(
        client=client,
        probe_live_context=True,
    )
    assert state2.reachable is True
    assert state2.live_pcb_context is False
    assert state2.live_schematic_context is False
    assert (state2.live_pcb_context or state2.live_schematic_context) is False

    # 3. PCB board loaded
    client.has_board = True
    state3 = get_ipc_capability_state(
        client=client,
        probe_live_context=True,
    )
    assert state3.reachable is True
    assert state3.live_pcb_context is True
    assert state3.live_schematic_context is False
    assert (state3.live_pcb_context or state3.live_schematic_context) is True

    # 4. Schematic also loaded
    client.has_schematic = True
    state4 = get_ipc_capability_state(
        client=client,
        probe_live_context=True,
    )
    assert state4.reachable is True
    assert state4.live_pcb_context is True
    assert state4.live_schematic_context is True
    assert (state4.live_pcb_context or state4.live_schematic_context) is True

    # 5. Documents unloaded (e.g. user closed project)
    client.has_board = False
    client.has_schematic = False
    state5 = get_ipc_capability_state(
        client=client,
        probe_live_context=True,
    )
    assert state5.reachable is True
    assert state5.live_pcb_context is False
    assert state5.live_schematic_context is False
    assert (state5.live_pcb_context or state5.live_schematic_context) is False

    # 6. KiCad closed / shutdown
    client.connected = False
    state6 = get_ipc_capability_state(
        client=client,
        probe_live_context=True,
    )
    assert state6.reachable is False
    assert state6.live_pcb_context is False
    assert state6.live_schematic_context is False
    assert (state6.live_pcb_context or state6.live_schematic_context) is False
