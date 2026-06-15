# KiCad Capability Parity (generated)

Machine-generated from `docs/compatibility/capability-parity-matrix.yaml`. Refresh with `uv run python scripts/build_parity_matrix.py`.

KiCad baseline: `10.0.x` · Updated: 2026-06-16

**Overall: 52 / 74 programmatically-reachable capabilities driven = 70.3%** (20 partial, 2 gap; 4 GUI-only with no KiCad API, excluded from the denominator).

## Coverage by domain

| Domain | Coverage | Covered | Partial | Gap | GUI-only (no API) |
|---|---:|---:|---:|---:|---:|
| `schematic_edit` | 84.6% | 11 | 2 | 0 | 1 |
| `pcb_edit` | 75.0% | 12 | 4 | 0 | 1 |
| `routing` | 66.7% | 4 | 2 | 0 | 1 |
| `library` | 57.1% | 4 | 3 | 0 | 0 |
| `analysis` | 27.3% | 3 | 7 | 1 | 0 |
| `export` | 100.0% | 9 | 0 | 0 | 0 |
| `project` | 80.0% | 4 | 1 | 0 | 0 |
| `cosmetics` | 71.4% | 5 | 1 | 1 | 1 |
| **Overall** | **70.3%** | 52 | 20 | 2 | 4 |

## Closeable surface (gap, then partial)

| Domain | Capability | Status | Channel | MCP tool | Notes |
|---|---|---|---|---|---|
| `analysis` | 2D/3D field / EM solver for impedance & coupling | `gap` | `file` | — | No field-solver integration yet; this is the Phase 3 (P3-T1/T3) accuracy upgrade. |
| `cosmetics` | Import a logo/bitmap as board art (bitmap2component) | `gap` | `cli` | — | KiCad's bitmap-to-silkscreen conversion has no MCP driver yet. |
| `analysis` | DC IR-drop / voltage-drop analysis | `partial` | `file` | `pdn_calculate_voltage_drop` | First-order estimate; distributed IR-drop / current-density solver is Phase 3 (P3-T2). |
| `analysis` | Decoupling recommendation / power-plane generation | `partial` | `file` | `pdn_recommend_decoupling_caps` | pdn_generate_power_plane covered; frequency-domain PDN target-Z synthesis is Phase 3 (P3-T2). |
| `analysis` | Differential-pair skew gate | `partial` | `file` | `si_check_differential_pair_skew` | Currently cannot return FAIL (work order K2); real PASS/WARN/FAIL is P1-T3, localized phase-skew is Phase 3 (P3-T3). |
| `analysis` | EMC layout compliance checks | `partial` | `file` | `emc_run_full_compliance` | Presence/heuristic checks with fixed Er (work order K2/K10); EM-result-based, standard-named, fail-capable checks are Phase 3 (P3-T5). |
| `analysis` | Length-matching validation | `partial` | `file` | `si_validate_length_matching` | Threshold-only; hard FAIL gating is P1-T3. |
| `analysis` | Single-ended / differential trace impedance | `partial` | `file` | `si_calculate_trace_impedance` | First-order closed-form (IPC-2141/Wheeler) estimate ~5-10% (work order K4); field-solver accuracy is Phase 3 (P3-T1). |
| `analysis` | Thermal via / copper-pour sizing | `partial` | `file` | `thermal_calculate_via_count` | thermal_check_copper_pour; proximity heuristic, real thermal network/FEA is Phase 3 (P3-T4). |
| `cosmetics` | Set drawing-sheet title-block fields | `partial` | `ipc` | `pcb_set_title_block_info` | Registered but orphaned (hidden from every profile); surfaced in P1-T2. |
| `library` | Generate an IPC-7351 footprint | `partial` | `file` | `lib_generate_footprint_ipc7351` | Footprint family coverage is limited (work order K10: SOT-23 implemented, SOT-223/SOT-89 not yet); datasheet/IPC validation hard-gate is Phase 4 (P4-T3). |
| `library` | Recommend / bind a part to a symbol | `partial` | `file` | `lib_recommend_part` | lib_bind_part_to_symbol; depends on the same sourcing backends as above. |
| `library` | Source live component data (price/stock/lifecycle) | `partial` | `file` | `lib_search_components` | Distributor clients (Nexar/DigiKey) are stubs requiring authenticated deployment (work order K10); real APIs land in Phase 4 (P4-T3). |
| `pcb_edit` | Auto-place footprints from schematic | `partial` | `ipc` | `pcb_auto_place_by_schematic` | Force-directed placement (pcb_auto_place_force_directed) is non-deterministic under a wall-clock cap (work order K7); deterministic placement is Phase 4 (P4-T2). |
| `pcb_edit` | Begin / push / revert an IPC commit transaction | `partial` | `ipc` | `pcb_push_commit` | pcb_begin_commit/push_commit/drop_commit/revert registered but orphaned; P1-T2. |
| `pcb_edit` | Read / set board groups | `partial` | `ipc` | `pcb_get_groups` | Tool is registered but orphaned (declared in no router category, hidden from every profile); surfaced in Phase 1 (P1-T2). |
| `pcb_edit` | Read / set drawing origin | `partial` | `ipc` | `pcb_set_origin` | pcb_get_origin/pcb_set_origin registered but orphaned (hidden from every profile); P1-T2. |
| `project` | Job sets (export automation) | `partial` | `cli` | `jobset_export` | jobset_run / jobset_validate are registered but orphaned (hidden from every profile); surfaced in P1-T2. |
| `routing` | Export Specctra DSN / import routed SES | `partial` | `cli` | `route_export_dsn` | route_import_ses stages but does not yet import headlessly (K1); honest manual-step surfacing is P1-T7. |
| `routing` | Full autoroute (FreeRouting orchestration) | `partial` | `cli` | `route_autoroute_freerouting` | End-to-end headless route is not yet wired; DSN export / SES import may require a manual KiCad step (work order K1). Full solution is Phase 4 (P4-T1). |
| `schematic_edit` | Modify a symbol property by reference | `partial` | `ipc` | `sch_modify_property` | Text-level property write uses regex fallback (work order K5); round-trip-safe AST is Phase 2 (P2-T1). |
| `schematic_edit` | Swap pins / gates | `partial` | `file` | `sch_swap_pins` | Experimental; sch_swap_gates is also experimental and profile-gated. |

