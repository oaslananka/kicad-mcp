from __future__ import annotations

from kicad_mcp.capabilities import (
    AccessTier,
    RuntimeRequirement,
    all_records,
    get,
    is_allowed,
    tools_for_profile,
)

REQUIRED_OASLANA_119_TOOLS = {
    "pcb_place_component",
    "pcb_route_trace",
    "pcb_add_zone",
    "pcb_set_design_rules",
    "pcb_move_component",
    "pcb_delete_object",
    "sch_add_component",
    "sch_modify_property",
}

FILE_BACKED_SCHEMATIC_WRITE_TOOLS = {
    "sch_add_symbol",
    "sch_add_wire",
    "sch_add_label",
    "sch_update_properties",
    "sch_build_circuit",
    "sch_annotate",
}


def test_is_allowed_for_known_tools_and_profiles() -> None:
    assert is_allowed("kicad_set_project", "minimal") is True
    assert is_allowed("sch_add_symbol", "schematic_only") is True
    assert is_allowed("sch_add_symbol", "minimal") is False
    assert is_allowed("pcb_add_track", "pcb_only") is True
    assert is_allowed("missing_tool", "agent_full") is False


def test_minimal_profile_only_has_read_project_tools() -> None:
    records = tools_for_profile("minimal")

    assert records
    assert {record.tier for record in records} == {AccessTier.READ}
    assert {record.name for record in records} == {
        "kicad_set_project",
        "project_get_design_spec",
        "project_quality_gate_report",
        "kicad_health",
        "kicad_doctor",
    }


def test_manufacturing_package_requires_human_gate() -> None:
    record = get("export_manufacturing_package")

    assert record is not None
    assert record.human_gate_required is True
    assert record.tier == AccessTier.HUMAN_ONLY
    assert record.supports_dry_run is True


def test_registered_tools_have_valid_verification_levels() -> None:
    valid_levels = {"verified", "experimental", "planned"}

    assert all_records()
    for record in all_records().values():
        assert record.verification_level in valid_levels


def test_oaslana_119_live_editing_tools_require_kicad_ipc() -> None:
    records = all_records()

    assert REQUIRED_OASLANA_119_TOOLS.issubset(records)
    for tool_name in REQUIRED_OASLANA_119_TOOLS:
        record = records[tool_name]
        assert record.runtime is RuntimeRequirement.KICAD_IPC
        assert record.tier is AccessTier.WRITE


def test_file_backed_schematic_write_tools_do_not_require_kicad_ipc() -> None:
    records = all_records()

    assert FILE_BACKED_SCHEMATIC_WRITE_TOOLS.issubset(records)
    for tool_name in FILE_BACKED_SCHEMATIC_WRITE_TOOLS:
        record = records[tool_name]
        assert record.runtime is RuntimeRequirement.NONE
        assert record.tier is AccessTier.WRITE


def test_profile_results_are_copies() -> None:
    records = all_records()
    records.clear()

    assert all_records()
