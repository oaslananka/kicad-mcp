# Agent Compatibility Matrix

## Feature Support

| Agent | Local STDIO | Remote HTTP | Skills/AGENTS.md | App UI | OAuth | Tool Filtering |
|-------|------------|-------------|-----------------|--------|-------|----------------|
| Claude Code | ✅ | ✅ | ✅ | — | ✅ | ✅ include/exclude |
| Codex CLI | ✅ | ✅ | ✅ AGENTS.md | — | — | ✅ enabled/disabled |
| Gemini CLI | ✅ | ✅ | — | — | ✅ | ✅ include/exclude |
| OpenCode | ✅ | ✅ | ✅ AGENTS.md | ✅ Plugin | ✅ | ✅ glob patterns |
| VS Code/Copilot | ✅ | ✅ | ✅ copilot-instructions.md | ⚠️ Experimental | ✅ | ✅ sandbox |
| Cursor | ✅ | ⚠️ Verify | ✅ Rules + Skills | — | — | ⚠️ Limited |
| Claude Desktop | ✅ | — | — | — | — | — |
| Claude.ai Web | ❌ | ✅ | ⚠️ Account feature | ⚠️ Limited | ✅ | ✅ tool allowlist |
| ChatGPT Web | ❌ | ✅ | — | ✅ Apps SDK | ✅ | ✅ tool allowlist |
| Antigravity | ⚠️ Verify | ✅ | — | — | ✅ | — |

## Notes

- **Local STDIO** requires `uvx kicad-mcp-pro` or `python -m kicad_mcp`
- **Remote HTTP** requires a publicly accessible HTTPS endpoint with Streamable HTTP
- **Skills** are Agent Skills standard format (SKILL.md with references)
- **App UI** refers to custom UI components within the agent interface
- **Tool Filtering** is the ability to limit which MCP tools are exposed

## Protocol Support

| Agent | STDIO | SSE | Streamable HTTP | OAuth 2.1 |
|-------|-------|-----|-----------------|-----------|
| Claude Code | ✅ | ✅ | ✅ | ✅ |
| Claude Desktop | ✅ | ❌ | ❌ | ❌ |
| Codex CLI | ✅ | ❌ | ❌ | ❌ |
| Gemini CLI | ✅ | ✅ | ✅ | ✅ |
| OpenCode | ✅ | ❌ | ✅ | ✅ |
| VS Code | ✅ | ✅ | ✅ | ✅ |
| Cursor | ✅ | ❌ | ✅ | ❌ |
| ChatGPT Web | ❌ | ✅ | ✅ | ✅ |
| Claude.ai Web | ❌ | ✅ | ✅ | ✅ |
| Antigravity | ✅ | ✅ | ✅ | ✅ |
