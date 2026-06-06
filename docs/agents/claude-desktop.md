# Claude Desktop Integration

## Quick Start

```bash
kicad-mcp setup claude-desktop
```

Or manually:

### macOS
`~/Library/Application Support/Claude/claude_desktop_config.json`

### Windows
`%APPDATA%\Claude\claude_desktop_config.json`

### Linux
`~/.config/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "kicad": {
      "command": "uvx",
      "args": ["kicad-mcp-pro"],
      "env": {
        "KICAD_MCP_PROJECT_DIR": "/absolute/path/to/kicad/project",
        "KICAD_MCP_PROFILE": "analysis",
        "KICAD_MCP_OPERATING_MODE": "readonly"
      }
    }
  }
}
```

## Important

Claude Desktop local config is **separate** from Claude.ai custom connectors. Local config runs directly on your machine with full KiCad access. Claude.ai connectors require a public remote endpoint.

## Verification

```bash
kicad-mcp doctor --agent claude-desktop
```

In Claude Desktop, ask: *"Use the kicad MCP server to inspect the current project."*
