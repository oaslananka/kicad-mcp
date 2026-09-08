# Scope-Aware Live Model Release Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make live-model release readiness block only releases whose configured agent contract changed since the previous published `mcp-server` release, while preserving the existing full-gate/baseline fail-closed policy for changed contracts.

**Architecture:** Extend the existing deterministic release policy with local previous-release tag resolution and a release-to-release contract comparison before baseline validation. If the candidate contract is unchanged, return a successful `none` decision without consulting baseline readiness; if it changed, execute the current baseline approval/freshness/digest rules unchanged. Ensure every release/publish workflow that invokes the policy checks out full Git history so previous tags are available.

**Tech Stack:** Python 3.13, pytest, PyYAML, Git, GitHub Actions YAML, `actions/checkout`, existing workflow-policy/actionlint/security checks.

**Spec:** `docs/superpowers/specs/2026-09-08-scope-live-model-release-gate-design.md`

## Global Constraints

- Keep Live Model Release Gate and baseline promotion fail-closed for actual agent-contract changes.
- Do not treat provider failures as passing evidence.
- Do not auto-promote baselines from CI.
- Do not decide from semantic version bump type; compare the configured agent contract bytes.
- Fail closed when the prior published server release cannot be identified or read.
- Keep deterministic release, unit, integration, replay, security, packaging, metadata, and required-status checks unchanged.
- Add no provider payloads, prompts, credentials, or secrets to release-policy output.

---

### Task 1: Resolve the previous published server release deterministically

**Files:**
- Modify: `src/kicad_mcp/evals/release_policy.py`
- Modify: `evals/live/release-policy.yaml`
- Test: `tests/unit/test_live_model_release_policy.py`

**Interfaces:**
- Consumes: `ReleasePolicyConfig`, local Git history, candidate ref.
- Produces: `ReleasePolicyConfig.release_tag_pattern: str` and `resolve_previous_release_ref(repo_root, policy, candidate_ref="HEAD") -> str`.

- [ ] **Step 1: Add failing schema/config tests** asserting `release_tag_pattern` is required, the committed value is `mcp-server-v*`, unsafe/empty patterns are rejected, and `load_release_policy()` exposes the field.

- [ ] **Step 2: Add failing Git fixture tests** that create lightweight and annotated `mcp-server-v*` tags and assert the resolver selects the highest version-sorted reachable tag whose commit differs from the candidate commit, including the case where the current release tag points at the candidate and must be skipped.

- [ ] **Step 3: Add a fail-closed test** asserting `ReleasePolicyError` when no prior matching reachable release tag exists.

- [ ] **Step 4: Run the new tests and confirm RED.**

Run:
```bash
.venv/bin/python -m pytest tests/unit/test_live_model_release_policy.py -q
```
Expected: failures for missing `release_tag_pattern` / resolver behavior.

- [ ] **Step 5: Implement the minimal policy schema and resolver.**

Implementation requirements:
```python
@dataclass(frozen=True, slots=True)
class ReleasePolicyConfig:
    baseline_max_age_days: int
    release_pull_request_head: str
    release_tag_pattern: str
    minimum_smoke_configurations: int
    agent_contract_paths: tuple[str, ...]
```

Add `release_tag_pattern` to `_POLICY_KEYS`, validate it is a non-empty relative tag glob without whitespace-only content, and load it from YAML.

Resolver behavior:
```python
def resolve_previous_release_ref(
    repo_root: str | Path,
    policy: ReleasePolicyConfig,
    *,
    candidate_ref: str = "HEAD",
) -> str:
    ...
```

Use local Git only. Resolve `candidate_ref` to a commit SHA, enumerate `git tag --merged <candidate_ref> --list <pattern> --sort=-version:refname`, peel each tag with `<tag>^{commit}`, skip tags resolving to the candidate commit, return the first remaining tag, and raise `ReleasePolicyError` when none is usable.

- [ ] **Step 6: Set the committed policy field.**

`evals/live/release-policy.yaml` must contain:
```yaml
release_tag_pattern: mcp-server-v*
```

- [ ] **Step 7: Run the focused tests and confirm GREEN.**

- [ ] **Step 8: Commit Task 1.**

```bash
git add src/kicad_mcp/evals/release_policy.py evals/live/release-policy.yaml tests/unit/test_live_model_release_policy.py
git commit -m "feat(evals): resolve prior server release for assurance"
```

---

### Task 2: Make release readiness contract-delta aware

