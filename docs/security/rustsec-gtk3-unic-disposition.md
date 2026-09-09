# RustSec GTK3 / rust-unic Advisory Disposition

This page records the reproducible advisory inventory behind [#779](https://github.com/oaslananka/kicad-mcp-pro/issues/779) and OpenSSF Scorecard code-scanning alert #53 (`VulnerabilitiesID`, severity `error`), the reachability evidence for each advisory family, and the accepted-risk decision for the desktop (`src-tauri`) Cargo dependency tree.

## Reproduction

```bash
cd src-tauri
cargo audit --file Cargo.lock --json
```

- Tool: `cargo-audit 0.22.2` (pinned by CI)
- Lockfile: `src-tauri/Cargo.lock`, SHA-256 `2afcb41a15b0a0bbfc59a2070c181be89bdcf5abaf4578d4ab9857b2cf0d8415`
- Repository commit: `7418fbfd6649d49764d8fd98362ff908b1f5a701`
- CI evidence: run `34402695443`, `security` job SUCCESS
- Result: `vulnerabilities.count = 0`, `warnings = 7` (6 `unmaintained`, 1 `unsound`)

cargo-audit's current advisory database classifies all 7 active findings as warning-kind (`unmaintained` or `unsound`), not vulnerability-kind. The ten former GTK3 unmaintained advisories `RUSTSEC-2024-0411`..`0420` are withdrawn and are no longer emitted by the current audit. `src-tauri/.cargo/audit.toml` still surfaces both warning kinds; no advisory-specific ignore or suppression was added.

Full machine-readable evidence, including current findings, reverse-dependency chains, Scorecard alert state, and upstream tracking, is recorded in:

- `docs/evidence/rustsec-gtk3-unic-audit-2026-09-09.json`

The earlier 2026-08-30/2026-09-04 17-finding snapshots are retained below as historical evidence, not current audit output.

## Advisory families

| Family | Advisories | Kind | Root package | Reachable from app code? |
| --- | --- | --- | --- | --- |
| GTK3 / gtk-rs bindings | `RUSTSEC-2024-0411`..`0420` (10 historical advisories) | **withdrawn by RustSec** | `gtk 0.18.2` and its `-sys`/companion crates | No — transitive only |
| glib soundness | `RUSTSEC-2024-0429` | **unsound** | `glib 0.18.5` | No — transitive only |
| proc-macro-error | `RUSTSEC-2024-0370` | unmaintained | `proc-macro-error 1.0.4` | No — build-time transitive only |
| rust-unic | `RUSTSEC-2025-0075`, `0080`, `0081`, `0098`, `0100` | unmaintained | `unic-* 0.9.0` | No — transitive only |

## Reachability and exploitability evidence

`grep -RnE 'VariantStrIter|unic_char|unic::|unic_common|unic_ucd' src-tauri/src` returns no matches. Application code in `src-tauri/src` never calls `glib::VariantStrIter` (the unsound symbol behind `RUSTSEC-2024-0429`) or any `unic-*` API directly. The current reproducible finding set is 7 active advisories, all transitive. The ten GTK3 IDs `RUSTSEC-2024-0411`..`0420` are now withdrawn by RustSec and are retained below only as dependency-maintenance context:

- **rust-unic family**: `unic-char-range <- unic-char-property <- unic-ucd-ident <- urlpattern <- tauri-utils <- tauri`/`tauri-build <- kicad-mcp-pro`. `urlpattern` is Tauri's own URL-pattern matcher; the repository never depends on `urlpattern` or `unic-*` directly.
- **GTK3 / glib family**: `gtk`/`glib`/`webkit2gtk`/`wry <- tauri` (also reachable via the tray/`libappindicator` path). `cargo tree -i glib` against the default target prints nothing; only `cargo tree -i glib --target all` resolves the chain, confirming these crates are pulled in exclusively under Tauri's `cfg(target_os = "linux")` GTK/WebKitGTK backend. They are absent from the macOS (WKWebView) and Windows (WebView2) dependency graphs.
- **proc-macro-error**: reached only as a build-time proc-macro dependency of `gtk3-macros`, itself only present on the Linux target.

No advisory in this set has a known proof-of-concept or CVE tied to reachable application behavior. The `unsound` classification on `glib 0.18.5` describes a soundness hazard in an API this codebase does not call.

## Upstream tracking

Upstream Tauri cannot remove the GTK3 chain today: Tauri's current development manifest still resolves Linux `gtk = 0.18` / `webkit2gtk = 2`, and this repository is already on the current stable `tauri 2.11.5`. The relevant upstream migration work, checked live on 2026-08-30:

| Tracking item | State | Notes |
| --- | --- | --- |
| [`tauri-apps/tauri#12561`](https://github.com/tauri-apps/tauri/issues/12561) — Upgrade `tauri-runtime-wry` to `gtk4-rs` | Open | Tracking issue for the runtime-side migration. |
| [`tauri-apps/tao#1104`](https://github.com/tauri-apps/tao/pull/1104) — Port to gtk4-rs | Open, not merged | Active as of 2026-08-18; ports `tao` (Tauri's windowing crate) from GTK3/webkit2gtk to GTK4/webkit6/soup3, which is the precondition for `wry`/`tauri` to drop the GTK3 chain. |

There is no compatible stable Tauri/wry release yet that removes any advisory in this set. A normal patch/minor dependency refresh cannot close this out; it is gated on the linked upstream PR/issue merging and a subsequent Tauri release adopting it.

## OpenSSF Scorecard alert #53

Read live again on 2026-09-09: alert #53 remains `state: open` on `refs/heads/main`, but its message now contains **7 active RustSec IDs**, exactly matching the reviewed cargo-audit baseline: `RUSTSEC-2024-0370`, `RUSTSEC-2024-0429`, and the five `RUSTSEC-2025-*` rust-unic advisories. The ten GTK3 IDs `RUSTSEC-2024-0411`..`0420` are no longer present because RustSec marks them withdrawn. The alert therefore reflects the remaining active findings rather than the historical 17-item inventory.

## Risk decision

- Do not suppress or dismiss Scorecard alert #53 to improve the score; it remains open and accurately reflects unresolved upstream advisories.
- Do not add per-advisory `cargo audit` ignores. The existing `informational_warnings = ["unmaintained", "unsound"]` setting in `src-tauri/.cargo/audit.toml` is a kind-level (not advisory-level) classification that predates this review; this document supplies the per-advisory reachability evidence the issue requires without narrowing CI enforcement further.
- Do not perform a GTK4 migration in this repository ahead of upstream Tauri/wry support landing; doing so would mean depending on unreleased/unpinned upstream crates.
- Accept the current active advisory risk as **low**: all 7 active findings are transitive-only and the application does not call the affected `glib::VariantStrIter` or `unic-*` APIs directly. The Linux GTK3 stack remains a maintenance migration concern even though its ten former RustSec unmaintained advisories are now withdrawn.

## Revisit triggers

Re-run this review and update the evidence file when any of the following occurs:

1. `tauri-apps/tao#1104` merges, or `tauri-apps/tauri#12561` closes.
2. A new stable `tauri`/`wry` release changes the Linux GTK/glib dependency versions in `src-tauri/Cargo.lock`.
3. `cargo audit` reports a new advisory in this set as `vulnerability`-kind rather than `warning`-kind.
4. Scorecard alert #53 changes state (closed, reopened, or its aggregated advisory list changes).

## 2026-09-04 remediation recheck

At that time, the engineering-audit remediation re-ran `osv-scanner 2.4.0` from the repository root and reproduced 17 Rust advisories: 0 Critical, 0 High, 1 Medium (`RUSTSEC-2024-0429`, `glib 0.18.5`), and 16 Unknown/informational advisories. No advisory was removed by the current compatible dependency set.

A fresh `cargo tree -i glib@0.18.5` under `src-tauri` still resolves the Linux chain through `gtk 0.18.2`, `webkit2gtk 2.0.2`, `wry 0.55.1`, and `tauri 2.11.5`, including the tray/runtime paths. `cargo update -p tauri --dry-run` reports `Locking 0 packages to latest compatible versions`, so there is no stable semver-compatible Tauri refresh available to this lockfile that removes the GTK3/glib family.

That 2026-09-04 result is historical evidence. The 2026-09-09 recheck below reflects RustSec withdrawals and the newer upstream `urlpattern 0.6` development path. Do not force `glib >=0.20` into the GTK3 0.18 graph or suppress remaining active advisories.

## 2026-09-09 upstream recheck

Fresh upstream inspection changes one tracking detail but does not yet permit a supported dependency remediation:

- Tauri commit `dd725f4b13c30a86b398ccc59eb498f151f461c5` (2026-07-06) updates `tauri-utils` from `urlpattern 0.3` to `0.6`. Its upstream lockfile diff removes all five `unic-* 0.9.0` crates, so the rust-unic advisory family now has a concrete upstream removal path.
- That change is still unreleased: `tauri-utils-v2.9.3` remains the latest stable tag, while `tauri-utils-v2.9.4` and `tauri-utils-v2.10.0` do not exist as of this review. This repository therefore cannot consume the removal without switching to unreleased Tauri code.
- Stable Tauri remains `2.11.5`. Tauri `dev` still declares Linux `gtk = 0.18` and `webkit2gtk = 2`; `tauri-apps/tao#1104` and `tauri-apps/wry#1530` remain open.
- Wry `0.57.0` was released on 2026-09-08, but its Linux manifest still uses `gtk 0.18` and `webkit2gtk 2.0.2`. Updating Wry alone therefore would not remove the GTK3/glib advisory family, and Tauri `2.11.5`'s runtime constraint remains on Wry `0.55.x`.
- Scorecard code-scanning alert #53 remains open on `main`. Direct application reachability is unchanged: `VariantStrIter` and `unic-*` API searches in `src-tauri/src` still return no matches.

The bounded decision remains: do not suppress the advisories, do not patch stable Tauri to unreleased git dependencies, and do not force a repository-local GTK4 migration. Revisit rust-unic immediately when a stable `tauri-utils` release includes `urlpattern >=0.6`; revisit GTK/glib when Tauri ships the GTK4/WebKit6 migration in a supported stable release.

Current machine-readable evidence is `docs/evidence/rustsec-gtk3-unic-audit-2026-09-09.json`.
