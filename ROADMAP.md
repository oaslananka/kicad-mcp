# Roadmap

KiCad MCP Pro follows a monthly minor release cadence. This document tracks
upcoming milestones and records what was delivered in completed cycles.

Dates are targets, not promises. Breaking changes follow the RFC process
described in `GOVERNANCE.md`.

---

## Completed Milestones

### ✅ 3.1 (Delivered)
- Hardened GitHub supply-chain: Renovate, CodeQL, Gitleaks, Scorecard, SBOM,
  Sigstore, artifact attestations.
- Expanded cross-platform CI for Windows and macOS unit smoke tests.

### ✅ 3.2 (Delivered)
- Deeper property-based tests for SI, PI, thermal, project discovery helpers.
- Mutation-testing baselines established.
- Docs expanded: troubleshooting, API stability, benchmark fixture contribution.

### ✅ 3.3 – 3.5 (Delivered)
- KiCad 10 primary target, full KiCad 10.x feature parity work.
- Multi-arch container publishing (GHCR).
- OpenTelemetry observability, structured logging lifecycle.
- Operating modes: readonly / write / manufacturing / experimental.
- MCP protocol 2025-11-25 compliance.
- Doctor diagnostics + redacted support bundles.

### ✅ 3.6 (Delivered — 2026-05-27)
- KiCad IPC capability gating.
- Localization infrastructure (i18n).
- STEPZ and XAO export formats.
- Streamable HTTP as primary transport; SSE deprecated and disabled by default.
- Compatibility matrix for KiCad 10.0.3 parity.

### ✅ 3.7.x (Delivered — 2026-06-03 to 2026-06-05)
- Initial migration from kicad-studio-kit monorepo.
- Protocol-schemas as public npm package.
- Scorecard workflow hardened; Gitleaks pre-commit hook added.

### ✅ 3.8.0 (Delivered — 2026-06-06)
- Phase 2 CLI-parity tools: 20+ footprint, symbol, jobset, upgrade, board import.
- 3D render formats: BREP, GLB, GenCAD, IPC-D356, PLY, STL, U3D, VRML, PS.
- Schematic export expansion: DXF, SVG, PS, python_bom, sch_upgrade.
- Path traversal hardening across all new tools.
- KiCad 9.x formally deprecated (scheduled canary retained, removal in 3.9).

---

## Upcoming

### 3.9 (Target: Q3 2026)
- **KiCad 9.x removal:** Drop scheduled canary coverage and remove best-effort
  fallback code paths. Requires a release note and migration guide.
- **MCP Protocol update:** Align `supportedMcpProtocolVersions` with the latest
  MCP spec revision if a new protocol version is published before 3.9.
- **opencode plugin stabilization:** Promote `integrations/opencode` plugin from
  example to officially supported integration with full CI coverage.
- **Performance baselines expansion:** Add benchmarks for large board (>500
  components) DRC and BOM generation.

### 4.0 (Target: TBD — RFC required)
- Remove APIs that have completed their documented deprecation window.
- Revisit profile names and tool grouping (requires RFC process per GOVERNANCE.md).
- Promote KiCad 10 as the sole primary path; document KiCad 8.x sunset.
- Evaluate Python 3.14 as minimum supported version once CPython 3.14 is stable.

---

## Ownership

Current maintainer: `@oaslananka`. Larger API or workflow changes go through
the RFC process described in `GOVERNANCE.md`.
