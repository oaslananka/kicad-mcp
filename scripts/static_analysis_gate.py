#!/usr/bin/env python3
"""No-regression gates for static analysis tools with existing baselines."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from typing import Any


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, check=False, text=True, capture_output=True)


def _pyright(args: argparse.Namespace) -> int:
    result = _run(["pyright", "--outputjson"])
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return result.returncode or 1

    summary = payload.get("summary", {})
    error_count = int(summary.get("errorCount", 0))
    warning_count = int(summary.get("warningCount", 0))
    print(
        f"Pyright baseline gate: {error_count} error(s), {warning_count} warning(s); "
        f"allowed errors: {args.max_errors}."
    )
    if error_count > args.max_errors:
        diagnostics = payload.get("generalDiagnostics", [])
        if isinstance(diagnostics, list):
            for diagnostic in diagnostics[:50]:
                if not isinstance(diagnostic, dict):
                    continue
                file_name = diagnostic.get("file", "<unknown>")
                message = str(diagnostic.get("message", "")).splitlines()[0]
                rule = diagnostic.get("rule", "")
                print(f"{file_name}: {message} ({rule})", file=sys.stderr)
        print(
            f"Pyright errors increased above baseline ({error_count} > {args.max_errors}).",
            file=sys.stderr,
        )
        return 1
    return 0


def _radon_rank_counts(payload: dict[str, list[dict[str, Any]]]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for blocks in payload.values():
        for block in blocks:
            rank = block.get("rank")
            if isinstance(rank, str) and rank in {"C", "D", "E", "F"}:
                counts[rank] += 1
    return counts


def _radon(args: argparse.Namespace) -> int:
    display = _run(["radon", "cc", "src", "-s", "-n", "C", "--total-average"])
    if display.stdout:
        print(display.stdout, end="")
    if display.stderr:
        print(display.stderr, end="", file=sys.stderr)
    if display.returncode != 0:
        return display.returncode

    result = _run(["radon", "cc", "src", "-s", "-n", "C", "-j"])
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    if result.returncode != 0:
        return result.returncode

    payload = json.loads(result.stdout)
    counts = _radon_rank_counts(payload)
    allowed = {
        "C": args.max_c,
        "D": args.max_d,
        "E": args.max_e,
        "F": args.max_f,
    }
    print(
        "Radon baseline gate: "
        + ", ".join(f"{rank}={counts[rank]}/{allowed[rank]}" for rank in ["C", "D", "E", "F"])
    )
    failures = [rank for rank, maximum in allowed.items() if counts[rank] > maximum]
    if failures:
        rendered = ", ".join(
            f"{rank} increased to {counts[rank]} above baseline {allowed[rank]}"
            for rank in failures
        )
        print(f"Radon complexity baseline exceeded: {rendered}.", file=sys.stderr)
        return 1
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="tool", required=True)

    pyright = subparsers.add_parser("pyright", help="Run pyright with an error baseline.")
    pyright.add_argument("--max-errors", type=int, required=True)

    radon = subparsers.add_parser("radon", help="Run radon with rank-count baselines.")
    radon.add_argument("--max-c", type=int, required=True)
    radon.add_argument("--max-d", type=int, required=True)
    radon.add_argument("--max-e", type=int, required=True)
    radon.add_argument("--max-f", type=int, required=True)

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.tool == "pyright":
        return _pyright(args)
    if args.tool == "radon":
        return _radon(args)
    raise AssertionError(f"unknown tool: {args.tool}")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
