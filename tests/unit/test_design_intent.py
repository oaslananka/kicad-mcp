from __future__ import annotations

from kicad_mcp.tools.project import DecouplingPairIntent, ProjectDesignIntent


def test_design_intent_round_trips_extended_fields() -> None:
    intent = ProjectDesignIntent(
        connector_refs=["J1"],
        critical_nets=["USB_D+"],
        decoupling_pairs=[DecouplingPairIntent(ic_ref="U1", cap_refs=["C1"])],
        manufacturer="JLCPCB",
        manufacturer_tier="standard",
    )

    restored = ProjectDesignIntent.model_validate_json(intent.model_dump_json())

    assert restored.connector_refs == ["J1"]
    assert restored.critical_nets == ["USB_D+"]
    assert restored.decoupling_pairs[0].ic_ref == "U1"
    assert restored.manufacturer == "JLCPCB"
