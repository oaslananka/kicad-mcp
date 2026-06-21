"""Tool-selection eval harness (external review's top recommendation).

With ~350 tools, the dominant quality risk is not missing features but the model
picking the *wrong* tool — or a destructive one for a read-only intent. This module
turns that into a measurable signal:

- a golden dataset of (prompt -> expected_tools / forbidden_tools) cases;
- a pure scorer computing per-case recall and forbidden-tool violations;
- an aggregate roll-up (pass rate, mean recall, total violations).

Everything here is dependency-free and headless. To actually exercise a model, call
``run_eval(cases, agent)`` where ``agent(prompt) -> list[str]`` returns the tool
names the model chose; the model itself lives outside this module.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True, slots=True)
class EvalCase:
    """One golden tool-selection expectation."""

    id: str
    prompt: str
    expected_tools: tuple[str, ...]
    forbidden_tools: tuple[str, ...] = ()
    notes: str = ""


@dataclass(frozen=True, slots=True)
class CaseResult:
    """The scored outcome of running one case against an agent."""

    case_id: str
    called: tuple[str, ...]
    matched_expected: tuple[str, ...]
    missing_expected: tuple[str, ...]
    forbidden_called: tuple[str, ...]
    recall: float
    passed: bool

    def as_dict(self) -> dict[str, object]:
        return {
            "case_id": self.case_id,
            "called": list(self.called),
            "matched_expected": list(self.matched_expected),
            "missing_expected": list(self.missing_expected),
            "forbidden_called": list(self.forbidden_called),
            "recall": round(self.recall, 4),
            "passed": self.passed,
        }


class EvalDatasetError(ValueError):
    """Raised when an eval dataset is structurally invalid."""


def load_cases(path: str | Path) -> list[EvalCase]:
    """Load and validate eval cases from a YAML file (``{cases: [...]}``)."""
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "cases" not in data:
        raise EvalDatasetError("Dataset must be a mapping with a top-level 'cases' list.")
    raw_cases = data["cases"]
    if not isinstance(raw_cases, list) or not raw_cases:
        raise EvalDatasetError("'cases' must be a non-empty list.")

    seen: set[str] = set()
    cases: list[EvalCase] = []
    for index, raw in enumerate(raw_cases):
        if not isinstance(raw, dict):
            raise EvalDatasetError(f"Case #{index} must be a mapping.")
        case_id = str(raw.get("id", "")).strip()
        prompt = str(raw.get("prompt", "")).strip()
        expected = tuple(
            str(t).strip() for t in (raw.get("expected_tools") or []) if str(t).strip()
        )
        forbidden = tuple(
            str(t).strip() for t in (raw.get("forbidden_tools") or []) if str(t).strip()
        )
        if not case_id:
            raise EvalDatasetError(f"Case #{index} is missing an 'id'.")
        if case_id in seen:
            raise EvalDatasetError(f"Duplicate case id: {case_id!r}.")
        seen.add(case_id)
        if not prompt:
            raise EvalDatasetError(f"Case {case_id!r} is missing a 'prompt'.")
        if not expected:
            raise EvalDatasetError(f"Case {case_id!r} needs at least one expected tool.")
        overlap = set(expected) & set(forbidden)
        if overlap:
            raise EvalDatasetError(
                f"Case {case_id!r} lists {sorted(overlap)} as both expected and forbidden."
            )
        cases.append(
            EvalCase(
                id=case_id,
                prompt=prompt,
                expected_tools=expected,
                forbidden_tools=forbidden,
                notes=str(raw.get("notes", "")).strip(),
            )
        )
    return cases


def score_case(case: EvalCase, called_tools: Iterable[str]) -> CaseResult:
    """Score one case: full recall of expected tools and zero forbidden calls = pass."""
    called = tuple(called_tools)
    called_set = set(called)
    expected_set = set(case.expected_tools)
    forbidden_set = set(case.forbidden_tools)

    matched = expected_set & called_set
    missing = expected_set - called_set
    forbidden_called = forbidden_set & called_set
    recall = len(matched) / len(expected_set) if expected_set else 1.0
    passed = not missing and not forbidden_called

    return CaseResult(
        case_id=case.id,
        called=called,
        matched_expected=tuple(sorted(matched)),
        missing_expected=tuple(sorted(missing)),
        forbidden_called=tuple(sorted(forbidden_called)),
        recall=recall,
        passed=passed,
    )


def aggregate(results: Sequence[CaseResult]) -> dict[str, Any]:
    """Roll case results up into headline metrics."""
    total = len(results)
    if total == 0:
        return {"cases": 0, "passed": 0, "pass_rate": 0.0, "mean_recall": 0.0, "violations": 0}
    passed = sum(1 for result in results if result.passed)
    violations = sum(len(result.forbidden_called) for result in results)
    mean_recall = sum(result.recall for result in results) / total
    return {
        "cases": total,
        "passed": passed,
        "pass_rate": round(passed / total, 4),
        "mean_recall": round(mean_recall, 4),
        "violations": violations,
    }


def run_eval(cases: Sequence[EvalCase], agent: Callable[[str], Iterable[str]]) -> list[CaseResult]:
    """Run every case through ``agent`` (``prompt -> called tool names``) and score it."""
    return [score_case(case, agent(case.prompt)) for case in cases]


def all_referenced_tools(cases: Iterable[EvalCase]) -> set[str]:
    """Return every tool name referenced (expected or forbidden) across cases."""
    names: set[str] = set()
    for case in cases:
        names.update(case.expected_tools)
        names.update(case.forbidden_tools)
    return names