## Full matrix

### `schematic_edit`

Symbol/wire/label/bus/hierarchy/power/no-connect/annotate/ERC editing of .kicad_sch.

| Capability | Channel | MCP tool | Status | KiCad | Notes |
|---|---|---|---|---|---|
| Place a library symbol at an absolute coordinate | `file` | `sch_add_symbol` | `covered` | 10.0.x | sch_add_component covers the by-library convenience path. |
| Move a placed symbol | `file` | `sch_move_symbol` | `covered` | 10.0.x |  |
| Delete a placed symbol and attached wires | `file` | `sch_delete_symbol` | `covered` | 10.0.x |  |
| Add a wire between points / between pins | `file` | `sch_route_wire_between_pins` | `covered` | 10.0.x | sch_add_wire for raw segments; sch_add_missing_junctions repairs T-junctions. |
| Add local / global / hierarchical labels | `file` | `sch_add_label` | `covered` | 10.0.x | sch_add_global_label, sch_add_hierarchical_label, sch_move_label, sch_delete_label. |
| Add a bus and bus-wire entries | `file` | `sch_add_bus` | `covered` | 10.0.x | sch_add_bus_wire_entry for member entries. |
| Add a power symbol / power flag | `file` | `sch_add_power_symbol` | `covered` | 10.0.x | sch_check_power_flags audits coverage. |
| Add no-connect markers | `file` | `sch_add_no_connect` | `covered` | 10.0.x |  |
| Create and wire hierarchical sheets | `file` | `sch_create_sheet` | `covered` | 10.0.x | sch_list_sheets / sch_get_sheet_info for inspection. |
| Annotate references | `file` | `sch_annotate` | `covered` | 10.0.x |  |
| Run ERC and inspect violations | `cli` | `run_erc` | `covered` | 10.0.x | erc_set_rule_severity / erc_list_rules tune severities. |
| Modify a symbol property by reference | `ipc` | `sch_modify_property` | `partial` | 10.0.x | Text-level property write uses regex fallback (work order K5); round-trip-safe AST is Phase 2 (P2-T1). |
| Swap pins / gates | `file` | `sch_swap_pins` | `partial` | 10.0.x | Experimental; sch_swap_gates is also experimental and profile-gated. |
| Interactive symbol graphic drawing in the editor | `gui-only` | — | `gui-only-no-api` | 10.0.x | Custom symbol bodies are created via lib_create_custom_symbol; freehand editor drawing is GUI-only. |

