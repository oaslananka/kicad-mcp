"""Prompt templates for common KiCad workflows."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from mcp.types import TextContent


def render_professional_circuit_design_prompt(
    *,
    circuit_description: str = "",
    board_size_mm: str = "100x80",
    layer_count: str = "2",
    target_fab: str = "jlcpcb_standard",
    design_notes: str = "",
) -> str:
    """Render the canonical professional circuit design workflow prompt."""
    notes = f"\n\nDesign intent summary:\n{design_notes.strip()}" if design_notes.strip() else ""
    return f"""
# Professional Circuit Design Workflow

Circuit: {circuit_description or "(not specified)"}
Board: {board_size_mm} mm, {layer_count} copper layer(s), target fab {target_fab}

1. Project setup:
   - `kicad_get_version()`
   - `kicad_create_new_project()` or `kicad_set_project()`
   - `project_set_design_intent()` before schematic work
   - Read `kicad://project/info`
2. Schematic capture:
   - Use `sch_find_free_placement()` before placing symbols
   - Add power symbols before dependent circuits
   - Route wires, then call `sch_add_missing_junctions()`
   - Run `sch_check_power_flags()` and `run_erc()`
3. PCB transfer and placement:
   - `pcb_set_board_outline()`
   - `pcb_sync_from_schematic()`; the pre-sync gate blocks dirty schematics
   - `pcb_auto_place_force_directed()` or the automatic sync placement result
   - `pcb_place_decoupling_caps()`
4. Routing:
   - `route_export_dsn()`
   - `route_autoroute_freerouting()`
   - `route_import_ses()`
   - `pcb_refill_zones()`
5. Validation and release:
   - `project_full_validation_loop(max_iterations=5)`
   - `pcb_score_placement()`
   - `check_design_for_manufacture(profile="{target_fab}")`
   - `export_manufacturing_package()` only after `project_quality_gate()` is PASS

Do not skip a stage. If a gate fails, read `kicad://project/fix_queue`, apply the
first recommended fix, and rerun the relevant gate.{notes}
""".strip()


def register(mcp: FastMCP) -> None:
    """Register reusable workflow prompts."""

    @mcp.prompt()
    def first_pcb(
        component_count: str = "10",
        board_size_mm: str = "50x50",
        layers: str = "2",
    ) -> list[TextContent]:
        """Guide an agent through a first-board workflow."""
        text = f"""
Design a new KiCad PCB with approximately {component_count} components, a board size of
{board_size_mm} mm, and {layers} copper layers.

Workflow:
1. Call `kicad_get_version()`.
2. Call `kicad_set_project()` or `kicad_create_new_project()`.
3. Review `kicad://project/info` and `kicad://board/summary`.
4. Define the outline with `pcb_set_board_outline()`.
5. Populate the schematic using the schematic and library tools.
6. Run `run_erc()` and fix issues before layout.
7. Route with PCB tools.
8. Run `run_drc()` and `check_design_for_manufacture()`.
9. Export a manufacturing package.
""".strip()
        return [TextContent(type="text", text=text)]

    @mcp.prompt()
    def schematic_to_pcb() -> list[TextContent]:
        """Guide an agent from schematic capture to PCB layout."""
        text = """
Move a design from schematic capture to PCB layout.

1. Inspect the active project and schematic.
2. Add or update symbols, labels, buses, and power flags.
3. Run ERC and power checks.
4. Export the netlist.
5. Inspect footprints and assign missing ones.
6. Move footprints, then do not skip the post-placement routing pass:
   a. `route_export_dsn()`
   b. `route_autoroute_freerouting()` — Docker-first, JAR fallback
   c. `route_import_ses()`
   d. `pcb_refill_zones()`
   e. `run_drc()`
