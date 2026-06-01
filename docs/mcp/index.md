# kicad-mcp-pro

`kicad-mcp-pro` is the MCP server in `packages/mcp-server`. It exposes KiCad project discovery,
schematic and PCB inspection, validation, exports, manufacturing workflows, library lookup, and
release-quality checks to MCP clients.

## Main User Paths

| Workflow                                                 | Documentation                                                  |
| -------------------------------------------------------- | -------------------------------------------------------------- |
| Review all tools and their profile availability          | [Tool catalog](tools.md)                                       |
| Connect through Streamable HTTP or stdio                 | [Transport](transport.md)                                      |
| Deploy with Docker, systemd, tunnels, or reverse proxies | [Deployment](deployment.md)                                    |
| Validate server-info and capabilities                    | [API reference](api-reference.md)                              |
| Connect to the VS Code extension                         | [KiCad Studio integration](../integration/kicad-studio-mcp.md) |

## Source Files

- Python package: `packages/mcp-server/pyproject.toml`
- Server entrypoint: `packages/mcp-server/src/kicad_mcp/server.py`
- Tool modules: `packages/mcp-server/src/kicad_mcp/tools/`
- Server-info schema: `packages/protocol-schemas/schemas/kicad-mcp-server-info.schema.json`

The MCP tool catalog is generated from the registered server tools with:

```bash
corepack pnpm --dir packages/mcp-server run docs:tools
```
