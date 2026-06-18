# Changelog

All notable changes to the `kicad-mcp-pro` Python server will be documented in
this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this package adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Comparison links will be added after the first public component tags are
published.

## [3.12.1](https://github.com/oaslananka/kicad-mcp/compare/mcp-server-v3.12.0...mcp-server-v3.12.1) (2026-06-18)


### Bug Fixes

* load CLI on Typer versions without the vendored _click module ([#105](https://github.com/oaslananka/kicad-mcp/issues/105)) ([5dc2b9f](https://github.com/oaslananka/kicad-mcp/commit/5dc2b9f9669b98875a6a448c40ef6d96fae023b3))
* silence mypy no-redef on the typer/click fallback import ([#106](https://github.com/oaslananka/kicad-mcp/issues/106)) ([6e51411](https://github.com/oaslananka/kicad-mcp/commit/6e514112c1484a865836fdf7c0a49afc422dc1dd))
* sync tauri.conf.json version to 3.12.0 ([#102](https://github.com/oaslananka/kicad-mcp/issues/102)) ([90add7a](https://github.com/oaslananka/kicad-mcp/commit/90add7a47e30fa83ac6a984332573a657d5511e1))


### Documentation

* add centered hero tagline and quick links to README ([#104](https://github.com/oaslananka/kicad-mcp/issues/104)) ([9b680b5](https://github.com/oaslananka/kicad-mcp/commit/9b680b53ae037797ffa5f8434048fa2577d08cdd))
* center README badges and show total downloads ([#103](https://github.com/oaslananka/kicad-mcp/issues/103)) ([b7eeb7e](https://github.com/oaslananka/kicad-mcp/commit/b7eeb7e5b4833c8a200012385560dd89b9ac8990))
* tidy README badges and add PyPI/npm download badges ([#100](https://github.com/oaslananka/kicad-mcp/issues/100)) ([29ab016](https://github.com/oaslananka/kicad-mcp/commit/29ab0164b8fcab2ab1dd669073e905df10c29768))

## [3.12.0](https://github.com/oaslananka/kicad-mcp/compare/mcp-server-v3.11.0...mcp-server-v3.12.0) (2026-06-18)


### Features

* **dashboard:** surface AI agent setup and prompt links in the sidebar ([#99](https://github.com/oaslananka/kicad-mcp/issues/99)) ([db56aa8](https://github.com/oaslananka/kicad-mcp/commit/db56aa83a7230beab0ae72ef832d9ea4be2cd356))


### Bug Fixes

* **gui:** pin a working backend version and stop the startup timeout from failing on cold installs ([#97](https://github.com/oaslananka/kicad-mcp/issues/97)) ([8d15056](https://github.com/oaslananka/kicad-mcp/commit/8d15056d032484cd9683f2d9b244758cb907075d))
* sync GUI app version in tauri.conf.json and auto-bump it on release ([#98](https://github.com/oaslananka/kicad-mcp/issues/98)) ([5c0b6b5](https://github.com/oaslananka/kicad-mcp/commit/5c0b6b563bc3c97fd77676dec1f6c9984e6a1ff8))


### Documentation

* add MCP client guides for Cline, Windsurf, Continue, and Zed ([#96](https://github.com/oaslananka/kicad-mcp/issues/96)) ([102f662](https://github.com/oaslananka/kicad-mcp/commit/102f662f1d43393a0be0524c96d16c48482676ba))
* unpin version from README install/transport examples ([#94](https://github.com/oaslananka/kicad-mcp/issues/94)) ([d4d6955](https://github.com/oaslananka/kicad-mcp/commit/d4d6955f8968a3c7c785c929dd91d2d4f8e38bb8))

## [3.11.0](https://github.com/oaslananka/kicad-mcp/compare/mcp-server-v3.10.0...mcp-server-v3.11.0) (2026-06-17)


### Features

* apply routed Specctra SES to the board headlessly (P4-T1) ([#91](https://github.com/oaslananka/kicad-mcp/issues/91)) ([0563efc](https://github.com/oaslananka/kicad-mcp/commit/0563efce3d5f54aa413cddde9f325d010f974a78))
* selective re-validation after edit completes first-class edit mode (P4-T4) ([#88](https://github.com/oaslananka/kicad-mcp/issues/88)) ([d827523](https://github.com/oaslananka/kicad-mcp/commit/d82752362b9924b54868a778a457f1ceed803a4e))


### Bug Fixes

* correct Specctra SES coordinate scale (1 mm = 1000 units, not 10000) ([#92](https://github.com/oaslananka/kicad-mcp/issues/92)) ([565a020](https://github.com/oaslananka/kicad-mcp/commit/565a02030d68cdb2b0bcddd325f5f5a1014ef66f))
* discover symbol/footprint libraries via sym-/fp-lib-table ([#78](https://github.com/oaslananka/kicad-mcp/issues/78)) ([#90](https://github.com/oaslananka/kicad-mcp/issues/90)) ([72fce79](https://github.com/oaslananka/kicad-mcp/commit/72fce791eaf87e48255807799a19595923c34d8a))

## [3.10.0](https://github.com/oaslananka/kicad-mcp/compare/mcp-server-v3.9.2...mcp-server-v3.10.0) (2026-06-17)


### Features

* 2-D finite-difference copper-plane thermal spreading solver (P3-T4) ([1aa70c5](https://github.com/oaslananka/kicad-mcp/commit/1aa70c5bee163b82f74f52f58648e30e69f9ae6f))
* add KiCad capability-parity matrix and kicad_capability_parity tool (P0-T4) ([c742a9e](https://github.com/oaslananka/kicad-mcp/commit/c742a9e0a303dc1245163490a384b959522f8947))
* bound deferred tool registration with a timeout (P5-T5) ([081f87b](https://github.com/oaslananka/kicad-mcp/commit/081f87b05e949b75a18fae638a0c4e3cc70e481e))
* complete error transient-class and tool idempotency contract (P1-T5, K9) ([97460dd](https://github.com/oaslananka/kicad-mcp/commit/97460dd587316e78a04a7142075bad1c939331bd))
* component derating + approved-vendor (AVL) sourcing gate (P4-T3) ([2e5e3e9](https://github.com/oaslananka/kicad-mcp/commit/2e5e3e954a6a2004abf83f69f16b8b5cd9a30ae5))
* deterministic convergence-based placement, no wall-clock cap (P4-T2, K7) ([cade887](https://github.com/oaslananka/kicad-mcp/commit/cade8877d6158f214c394cf39b5ebcf028a60148))
* deterministic, provenance-stamped reproducible release manifest (P2-T5) ([a6d9de2](https://github.com/oaslananka/kicad-mcp/commit/a6d9de21790a7f272af5d0103fc31550830e89c8))
* edit-impact analysis to scope re-validation after edits (P4-T4) ([fca853f](https://github.com/oaslananka/kicad-mcp/commit/fca853ffcdcfc016af00fbd10170423110c08722))
* field-solver adapter seam + honest impedance method labeling (P3-T1) ([11a4a4d](https://github.com/oaslananka/kicad-mcp/commit/11a4a4d10ebff4a4b3bed83e4f71cc44ce197b1a))
* high-speed channel insertion-loss / eye analysis via ngspice (P3-T3) ([e3f3778](https://github.com/oaslananka/kicad-mcp/commit/e3f377833a73267c253773c8d800438c7864cf2e))
* honest FreeRouting manual-step handling and headless DSN attempt (P1-T7, K1) ([e0154f5](https://github.com/oaslananka/kicad-mcp/commit/e0154f572b51ab23973d631187dff3a493433420))
* IPC-2221 current-density fusing + honest distributed-PDN labeling (P3-T2) ([4e278d8](https://github.com/oaslananka/kicad-mcp/commit/4e278d8f8bad3decb02de826ee92df983f905783))
* IPC-7351B footprint validation hard-gate for chip packages (P4-T3) ([6db8e46](https://github.com/oaslananka/kicad-mcp/commit/6db8e461b9555acc425c30364c954ded64872a35))
* live Mouser keyword-search client completes the distributor trio (P4-T3) ([ee613ae](https://github.com/oaslananka/kicad-mcp/commit/ee613ae712923d280667892fb882bfc99fbf178b))
* manufacturing sign-off report binding requirements to checks (P5-T3) ([de3c500](https://github.com/oaslananka/kicad-mcp/commit/de3c500fdecbd4b451876af93608485e5cfec1c9))
* Nexar lifecycle/RoHS sourcing data + actionable quota error (P4-T3) ([f6b98c7](https://github.com/oaslananka/kicad-mcp/commit/f6b98c7ddc9941c3bb5ea259d005efec67db7adc))
* parity coverage-regression gate, baseline, and README badge (P5-T6) ([b02eebe](https://github.com/oaslananka/kicad-mcp/commit/b02eebe0400c7457de1d49a633114dd934cd21bf))
* PDN + thermal solver-adapter seams with honest method labeling (P3-T2/T4 seams) ([8d3af87](https://github.com/oaslananka/kicad-mcp/commit/8d3af879ee02197c6d87f952d7caf7b449502a9c))
* rate-limit the bridge daemon against floods and pairing brute force (P5-T5, K8) ([1fecc9d](https://github.com/oaslananka/kicad-mcp/commit/1fecc9d5ebb009db87091daf6828cba82fca3624))
* real DigiKey Product Information (v4) client (P4-T3) ([b9b36d4](https://github.com/oaslananka/kicad-mcp/commit/b9b36d43880ddacd2691ab3c655b1ee401c9c8ae))
* real Nexar Supply client + .env credential loading (P4-T3) ([d797759](https://github.com/oaslananka/kicad-mcp/commit/d797759413c1de9a43c5fc2e306a9ca2d4edac4b))
* real PASS/WARN/FAIL verdicts for SI gates (P1-T3, K2) ([915c752](https://github.com/oaslananka/kicad-mcp/commit/915c752dd900c2388750f6c53924829d826d0ada))
* real task cancellation + execution timeout in the Tasks layer (P5-T5) ([c1f96cb](https://github.com/oaslananka/kicad-mcp/commit/c1f96cbcabeb879007b37dd5e186a54f76064e13))
* round-trip-safe schematic edit primitive with corruption guard (P2-T1/T2, K5/K6) ([2e1dbf6](https://github.com/oaslananka/kicad-mcp/commit/2e1dbf66f44e2e687743ea5075d43e531eeffd70))
* structural IPC error classification + restart cache invalidation (P5-T5) ([bdb7cb4](https://github.com/oaslananka/kicad-mcp/commit/bdb7cb4d87727f879b9367c3520c3e8b6e70943f))
* structured verdict payloads for high-traffic gate tools (P1-T4) ([ee3c21a](https://github.com/oaslananka/kicad-mcp/commit/ee3c21a6b2b27f6954a7530b26635330169351ac))


### Bug Fixes

* align main ruleset with real CI check names + guard (P5-T4) ([f23ac33](https://github.com/oaslananka/kicad-mcp/commit/f23ac3328f6b58a5013d59d1ad097f74ca48aac2))
* bump compatibility.yaml version from 3.9.1 to 3.9.2 ([a9ef4ff](https://github.com/oaslananka/kicad-mcp/commit/a9ef4ff2d85b0862b69f77812910a81450d88426))
* bump hardcoded version refs from 3.9.1 to 3.9.2 in tests, dashboard, compatibility, README ([40a080b](https://github.com/oaslananka/kicad-mcp/commit/40a080b1b3251d0fce46e621be5a4808731fc18e))
* bump playwright e2e test version assertion v3.9.1 -&gt; v3.9.2 ([28ffa0a](https://github.com/oaslananka/kicad-mcp/commit/28ffa0a49453848cc1d68945fe1941f2fe540a05))
* **chatgpt-app:** add path-traversal guards, XSS escaping, and rate limiting ([0084de5](https://github.com/oaslananka/kicad-mcp/commit/0084de587e8639a50caebde230e2ac35c165bcaa))
* **ci:** repair container build hash-pinning and patch starlette CVE-2026-54283 ([023ee30](https://github.com/oaslananka/kicad-mcp/commit/023ee30dc25dc4c015f8f981a3baa4a0b89f5c3d))
* resolve 15 pre-existing schematic integration test failures ([f298b5a](https://github.com/oaslananka/kicad-mcp/commit/f298b5a2580f12f19f16442c2bd7fc3818d5d133))
* surface partially-unresolved nets in sch_build_circuit result (P2-T4) ([b046f86](https://github.com/oaslananka/kicad-mcp/commit/b046f866ac55f16fe682920b1e84e9df38755f75))


### Documentation

* add root ARCHITECTURE.md and link from README (P0-T1) ([0b231f6](https://github.com/oaslananka/kicad-mcp/commit/0b231f60bc13db4ae8afa851ba85662c6e795724))
* add synced error-code catalog and consolidate install docs (P1-T8) ([d2497a8](https://github.com/oaslananka/kicad-mcp/commit/d2497a87bbe15ae4aff25bd5d4c9025dda667a2e))
* bus-factor governance — succession, continuity, tool on-ramp (P5-T1) ([a2e243c](https://github.com/oaslananka/kicad-mcp/commit/a2e243cce78ce59bd94d43eeb05a3b73b43fbada))
* doc-code honesty pass for footprints, sourcing, and analysis (P1-T6, K10/K4) ([4e1a5e9](https://github.com/oaslananka/kicad-mcp/commit/4e1a5e9a4057f1864f6f1425f3cc6cde799e570a))
* document SERVER_INITIALIZING in the error catalog (fix sync test) ([847e7e6](https://github.com/oaslananka/kicad-mcp/commit/847e7e6b819b85702e6c4e5d67c895fad31d5314))
* regenerate tool catalog (311-&gt;314) for schematic label tools ([b887175](https://github.com/oaslananka/kicad-mcp/commit/b88717569a32c63f5db665e345e708ab183bdaa1))
* regenerate tool catalog for P1-T7 routing summary changes ([6e5d910](https://github.com/oaslananka/kicad-mcp/commit/6e5d910c329e028f9730c1a793dad478982d9ff2))
* **security:** rigorous threat model with verified CLI-injection/path controls (P5-T2, K8) ([b075b44](https://github.com/oaslananka/kicad-mcp/commit/b075b446ef2eb8d561aaee3e3f1b4fd07ade1e13))
* turn manufacturing-export skeleton into a real sourcing-to-signoff guide ([daba9e3](https://github.com/oaslananka/kicad-mcp/commit/daba9e3372e601a0c5d19de3b6f1e6c43840b24c))

## [Unreleased]

### Added

### Fixed

### Changed

## [3.9.1](https://github.com/oaslananka/kicad-mcp/compare/mcp-server-v3.9.0...mcp-server-v3.9.1) (2026-06-10)


### Fixed

- Resolved CI test failure (`test_readme_listing_references_use_current_package_version`) caused by README version marker not matching the table format in `check_submission_readiness.py`.
- Pinned `ruff!=0.15.10` in dev dependencies to avoid a dyld rebase crash on macOS ARM64 runners.
- Fixed TypeScript syntax error in `apps-sdk/src/server.ts` where optional chaining was incorrectly applied after a type assertion.
- Removed the final obsolete release-token setup instruction.
- Hardened release workflows against excessive permissions, template injection,
  and publish-job cache poisoning.
- Restored the missing root contribution guide and required README sections.
- Restored the Tauri Rust format and Clippy quality gates.

### Changed

- Aligned the enforced full-suite coverage baseline with the measured repository
  coverage so the local quality gate detects regressions and remains runnable.

## [3.9.0](https://github.com/oaslananka/kicad-mcp/compare/mcp-server-v3.8.0...mcp-server-v3.9.0) (2026-06-07)


### Features

* add SPICE model assignment and library management tools ([ec14eb6](https://github.com/oaslananka/kicad-mcp/commit/ec14eb6c4dc01d0632b1f4b6b8ac3fd5cbe1c9f0))
* **cli:** add init, status, log commands with improved errors ([e66a6ef](https://github.com/oaslananka/kicad-mcp/commit/e66a6ef20e461651dc2983915a8f5054b89c9e74))
* complete all 20-phase plan — 22 new tools, 31 new files, full KiCad MCP feature parity ([34a1d92](https://github.com/oaslananka/kicad-mcp/commit/34a1d92001cae2ca7d8936a0b01a2a3386022276))
* **dev:** add hot reload, inspector command, IPC mock fixtures, better error logging, pre-commit pytest ([ed583f0](https://github.com/oaslananka/kicad-mcp/commit/ed583f04c1b98d76000e630b07e1a3f79c87d505))


### Bug Fixes

* address issues [#56](https://github.com/oaslananka/kicad-mcp/issues/56), [#57](https://github.com/oaslananka/kicad-mcp/issues/57), [#61](https://github.com/oaslananka/kicad-mcp/issues/61) (pagination, DNP test, canary extension) ([1d4e7b3](https://github.com/oaslananka/kicad-mcp/commit/1d4e7b39fe059b8dc2b89d4a1f0acf22cdeedeeb))
* **ci:** update sync_mcp_metadata.py source with correct descriptions and empty remotes ([9889890](https://github.com/oaslananka/kicad-mcp/commit/98898905e95a0a0a4c626d3d390348c5247ba94c))
* guard watch and _run_with_watch params against leaked OptionInfo objects ([bef4a06](https://github.com/oaslananka/kicad-mcp/commit/bef4a064dd7a6ef58d3d2acbca9a9d82f529a53d))
* KiCad IPC lifecycle — TTL cache, exponential backoff, IpcDisconnectedError ([cd930c7](https://github.com/oaslananka/kicad-mcp/commit/cd930c7997e1ea727330b4ac12fdea427e0b9b58)), closes [#42](https://github.com/oaslananka/kicad-mcp/issues/42)
* move importlib.util import to top of tray.py to fix ruff E402 ([8f3c230](https://github.com/oaslananka/kicad-mcp/commit/8f3c23012c55c768cbbcc591caaafe625c1af230))
* remove structuredContent from error CallToolResult to avoid IPC schema validation error ([12a4982](https://github.com/oaslananka/kicad-mcp/commit/12a4982a60aae9dfbc7f0ee25aeeab9d89e5fdfc))
* resolve all 15 audit issues from TEMP audit ([48dec8c](https://github.com/oaslananka/kicad-mcp/commit/48dec8c61e2452f71eb53cf07459fca16307166b))
* resolve mypy type errors in tray.py and routes.py ([70dd6bf](https://github.com/oaslananka/kicad-mcp/commit/70dd6bf1dc0ef411aa53da34a240004498465b2b))
* ruff format for 4 files (net_analysis.py, test_project_embedded_files.py, test_validation_tools.py, test_variants_extended.py) ([4095167](https://github.com/oaslananka/kicad-mcp/commit/409516783d1f2648c66a1c85be8f3706c567252a))
* **server.json:** correct default port from 8090 to 3334 ([cbaab66](https://github.com/oaslananka/kicad-mcp/commit/cbaab666c9f8aa11ec079b85127af522df9951ce))
* sync MCP metadata generator with server.json to fix CI metadata check ([1cf031d](https://github.com/oaslananka/kicad-mcp/commit/1cf031dbd214f97fc2b860b1ad2897a62d71df9a))
* **tests:** update kicad 9.x removal assertion to 3.9.0 after compatibility.yaml change ([2a048cf](https://github.com/oaslananka/kicad-mcp/commit/2a048cfc9ded6dcec15d8393eae0f1295553fdc9))
* three CI test failures (cli missing binary, footprint 3d dir, Dockerfile UV_VERSION) ([c2512da](https://github.com/oaslananka/kicad-mcp/commit/c2512daded1d369e11aac7805ca44f1123a79f47))
* **typecheck:** resolve 7 mypy strict errors in server.py ([dacca41](https://github.com/oaslananka/kicad-mcp/commit/dacca4133880ac4d2ab95cb81a1d2e248b504350))
* **watch:** start server in subprocess, kill and respawn on changes ([26473f2](https://github.com/oaslananka/kicad-mcp/commit/26473f21fc2213590108d438c3afd3911437ddca))


### Documentation

* sync tools-reference after pcb_export_stats profile update ([683ad46](https://github.com/oaslananka/kicad-mcp/commit/683ad46bd1e3cf07fa56f92b63b5dcc3d92357bb))

## [3.8.0](https://github.com/oaslananka/kicad-mcp/releases/tag/mcp-server-v3.8.0) (2026-06-06)

### Added

- **Phase 2 CLI-parity tools** — 20+ new footprint, symbol, jobset, upgrade, and
  manufacturing board import wrappers completing KiCad 10.0.3 CLI parity.
- **3D render formats**: BREP, GLB, GenCAD, IPC-D356, PLY, STL, U3D, VRML, PS
  with camera panning controls and variant support.
- **Schematic export expansion**: DXF, SVG, PS, python_bom, sch_upgrade.
- **Footprint tools**: `fp_export_svg`, `fp_upgrade`.
- **Symbol tools**: `sym_export_svg`, `sym_upgrade`.
- **Jobset tools**: `jobset_run`, `jobset_list_templates`, `jobset_list_outputs`.
- **Manufacturing board import**: PADS, gEDA, Specctra, Allegro (blocked) formats.
- **KiCad 10.0.3 contract canaries**: shared fixtures, Windows primary smoke
  coverage, scheduled 9.x/10.x lanes.
- **Doctor diagnostics**: `kicad-mcp-pro doctor`, JSON diagnostics, and redacted
  support bundles for setup troubleshooting.

### Fixed

- **Security**: Path traversal hardening across footprint, symbol, jobset, and
  upgrade tools — output paths validated with `resolve_under` and `Path().name`.
- **Fragile import in manufacturing.py**: `_run_cli_variants` imported from
  `.export_support` instead of `.export`.
- **Integer division bug**: `_human_size` uses float division preserving
  fractional byte sizes across KB/MB/GB conversions.
- **Pan logic**: Simplified falsy check for `pan_x`/`pan_y` in 3D render tool.
- **CI pipeline**: Format, lint, and typecheck errors resolved across all
  platforms (macOS, Windows, Linux).

### Deprecated

- Marked KiCad 9.x as a deprecated best-effort compatibility line in MCP
  discovery metadata while retaining scheduled non-blocking canary coverage.

## [3.7.6](https://github.com/oaslananka/kicad-mcp/compare/mcp-server-v3.7.5...mcp-server-v3.7.6) (2026-06-05)

### Bug Fixes

- **ci:** harden scorecard workflow ([#27](https://github.com/oaslananka/kicad-mcp/issues/27)) ([f5a163d](https://github.com/oaslananka/kicad-mcp/commit/f5a163dfc297839c6752a83669af4d0ee55af18b))
- **security:** add gitleaks pre-commit hook ([#28](https://github.com/oaslananka/kicad-mcp/issues/28)) ([5dad852](https://github.com/oaslananka/kicad-mcp/commit/5dad85216ef50fc6feb8e4feac2fc39e84f0f29e))

## [3.7.0](https://github.com/oaslananka/kicad-mcp/compare/mcp-server-v3.6.0...mcp-server-v3.7.0) (2026-06-03)

### Features

- initial migration from kicad-studio-kit monorepo ([#1](https://github.com/oaslananka/kicad-mcp/issues/1)) ([be9b16f](https://github.com/oaslananka/kicad-mcp/commit/be9b16f33aaea94fbea525edd173a93a7e3e5012))
- publish protocol-schemas as public npm package ([f09a57e](https://github.com/oaslananka/kicad-mcp/commit/f09a57ebedeab9a28c5bab6f34052baf1a4aed49))

### Bug Fixes

- add repository.url for npm provenance verification ([42045f5](https://github.com/oaslananka/kicad-mcp/commit/42045f5d35404c22c3023806c1714e768ba4f1f0))
- handle scoped tarball name mismatch in verify-npm-release, make publish idempotent ([#5](https://github.com/oaslananka/kicad-mcp/issues/5)) ([6e8f09b](https://github.com/oaslananka/kicad-mcp/commit/6e8f09b92fdae9ab0cd6f2a97ad2df26ccc2c731))
- pass NPM_TOKEN as NODE_AUTH_TOKEN for publish ([48a27fa](https://github.com/oaslananka/kicad-mcp/commit/48a27fa4e5f26bf276076962446c150ccb22f4ec))
- **protocol-schemas:** export package.json for require.resolve consumers ([e4c6f6f](https://github.com/oaslananka/kicad-mcp/commit/e4c6f6f75c70ea63eec5fd55063fcdc913e7ac94))
- restore release readiness baseline ([bc08eca](https://github.com/oaslananka/kicad-mcp/commit/bc08eca753a32da76355ad1c1fb20a8ddcceb6b2)), closes [#6](https://github.com/oaslananka/kicad-mcp/issues/6)

## [3.6.0](https://github.com/oaslananka/kicad-mcp/compare/mcp-server-v3.5.2...mcp-server-v3.6.0) (2026-05-27)

### Features

- **compat:** add release compatibility matrix ([f35ba2d](https://github.com/oaslananka/kicad-mcp/commit/f35ba2d34327a51890ad702cba7b188f10597a4b))
- **kicad-mcp-pro:** add multi-arch container publishing ([db4f98a](https://github.com/oaslananka/kicad-mcp/commit/db4f98a3cccd3dbd2e504d44662f743b0b3cf9b6))
- **kicad-mcp-pro:** add multi-arch container publishing ([2dc0ebc](https://github.com/oaslananka/kicad-mcp/commit/2dc0ebcfa2d755278a833149d81c44ec2dc26d5f))
- **kicad-mcp-pro:** add OpenTelemetry observability ([b34ab19](https://github.com/oaslananka/kicad-mcp/commit/b34ab192f59c6186a6090951139c8b801612641d))
- **kicad-mcp-pro:** add OpenTelemetry observability ([b4f38b8](https://github.com/oaslananka/kicad-mcp/commit/b4f38b80b4c4ceeecd2acf73e92354ae1aee8f9a))
- **kicad-mcp-pro:** add structured logging lifecycle ([3e4f9bf](https://github.com/oaslananka/kicad-mcp/commit/3e4f9bf03b25d58328de9ea5baf645ee35f7cde9))
- **kicad-mcp-pro:** add structured logging lifecycle ([8293e25](https://github.com/oaslananka/kicad-mcp/commit/8293e25840f2ee8dbbeb56466e58353e01c15bc3))
- **kicad-studio/kicad-mcp-pro:** add doctor diagnostics ([88dca0c](https://github.com/oaslananka/kicad-mcp/commit/88dca0cc015a24d50b8d8b2db948783be68240ff)), closes [#74](https://github.com/oaslananka/kicad-mcp/issues/74)
- **kicad-studio/kicad-mcp-pro:** add KiCad IPC capability gating ([835e488](https://github.com/oaslananka/kicad-mcp/commit/835e48820404ad93c24b8cfd66bb68710ef2983c))
- **kicad-studio/kicad-mcp-pro:** add KiCad IPC capability gating ([c81db7a](https://github.com/oaslananka/kicad-mcp/commit/c81db7ac31b275be1d667d12eb61cdb96ad03cd7))
- **kicad-studio/kicad-mcp-pro:** add localization infrastructure ([49f949e](https://github.com/oaslananka/kicad-mcp/commit/49f949e7dc4914a8a4fc58486eca388694da1a60))
- **kicad-studio/kicad-mcp-pro:** add localization infrastructure ([fbe63e0](https://github.com/oaslananka/kicad-mcp/commit/fbe63e0d156e6d044cc5b515e1919b51ea86581e))
- **kicad-studio/kicad-mcp-pro:** add monorepo dev doctor ([7766750](https://github.com/oaslananka/kicad-mcp/commit/77667509d6ffef1e9c5779b63701b95c39433939))
- **kicad-studio/kicad-mcp-pro:** add monorepo dev doctor ([11f2168](https://github.com/oaslananka/kicad-mcp/commit/11f2168c9482daeceff89f74806b21697d4fc9df))
- **kicad-studio/kicad-mcp-pro:** add operating modes ([2cd849a](https://github.com/oaslananka/kicad-mcp/commit/2cd849a050e0119cd9ec7bb02463b3e37ff0a35a)), closes [#73](https://github.com/oaslananka/kicad-mcp/issues/73)
- **kicad-studio/kicad-mcp-pro:** add opt-in privacy-safe reporting ([55ca498](https://github.com/oaslananka/kicad-mcp/commit/55ca498d881d30cb725e532b6200bccefe3662e0))
- **kicad-studio/kicad-mcp-pro:** add opt-in privacy-safe reporting ([4d0e902](https://github.com/oaslananka/kicad-mcp/commit/4d0e902d938fa196a9d9c4c4468c918f7205b2b7))
- **kicad-studio/kicad-mcp-pro:** add product release provenance evidence ([#195](https://github.com/oaslananka/kicad-mcp/issues/195)) ([e2caccd](https://github.com/oaslananka/kicad-mcp/commit/e2caccd5663e394585b017554305ef0954b62d66))
- **kicad-studio/kicad-mcp-pro:** add shared protocol schemas package ([684ef9f](https://github.com/oaslananka/kicad-mcp/commit/684ef9fd9b8363914120a7228fa8cbf82e65d4db)), closes [#53](https://github.com/oaslananka/kicad-mcp/issues/53)
- **kicad-studio/kicad-mcp-pro:** add STEPZ and XAO exports ([b098507](https://github.com/oaslananka/kicad-mcp/commit/b098507762c456a875a4525108ab7eea58a60172)), closes [#232](https://github.com/oaslananka/kicad-mcp/issues/232)
- **mcp:** add server info capabilities contract ([759ef3a](https://github.com/oaslananka/kicad-mcp/commit/759ef3ae7c18d6c0f87eb1049ccc80d743eb3bc9))
- **repo:** add KiCad 10 parity matrix ([394f819](https://github.com/oaslananka/kicad-mcp/commit/394f81976e249ba7f728cfd11c812629d035bba5))
- **repo:** add KiCad 10.0.3 parity matrix ([7c3e9f7](https://github.com/oaslananka/kicad-mcp/commit/7c3e9f7bf0d8f3bfcc9de3905f63b3a86d2c3665))
- **repo:** harden KiCad 11 IPC readiness ([41f6376](https://github.com/oaslananka/kicad-mcp/commit/41f637646e51f0c557a60e10c700a38e9e077e4f)), closes [#182](https://github.com/oaslananka/kicad-mcp/issues/182)

### Bug Fixes

- keep MCP manifest tests release-safe ([7688545](https://github.com/oaslananka/kicad-mcp/commit/7688545af24745ea5a0ee0462fba5c2bbeea78c9))
- keep release preparation checks stable ([66123b7](https://github.com/oaslananka/kicad-mcp/commit/66123b7f1b10e6c4cdf81291aaecfa7a6fb0682a))
- **kicad-mcp-pro:** bind container http to all interfaces ([b89a967](https://github.com/oaslananka/kicad-mcp/commit/b89a96728cecff0a2d17190ce755c12e8044ee3a))
- **kicad-mcp-pro:** bump starlette security floor ([68cadc9](https://github.com/oaslananka/kicad-mcp/commit/68cadc9203f6dca94ea4711376b11cc0e1607e48))
- **kicad-mcp-pro:** make npm launcher build smoke cross-platform ([f96baca](https://github.com/oaslananka/kicad-mcp/commit/f96baca8b349856ae61bd5ee21cfed33c670bcef)), closes [#191](https://github.com/oaslananka/kicad-mcp/issues/191)
- **kicad-mcp-pro:** use shared GUI smoke fixture ([18b64df](https://github.com/oaslananka/kicad-mcp/commit/18b64dfc3ded282b6d9013d4dd32f56452339566)), closes [#186](https://github.com/oaslananka/kicad-mcp/issues/186)
- **kicad-mcp-pro:** use trivy-clean container base ([498c212](https://github.com/oaslananka/kicad-mcp/commit/498c21225c0b60ae8c8828fecb9b816ccec88168))
- **kicad-studio/kicad-mcp-pro:** mark KiCad 9.x deprecated ([11fb19a](https://github.com/oaslananka/kicad-mcp/commit/11fb19a6aceb7932fd200077bc97082c725f61fb))
- **kicad-studio/kicad-mcp-pro:** mark KiCad 9.x deprecated ([11fb19a](https://github.com/oaslananka/kicad-mcp/commit/11fb19a6aceb7932fd200077bc97082c725f61fb))
- **kicad-studio/kicad-mcp-pro:** mark KiCad 9.x deprecated ([c421156](https://github.com/oaslananka/kicad-mcp/commit/c42115697dab897d2bbc9ae5fb20853ebf62cf04))
- **kicad-studio/kicad-mcp-pro:** raise public compatibility floors ([98283a7](https://github.com/oaslananka/kicad-mcp/commit/98283a7374fcd666c392044e95aafb0c330d896e)), closes [#209](https://github.com/oaslananka/kicad-mcp/issues/209)
- **kicad-studio/kicad-mcp-pro:** reset extension marketplace identity ([2f907a1](https://github.com/oaslananka/kicad-mcp/commit/2f907a14c9b28b8d9c80f6581409f24ed53e66d0))
- **kicad-studio/kicad-mcp-pro:** reset extension marketplace identity ([11f3fd0](https://github.com/oaslananka/kicad-mcp/commit/11f3fd0e99bdaf761e99dc733a9a8b8c26fc403f))
- link release package versions ([a5879a8](https://github.com/oaslananka/kicad-mcp/commit/a5879a805594de843c9f2159747260f619183a6b))
- **mcp:** extend pcb file-backed read fallback ([0d14589](https://github.com/oaslananka/kicad-mcp/commit/0d14589fb250683da95a11f1d854b3dea9e7cef9))
- **mcp:** support stateless http and pcb file fallback ([6ebe260](https://github.com/oaslananka/kicad-mcp/commit/6ebe260cb005b6c3bb3dd769b96201ddafdf1047))
- **repo:** enforce pnpm supply-chain policy ([92eb31c](https://github.com/oaslananka/kicad-mcp/commit/92eb31cc8ea24e296a366945a4ccff98fd421c7b))
- **repo:** enforce pnpm supply-chain policy ([92eb31c](https://github.com/oaslananka/kicad-mcp/commit/92eb31cc8ea24e296a366945a4ccff98fd421c7b))
- **repo:** enforce pnpm supply-chain policy ([0943f9e](https://github.com/oaslananka/kicad-mcp/commit/0943f9ed5e770bef6fb865399c360c7f01b85de4)), closes [#202](https://github.com/oaslananka/kicad-mcp/issues/202)
- **security:** make python audit gate deterministic ([5350ec8](https://github.com/oaslananka/kicad-mcp/commit/5350ec818e1b8d9c1a17aeec744a612a50c73044))

### Documentation

- **kicad-mcp-pro:** normalize MCP client onboarding config ([dce5001](https://github.com/oaslananka/kicad-mcp/commit/dce5001e810e57a61f118a6e2885066825ecb500))
- **kicad-studio/kicad-mcp-pro/repo:** normalize changelog format ([a921810](https://github.com/oaslananka/kicad-mcp/commit/a9218103228f02f26455873e83acac8e9a85d8cb))
- **kicad-studio/kicad-mcp-pro/repo:** normalize changelog format ([234e274](https://github.com/oaslananka/kicad-mcp/commit/234e27446dd52141c47c776234b4275d48e2c309))
- **kicad-studio/kicad-mcp-pro/repo:** use past-tense changelog entries ([d162686](https://github.com/oaslananka/kicad-mcp/commit/d162686f3a8e69a783a2ac23c71e43efd2b6bdcb))
- **kicad-studio/kicad-mcp-pro:** add agent MCP onboarding pack ([1375574](https://github.com/oaslananka/kicad-mcp/commit/13755744b741b6a95369806656955417856cab0a))
- **kicad-studio:** add marketplace listing assets ([4dceac5](https://github.com/oaslananka/kicad-mcp/commit/4dceac5e3a5d18cdb44bf8c406394f7944a1e5d1))
- **repo:** add platform client setup examples ([#166](https://github.com/oaslananka/kicad-mcp/issues/166)) ([20440e0](https://github.com/oaslananka/kicad-mcp/commit/20440e0d2d452e06225703109158390731a87346))
- **repo:** align ownership policy checks ([fa52a74](https://github.com/oaslananka/kicad-mcp/commit/fa52a746c9bc19a5ab307f3327acab6a054a5a31)), closes [#64](https://github.com/oaslananka/kicad-mcp/issues/64)
- **repo:** clarify MCP client config destinations ([6049ca3](https://github.com/oaslananka/kicad-mcp/commit/6049ca3077db5b8e6490205a55b4581b367a0009))

## [1.0.0] - 2026-05-20

### Added

- Released the baseline KiCad MCP Pro server from the canonical monorepo.
