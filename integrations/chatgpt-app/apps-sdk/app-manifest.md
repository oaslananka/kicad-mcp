# KiCad MCP GPT App Manifest

## App Info
- **Name:** KiCad MCP
- **Description:** Analyze KiCad PCB projects, interpret DRC/ERC reports, assess manufacturing readiness, and generate agent config snippets.
- **Category:** Developer Tools / Electronics

## Tools

| Tool | Description | Read-only |
|------|-------------|-----------|
| `search_kicad_knowledge` | Search KiCad documentation | ✅ |
| `analyze_uploaded_kicad_project` | Analyze uploaded KiCad project | ✅ |
| `explain_drc_report` | Interpret DRC results | ✅ |
| `explain_erc_report` | Interpret ERC results | ✅ |
| `generate_manufacturing_readiness_report` | Check board readiness | ✅ |
| `generate_agent_config` | Generate config for any agent | ✅ |

## UI Components

| Widget | File | Description |
|--------|------|-------------|
| Project Overview | `public/kicad-dashboard.html` | Board info, layers, component count |
| Issue Table | `public/project-review.html` | DRC/ERC issues grouped by severity |
| Release Checklist | `public/manufacturing-report.html` | Step-by-step release tracker |

## Auth
- **Dev mode:** No auth for local development
- **Production:** OAuth 2.1 / PKCE

## Submission Checklist
- [ ] Publicly accessible HTTPS endpoint
- [ ] OAuth configured (production)
- [ ] All tools return valid MCP responses
- [ ] UI components render correctly in ChatGPT iframe
- [ ] Privacy policy and terms of service
- [ ] Rate limiting and quota management
