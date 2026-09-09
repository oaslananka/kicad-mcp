# Short Live Release Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Shorten contract-changing live release readiness by keeping two independent smoke providers while running the full corpus only on NVIDIA at a two-repeat evidence floor.

**Architecture:** Release policy owns the two-provider smoke set, while the baseline owns the one-provider full-benchmark set. Workflows consume those sets according to purpose: routine/main smoke uses policy smoke configurations, the protected release gate smokes both providers, and only NVIDIA produces full benchmark evidence used for baseline promotion.

**Tech Stack:** Python 3.13, PyYAML, pytest, GitHub Actions YAML, uv 0.11.31, Ruff, mypy.

**Spec:** `docs/superpowers/specs/2026-09-09-short-live-release-gate-design.md`

## Global Constraints

- Required smoke providers are exactly `nvidia-nemotron-3-5-lightning-30b-a3b` and `opencode-cli-mimo-v2-5-free`.
- `minimum_smoke_configurations` remains `2`; both provider paths are required.
- The protected full benchmark configuration is exactly `nvidia-nemotron-3-5-lightning-30b-a3b`.
- Baseline `minimum_repeats` becomes `2`.
- Protected gate default repeats is `2`; dispatch accepts only `2..3`.
- Smoke remains fail-closed and sequential.
- No threshold, safety, telemetry, or per-case failure is suppressed.
- OpenCode MiMo remains in `evals/live/configurations.yaml` for smoke/manual diagnostics.

---

### Task 1: Split smoke configuration policy from full baseline configurations

**Files:**
- Modify: `evals/live/release-policy.yaml`
- Modify: `src/kicad_mcp/evals/release_policy.py`
- Modify: `scripts/check_live_model_release_policy.py`
- Test: `tests/unit/test_live_model_release_policy.py`

**Interfaces:**
- Consumes: existing strict policy YAML loader and `ReleasePolicyDecision` serialization.
- Produces: `ReleasePolicyConfig.smoke_configurations: tuple[str, ...]`, `ReleasePolicyDecision.smoke_configurations: tuple[str, ...]`, and GitHub output `smoke_configurations=<json-array>`.

- [ ] **Step 1: Write failing policy tests**

Add tests that construct a policy with:

```yaml
minimum_smoke_configurations: 2
smoke_configurations:
  - alpha
  - beta
```

and assert:

```python
assert policy.smoke_configurations == ("alpha", "beta")
assert decision.smoke_configurations == ("alpha", "beta")
```

Also add explicit failures for duplicate smoke ids and `minimum_smoke_configurations > len(smoke_configurations)`.

- [ ] **Step 2: Run the tests and verify RED**

Run:

```bash
/tmp/kicad-uv-0.11.31/bin/uv run --all-extras python -m pytest -q \
  tests/unit/test_live_model_release_policy.py
```

Expected: failures because the policy schema does not yet accept or expose `smoke_configurations`.

- [ ] **Step 3: Implement strict smoke policy loading**

Update `_POLICY_KEYS`, `ReleasePolicyConfig`, `ReleasePolicyDecision.as_dict()`, all decision constructors, and `load_release_policy()` so the policy requires a unique non-empty smoke list and validates:

```python
if minimum_smoke > len(smoke_configurations):
    raise ReleasePolicyError(
        "minimum_smoke_configurations cannot exceed smoke_configurations."
    )
```

Preserve `required_configurations` on the decision as the full baseline configuration set.

- [ ] **Step 4: Emit a separate GitHub output**

In `scripts/check_live_model_release_policy.py`, write:

```python
"smoke_configurations": json.dumps(
    list(decision.smoke_configurations), separators=(",", ":")
),
```

while retaining the existing `required_configurations` output.

- [ ] **Step 5: Set the committed smoke configuration list**

Add to `evals/live/release-policy.yaml`:

