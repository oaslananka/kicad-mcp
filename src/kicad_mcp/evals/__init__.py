"""Evaluation harnesses for kicad-mcp.

Currently hosts the tool-selection eval: a golden prompt suite plus a pure scorer
that measures whether an agent calls the right tools (recall) and avoids the wrong
ones (forbidden-tool violations) for a given intent. The scoring and dataset are
dependency-free and headless; running the suite against a live model is done by
injecting an ``agent`` callable.
"""

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
    "EvalCase",
    "aggregate",
    "all_referenced_tools",
    "load_cases",
    "run_eval",
    "score_case",
]
