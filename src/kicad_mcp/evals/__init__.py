"""Evaluation harnesses for kicad-mcp.

Hosts the tool-selection eval and the golden-corpus eval:

- **Tool-selection eval:** a golden prompt suite plus a pure scorer that measures
  whether an agent calls the right tools (recall) and avoids forbidden ones.
- **Golden-corpus eval:** a project-level end-to-end benchmark that loads golden
  KiCad projects from ``evals/golden_corpus.yaml``, validates their structure,
  and (when KiCad is available) runs quality gates against answer keys.
"""

from .corpus import (
    CorpusEvalResult,
    CorpusEvalSummary,
    GoldenProject,
    aggregate_metrics,
    evaluate_corpus,
    evaluate_project,
    load_corpus,
)
from .tool_selection import (
    CaseResult,
    EvalCase,
    aggregate,
    all_referenced_tools,
    load_cases,
    run_eval,
    score_case,
)

__all__ = [
    "CaseResult",
    "CorpusEvalResult",
    "CorpusEvalSummary",
    "EvalCase",
    "GoldenProject",
    "aggregate",
    "aggregate_metrics",
    "all_referenced_tools",
    "evaluate_corpus",
    "evaluate_project",
    "load_cases",
    "load_corpus",
    "run_eval",
    "score_case",
]
