# Toolset Profiles

KiCad MCP has over 170 tools. To reduce context token usage in AI agents, use toolset profiles to expose only the tools needed for each task.

## Available Toolsets

| Profile | Tools | Use Case |
|---------|-------|----------|
| `readonly` | ~10 | Inspection, ERC/DRC, quality gates |
| `schematic` | ~5 | Schematic design |
| `pcb_layout` | ~7 | PCB layout and routing |
| `manufacturing` | ~11 | Gerber export, DFM, BOM, release |
| `simulation` | ~3 | SPICE simulation |
| `high_speed` | ~5 | High-speed design review |
| `full_write` | ~22 | Full unrestricted access (dangerous) |

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