```yaml
smoke_configurations:
  - nvidia-nemotron-3-5-lightning-30b-a3b
  - opencode-cli-mimo-v2-5-free
```

- [ ] **Step 6: Run policy tests and commit**

Run the Task 1 pytest command again; expected PASS.

Commit:

```bash
git add evals/live/release-policy.yaml src/kicad_mcp/evals/release_policy.py \
  scripts/check_live_model_release_policy.py tests/unit/test_live_model_release_policy.py
git commit -m "refactor(evals): separate smoke and benchmark provider sets"
```

---

### Task 2: Make routine smoke assurance consume the policy smoke set

**Files:**
- Modify: `scripts/evaluate_live_model_smoke_assurance.py`
- Modify: `.github/workflows/live-model-assurance.yml`
- Test: `tests/unit/test_live_model_release_policy.py`
- Test: `tests/unit/test_live_model_smoke_assurance.py`

**Interfaces:**
- Consumes: `ReleasePolicyConfig.smoke_configurations` and GitHub output `smoke_configurations` from Task 1.
- Produces: routine main-push smoke execution/evaluation over the two policy smoke providers independent of baseline full-benchmark configuration count.

- [ ] **Step 1: Add RED tests for policy-owned smoke selection**

Assert the assurance workflow exposes and consumes `smoke_configurations`:

```python
assert "smoke_configurations: ${{ steps.policy.outputs.smoke_configurations }}" in workflow
assert "fromJSON(needs.classify.outputs.smoke_configurations)" in workflow
```

Add a script-level or unit test demonstrating smoke assurance receives `policy.smoke_configurations`, not `baseline.required_configurations`.

- [ ] **Step 2: Run focused tests and verify RED**

Run:

```bash
/tmp/kicad-uv-0.11.31/bin/uv run --all-extras python -m pytest -q \
  tests/unit/test_live_model_release_policy.py \
  tests/unit/test_live_model_smoke_assurance.py
```

- [ ] **Step 3: Update smoke assurance script and workflow**

Change `scripts/evaluate_live_model_smoke_assurance.py` to pass:

```python
required_configurations=policy.smoke_configurations
```

Update `live-model-assurance.yml` classify outputs and matrix to use `smoke_configurations`.

- [ ] **Step 4: Re-run focused tests and commit**

Expected: PASS.

Commit:

```bash
git add scripts/evaluate_live_model_smoke_assurance.py \
  .github/workflows/live-model-assurance.yml \
  tests/unit/test_live_model_release_policy.py \
  tests/unit/test_live_model_smoke_assurance.py
git commit -m "fix(evals): keep two-provider routine smoke assurance"
```

---

### Task 3: Reduce the full baseline to one provider and two repeats

**Files:**
- Modify: `evals/live/baselines.yaml`
- Modify: `src/kicad_mcp/evals/release_gate.py`
- Modify: `src/kicad_mcp/evals/release_policy.py`
- Modify: `src/kicad_mcp/evals/baseline_promotion.py`
- Test: `tests/unit/test_live_model_release_gate.py`
- Test: `tests/unit/test_live_model_release_policy.py`
- Test: `tests/unit/test_live_model_baseline_promotion.py`

**Interfaces:**
- Consumes: baseline `required_configurations` as full benchmark configurations.
- Produces: valid one-provider baseline metadata and promotion at `minimum_repeats: 2`.

- [ ] **Step 1: Add RED tests for one full configuration**

Add/adjust tests so:

```python
baseline["required_configurations"] = ["alpha"]
baseline["minimum_repeats"] = 2
```

is accepted by baseline metadata loading, aggregate gate evaluation, and baseline promotion when evidence is clean and has `repeats == 2`.

Retain explicit tests that an empty required list and evidence with `repeats == 1` fail closed.

- [ ] **Step 2: Run focused tests and verify RED**

Run:

```bash
/tmp/kicad-uv-0.11.31/bin/uv run --all-extras python -m pytest -q \
  tests/unit/test_live_model_release_gate.py \
  tests/unit/test_live_model_release_policy.py \
  tests/unit/test_live_model_baseline_promotion.py
```

- [ ] **Step 3: Relax only the full-benchmark cardinality floor**

Change validators from “at least two unique required configurations” to “at least one unique required configuration” in baseline metadata, release gate loading, and baseline promotion. Do not change smoke assurance’s two-provider floor.

- [ ] **Step 4: Update committed pending baseline**

Set:

```yaml
minimum_repeats: 2
required_configurations:
  - nvidia-nemotron-3-5-lightning-30b-a3b
```

Keep `approved: false`, null audit metadata, and `configurations: {}` until a fresh protected gate generates the candidate.

- [ ] **Step 5: Re-run focused tests and commit**

Expected: PASS.

Commit:

```bash
git add evals/live/baselines.yaml src/kicad_mcp/evals/release_gate.py \
  src/kicad_mcp/evals/release_policy.py src/kicad_mcp/evals/baseline_promotion.py \
  tests/unit/test_live_model_release_gate.py tests/unit/test_live_model_release_policy.py \
  tests/unit/test_live_model_baseline_promotion.py
git commit -m "fix(evals): benchmark one provider at two repeats"
```

---

### Task 4: Shorten the protected release-gate workflow

**Files:**
- Modify: `.github/workflows/live-model-release-gate.yml`
- Test: `tests/unit/test_live_model_release_gate.py`

**Interfaces:**
- Consumes: two smoke configuration ids and one full baseline configuration id.
- Produces: a protected run with two sequential smokes, one NVIDIA full benchmark, and aggregate/candidate generation from that benchmark.

- [ ] **Step 1: Add RED workflow-shape tests**

Split smoke and benchmark blocks and assert:

```python
assert smoke_block.count("nvidia-nemotron-3-5-lightning-30b-a3b") == 1
assert smoke_block.count("opencode-cli-mimo-v2-5-free") == 1
assert benchmark_block.count("nvidia-nemotron-3-5-lightning-30b-a3b") == 1
assert "opencode-cli-mimo-v2-5-free" not in benchmark_block
assert "default: 2" in workflow
assert 'test "$REPEATS" -ge 2' in workflow
assert 'test "$REPEATS" -le 3' in workflow
```

Also assert smoke is bounded at 15m/18m and benchmark at 75m/90m.

- [ ] **Step 2: Run release-gate tests and verify RED**

Run:

```bash
/tmp/kicad-uv-0.11.31/bin/uv run --all-extras python -m pytest -q \
  tests/unit/test_live_model_release_gate.py
```

- [ ] **Step 3: Update workflow matrices and bounds**

Keep smoke matrix:

```yaml
configuration:
  - nvidia-nemotron-3-5-lightning-30b-a3b
  - opencode-cli-mimo-v2-5-free
```

Change benchmark matrix to:

```yaml
configuration:
  - nvidia-nemotron-3-5-lightning-30b-a3b
```

Change repeats default/guard to `2..3`, smoke timeout to `15m` inside `18` minutes, and benchmark timeout to `75m` inside `90` minutes.

- [ ] **Step 4: Run release-gate tests and commit**

Expected: PASS.

Commit:

```bash
git add .github/workflows/live-model-release-gate.yml tests/unit/test_live_model_release_gate.py
git commit -m "ci(evals): shorten protected live release gate"
```

---

### Task 5: Update documentation and verify the complete policy contract

**Files:**
- Modify: `evals/README.md`
- Modify: `docs/development/release-process.md`
- Test: all relevant unit suites

**Interfaces:**
- Consumes: Tasks 1–4 behavior.
- Produces: operator documentation matching the shortened gate.

- [ ] **Step 1: Update gate documentation**

Document that both NVIDIA and MiMo must pass smoke, only NVIDIA runs the full corpus, the standard full evidence floor is two repeats, and MiMo remains available for manual diagnostics.

