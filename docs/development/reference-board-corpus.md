# Reference-board corpus publication contract

Issue #730 requires realistic PCB projects created from written specifications with complete
attempt accounting. This page documents the publication contract used by those future
reference-board runs. The validator described here is infrastructure for that evidence; it
does **not** by itself satisfy the requirement to publish at least three serious reference
boards.

## Canonical bundle layout

Each maintained board is published as one self-contained directory:

```text
<board-root>/
  specification.md
  original-prompt.md
  benchmark.json
  attempt-manifest.json
  attempts/
    <attempt-id>/
      attempt.json
      agent-log.jsonl
      schematic.kicad_sch
      board.kicad_pcb
      ERC.txt
      DRC.txt
      BOM.csv
      manufacturing-report.md
      Gerbers/
```

`benchmark.json` uses the existing `pcb-task-outcome.v1` benchmark contract. Each
`attempt.json` uses the existing `AttemptRecord` contract, so real-board publication does not
create a second success/failure taxonomy or KPI schema.

## Complete attempt denominator

`attempt-manifest.json` is the publication ledger for one board. Its
`pcb-reference-board.v1` records a `reference_inputs_digest` for the specification, original
prompt, and benchmark, plus canonical `attempts/<attempt-id>` directories and a
`sha256:<64 lowercase hex>` evidence digest per attempt. The validator requires exact equality between
manifest entries and direct attempt directories on disk. It then recomputes a deterministic
digest over sorted POSIX relative paths and each file SHA-256. An undisclosed failed attempt
or any post-manifest file addition, removal, or byte change therefore fails validation instead
of silently dropping out of the denominator or reusing stale residual output.

Provider and tool failures remain normal valid attempts and stay in the product-success
denominator. Only an existing `infrastructure_invalid` record that satisfies the reviewed
pre-task contract is separated from that denominator. A successful attempt with
`manual_repair=true` is not publishable as autonomous success. A record declared as `success`
must also be counted as successful by the canonical `aggregate_task_outcomes` quality gates;
failed required stages, validation, recovery/integrity, or manufacturing requirements therefore
make the publication bundle invalid instead of silently relabeling the result.

## Attempt evidence

Every attempt, including failed attempts, must contain `attempt.json` and an ordered
`agent-log.jsonl`. If ERC or DRC is required by the referenced task contract, the attempt must
carry explicit validation evidence recording whether execution was attempted, completed, and
consumed.

A successful attempt additionally requires the final schematic, board, BOM,
manufacturing report, required `ERC.txt`/`DRC.txt`, and a non-empty `Gerbers/` directory. The
validator rejects symlinked bundle, attempt, log, final-design, and manufacturing evidence so
publication cannot silently resolve to unrelated local state.

## Sanitized action history

`agent-log.jsonl` is a reconstruction log, not a raw conversation transcript. Each line is a
strict `pcb-reference-agent-log.v1` event whose `attempt_id` must match `attempt.json`, with a
contiguous sequence starting at 1, a
timezone-aware nondecreasing timestamp, a bounded event name, event/status enums, and optional
scalar-only details.

Events pass the shared evaluation-evidence sanitization guard. The specification, original
prompt, and required successful text artifacts use the same secret/private-path guard. Do not
publish raw provider responses, environment dumps, credentials, secret-bearing strings,
unrelated absolute user paths, or arbitrary nested provider/debug payloads.

## Human manufacturing approval handoff

Reference-board agents do not bypass the production manufacturing human gate. The schematic
and PCB phases remain autonomous, but the manufacturing phase starts only after a reviewer has
approved the exact project state. The runner looks for the fixed project-local file
`reference-manufacturing-approval.json`; arbitrary approval paths are not accepted by the
benchmark harness.

The approval object uses schema `pcb-reference-manufacturing-approval.v1` and binds the reviewer
to the board id, benchmark version, attempt id, exact source revision, and a deterministic SHA-256
over the KiCad schematic/PCB/project/rule files. It also carries the production-required
`approved_by`, `approved_at_utc`, and `approval_scope=manufacturing_release` fields. If the file is
missing, symlinked, malformed, belongs to another attempt/source revision, or the design changed
after review, the manufacturing phase fails before the provider session starts. The same approved
project-file SHA-256 manifest is revalidated by the manufacturing export service immediately before
artifact generation, so state drift during the provider session also fails closed.

The runner also requires the runtime `src/`, `scripts/`, `pyproject.toml`, and `uv.lock` state to be
clean before accepting the source revision as exact. On a valid handoff it adds only the fixed
relative approval path to the manufacturing prompt and records a sanitized
`human_manufacturing_approval` workflow event containing the reviewer, source revision, approval
time, and approved project-state digest. The manufacturing profile does not
expose design-mutation tools, so a post-approval design change requires a new review rather than
reusing stale approval evidence.

## Validate before publication

Run the validator from a clean checkout with the repository's pinned environment:

```bash
uv run --frozen python scripts/validate_reference_board_bundle.py \
  --bundle docs/evidence/reference-boards/<board-id>/<benchmark-version>
```

Success prints only stable public identity and attempt counters. Validation failures are
fail-closed and do not dump the agent log or provider content.

The tree digest is an integrity/freshness binding, not independent proof that an
intentionally re-hashed design was authored by the claimed agent. The returned aggregate is
generated by the existing `aggregate_task_outcomes` path. Board publication must still include
board-specific quality scoring, clean-start/source identity, reproducible manufacturing
outputs, independent reruns, and the physical/reference projects required by #730 before the
corpus can be treated as representative product evidence.
