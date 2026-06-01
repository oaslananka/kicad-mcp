# MCP API Reference

Machine-maintained from `packages/protocol-schemas/schemas/kicad-mcp-server-info.schema.json`
and `compatibility.yaml`. Refresh with `corepack pnpm run docs:generate`.

## Current Contract

| Surface | Value |
| --- | --- |
| MCP protocol version | `2025-11-25` |
| Tool schema version | `1.0` |
| Registry schema version | `2025-12-11` |
| Server package version | `3.6.0` |

## Server Info Fields

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `schemaVersion` | string | yes |  |
| `server` | object | yes |  |
| `description` | string | no |  |
| `localizedDescriptions` | object | no |  |
| `version` | string | yes |  |
| `mcpProtocolVersion` | string | yes |  |
| `toolSchemaVersion` | string | yes |  |
| `compatibilityRange` | object | yes |  |
| `transport` | object | yes |  |
| `kicad` | object | yes |  |
| `operatingMode` | object | yes |  |
| `capabilities` | object | yes |  |
| `diagnostics` | array | yes |  |

## Capability Fields

| Capability | Type | Description |
| --- | --- | --- |
| `fileBackedDrc` | boolean |  |
| `fileBackedErc` | boolean |  |
| `fileBackedExports` | boolean |  |
| `livePcbRead` | boolean |  |
| `livePcbWrite` | boolean |  |
| `liveSchematicRead` | boolean |  |
| `liveSchematicWrite` | boolean |  |
| `liveEditingTools` | object |  |
| `chatgptConnectorCompatible` | boolean |  |
| `cliExports` | object |  |

## Release-Gated MCP Tools

| Gate | Tool |
| --- | --- |
| required | `kicad_get_version` |
| required | `kicad_get_project_info` |
| required | `kicad_set_project` |
| required | `sch_get_symbols` |
| required | `pcb_get_board_summary` |
| required | `export_gerber` |
| required | `export_drill` |
| required | `export_manufacturing_package` |
| optional | `variant_list` |
| optional | `variant_set_active` |
| optional | `export_odb` |
| optional | `pcb_export_3d_pdf` |
| optional | `dfm_run_manufacturer_check` |