**Files:**
- Modify: `src/kicad_mcp/evals/release_policy.py`
- Test: `tests/unit/test_live_model_release_policy.py`

**Interfaces:**
- Consumes: `resolve_previous_release_ref(...)`, `compute_agent_contract_digest(...)`, existing baseline metadata.
- Produces: `ReleasePolicyDecision.release_base_ref: str | None` and `ReleasePolicyDecision.release_contract_changed: bool | None`; updated `evaluate_release_readiness(...)` semantics.

- [ ] **Step 1: Add failing decision tests** for these exact cases:
  - unapproved baseline + unchanged contract since previous release => `mode="none"`, `reason="no_agent_contract_change_since_release"`;
  - stale baseline + unchanged contract => same successful `none` decision;
  - unapproved baseline + changed contract => existing `full/baseline_unapproved`;
  - stale baseline + changed contract => existing `full/baseline_stale`;
  - fresh matching baseline + changed contract => existing `smoke/approved_baseline_reusable`.

Each release decision must expose the selected base tag and boolean changed flag.

- [ ] **Step 2: Add regression tests** asserting push/noop decisions set `release_base_ref is None` and `release_contract_changed is None`.

- [ ] **Step 3: Run the focused tests and confirm RED.**

- [ ] **Step 4: Extend `ReleasePolicyDecision`.**

Required fields:
```python
release_base_ref: str | None
release_contract_changed: bool | None
```

`as_dict()` must emit both fields without removing existing output keys.

- [ ] **Step 5: Implement the two-stage release decision.**

At the start of `evaluate_release_readiness()`:
1. load policy and baseline;
2. resolve previous release tag;
3. compute candidate and previous-release contract digests;
4. if equal, return `mode="none"`, `reason="no_agent_contract_change_since_release"`, the selected tag, and `release_contract_changed=False` without requiring approved baseline metadata;
5. if different, set `release_contract_changed=True` and run the existing baseline checks unchanged.

All changed-contract return branches must preserve their existing `mode` and `reason` strings and include the release-base audit fields.

- [ ] **Step 6: Run focused tests and confirm GREEN.**

- [ ] **Step 7: Commit Task 2.**

```bash
git add src/kicad_mcp/evals/release_policy.py tests/unit/test_live_model_release_policy.py
git commit -m "fix(evals): scope release readiness to contract changes"
```

---

### Task 3: Expose release comparison context through the CLI

**Files:**
- Modify: `scripts/check_live_model_release_policy.py`
- Test: `tests/unit/test_live_model_release_policy.py`

**Interfaces:**
- Consumes: extended `ReleasePolicyDecision`.
- Produces GitHub outputs `release_base_ref` and `release_contract_changed`.

- [ ] **Step 1: Extend the CLI output test** so a release decision writes:
```text
release_base_ref=mcp-server-v1.0.0
release_contract_changed=false
```
for an unchanged fixture.

- [ ] **Step 2: Add/adjust CLI fail-closed coverage** so changed contract + unapproved baseline still returns exit 1 with `--require-ready`, while unchanged contract + unapproved baseline returns exit 0.

- [ ] **Step 3: Run the CLI-focused tests and confirm RED.**

- [ ] **Step 4: Update `_write_outputs()`.**

Serialize:
```python
"release_base_ref": decision.release_base_ref or "",
"release_contract_changed": (
    "" if decision.release_contract_changed is None
    else str(decision.release_contract_changed).lower()
),
```

Do not change `--require-ready`: it must continue to fail only when `decision.mode == "full"`.

- [ ] **Step 5: Run the release-policy unit file and confirm GREEN.**

- [ ] **Step 6: Commit Task 3.**

```bash
git add scripts/check_live_model_release_policy.py tests/unit/test_live_model_release_policy.py
git commit -m "feat(evals): report release contract comparison"
```

---

### Task 4: Ensure release and publish workflows fetch prior release tags

**Files:**
- Modify: `.github/workflows/ci.yml`
- Modify: `.github/workflows/release.yml`
- Modify: `.github/workflows/gui-release.yml`
- Modify: `.github/workflows/publish-kicad-pcm.yml`
- Modify: `.github/workflows/publish-mcp-container.yml`
- Modify: `.github/workflows/publish-mcp-registry.yml`
- Modify: `.github/workflows/publish-mcpb.yml`
- Modify: `.github/workflows/publish-npm.yml`
- Modify: `.github/workflows/publish-protocol-schemas.yml`
- Modify: `.github/workflows/publish-python.yml`
- Test: `tests/unit/test_live_model_release_policy.py`
- Test: `tests/unit/test_release_hardening.py`