- [ ] **Step 2: Run the focused eval suites**

Run:

```bash
/tmp/kicad-uv-0.11.31/bin/uv run --all-extras python -m pytest -q \
  tests/unit/test_live_model_release_gate.py \
  tests/unit/test_live_model_release_policy.py \
  tests/unit/test_live_model_baseline_promotion.py \
  tests/unit/test_live_model_smoke_assurance.py
```

Expected: PASS.

- [ ] **Step 3: Run workflow and static validation**

Run the repository workflow-policy checker plus:

```bash
/tmp/kicad-uv-0.11.31/bin/uv run --all-extras ruff check \
  src/kicad_mcp/evals/release_policy.py \
  src/kicad_mcp/evals/release_gate.py \
  src/kicad_mcp/evals/baseline_promotion.py \
  scripts/check_live_model_release_policy.py \
  scripts/evaluate_live_model_smoke_assurance.py \
  tests/unit/test_live_model_release_gate.py \
  tests/unit/test_live_model_release_policy.py \
  tests/unit/test_live_model_baseline_promotion.py \
  tests/unit/test_live_model_smoke_assurance.py
```

and full-project mypy using the repository’s configured command.

- [ ] **Step 4: Run full unit verification**

Run the repository unit runner. Any unrelated timing-only benchmark failure must be reproduced on `origin/main` before being classified as pre-existing; do not weaken thresholds.

- [ ] **Step 5: Run security scans**

Run OSV-Scanner against the changed tree/lockfiles and Trivy HIGH/CRITICAL filesystem scanning. No new unreviewed advisory is acceptable.

- [ ] **Step 6: Independent review, final diff check, and commit docs**

Run read-only Codex review against `origin/main`, fix actionable findings, then:

```bash
git diff --check
git status --short
git add evals/README.md docs/development/release-process.md \
  docs/superpowers/specs/2026-09-09-short-live-release-gate-design.md \
  docs/superpowers/plans/2026-09-09-short-live-release-gate.md
git commit -m "docs(evals): document shortened live release gate"
```

---

### Task 6: Protected integration and fresh evidence

**Files:**
- No direct main edits.
- Promotion follow-up modifies only `evals/live/baselines.yaml` from the generated candidate.

**Interfaces:**
- Consumes: verified feature branch and GitHub protected workflows.
- Produces: merged gate policy, fresh protected candidate, promoted baseline, and a release-ready #849.

- [ ] **Step 1: Push branch and open PR**

Use title:

```text
fix(evals): shorten protected live release gate
```

PR body must explain that provider-diverse smoke remains mandatory while only NVIDIA supplies full baseline metrics.

- [ ] **Step 2: Require CI/security/Sonar green**

Wait for exact-head Required PR Gate, coverage, SonarCloud, CodeQL, Semgrep, dependency review, and platform tests. Do not bypass failures.

- [ ] **Step 3: Merge through protected rules**

Squash merge only after the exact PR head is green.

- [ ] **Step 4: Dispatch one fresh Live Model Release Gate on new main**

Use `repeats=2`. Do not start duplicate gates.

- [ ] **Step 5: Validate candidate before promotion**

Require:

```text
source_revision == merged main SHA
workflow_run_id == fresh protected run id
approved == true
minimum_repeats == 2
required_configurations == [nvidia-nemotron-3-5-lightning-30b-a3b]
safety/quality/infrastructure/telemetry/per-case failures == []
```

- [ ] **Step 6: Promote generated baseline through a normal PR**

Replace `evals/live/baselines.yaml` with the generated candidate exactly; do not hand-edit approval metadata. Run focused tests/CI and merge protected.

- [ ] **Step 7: Re-evaluate release PR #849**

Confirm release readiness no longer reports `baseline_unapproved`, wait for required checks, and merge only when protected release governance is green.
