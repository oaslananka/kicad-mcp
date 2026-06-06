# Claude.ai Custom Connector — KiCad MCP (Remote)

Connect [Claude.ai](https://claude.ai) to the KiCad MCP cloud server via a custom connector.

> **Important**: Claude.ai custom connectors require a **publicly reachable remote MCP endpoint**. They cannot connect to local STDIO servers on your machine. For local KiCad access, use Claude Desktop or Claude Code with STDIO transport.

## Prerequisites

- Claude Pro/Max account (for Customize → Connectors)
- Team/Enterprise: Owner or Primary Owner must add the organization connector first
- A publicly hosted MCP server (see Remote MCP profile)

## Connector Setup (Pro/Max)

1. Go to **Settings → Customize → Connectors → Add custom connector**
2. Enter the MCP server URL: `https://mcp.kicad.example.com/mcp`
3. Complete any required OAuth flow
4. The connector appears in your Claude.ai interface

## Team/Enterprise

1. Organization Owner adds the connector at organization level
2. Members can connect from their own Claude.ai settings
3. Owner manages access and permissions

## V1 Features (Read-only)

- `search_kicad_docs` — search KiCad documentation
- `analyze_uploaded_project` — analyze an uploaded KiCad project zip
- `summarize_project` — get project summary
- `explain_drc_report` — interpret DRC results
- `explain_erc_report` — interpret ERC results
- `generate_manufacturing_readiness_report` — readiness report
- `generate_agent_config` — get config snippet for local agents

## Security

- Claude.ai cannot directly access your local KiCad installation.
- Uploaded project archives may contain untrusted content.
- Start with read-only analysis before allowing any write operations.
- See `security.md` for prompt injection and data handling guidance.