### `pcb_edit`

Footprint place/move, track/via/zone/stackup/rules/groups/teardrops/fanout on .kicad_pcb.

| Capability | Channel | MCP tool | Status | KiCad | Notes |
|---|---|---|---|---|---|
| Place / move a footprint | `ipc` | `pcb_place_component` | `covered` | 10.0.x | pcb_move_footprint / pcb_move_component for relocation. |
| Add a track / route a trace | `ipc` | `pcb_add_track` | `covered` | 10.0.x | pcb_route_trace, pcb_add_tracks_bulk for batches. |
| Add through / blind / micro vias | `ipc` | `pcb_add_via` | `covered` | 10.0.x | pcb_add_blind_via, pcb_add_microvia. |
| Add and refill copper zones | `ipc` | `pcb_add_copper_zone` | `covered` | 10.0.x | pcb_add_zone, pcb_refill_zones. |
| Read / set the layer stackup | `file` | `pcb_set_stackup` | `covered` | 10.0.x | pcb_get_stackup for inspection. |
| Read / set design rules | `file` | `pcb_set_design_rules` | `covered` | 10.0.x | pcb_get_design_rules; drc_rule_create/delete/enable for custom rules. |
| Assign net classes | `file` | `pcb_set_net_class` | `covered` | 10.0.x | route_set_net_class_rules for routing constraints. |
| Add teardrops | `ipc` | `pcb_add_teardrops` | `covered` | 10.0.x |  |
| BGA / fine-pitch fanout | `ipc` | `pcb_bga_fanout` | `covered` | 10.0.x |  |
| Set the board outline | `ipc` | `pcb_set_board_outline` | `covered` | 10.0.x |  |
| Auto-place footprints from schematic | `ipc` | `pcb_auto_place_by_schematic` | `partial` | 10.0.x | Force-directed placement (pcb_auto_place_force_directed) is non-deterministic under a wall-clock cap (work order K7); deterministic placement is Phase 4 (P4-T2). |
| Run DRC and inspect violations | `cli` | `run_drc` | `covered` | 10.0.x | drc_add_exclusion / drc_validate_exclusions manage waivers. |
| Manage design blocks / reusable groups | `file` | `pcb_block_create_from_selection` | `covered` | 10.0.x | pcb_block_list, pcb_block_place. |
| Read / set board groups | `ipc` | `pcb_get_groups` | `partial` | 10.0.x | Tool is registered but orphaned (declared in no router category, hidden from every profile); surfaced in Phase 1 (P1-T2). |
| Read / set drawing origin | `ipc` | `pcb_set_origin` | `partial` | 10.0.x | pcb_get_origin/pcb_set_origin registered but orphaned (hidden from every profile); P1-T2. |
| Begin / push / revert an IPC commit transaction | `ipc` | `pcb_push_commit` | `partial` | 10.0.x | pcb_begin_commit/push_commit/drop_commit/revert registered but orphaned; P1-T2. |
| Interactive push-and-shove routing | `gui-only` | — | `gui-only-no-api` | 10.0.x | KiCad's interactive router (push/shove, walkaround) has no IPC/CLI surface. |

### `routing`

Autoroute, length/skew tuning, diff-pair, and interactive routing.

| Capability | Channel | MCP tool | Status | KiCad | Notes |
|---|---|---|---|---|---|
| Route a single track / pad-to-pad | `ipc` | `route_single_track` | `covered` | 10.0.x | route_from_pad_to_pad. |
| Route a differential pair | `ipc` | `route_differential_pair` | `covered` | 10.0.x |  |
| Tune track / diff-pair length | `file` | `route_tune_length` | `covered` | 10.0.x | tune_diff_pair_length, route_tune_time_domain, tuning-profile tools. |
| Full autoroute (FreeRouting orchestration) | `cli` | `route_autoroute_freerouting` | `partial` | 10.0.x | End-to-end headless route is not yet wired; DSN export / SES import may require a manual KiCad step (work order K1). Full solution is Phase 4 (P4-T1). |
| Export Specctra DSN / import routed SES | `cli` | `route_export_dsn` | `partial` | 10.0.x | route_import_ses stages but does not yet import headlessly (K1); honest manual-step surfacing is P1-T7. |
| Set per-net-class routing rules | `file` | `route_set_net_class_rules` | `covered` | 10.0.x |  |
| Interactive length tuning / meander drawing | `gui-only` | — | `gui-only-no-api` | 10.0.x | Interactive trace tuning UX is GUI-only; programmatic tuning is modeled by route_tune_length. |

