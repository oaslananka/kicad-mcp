# Public Listing Source of Truth

KiCad MCP Pro public listing status is tracked here before and after external directory submissions.
This file is intentionally maintained in the repository root so reviewers and maintainers can find the current listing posture without searching platform-specific docs.

## Listing Targets

| Target                        | Status                  | Submitted (UTC)      | Approved (UTC)       | Listing URL                                                                |
| ----------------------------- | ----------------------- | -------------------- | -------------------- | -------------------------------------------------------------------------- |
| Anthropic Connector Directory | Not submitted           |                      |                      |                                                                            |
| ChatGPT Apps                  | Not submitted           |                      |                      |                                                                            |
| OpenAI/MCP Registry           | Listed (stale: `2.1.0`) | 2026-04-15T21:15:40Z | 2026-04-15T21:15:40Z | <https://registry.modelcontextprotocol.io/v0/servers?search=kicad-mcp-pro> |

> OpenAI/MCP Registry status verified 2026-05-31 (issue #272): the server
> `io.github.oaslananka/kicad-mcp-pro` is `active` in the official registry but pinned at
> `2.1.0` from before the monorepo migration, while the current product line is `3.6.0`.
> Refreshing the listing requires a production publish — see
> [`docs/submission/openai-mcp-registry.md`](docs/submission/openai-mcp-registry.md)
> "Verified Registry Status" for the update path. No publish was performed during verification.

## Pre-submission Gate

Run the submission readiness validator before any external form is submitted:

```bash
pnpm run submission:check
```

Run the stricter placeholder check before final production screenshots are uploaded:

```bash
SUBMISSION_MODE=1 pnpm run submission:check
```

The stricter command is expected to fail while committed screenshot placeholders are still present.
Replace the five screenshots in `docs/assets/screenshots/` with real 1920x1080 captures before final production submission when a platform requires screenshots.

## Maintainer Action Items

- Read `TALIMAT.md` for local-only manual steps that are not committed to this repository.
- Confirm access to the `oaslananka` GitHub account before external submission.
- Confirm the package owner is Osman Aslan before external submission.
- Confirm `oaslananka.dev` domain verification can be completed before ChatGPT Apps submission.
- Confirm PyPI Trusted Publisher is active before registry publish.
- Confirm GHCR image `ghcr.io/oaslananka/kicad-mcp-pro:<version>` exists before registry publish.
- Confirm the docs site is live at `https://oaslananka.github.io/kicad-mcp`.
- Confirm the privacy page is live at `https://oaslananka.github.io/kicad-mcp/privacy/`.
- Confirm support URL is `https://github.com/oaslananka/kicad-mcp/issues`.
- Confirm no submitted text contains tokens, cookies, API keys, or private file paths.

## Submission Log

| Date (UTC) | Target              | Version | Outcome            | Notes                                                                                                         |
| ---------- | ------------------- | ------- | ------------------ | ------------------------------------------------------------------------------------------------------------- |
| 2026-04-15 | OpenAI/MCP Registry | 2.1.0   | Published (active) | Pre-monorepo publish; discovered during #272 verification on 2026-05-31. Listing is stale vs current `3.6.0`. |

## Target Field Values

- Product name: `KiCad MCP Pro`.
- Maintainer identity: Osman Aslan (`oaslananka`).
- Repository: `https://github.com/oaslananka/kicad-mcp`.
- Documentation: `https://oaslananka.github.io/kicad-mcp`.
- Privacy: `https://oaslananka.github.io/kicad-mcp/privacy/`.
- Support: `https://github.com/oaslananka/kicad-mcp/issues`.
- MCP server name: `io.github.oaslananka/kicad-mcp-pro`.
- PyPI package: `kicad-mcp-pro`.
- Container image: `ghcr.io/oaslananka/kicad-mcp-pro:<version>`.
- Default transport: `stdio`.
- Primary category: `EDA / Hardware Design`.
- Fallback category: `Developer Tools`.

## Target Documents

- Anthropic submission guide: `docs/submission/anthropic-directory.md`.
- ChatGPT Apps submission guide: `docs/submission/chatgpt-apps.md`.
- OpenAI/MCP Registry guide: `docs/submission/openai-mcp-registry.md`.
- Reviewer prompt guide: `docs/submission/reviewer-test-prompts.md`.
- Safety statement: `docs/submission/safety-and-permissions.md`.
- Screenshot capture manifest: `docs/assets/screenshots/README.md`.
- Demo media instructions: `docs/demo-media.md`.

## Post-Approval Operations

- Update the target row in the Listing Targets table with `Approved` status.
- Add the public listing URL once it is visible without maintainer authentication.
- Record approval in the Submission Log table with the release version.
- Open a follow-up issue for any reviewer-requested wording changes.
- Re-run `pnpm run metadata:check` after any version bump.
- Re-run `pnpm run submission:check` after any metadata update.
- Re-run `pnpm run docs:tools:check` after any tool registration change.
- Re-run `uv run --all-extras properdocs build -f mkdocs.yml --strict` after any documentation update.
- Re-sync `mcp.json` and `server.json` from `pyproject.toml` after version changes.
- Publish a patch release if a directory requires metadata changes tied to package version.
- Keep release notes concise and do not add reviewer-private details to public changelog entries.
- If Anthropic triggers a re-review, freeze public listing text until the new review outcome is known.
- If ChatGPT Apps requests new screenshots, replace placeholders and rerun `SUBMISSION_MODE=1 pnpm run submission:check`.
- If the MCP registry rejects schema data, fix `server.json` first and regenerate dependent metadata.

## Anthropic Re-review Procedure

- Confirm current listing URL still resolves.
- Confirm repository default branch still contains the approved metadata.
- Confirm privacy policy effective date is current enough for the review period.
- Confirm reviewer prompts still run against `tests/fixtures/benchmark_projects/pass_sensor_node/demo.kicad_pro`.
- Confirm manufacturing export remains gated by `project_quality_gate`.
- Confirm default stdio path still has no server network egress.
- Record re-review start and completion in the Submission Log.

## ChatGPT Apps Update Procedure

- Confirm `oaslananka.dev` domain verification remains valid.
- Confirm screenshots meet the current platform minimum size.
- Confirm the short description remains under 80 characters.
- Confirm the long description remains under 500 characters.
- Confirm tool annotations still expose read-only, destructive, and open-world hints.
- Confirm English is the only claimed launch locale unless localization has shipped.
- Record dashboard publish changes in the Submission Log.

## MCP Registry Update Procedure

- Run `uv run --all-extras python scripts/publish_mcp_registry.py --dry-run`.
- Inspect the generated payload for package and image identifiers.
- Verify PyPI version availability.
- Verify GHCR image digest and provenance.
- Verify Sigstore identity.
- Submit live only after dry-run output matches `server.json`.
- Record the registry response in the Submission Log.

## Maintainer Identity

- Maintainer: Osman Aslan.
- GitHub handle: `oaslananka`.
- Contact route: GitHub issues at `https://github.com/oaslananka/kicad-mcp/issues`.
- No co-maintainer or external agency identity should be added to listing forms.
- No automated tool attribution should be added to listing forms.
- No co-author trailers should be added to public listing metadata.

## Listing Risk Register

- Risk: screenshot placeholders remain in final production submission. Control: `SUBMISSION_MODE=1 pnpm run submission:check`.
- Risk: package metadata drifts. Control: `pnpm run metadata:check`.
- Risk: tool catalog drifts. Control: `pnpm run docs:tools:check`.
- Risk: old namespace returns. Control: `pnpm run submission:check` namespace checks.
- Risk: runner policy regresses. Control: self-hosted runner checks in `pnpm run submission:check`.
- Risk: privacy page missing. Control: docs build and submission readiness validator.
- Risk: registry schema changes. Control: cached schema validation and dry-run publish.
- Risk: CI environment drift. Control: self-hosted smoke workflows and local final gate.
- Risk: release artifact provenance missing. Control: Sigstore, GHCR provenance, checksums, and SBOM review.
- Risk: reviewer uses a wrong local path. Control: reviewer prompt docs explain fixture path failure handling.

## Manual Review Checklist

- Confirm `PUBLIC_LISTING_READY.md` exists before submitting.
- Confirm current branch was merged or intentionally selected for release evidence.
- Confirm working tree is clean before copying field values.
- Confirm `server.json` and `mcp.json` versions match release version.
- Confirm external forms use `oaslananka` account ownership only.
- Confirm all screenshots avoid private data.
- Confirm all demo media avoids private paths and hostnames.
- Confirm privacy language says telemetry is disabled by default and optional OpenTelemetry export is explicit.
- Confirm safety language says KiCad CLI is the required subprocess.
- Confirm optional Freerouting Docker is described as opt-in.
- Confirm support path points to GitHub issues.
- Confirm listing URLs are written back after approval.

## Completion Rule

This file is not a substitute for the final gate. The repository is ready for public listing submission only when `PUBLIC_LISTING_READY.md` says `READY FOR SUBMISSION` and the final acceptance gate is green.
