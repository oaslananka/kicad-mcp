# KiCad MCP — OpenCode Usage Guide

When the task involves KiCad, PCB design, schematic review, ERC/DRC, manufacturing export, BOM, routing, DFM, or KiCad project files, use the `kicad` MCP server.

## Default Policy

1. **Inspect before editing.** Always read current project state first.
2. **Run quality gates.** Use `project_quality_gate` before suggesting release.
3. **Never run destructive tools** without explicit user confirmation.
4. **Prefer read-only tools** unless the user asks to modify the project.
5. **After edits**, run ERC/DRC and summarize changed files.

## Tool Categories

| Category | Behavior |
|----------|----------|
| `kicad_*` | All KiCad MCP tools |
| `write` | File write operations — set to "ask" |
| `bash` | Shell execution — set to "ask" |

## Quick Start

```bash
# Install the MCP server
uvx kicad-mcp-pro
```

In OpenCode, the kicad tools appear automatically once configured in `opencode.json`.