### `library`

Symbol/footprint/3D generation + assignment + part sourcing.

| Capability | Channel | MCP tool | Status | KiCad | Notes |
|---|---|---|---|---|---|
| Search symbols / footprints | `file` | `lib_search_symbols` | `covered` | 10.0.x | lib_search_footprints, lib_list_libraries, lib_rebuild_index. |
| Assign a footprint to a symbol | `file` | `lib_assign_footprint` | `covered` | 10.0.x |  |
| Create a custom symbol | `file` | `lib_create_custom_symbol` | `covered` | 10.0.x | lib_generate_symbol_from_pintable for pin-table-driven generation. |
| Generate an IPC-7351 footprint | `file` | `lib_generate_footprint_ipc7351` | `partial` | 10.0.x | Footprint family coverage is limited (work order K10: SOT-23 implemented, SOT-223/SOT-89 not yet); datasheet/IPC validation hard-gate is Phase 4 (P4-T3). |
| Assign / manage 3D models | `file` | `lib_set_3d_model_path` | `covered` | 10.0.x | lib_bulk_assign_3d_models, lib_search_3d_models, lib_remove_3d_model. |
| Source live component data (price/stock/lifecycle) | `file` | `lib_search_components` | `partial` | 10.0.x | Distributor clients (Nexar/DigiKey) are stubs requiring authenticated deployment (work order K10); real APIs land in Phase 4 (P4-T3). |
| Recommend / bind a part to a symbol | `file` | `lib_recommend_part` | `partial` | 10.0.x | lib_bind_part_to_symbol; depends on the same sourcing backends as above. |

### `analysis`

SI / PI / EMC / thermal / DFM / SPICE analysis.

| Capability | Channel | MCP tool | Status | KiCad | Notes |
|---|---|---|---|---|---|
| Single-ended / differential trace impedance | `file` | `si_calculate_trace_impedance` | `partial` | 10.0.x | First-order closed-form (IPC-2141/Wheeler) estimate ~5-10% (work order K4); field-solver accuracy is Phase 3 (P3-T1). |
| Differential-pair skew gate | `file` | `si_check_differential_pair_skew` | `partial` | 10.0.x | Currently cannot return FAIL (work order K2); real PASS/WARN/FAIL is P1-T3, localized phase-skew is Phase 3 (P3-T3). |
| Length-matching validation | `file` | `si_validate_length_matching` | `partial` | 10.0.x | Threshold-only; hard FAIL gating is P1-T3. |
| Synthesize a stackup for target interfaces | `file` | `si_synthesize_stackup_for_interfaces` | `covered` | 10.0.x | si_generate_stackup, si_bind_interfaces_to_net_classes, si_list_dielectric_materials. |
| DC IR-drop / voltage-drop analysis | `file` | `pdn_calculate_voltage_drop` | `partial` | 10.0.x | First-order estimate; distributed IR-drop / current-density solver is Phase 3 (P3-T2). |
| Decoupling recommendation / power-plane generation | `file` | `pdn_recommend_decoupling_caps` | `partial` | 10.0.x | pdn_generate_power_plane covered; frequency-domain PDN target-Z synthesis is Phase 3 (P3-T2). |
| Thermal via / copper-pour sizing | `file` | `thermal_calculate_via_count` | `partial` | 10.0.x | thermal_check_copper_pour; proximity heuristic, real thermal network/FEA is Phase 3 (P3-T4). |
| EMC layout compliance checks | `file` | `emc_run_full_compliance` | `partial` | 10.0.x | Presence/heuristic checks with fixed Er (work order K2/K10); EM-result-based, standard-named, fail-capable checks are Phase 3 (P3-T5). |
| DFM manufacturer checks and cost | `file` | `dfm_run_manufacturer_check` | `covered` | 10.0.x | dfm_load_manufacturer_profile, dfm_calculate_manufacturing_cost. |
| SPICE simulation (op / AC / transient / DC sweep) | `cli` | `sim_run_transient` | `covered` | 10.0.x | ngspice engine; sim_run_operating_point/ac_analysis/dc_sweep, sim_check_stability. |
| 2D/3D field / EM solver for impedance & coupling | `file` | — | `gap` | 10.0.x | No field-solver integration yet; this is the Phase 3 (P3-T1/T3) accuracy upgrade. |