7. Compare PCB versus schematic footprints.
""".strip()
        return [TextContent(type="text", text=text)]

    @mcp.prompt()
    def professional_circuit_design(
        circuit_description: str = "",
        board_size_mm: str = "100x80",
        layer_count: str = "2",
        target_fab: str = "jlcpcb_standard",
    ) -> list[TextContent]:
        """Canonical workflow for a complete professional circuit design."""
        text = render_professional_circuit_design_prompt(
            circuit_description=circuit_description,
            board_size_mm=board_size_mm,
            layer_count=layer_count,
            target_fab=target_fab,
        )
        return [TextContent(type="text", text=text)]

    @mcp.prompt()
    def post_placement_routing() -> list[TextContent]:
        """Route a placed PCB through DSN, FreeRouting, SES import, and DRC."""
        text = """
Run the mandatory post-placement routing loop.

1. Confirm placement is acceptable with `pcb_score_placement()`.
2. Export routing input with `route_export_dsn()`.
3. Run `route_autoroute_freerouting()` — run this after placement and do not skip it.
4. Import the routed result with `route_import_ses()`.
5. Refill copper with `pcb_refill_zones()`.
6. Run `run_drc()` and inspect `kicad://project/fix_queue`.
7. Repeat only the failing step; do not restart schematic capture unless the transfer gate fails.
""".strip()
        return [TextContent(type="text", text=text)]

    @mcp.prompt()
    def manufacturing_export() -> list[TextContent]:
        """Checklist for manufacturing exports."""
        text = """
Run a manufacturing release pass. Treat `export_manufacturing_package()` as a release
step, not a debugging shortcut. In the `manufacturing` profile it is the only gated
manufacturing export tool.

1. `project_quality_gate()`
2. If the gate is not `PASS`, stop and fix the blocking issues first.
3. `pcb_transfer_quality_gate()`
4. `run_drc()`
5. `run_erc()`
6. `get_board_stats()`
7. `check_design_for_manufacture()`
8. If you need low-level debug or interchange artifacts, switch to a broader profile
   such as `full` or `minimal` and use the direct `export_*()` tools there.
9. Only after a clean gate, call `export_manufacturing_package()`.
""".strip()
        return [TextContent(type="text", text=text)]

    @mcp.prompt()
    def design_review_loop() -> list[TextContent]:
        """Closed-loop inspection workflow driven by quality gates."""
        text = """
Run a closed-loop design review instead of trusting a single build pass.

1. Inspect the current context:
   - `kicad://project/info`
   - `kicad://project/spec`
   - `kicad://project/quality_gate`
   - `kicad://project/fix_queue`
   - `kicad://project/next_action`
   - `kicad://schematic/connectivity`
   - `kicad://board/placement_quality`
   - `project_get_design_spec()`
2. Call the blocking gate tools directly when you need fresh detail:
   - `project_quality_gate()`
   - `project_quality_gate_report()`
   - `schematic_connectivity_gate()`
   - `pcb_transfer_quality_gate()`
   - `pcb_score_placement()`
   - `pcb_placement_quality_report()`
3. Fix the highest-severity blocking issue first.
4. Re-run the relevant gates after every fix.
5. Repeat until the full project gate is `PASS`.
6. Only then move on to release exports.
""".strip()
        return [TextContent(type="text", text=text)]

    @mcp.prompt()
    def fix_blocking_issues() -> list[TextContent]:
        """Prompt focused on consuming the fix queue and clearing blockers."""
        text = """
Use the project fix queue as the source of truth for what to fix next.

1. Read `kicad://project/fix_queue`.
2. Read `kicad://project/next_action`.
3. Pick the first blocking item unless `project_get_next_action()` surfaces
   a higher-priority blocker.
4. Use the suggested tool on that line to inspect or repair the issue.
5. If the blocker is spec-aware, refresh `project_get_design_spec()` or update it with
   `project_set_design_intent()`, then verify with `project_validate_design_spec()`
   before moving footprints again.
