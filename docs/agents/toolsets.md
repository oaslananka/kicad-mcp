# Toolset Profiles

KiCad MCP has 300+ tools. To reduce context token usage in AI agents, use toolset profiles to expose only the tools needed for each task.

`integrations/common/toolsets.json` is **generated from the router profile source of
truth** (`src/kicad_mcp/tools/router.py`) by `scripts/build_toolsets.py`; each toolset
resolves to a router profile (and operating mode). Do not edit it by hand — run
`pnpm run toolsets:build`. CI enforces it never drifts (`pnpm run toolsets:check`) and
that every listed tool is really registered.

## Available Toolsets

| Profile | Router profile / mode | Tools | Use Case |
|---------|-----------------------|------:|----------|
| `readonly` | `agent_full` / readonly | 183 | Inspection, ERC/DRC, quality gates |
| `schematic` | `schematic` | 173 | Schematic design, library, export |
| `pcb_layout` | `pcb_only` | 112 | PCB layout and routing |
| `manufacturing` | `manufacturing` | 110 | Gerber export, DFM, BOM, release |
| `simulation` | `simulation` | 154 | SPICE simulation |
| `high_speed` | `high_speed` | 268 | High-speed design review |
| `full_write` | `agent_full` / experimental | 328 | Full unrestricted access (dangerous) |

Counts are derived; refresh this table from `toolsets.json` when profiles change.

## Using Toolsets

### Codex CLI
```toml
[mcp_servers.kicad]
enabled_tools = ["kicad_get_project_info", "project_quality_gate", "run_erc", "run_drc"]
```

### Gemini CLI
```json
{
  "mcpServers": {
    "kicad": {
      "includeTools": ["kicad_get_project_info", "project_quality_gate"]
    }
  }
}
```

### OpenCode
```json
{
  "agent": {
    "pcb-review": {
      "tools": { "kicad_*": true }
    }
  }
}
```

### VS Code
```json
{
  "sandbox": {
    "filesystem": { "allowWrite": ["${workspaceFolder}"] }
  }
}
```

## Why Use Toolsets?

- Reduces context token usage by MCP server tool registration
- Prevents accidental destructive operations
- Keeps agent focused on the task at hand
- Improves discovery latency (fewer tools to list)

## References

- `integrations/common/toolsets.json` — machine-readable toolset definitions
- `integrations/common/profiles.md` — deployment profiles
