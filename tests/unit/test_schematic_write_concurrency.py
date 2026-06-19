"""Concurrent file-backed schematic writes must not lose or duplicate blocks.

FastMCP executes synchronous tools in a worker-thread pool, so a batch of write
tools (for example several ``sch_add_no_connect`` calls issued together) can run
the read-mutate-write cycle concurrently. Without serialization each thread reads
the same baseline and clobbers the others, yielding lost or duplicated blocks.
"""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from kicad_mcp.tools import schematic as sch

_MINIMAL_SCH = (
    "(kicad_sch\n"
    "\t(version 20250316)\n"
    '\t(generator "pytest")\n'
    '\t(uuid "00000000-0000-0000-0000-000000000000")\n'
    '\t(paper "A4")\n'
    "\t(lib_symbols)\n"
    "\t(sheet_instances\n"
    '\t\t(path "/" (page "1"))\n'
    "\t)\n"
    "\t(embedded_fonts no)\n"
    ")\n"
)


def test_concurrent_transactional_writes_do_not_race(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sch_file = tmp_path / "concurrent.kicad_sch"
    sch_file.write_text(_MINIMAL_SCH, encoding="utf-8")
    monkeypatch.setattr(sch, "_get_schematic_file", lambda: sch_file)

    count = 40

    def add_marker(index: int) -> None:
        # Each call appends one no-connect marker with a unique x coordinate, so
        # every successful write is independently identifiable in the result.
        sch._transactional_write_to_schematic(
            lambda current: sch._append_before_sheet_instances(
                current, sch.no_connect_block(float(index), 0.0)
            )
        )

    with ThreadPoolExecutor(max_workers=16) as pool:
        list(pool.map(add_marker, range(count)))

    final = sch_file.read_text(encoding="utf-8")
    xs = sorted(int(float(m)) for m in re.findall(r"\(no_connect \(at (\S+) 0\)", final))
    assert xs == list(range(count)), (
        f"expected {count} unique markers, got {len(xs)} "
        f"(duplicates/losses indicate an unsynchronized write cycle)"
    )