6. Re-run `project_quality_gate()` after the fix.
7. Stop only when the queue says there are no blocking issues left.
""".strip()
        return [TextContent(type="text", text=text)]

    @mcp.prompt()
    def manufacturing_release_checklist() -> list[TextContent]:
        """Final release checklist for fab-ready handoff."""
        text = """
Treat manufacturing release as a gated handoff.

1. Read `kicad://project/quality_gate`.
2. If the project gate is not `PASS`, stop immediately and clear blockers.
3. Read `kicad://project/fix_queue` to confirm nothing actionable remains.
4. Re-run:
   - `project_quality_gate()`
   - `pcb_transfer_quality_gate()`
   - `run_drc()`
   - `run_erc()`
   - `check_design_for_manufacture()`
5. If you need low-level debug artifacts, switch to a broader profile such as `full`
   or `minimal`; the `manufacturing` profile stays focused on gated release handoff.
6. Release with `export_manufacturing_package()` only after every gate is clean.
""".strip()
        return [TextContent(type="text", text=text)]

    @mcp.prompt()
    def high_speed_review_loop() -> list[TextContent]:
        """Agent loop for SI, stackup, routing, and high-speed checkpoint review."""
        text = """
Run a high-speed review loop for critical nets.

1. Read `kicad://project/design_intent` and confirm `critical_nets`.
2. Run `pcb_get_stackup()` and check dielectric/copper assumptions.
3. Run `route_tune_time_domain()` for each timing-critical net.
4. Run `si_check_via_stub()` and look for critical-frequency resonance warnings.
5. Run `emc_check_return_path_continuity(reference_plane_layer="auto")`.
6. Re-route or add stitching vias where the return path is weak.
7. Run `route_autoroute_freerouting()` only when DSN/SES staging is ready.
8. Re-check SI/EMC and create a `vcs_commit_checkpoint()` when the board improves.
""".strip()
        return [TextContent(type="text", text=text)]

    @mcp.prompt()
    def new_board_bringup() -> list[TextContent]:
        """Agent loop for starting a new board from schematic through first DRC."""
        text = """
Bring up a new board in small reversible steps.

1. Set or create the project with `kicad_set_project()` / `kicad_create_new_project()`.
2. Capture or import the schematic and run `run_erc()`.
3. Assign footprints and verify `validate_footprints_vs_schematic()`.
4. Define board outline, stackup, and basic design rules.
5. Run `pcb_auto_place_by_schematic()` and inspect `pcb_score_placement()`.
6. Route critical nets first, refill zones, and run `run_drc()`.
7. Commit checkpoints after every clean gate.
""".strip()
        return [TextContent(type="text", text=text)]

    @mcp.prompt()
    def dfm_polish_loop() -> list[TextContent]:
        """Agent loop for manufacturer-specific DFM cleanup."""
        text = """
Polish the design against a manufacturer profile.

1. Load the target profile with `dfm_load_manufacturer_profile()`.
2. Run `dfm_run_manufacturer_check()` and `project_quality_gate()`.
3. Fix hard blockers first: trace/space, drill, annular ring, silk, courtyard.
4. Re-run DFM after each fix and read `kicad://project/fix_queue`.
5. Stop for human review if a warning requires a fab-specific decision.
6. Export only with `export_manufacturing_package()` after the gates pass.
""".strip()
        return [TextContent(type="text", text=text)]

    @mcp.prompt()
    def regression_sweep() -> list[TextContent]:
        """CI-style prompt for repeatable ERC, DRC, and quality-gate regression checks."""
        text = """
Run a repeatable project regression sweep.

1. Read `kicad://project/manifest` to capture the file/hash baseline.
2. Run `run_erc()` and `run_drc()`.
3. Run `project_quality_gate()` and `project_quality_gate_report()`.
4. Read `kicad://project/gate_history` and compare current outcomes.
5. Report any new FAIL/BLOCKED gate before release work continues.
""".strip()
        return [TextContent(type="text", text=text)]
