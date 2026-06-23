from __future__ import annotations

import json
from pathlib import Path

import pytest

from kicad_mcp.server import build_server
from tests.conftest import call_tool_text


@pytest.mark.anyio
async def test_project_set_design_intent_can_clear_manufacturer_fields(
    sample_project: Path,
) -> None:
    server = build_server("schematic_authoring")

    await call_tool_text(
        server,
        "project_set_design_intent",
        {"manufacturer": "JLCPCB", "manufacturer_tier": "standard"},
    )
    await call_tool_text(
        server,
        "project_set_design_intent",
        {"manufacturer": "", "manufacturer_tier": ""},
    )

    payload = json.loads((sample_project / ".kicad-mcp" / "project_spec.json").read_text())
    assert payload["manufacturer"] == ""
    assert payload["manufacturer_tier"] == ""
