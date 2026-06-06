---
name: kicad-pcb-review
description: KiCad PCB review and manufacturing readiness agent skill for Cursor.
---

# KiCad PCB Review Skill

Use this skill when the task involves KiCad PCB projects, schematic review, DRC/ERC, DFM, manufacturing exports, BOM generation, or release preparation.

## Workflow

1. **Verify**: Call `kicad_get_project_info` and `project_quality_gate`.
2. **Inspect**: Read current schematic and PCB state before editing.
3. **Edit**: Explain changes, use dry-run if available, ask for confirmation.
4. **Validate**: After any edit, run ERC → DRC → DFM checks.
5. **Release**: Run full validation, export all artifacts, generate manifest.

## Read-only First

Always prefer these tools unless modification is explicitly requested:
- `kicad_get_project_info`, `sch_get_symbols`, `pcb_get_board_summary`
- `run_erc`, `run_drc`, `validate_design`, `project_quality_gate`

## Refusal

Do not claim manufacturing readiness without passing all quality gates.
