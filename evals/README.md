# kicad-mcp evals

Measurable quality signals for the agent-facing surface. The first harness is
**tool selection**: with ~350 tools, the biggest risk is the model calling the
*wrong* tool — or a destructive one for a read-only request — not missing features.

## Tool-selection eval

- Dataset: [`tool_selection/cases.yaml`](tool_selection/cases.yaml) — each case maps
  a user intent to `expected_tools` (should be called) and `forbidden_tools` (must
  not be called). A case passes when every expected tool was called and no forbidden
  tool was.
- Harness: [`src/kicad_mcp/evals/tool_selection.py`](../src/kicad_mcp/evals/tool_selection.py)
  — pure, dependency-free loader + scorer (`recall`, forbidden-tool `violations`,
  per-case `passed`) and an `aggregate` roll-up (pass rate, mean recall).
- The dataset is kept honest by `tests/unit/test_tool_selection_eval.py`, which
  validates the schema and asserts every referenced tool name is actually
  registered — so the suite cannot drift to stale/typo'd tool names.

### Running against a model

The harness is model-agnostic. Supply an `agent` callable that returns the tool
names a model chose for a prompt, then score:

```python
from kicad_mcp.evals.tool_selection import load_cases, run_eval, aggregate

cases = load_cases("evals/tool_selection/cases.yaml")

def agent(prompt: str) -> list[str]:
    # Drive your MCP host / model here and return the tool names it called.
    ...

results = run_eval(cases, agent)
print(aggregate(results))            # {'cases': 8, 'passed': ..., 'pass_rate': ..., ...}
for r in results:
    if not r.passed:
        print(r.case_id, "missing", r.missing_expected, "forbidden", r.forbidden_called)
```

Wiring a live model is intentionally left to the caller so the dataset and scorer
stay fast and headless in CI; the model run is a separate, billed step.

### Adding cases

Add an entry to `cases.yaml` with a unique `id`, a `prompt`, `expected_tools`, and
(usually) `forbidden_tools`. Keep tool names spelled exactly as registered — the
integrity test will fail otherwise. Prefer cases that pin a *behavioural contract*:
read-only intents should forbid mutating/destructive tools.
