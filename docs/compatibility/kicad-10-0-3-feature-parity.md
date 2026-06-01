# KiCad 10.0.3 Feature Parity

This page is the human-readable view of
[`compatibility.yaml`](../../compatibility.yaml) `kicad10FeatureParity`. It
tracks KiCad 10.0.3 parity separately from the current KiCad 11 readiness plan
so release gates stay focused on the stable KiCad line.

Status vocabulary:

| State            | Meaning                                                                                   |
| ---------------- | ----------------------------------------------------------------------------------------- |
| `supported`      | Product support exists and is backed by a test, fixture, command probe, or smoke path.    |
| `not-applicable` | KiCad-native GUI behavior is intentionally outside the extension or MCP product surface.  |
| `partial`        | Some product support exists, but a tracked gap remains.                                   |
| `blocked`        | Product support is intentionally prevented by an upstream or policy boundary.             |
| `future`         | The upstream feature exists or is expected, but product adoption is scheduled separately. |

## Importers

| Feature id    | State       | Product boundary                                                                                                | Evidence or issue                                                                             |
| ------------- | ----------- | --------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------- |
| `altium`      | `supported` | Extension import command and MCP manufacturing probe after `kicad-cli pcb import --help` advertises the format. | `apps/vscode-extension/test/unit/importCommands.test.ts`                                      |
| `allegro`     | `blocked`   | Extension command is registered for future compatibility but hidden unless CLI support appears.                 | [#179](https://github.com/oaslananka/kicad-studio-kit/issues/179), `kicad-10-0-3-regressions` |
| `cadstar`     | `supported` | Extension command is probe-gated by CLI help.                                                                   | `apps/vscode-extension/test/unit/importCommands.test.ts`                                      |
| `eagle`       | `supported` | Extension command is probe-gated by CLI help.                                                                   | `apps/vscode-extension/test/unit/importCommands.test.ts`                                      |
| `fabmaster`   | `supported` | Extension command is probe-gated by CLI help.                                                                   | `apps/vscode-extension/test/unit/importCommands.test.ts`                                      |
| `geda_lepton` | `supported` | Extension and MCP support require the installed CLI to advertise `geda`.                                        | `packages/mcp-server/tests/integration/test_manufacturing_tools.py`                           |
| `pads`        | `supported` | Extension, MCP, fixture, and canary coverage exercise the PADS import boundary.                                 | `packages/mcp-server/tests/unit/test_kicad_canary.py`                                         |
| `pcad`        | `supported` | Extension command is probe-gated by CLI help.                                                                   | `apps/vscode-extension/test/unit/importCommands.test.ts`                                      |
| `solidworks`  | `supported` | Extension command is probe-gated by CLI help.                                                                   | `apps/vscode-extension/test/unit/importCommands.test.ts`                                      |

## Exports

| Feature id                           | State       | Product boundary                                                                                     | Evidence or issue                                                             |
| ------------------------------------ | ----------- | ---------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------- |
| `gerber`                             | `supported` | MCP manufacturing and extension export workflows depend on the KiCad CLI Gerber export.              | `packages/mcp-server/scripts/kicad_canary.py`                                 |
| `drill`                              | `supported` | MCP manufacturing and extension export workflows depend on the KiCad CLI drill export.               | `packages/mcp-server/scripts/kicad_canary.py`                                 |
| `pdf`                                | `supported` | Schematic and PCB PDF exports are part of the primary KiCad canary plan.                             | `packages/mcp-server/tests/unit/test_kicad_canary.py`                         |
| `pcb_pdf_property_popup_suppression` | `supported` | KiCad 10.0.3-specific PDF flag is covered by a fixture and canary probe.                             | `kicad-10-0-3-regressions`                                                    |
| `ipc2581`                            | `supported` | Extension command and MCP `export_ipc2581` tool both expose the export.                              | `packages/mcp-server/tests/integration/test_pcb_export_validation_surface.py` |
| `odbpp`                              | `supported` | Extension command and MCP `export_odb` tool expose ODB++ behind capability checks.                   | `packages/mcp-server/tests/integration/test_export_tools.py`                  |
| `step`                               | `supported` | MCP `export_step` and `export_3d_step` tools cover the KiCad CLI STEP export.                        | `packages/mcp-server/tests/integration/test_export_tools.py`                  |
| `stepz`                              | `supported` | MCP `export_stepz` exposes KiCad's `stpz` CLI export for headless STEPZ/GZIP-compressed STEP output. | `packages/mcp-server/tests/integration/test_export_tools.py`                  |
| `xao`                                | `supported` | MCP `export_xao` exposes the KiCad CLI XAO export for headless interchange workflows.                | `packages/mcp-server/tests/integration/test_export_tools.py`                  |

## GUI Editor

| Feature id                  | State            | Product boundary                                                                                                       | Evidence or issue                                             |
| --------------------------- | ---------------- | ---------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------- |
| `design_blocks`             | `supported`      | Product support is headless through parser coverage and MCP `pcb_block_*` tools.                                       | `apps/vscode-extension/test/unit/sExpressionParser.test.ts`   |
| `graphical_drc_rule_editor` | `not-applicable` | The native GUI editor remains a KiCad-owned surface; product support is textual `.kicad_dru` guidance and diagnostics. | `apps/vscode-extension/test/unit/drcRulesProvider.test.ts`    |
| `variants`                  | `supported`      | Extension variants view and MCP `variant_*` tools cover list, activation, diff, and export integration.                | `apps/vscode-extension/test/unit/variantProvider.test.ts`     |
| `barcode_support`           | `supported`      | MCP `pcb_add_barcode` supports headless barcode insertion; visual editing stays in KiCad.                              | `packages/mcp-server/tests/unit/test_kicad10_parity_tools.py` |
| `time_domain_tuning`        | `supported`      | MCP tuning helpers model and validate routing intent; the native interactive routing UX remains KiCad-owned.           | `packages/mcp-server/tests/integration/test_routing_tools.py` |

## IPC

| Feature id                      | State       | Product boundary                                                                       | Evidence or issue                                                 |
| ------------------------------- | ----------- | -------------------------------------------------------------------------------------- | ----------------------------------------------------------------- |
| `kicad_python_ipc`              | `supported` | KiCad IPC is the supported live-editor direction for current and future KiCad lines.   | `packages/mcp-server/tests/gui/test_kicad_gui_live_context.py`    |
| `swig_pcbnew_direct_dependency` | `blocked`   | Production direct `pcbnew` imports are forbidden because SWIG bindings are deprecated. | [#197](https://github.com/oaslananka/kicad-studio-kit/issues/197) |

## Product Surfaces

| Feature id                        | State       | Product boundary                                                                        | Evidence or issue                                                 |
| --------------------------------- | ----------- | --------------------------------------------------------------------------------------- | ----------------------------------------------------------------- |
| `status_surface`                  | `supported` | The extension status bar and command menu expose detected KiCad line and feature gates. | `apps/vscode-extension/test/unit/kicadCliSupport.test.ts`         |
| `importer_command_gating`         | `supported` | Import commands are unavailable until the matching CLI capability probe passes.         | `apps/vscode-extension/test/unit/importCommands.test.ts`          |
| `server_info_capability_contract` | `supported` | MCP server-info compatibility and capability payloads are schema and docs gated.        | `packages/mcp-server/tests/unit/test_server_info_contract.py`     |
| `empty_project_read_tools`        | `partial`   | File-backed empty-project behavior is tracked outside this matrix.                      | [#228](https://github.com/oaslananka/kicad-studio-kit/issues/228) |
| `ipc_state_consistency`           | `partial`   | IPC lifecycle consistency is tracked in the MCP compatibility milestone.                | [#223](https://github.com/oaslananka/kicad-studio-kit/issues/223) |

## Release

| Feature id               | State       | Product boundary                                                                        | Evidence or issue                         |
| ------------------------ | ----------- | --------------------------------------------------------------------------------------- | ----------------------------------------- |
| `vsix_provenance`        | `supported` | VSIX release evidence includes checksums, SBOM, and artifact attestations.              | `.github/workflows/publish-extension.yml` |
| `wheel_provenance`       | `supported` | Python release evidence includes checksums, SBOM, trusted publishing, and attestations. | `.github/workflows/publish-python.yml`    |
| `npm_tarball_provenance` | `supported` | npm launcher release evidence includes checksums, SBOM, and provenance.                 | `.github/workflows/publish-npm.yml`       |

## KiCad 11 Readiness

KiCad 11 readiness is represented separately from KiCad 10.0.3 parity:

| Feature id           | State       | Product boundary                                                                                   | Evidence or issue                                                 |
| -------------------- | ----------- | -------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------- |
| `protocol_upgrade`   | `future`    | MCP protocol and KiCad 11 support planning remain separate from the stable KiCad 10 gate.          | [#197](https://github.com/oaslananka/kicad-studio-kit/issues/197) |
| `nightly_canary`     | `supported` | Manual nightly canary commands track prerelease behavior without changing the stable support line. | `corepack pnpm run test:kicad-cli-contract:nightly`               |
| `swig_removal_guard` | `supported` | The direct-`pcbnew` guard keeps production code away from APIs planned for removal.                | `packages/mcp-server/scripts/check_no_pcbnew.py`                  |

## Validation

Linux and macOS:

```bash
corepack pnpm run check:compatibility
corepack pnpm run test:contract
corepack pnpm run test:fixtures
```

Windows 11 PowerShell:

```powershell
corepack pnpm run check:compatibility
corepack pnpm run test:contract
corepack pnpm run test:fixtures
```

The compatibility gate verifies that every supported item has product evidence,
every partial or blocked item links a GitHub issue, and every feature id in the
matrix appears on this page.

## Source Verification

Checked on 2026-05-27:

- [KiCad 10.0.3 release notes](https://www.kicad.org/blog/2026/05/KiCad-10.0.3-Release/)
- [KiCad 10.0.3 GitHub release tag](https://github.com/KiCad/kicad-source-mirror/releases/tag/10.0.3)
- [KiCad 10.0 CLI reference](https://docs.kicad.org/10.0/en/cli/cli.html)
- [KiCad 10.0 PCB Editor reference](https://docs.kicad.org/10.0/en/pcbnew/pcbnew.html)
- [KiCad PCB Python bindings deprecation notice](https://dev-docs.kicad.org/en/apis-and-binding/pcbnew/)
- [KiCad nightly and release candidate guidance](https://www.kicad.org/help/nightlies-and-rcs/)
