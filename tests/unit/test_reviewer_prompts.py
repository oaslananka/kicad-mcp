from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROMPTS_PATH = ROOT / "tests" / "reviewer" / "prompts.json"


def test_reviewer_prompts_schema() -> None:
    payload = json.loads(PROMPTS_PATH.read_text(encoding="utf-8"))

    assert payload["fixture"] == "tests/fixtures/benchmark_projects/pass_sensor_node"
    prompts = payload["prompts"]
    assert len(prompts) == 5

    ids = [entry["id"] for entry in prompts]
    assert len(ids) == len(set(ids))

    for entry in prompts:
        assert entry["id"]
        assert entry["prompt"].strip()
        assert isinstance(entry["expected_tool_calls"], list)
        assert entry["expected_tool_calls"]
        assert entry["pass_criteria"].strip()