**Interfaces:**
- Consumes: Git-history requirement of `resolve_previous_release_ref(...)`.
- Produces: full-history checkout before every `check_live_model_release_policy.py ... release` invocation.

- [ ] **Step 1: Add failing workflow tests** that parse/inspect every workflow containing `--require-ready release` and assert the checkout feeding that readiness step has `fetch-depth: 0`.

The test must cover all current release/publish workflows listed above and fail if a future readiness workflow is added without full history.

- [ ] **Step 2: Run the workflow tests and confirm RED.**

- [ ] **Step 3: Add `fetch-depth: 0` to the relevant `actions/checkout` blocks.**

Keep `persist-credentials: false`, existing `ref:` expressions, permissions, environments, and job ordering unchanged.

- [ ] **Step 4: Run release-policy and release-hardening tests and confirm GREEN.**

- [ ] **Step 5: Run workflow validation.**

```bash
corepack pnpm run workflows:policy
corepack pnpm run workflows:lint
corepack pnpm run workflows:security
```
Expected: all pass.

- [ ] **Step 6: Commit Task 4.**

```bash
git add .github/workflows/ci.yml .github/workflows/release.yml .github/workflows/gui-release.yml \
  .github/workflows/publish-kicad-pcm.yml .github/workflows/publish-mcp-container.yml \
  .github/workflows/publish-mcp-registry.yml .github/workflows/publish-mcpb.yml \
  .github/workflows/publish-npm.yml .github/workflows/publish-protocol-schemas.yml \
  .github/workflows/publish-python.yml tests/unit/test_live_model_release_policy.py tests/unit/test_release_hardening.py
git commit -m "ci: fetch release history for live assurance"
```

---

### Task 5: Documentation, end-to-end policy verification, and integration

**Files:**
- Modify: `docs/development/release-process.md`
- Modify: `evals/README.md`
- Review: `docs/superpowers/specs/2026-09-08-scope-live-model-release-gate-design.md`
- Review: all files changed in Tasks 1-4.

**Interfaces:**
- Produces: one protected PR with auditable policy semantics and regression coverage.

- [ ] **Step 1: Document the release boundary**: Live Model Release Gate is blocking only when the configured contract differs from the previous published `mcp-server` release; unchanged releases do not require an approved live baseline; missing prior release history fails closed.

- [ ] **Step 2: Run focused verification.**

```bash
.venv/bin/python -m pytest tests/unit/test_live_model_release_policy.py tests/unit/test_release_hardening.py -q
```

- [ ] **Step 3: Run formatting/lint/type checks.**

```bash
corepack pnpm run format:check
corepack pnpm run lint
corepack pnpm run typecheck
```

- [ ] **Step 4: Run the full unit suite.**

```bash
.venv/bin/python scripts/run_pytest.py unit
```
Expected: exit 0; only pre-existing skips/warnings are acceptable.

- [ ] **Step 5: Run final repository checks.**

```bash
git diff --check
git status --short --branch
```
Review the complete branch diff against `origin/main` and confirm there are no unrelated changes.

- [ ] **Step 6: Verify the current release remains correctly blocked.**

With full history available, run the policy on current branch/repository and confirm the previous release is `mcp-server-v3.34.0`, `release_contract_changed=true`, and the unapproved baseline still yields `mode=full` / `reason=baseline_unapproved`.

- [ ] **Step 7: Verify an unchanged fixture release is allowed.**

Use the unit fixture or a temporary Git fixture with prior tag and byte-identical contract; confirm unapproved baseline yields `mode=none` / `reason=no_agent_contract_change_since_release` and `--require-ready` exits 0.

- [ ] **Step 8: Commit docs and plan checkbox updates.**

```bash
git add docs/development/release-process.md evals/README.md docs/superpowers/plans/2026-09-08-scope-live-model-release-gate.md
git commit -m "docs: explain scope-aware live release assurance"
```

- [ ] **Step 9: Push branch and open a PR** targeting `main` with the spec, behavior matrix, current #849 non-bypass proof, and verification results.

- [ ] **Step 10: Monitor exact-head CI and merge only through the protected process.** Do not bypass required checks.

- [ ] **Step 11: After merge**, allow Release Please #849 to update naturally. Because #849 contains real contract changes, continue to require its already-running/current full live gate and baseline promotion before release.
