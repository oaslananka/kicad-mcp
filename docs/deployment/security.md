# Security

For HTTP deployments, the following checks are recommended:

- Enable bearer-token protection with `KICAD_MCP_AUTH_TOKEN`.
- Limit `KICAD_MCP_CORS_ORIGINS` to only the origins you actually need.
- Use the `resolve_within_project()` flow for path parameters so requests cannot escape the active project root.
- Run manufacturing/export tools only after the relevant quality gate passes.
