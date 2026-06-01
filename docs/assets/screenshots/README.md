# Screenshot Capture Manifest

The committed PNG files in this directory are deterministic placeholders
rendered by `scripts/render_screenshots.py`. They reserve the public listing
slots for real client captures while keeping the repository ready for directory
review dry runs.

Each replacement must preserve the filename and the 1920x1080 dimensions. Do not
include private project paths, tokens, usernames, local hostnames, customer data,
or unreleased board files in screenshots.

| File | Intended real capture | Client | Fixture project | Exact tool call |
|---|---|---|---|---|
| `01-claude-desktop-quality-gate.png` | Quality gate review with pass/fix queue visible | Claude Desktop | `tests/fixtures/benchmark_projects/pass_sensor_node/demo.kicad_pro` | `project_quality_gate` |
| `02-cursor-schematic-build.png` | Schematic construction prompt and result summary | Cursor | `tests/fixtures/benchmark_projects/pass_sensor_node/demo.kicad_pro` | `sch_build_circuit` |
| `03-vscode-pcb-inspection.png` | Board state inspection with safe read-only result | VS Code MCP | `tests/fixtures/benchmark_projects/pass_sensor_node/demo.kicad_pro` | `pcb_get_board_state` |
| `04-tools-reference.png` | Tools reference catalog page or generated tool table | Browser/docs | `tests/fixtures/benchmark_projects/pass_sensor_node/demo.kicad_pro` | `kicad_list_tool_categories` |
| `05-export-manufacturing.png` | Manufacturing export gate result showing gated release posture | Claude Desktop | `tests/fixtures/benchmark_projects/pass_sensor_node/demo.kicad_pro` | `export_manufacturing_package` |

Replacement checklist:

1. Open the fixture project from the repository path, not a private board.
2. Run the exact tool call listed above through the named client.
3. Capture at 1920x1080 or crop/export to exactly 1920x1080.
4. Preserve the existing filename.
5. Re-run `pnpm run assets:screenshots` only when regenerating placeholders; do
   not run it after adding real captures because it will overwrite them.
6. In final submission mode, `pnpm run submission:check` with `SUBMISSION_MODE=1`
   fails if these placeholder hashes are still present.
