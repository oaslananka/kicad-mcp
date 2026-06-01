from __future__ import annotations

from kicad_mcp.tools.fixers import (
    BLOCKING_GATES,
    GATE_FIXERS,
    FixerAction,
    auto_fix_description,
    first_agent_action,
    fixers_for_gate,
    sampling_prompt_for_gate,
)


def test_fixers_registry_helpers() -> None:
    schematic_fixers = fixers_for_gate("Schematic")
    assert len(schematic_fixers) == 3
    assert auto_fix_description("Schematic") == "Annotate un-annotated schematic symbols."
    assert first_agent_action("Schematic").tool == "sch_get_bounding_boxes"

    assert fixers_for_gate("Unknown") == []
    assert auto_fix_description("Unknown") is None
    assert first_agent_action("Unknown") is None

    assert "Schematic" in BLOCKING_GATES
    assert "Schematic connectivity" in BLOCKING_GATES


def test_sampling_prompt_for_gate_includes_trimmed_details() -> None:
    prompt = sampling_prompt_for_gate(
        "Placement",
        "Caps too far",
        [f"detail-{index}" for index in range(10)],
    )

    assert "Gate: Placement" in prompt
    assert "Summary: Caps too far" in prompt
    assert "- detail-0" in prompt
    assert "- detail-7" in prompt
    assert "detail-8" not in prompt


def test_all_callable_imports_resolve() -> None:
    from kicad_mcp.tools.fixers import validate_callable_imports

    assert validate_callable_imports(GATE_FIXERS) == []


def test_validate_callable_imports_logs_invalid_paths(monkeypatch) -> None:
    from kicad_mcp.tools import fixers

    warnings: list[tuple[str, dict[str, object]]] = []
    monkeypatch.setattr(
        fixers.logger,
        "warning",
        lambda event, **kwargs: warnings.append((event, kwargs)),
    )

    missing = fixers.validate_callable_imports(
        {
            "Bad gate": [
                FixerAction(
                    tool="bad_tool",
                    description="Bad import path for startup validation.",
                    auto_applicable=True,
                    callable_import="tools.not_a_module:missing",
                )
            ]
        }
    )

    assert missing == ["Bad gate: tools.not_a_module:missing"]
    assert warnings[0][0] == "fixer_callable_import_invalid"
