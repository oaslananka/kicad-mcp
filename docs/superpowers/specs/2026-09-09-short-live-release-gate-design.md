# Short Live Release Gate Design

## Context

The protected Live Model Release Gate currently uses the same two configurations for both smoke coverage and full-corpus benchmarking. That preserves provider diversity, but it also makes every contract-changing release wait for a full OpenCode MiMo benchmark that has historically taken about an hour by itself.

The release gate should preserve two independent provider paths for fast fail-closed checks without requiring both providers to run the expensive 65-case corpus.

## Goals

- Keep NVIDIA Nemotron Lightning and OpenCode MiMo as required smoke providers.
- Run the full 65-case benchmark only on NVIDIA Nemotron Lightning.
- Make two full-corpus repetitions the standard release evidence floor.
- Preserve fail-closed safety, selection, infrastructure, telemetry, and per-case checks for full benchmark evidence.
- Preserve MiMo as a versioned configuration that can still be run manually or diagnostically.
- Keep baseline promotion auditable and tied to one protected workflow run and exact source revision.

## Non-goals

- Do not remove OpenCode MiMo from the configuration registry.
- Do not weaken the smoke corpus or its refusal/confirmation/destructive-operation coverage.
- Do not suppress provider, safety, selection, or telemetry failures.
- Do not make release publishing bypass the live-model readiness policy.
- Do not add a third blocking provider.

## Architecture

### Separate smoke and benchmark configuration sets

`evals/live/release-policy.yaml` gains a versioned `smoke_configurations` list. It contains exactly the two independent smoke providers used by protected assurance:

- `nvidia-nemotron-3-5-lightning-30b-a3b`
- `opencode-cli-mimo-v2-5-free`

`minimum_smoke_configurations` remains `2`, so both providers must succeed. Policy loading rejects duplicate/empty smoke ids and rejects a minimum greater than the configured smoke set.

The baseline file continues to use `required_configurations`, but its meaning is narrowed to configurations that must produce full-corpus baseline metrics. For the shortened gate this list contains only:

- `nvidia-nemotron-3-5-lightning-30b-a3b`

This keeps baseline comparison and promotion focused on the one full benchmark while the policy separately preserves provider-diverse smoke coverage.

### Release-policy outputs

`ReleasePolicyDecision` exposes both sets:

- `required_configurations`: full benchmark/baseline configurations.
- `smoke_configurations`: provider-diverse smoke configurations.

`check_live_model_release_policy.py` writes both JSON arrays to GitHub outputs. `live-model-assurance.yml` consumes `smoke_configurations` for routine main-push smoke. Existing release readiness output retains `required_configurations` for auditability of the full baseline set.

### Protected full gate

`.github/workflows/live-model-release-gate.yml` keeps the smoke matrix at two providers but reduces the benchmark matrix to NVIDIA only.

Standard repetitions change from three to two. The workflow input defaults to `2` and allows only `2..3`, preventing accidental 4- or 5-repeat release runs while retaining an explicit deeper-evidence option.

Smoke remains sequential and fail-fast. Its command is bounded at 15 minutes inside an 18-minute job. The NVIDIA full benchmark is bounded at 75 minutes inside a 90-minute job. Aggregate still runs only after smoke succeeds and consumes the single required full benchmark artifact.

### Baseline promotion

`evals/live/baselines.yaml` changes to `minimum_repeats: 2` and one full-benchmark `required_configuration`. Baseline loading, gate evaluation, release-policy metadata loading, and baseline promotion therefore accept one unique full-benchmark configuration while smoke assurance still requires the two policy smoke configurations.

A successful aggregate may generate an approved baseline candidate only when the NVIDIA full evidence is complete, at or above two repeats, and contains no safety, quality, infrastructure, telemetry, or per-case failures. The candidate still records exact source revision, agent-contract digest, workflow run id, aggregate SHA-256, provider identity, metrics, and approval date.

## Failure behavior

- Either smoke provider fails or times out: full benchmark is skipped and the gate fails.
- NVIDIA full benchmark fails, times out, is incomplete, or violates a threshold: aggregate fails and no promotable baseline is accepted.
- MiMo full benchmark is not part of release readiness and therefore cannot delay a release after passing smoke.
- Missing or malformed policy smoke configuration metadata fails closed during policy loading.
- A baseline with zero full-benchmark configurations remains invalid.

## Expected runtime

Historical protected runs show the two smokes finishing in roughly five minutes total and NVIDIA three-repeat full benchmarking in roughly 20–30 minutes. With two repeats and no MiMo full benchmark, the normal protected path is expected to finish in roughly 20–25 minutes, with bounded headroom for provider variance.

## Verification

Required regression coverage includes:

- policy accepts one full baseline configuration plus two smoke configurations;
- policy rejects empty/duplicate/undersized smoke sets;
- routine smoke assurance consumes the policy smoke set rather than the baseline full set;
- release-gate workflow contains both smoke providers but only NVIDIA in the benchmark block;
- standard gate repeats default to two and cannot exceed three;
- baseline promotion and aggregate gate accept one required full configuration at two repeats;
- one required full configuration below two repeats still fails closed;
- docs accurately describe the shortened architecture.

Final verification includes focused eval-policy/gate suites, workflow policy checks, full unit tests, Ruff, mypy, OSV-Scanner, Trivy, SonarCloud PR analysis, and protected GitHub CI before merge.
