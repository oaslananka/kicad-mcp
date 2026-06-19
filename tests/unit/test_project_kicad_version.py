from __future__ import annotations

import pytest

from kicad_mcp.server import create_server
from tests.conftest import call_tool_text
from unittest.mock import patch, MagicMock


@pytest.mark.anyio
async def test_kicad_get_version_partial_document_availability(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # We want to test the case where get_open_documents throws an error
    # for DOCTYPE_PCB but succeeds for DOCTYPE_SCHEMATIC.
    # The output should say "unavailable" for PCB and report the count for Schematic.

    class MockKiCadPartial:
        def get_version(self) -> str:
            return "10.0.0-mock"

        def get_open_documents(self, doc_type: int) -> list[str]:
            from kipy.proto.common.types.base_types_pb2 import DocumentType

            if doc_type == DocumentType.DOCTYPE_PCB:
                raise RuntimeError("No handler for DOCTYPE_PCB")
            elif doc_type == DocumentType.DOCTYPE_SCHEMATIC:
                return ["sch1", "sch2"]
            return []

    # Mock get_kicad
    monkeypatch.setattr("kicad_mcp.tools.project.get_kicad", MockKiCadPartial)

    server = create_server()
    output = await call_tool_text(server, "kicad_get_version", {})

    assert "IPC version: 10.0.0-mock" in output
    assert "Open PCB documents: unavailable" in output
    assert "Open schematic documents: 2" in output


@pytest.mark.anyio
async def test_kicad_get_version_partial_document_availability_sch_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Same but error on schematic
    class MockKiCadPartialSch:
        def get_version(self) -> str:
            return "10.0.0-mock"

        def get_open_documents(self, doc_type: int) -> list[str]:
            from kipy.proto.common.types.base_types_pb2 import DocumentType

            if doc_type == DocumentType.DOCTYPE_SCHEMATIC:
                raise RuntimeError("No handler for DOCTYPE_SCHEMATIC")
            elif doc_type == DocumentType.DOCTYPE_PCB:
                return ["pcb1"]
            return []

    # Mock get_kicad
    monkeypatch.setattr("kicad_mcp.tools.project.get_kicad", MockKiCadPartialSch)

    server = create_server()
    output = await call_tool_text(server, "kicad_get_version", {})

    assert "IPC version: 10.0.0-mock" in output
    assert "Open PCB documents: 1" in output
    assert "Open schematic documents: unavailable" in output
