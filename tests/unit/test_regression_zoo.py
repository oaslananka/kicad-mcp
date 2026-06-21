"""Regression zoo + benchmark suite for headless engines (issue #159).

Covers:
- a synthetic large-board generator (no committed multi-MB fixtures);
- runtime + peak-memory benchmarks for the headless visual-QA and contract
  parsers, guarded by generous tolerances so pathological regressions fail CI;
- robustness against malformed S-expressions and unicode net names/paths;
- a consistency check that every manifest fixture directory actually exists.

Heavy timing checks are marked ``benchmark`` so CI can run a fast subset by
default (``-m "not benchmark"``) and the full suite on a schedule.
"""

from __future__ import annotations

import json
import time
import tracemalloc
from pathlib import Path

import pytest
import yaml

from kicad_mcp.models import visual_qa
from kicad_mcp.models.contract_verifier import parse_footprint, parse_symbol_pins
from tests.synthetic import (
    generate_resistor_grid,
    generate_unicode_schematic,
    malformed_schematics,
)

FIXTURES_ROOT = Path(__file__).resolve().parents[1] / "fixtures"
MANIFEST_PATH = FIXTURES_ROOT / "manifest.yaml"


def test_synthetic_generator_scales() -> None:
    text = generate_resistor_grid(50)
    symbols = visual_qa.parse_symbols(text)
    labels = visual_qa.parse_labels(text)
    assert len(symbols) == 50
    assert len(labels) == 50
    # A clean grid must not trip readability heuristics.
    report = visual_qa.run_visual_qa(text)
    assert report["status"] == "PASS"


def test_malformed_sexpr_does_not_crash() -> None:
    for name, text in malformed_schematics().items():
        # None of these may raise; engines must degrade gracefully.
        report = visual_qa.run_visual_qa(text)
        assert isinstance(report, dict), name
        assert "status" in report, name
        assert isinstance(parse_symbol_pins(text), tuple), name
        assert parse_footprint(text).connectable_pads == (), name


def test_unicode_net_names_are_preserved() -> None:
    text = generate_unicode_schematic()
    labels = {label.text for label in visual_qa.parse_labels(text)}
    assert "GÜÇ_3V3" in labels
    assert "TOPRAK" in labels
    report = visual_qa.run_visual_qa(text)
    assert report["status"] in {"PASS", "INFO", "WARN"}


@pytest.mark.anyio
async def test_unicode_project_path(tmp_path: Path) -> None:
    """Tools must work from a project directory with non-ASCII characters."""
    from kicad_mcp.server import create_server
    from tests.conftest import call_tool_text

    project_dir = tmp_path / "Ölçüm_Kartı"
    project_dir.mkdir()
    (project_dir / "test.kicad_pro").write_text("{}", encoding="utf-8")
    (project_dir / "test.kicad_pcb").write_text("", encoding="utf-8")
    (project_dir / "test.kicad_sch").write_text(generate_unicode_schematic(), encoding="utf-8")

    server = create_server()
    await call_tool_text(server, "kicad_set_project", {"project_dir": str(project_dir)})
    raw = await call_tool_text(server, "sch_visual_qa", {})
    payload = json.loads(raw)
    assert "sheets" in payload


def test_manifest_fixture_dirs_exist() -> None:
    manifest = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))
    missing = [
        entry["id"] for entry in manifest["fixtures"] if not (FIXTURES_ROOT / entry["dir"]).is_dir()
    ]
    assert missing == [], f"Manifest references missing fixture dirs: {missing}"


@pytest.mark.benchmark
def test_visual_qa_large_board_runtime_and_memory() -> None:
    """500-component board: visual QA must stay well under a generous budget."""
    text = generate_resistor_grid(500)

    tracemalloc.start()
    start = time.perf_counter()
    report = visual_qa.run_visual_qa(text)
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    _current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    assert report["symbol_count"] == 500
    assert report["status"] == "PASS"
    # Generous regression ceilings — these catch O(n^3) blowups, not normal jitter.
    assert elapsed_ms < 5000.0, f"visual QA took {elapsed_ms:.0f} ms for 500 components"
    assert peak < 256 * 1024 * 1024, f"visual QA peaked at {peak / 1e6:.1f} MB"


@pytest.mark.benchmark
def test_symbol_parse_scales_linearly() -> None:
    """Parsing throughput should grow roughly linearly, not super-linearly."""
    small = generate_resistor_grid(100)
    large = generate_resistor_grid(400)

    def _time(text: str) -> float:
        start = time.perf_counter()
        visual_qa.parse_symbols(text)
        return time.perf_counter() - start

    t_small = _time(small)
    t_large = _time(large)
    # 4x the work should not cost more than ~12x the time (loose super-linear guard).
    if t_small > 0:
        assert t_large / t_small < 12.0, f"parse scaling {t_large / t_small:.1f}x for 4x size"
