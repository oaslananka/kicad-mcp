# Scope-Aware Live Model Release Gate Design

## Status

Approved direction from the operator: keep Live Model Release Gate as a protected assurance mechanism, but stop treating an unavailable, stale, or unapproved live-model baseline as a universal blocker for every release.

## Problem

The current release policy evaluates only the candidate contract digest against the approved baseline. If the baseline is unapproved, stale, future-dated, or digest-mismatched, `evaluate_release_readiness()` returns `mode=full`, and every Release Please PR plus downstream publish workflow fails closed.

That protects model-facing releases, but it also couples unrelated patch releases to external live-model providers. Provider outages, rate limits, or a pending baseline migration can therefore block a release whose model-facing contract is identical to the previously published server release.

The release gate must remain fail-closed when a release actually changes the versioned live-model/agent contract.

## Goals

1. Block a release on Live Model Release Gate only when the release candidate changes the configured agent contract relative to the previous published `mcp-server` release.
2. Preserve the existing baseline freshness, approval, evidence, and digest checks when such a contract change exists.
3. Allow an unrelated release to proceed when the configured agent contract is byte-identical to the previous published server release, even if the live-model baseline is stale or temporarily unapproved.
4. Keep `Live Model Assurance` and the protected full gate available for model/eval drift, provider changes, scheduled assurance, and baseline promotion.
5. Keep all deterministic release, unit, integration, replay, security, packaging, metadata, and required-status gates unchanged.
6. Fail closed if the previous published server release cannot be identified or its contract cannot be read.

## Non-goals

- Do not remove the Live Model Release Gate.
- Do not weaken safety, forbidden-call, tool-selection, threshold, artifact-integrity, or baseline-promotion checks.
- Do not treat provider failures as successful model evidence.
- Do not auto-promote a baseline from CI.
- Do not bypass the gate merely because a PR is a patch release; the actual contract diff decides.
- Do not redesign the live-model corpus, adapters, or provider matrix in this change.

## Decision

Release readiness becomes a two-stage decision.

### Stage 1: Did this release change the agent contract?

The policy finds the previous published server release using a versioned policy field:

```yaml
release_tag_pattern: mcp-server-v*
```

For candidate ref `HEAD`, it enumerates matching tags reachable from the candidate, resolves each tag to its commit, and selects the newest matching tag whose commit is different from the candidate commit. This is important for post-release and downstream publish workflows, where the newly created current release tag may already point at `HEAD`; that tag must be skipped so the comparison remains against the prior release.

The configured `agent_contract_paths` remain the source of truth for the contract. The policy computes the existing deterministic contract digest at the previous release ref and at the candidate ref.

If the digests match, release readiness is successful regardless of baseline approval/freshness state:

- `mode: none`
- `reason: no_agent_contract_change_since_release`

This does not certify live providers; it only establishes that the release is not changing the contract they are used to assure.

If the digests differ, proceed to Stage 2.

### Stage 2: Is there reusable approved evidence for the changed contract?

For a changed contract, preserve the current rules exactly:

- unapproved baseline -> `full`, block
- baseline approval date in the future -> `full`, block
- baseline older than `baseline_max_age_days` -> `full`, block
- baseline contract digest differs from the candidate digest -> `full`, block
- fresh approved baseline whose digest equals the candidate -> `smoke`, ready

`--require-ready` continues to return non-zero only for `mode=full`.

## Previous Release Resolution

Add one strict helper in `release_policy.py` that resolves the previous release ref locally from Git history. The helper must:

1. use the configured `release_tag_pattern`;
2. consider only tags merged into the candidate ref;
3. resolve annotated/lightweight tags to commit SHAs;
4. skip tags whose resolved commit equals the candidate commit;
5. select the highest version-sorted remaining tag;
6. raise `ReleasePolicyError` when no prior matching release can be established.

An unavailable release base is a hard failure, not a silent bypass.

## Workflow Requirements

Every workflow invoking `check_live_model_release_policy.py ... release` must have the prior release tags/history available locally. The checkout used by the readiness step therefore needs `fetch-depth: 0`.

This applies to the release-readiness lane and downstream server-derived publish lanes that currently enforce this policy. Existing protected credentials, permissions, environments, and publish ordering remain unchanged.

The live-model main-push assurance workflow already uses full history and keeps its existing push classification behavior.

## Audit Output

Extend the release decision with enough machine-readable context to explain why a release was or was not blocked:

- `release_base_ref`: selected previous server release tag or null when not applicable
- `release_contract_changed`: boolean for release decisions, null for push/noop decisions

Keep current digest, baseline digest, age, reason, mode, and required configuration outputs.

No secret/provider payload data is added.

## Failure Semantics

The following remain fail-closed:

- missing or malformed release policy;
- no reachable previous server release tag;
- Git/ref resolution failure;
- contract digest computation failure;
- changed contract with unapproved/stale/mismatched baseline;
- malformed approved baseline evidence.

The only new non-blocking case is: **candidate contract equals the previous published server contract**.

## Current Release #849

This policy change is not a bypass for the current release. Compared with `mcp-server-v3.34.0`, current `main` changes these configured contract files:

- `.github/workflows/live-model-release-gate.yml`
- `docs/tools-reference.generated.md`
- `evals/live/configurations.yaml`
- `evals/tool_selection/cases.yaml`
- `src/kicad_mcp/evals/nvidia_nim_adapter.py`
- `src/kicad_mcp/evals/opencode_cli_adapter.py`

Therefore #849 still legitimately requires a successful full gate and approved baseline under the new policy. The improvement is that future releases with no configured contract delta will not be held hostage by baseline/provider state.

## Tests

Use TDD and add/adjust tests for:

1. unapproved baseline + unchanged contract since previous release -> ready (`none`);
2. stale baseline + unchanged contract -> ready (`none`);
3. unapproved baseline + changed contract -> `full`;
4. stale baseline + changed contract -> `full`;
5. fresh matching baseline + changed contract -> ready (`smoke`);
6. current release tag at candidate commit is skipped and the prior tag is selected;
7. no prior matching release tag -> fail closed;
8. annotated and lightweight tags resolve correctly;
9. CLI outputs include release base and changed flag;
10. all release/publish readiness checkout steps have full history;
11. existing push/noop assurance behavior remains unchanged;
12. workflow policy, actionlint/security, format, lint, typecheck, focused unit tests, and full unit suite remain green.

## Rollout

1. Land this policy change through a protected PR.
2. Do not cancel the already-running full gate for the current release; #849 contains real contract changes and still needs it.
3. After merge, verify release-readiness decisions on a fixture representing both an unchanged patch release and a changed-contract release.
4. Keep the existing baseline-promotion review process.

## Rollback

A single revert restores the current universal baseline-based hard-block behavior. No baseline schema migration or provider secret change is required.
