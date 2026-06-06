# KiCad MCP — GitHub Copilot Instructions

When working on a KiCad project in this repository:

1. Use the `kicad` MCP server for PCB and schematic operations.
2. Start with read-only tools: `kicad_get_project_info`, `pcb_get_board_summary`, `sch_get_symbols`, `run_erc`, `run_drc`, `validate_design`.
3. Before any edit, inspect the current board and schematic state.
4. After any edit, run ERC and DRC to verify correctness.
5. For manufacturing readiness, run the full validation loop and export checks.
6. Do not claim manufacturing readiness without passing all quality gates.
7. Prefer non-destructive inspection unless the user explicitly requests modification.

## Tool Categories

| Category | Tools | Approval |
|----------|-------|----------|
| Read-only | `kicad_get_project_info`, `pcb_get_board_summary`, `sch_get_symbols`, `run_erc`, `run_drc`, `validate_design`, `project_quality_gate` | None needed |
| Write | `pcb_add_*`, `sch_add_*`, `route_*`, `export_*` | User confirmation required |
| Destructive | `git_restore_checkpoint`, `project_auto_fix_loop` | Explicit user approval |
