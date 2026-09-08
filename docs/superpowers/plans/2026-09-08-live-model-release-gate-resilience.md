# Live Model Release Gate Resilience Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the reproducible OpenCode live-gate blockers without weakening release safety or baseline-promotion requirements.

**Architecture:** Keep the aggregate gate fail-closed: adapter failures still block baseline promotion. Improve deterministic recovery only when one catalog tool is uniquely supported by the user prompt, and expand the bounded retry envelope for the two blocking OpenCode CLI configurations so transient provider/invalid-output failures get additional chances rather than being promoted as evidence.

**Tech Stack:** Python 3.13, pytest, GitHub Actions YAML, OpenCode CLI 1.18.10, existing live-model evaluation framework.

**Spec:** `docs/superpowers/plans/2026-09-03-engineering-audit-remediation.md` Task 6 plus the observed failed gate run 34154719676.

## Global Constraints

- Never accept or promote evidence containing adapter, safety, or per-case failures.
- Never persist provider stderr, API keys, prompts, or raw model output in release artifacts.
- Keep retry behavior bounded by configuration and workflow wall-clock time.
- Preserve the existing protected full-gate + reviewed baseline-promotion workflow.

---

### Task 1: Recover uniquely named direct project creation

**Files:**
- Modify: `tests/unit/test_nvidia_nim_eval_adapter.py`
- Modify: `src/kicad_mcp/evals/nvidia_nim_adapter.py`

**Interfaces:**
- Consumes: `_unique_direct_tool_match(prompt, catalog)` and `normalize_classifier_text(...)`.
- Produces: deterministic tie-breaking that rewards exact tool-name token overlap while preserving ambiguity rejection.

- [x] **Step 1: Write a failing regression test** using the generated catalog, prompt `Create a new KiCad project named sensor-node.`, and an unknown selected tool name. Assert normalization recovers `kicad_create_new_project`.
- [x] **Step 2: Run only that test** and confirm it fails with `failure_detail=unknown_tool`.
- [x] **Step 3: Implement the minimal matcher change** by adding a tool-name lexical overlap score to the existing direct-action score; do not use case expectations.
- [x] **Step 4: Run the new test plus all existing unknown-tool/postcondition tests** and confirm they pass, including ambiguity and informational-request rejection.

### Task 2: Give transient OpenCode CLI failures a bounded recovery window

**Files:**
- Modify: `tests/unit/test_opencode_cli_eval_adapter.py`
- Modify: `tests/unit/test_opencode_cli_mimo_candidate.py`
- Modify: `tests/unit/test_live_model_eval_runner.py`
- Modify: `src/kicad_mcp/evals/opencode_cli_adapter.py`
- Modify: `evals/live/configurations.yaml`

**Interfaces:**
- Consumes: sanitized adapter error schema (`retry_after_seconds`) and per-configuration `max_retries`.
- Produces: OpenCode non-zero results as `provider_unavailable` with a bounded 15-second retry hint; blocking OpenCode CLI configurations allow 4 retries (5 total attempts).

- [x] **Step 1: Write failing tests** asserting a non-zero OpenCode CLI subprocess result includes `retry_after_seconds: 15.0`, and both blocking CLI configurations have `max_retries == 4`.
- [x] **Step 2: Run those tests** and confirm they fail against the current 2-retry/no-hint behavior.
- [x] **Step 3: Implement the minimal adapter/config changes** without changing gate classification or baseline rules.
- [x] **Step 4: Run the OpenCode adapter, runner, live-config, and release-gate unit suites** and confirm they pass.

### Task 3: Verification and integration

**Files:**
- Review all modified files above plus this plan.

**Interfaces:**
- Produces: one reviewable bugfix branch ready for GitHub CI and protected merge.

- [x] **Step 1: Run focused pytest suites** for NVIDIA normalization, OpenCode CLI, live runner, release gate, and candidate configuration.
- [x] **Step 2: Run repository formatting/lint/type/workflow-policy checks relevant to the changed files.**
- [x] **Step 3: Run `git diff --check`, inspect the complete diff, and verify the worktree is otherwise clean.**
- [ ] **Step 4: Commit and push the branch, open a PR, monitor CI, and merge only through the repository's protected process.**
- [ ] **Step 5: After merge, dispatch `Live Model Release Gate` on current `main`; if and only if it succeeds, promote its generated reviewed baseline candidate and rerun release PR #849 checks.**