### `export`

Gerber/drill/BOM/POS/STEP/ODB/IPC2581/SVG/PDF/3D manufacturing outputs.

| Capability | Channel | MCP tool | Status | KiCad | Notes |
|---|---|---|---|---|---|
| Gerber export | `cli` | `export_gerber` | `covered` | 10.0.x |  |
| Drill export | `cli` | `export_drill` | `covered` | 10.0.x |  |
| BOM export | `cli` | `export_bom` | `covered` | 10.0.x | export_sch_python_bom for the Python BOM path. |
| Pick-and-place (POS/CPL) export | `cli` | `export_pick_and_place` | `covered` | 10.0.x | mfg_correct_cpl_rotations for fab rotation fixups. |
| STEP / 3D model export | `cli` | `export_step` | `covered` | 10.0.x | export_stepz, export_glb, export_vrml, export_stl, export_ply, export_brep, export_u3d. |
| IPC-2581 / ODB++ interchange export | `cli` | `export_ipc2581` | `covered` | 10.0.x | export_odb. |
| SVG / PDF / DXF documentation export | `cli` | `export_pcb_pdf` | `covered` | 10.0.x | export_sch_pdf, export_svg, export_dxf, export_sch_svg, export_sch_dxf. |
| Netlist export | `cli` | `export_netlist` | `covered` | 10.0.x | export_spice_netlist. |
| Release-gated manufacturing package | `cli` | `export_manufacturing_package` | `covered` | 10.0.x | Hard-gated on project_quality_gate PASS. |

### `project`

Variants, embedded files, jobsets, VCS, and design intent.

| Capability | Channel | MCP tool | Status | KiCad | Notes |
|---|---|---|---|---|---|
| Assembly variants (create / activate / diff / export) | `file` | `variant_create` | `covered` | 10.0.x | variant_set_active, variant_diff_bom, variant_export_bom, variant_clone. |
| Embedded project files | `file` | `project_embed_file` | `covered` | 10.0.x | project_list_embedded_files, project_extract_embedded_file, project_remove_embedded_file. |
| Job sets (export automation) | `cli` | `jobset_export` | `partial` | 10.0.x | jobset_run / jobset_validate are registered but orphaned (hidden from every profile); surfaced in P1-T2. |
| Version-control checkpoints | `file` | `vcs_commit_checkpoint` | `covered` | 10.0.x | vcs_init_git, vcs_list_checkpoints, vcs_restore_checkpoint, vcs_diff_with_checkpoint, vcs_tag_release. |
| Capture / infer design intent and spec | `file` | `project_set_design_intent` | `covered` | 10.0.x | project_get_design_spec, project_infer_design_spec, project_validate_design_spec. |

### `cosmetics`

Silk, board art, drawing sheet / title block, fab notes, fiducials, mounting holes.

| Capability | Channel | MCP tool | Status | KiCad | Notes |
|---|---|---|---|---|---|
| Add silkscreen / fab text | `ipc` | `pcb_add_text` | `covered` | 10.0.x |  |
| Add a barcode / data-matrix | `file` | `pcb_add_barcode` | `covered` | 10.0.x |  |
| Add fiducials | `ipc` | `pcb_add_fiducial_marks` | `covered` | 10.0.x |  |
| Add mounting holes | `ipc` | `pcb_add_mounting_holes` | `covered` | 10.0.x |  |
| Add inner-layer graphics to a footprint | `file` | `add_footprint_inner_layer_graphic` | `covered` | 10.0.x |  |
| Set drawing-sheet title-block fields | `ipc` | `pcb_set_title_block_info` | `partial` | 10.0.x | Registered but orphaned (hidden from every profile); surfaced in P1-T2. |
| Import a logo/bitmap as board art (bitmap2component) | `cli` | — | `gap` | 10.0.x | KiCad's bitmap-to-silkscreen conversion has no MCP driver yet. |
| Custom drawing-sheet (.kicad_wks) template design | `gui-only` | — | `gui-only-no-api` | 10.0.x | The page-layout editor is interactive; no headless drawing-sheet authoring surface. |
