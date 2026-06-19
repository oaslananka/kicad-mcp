from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

from kicad_mcp.tools import schematic


def test_file_backed_schematic_writes_are_serialized(monkeypatch, tmp_path) -> None:
    sch_file = tmp_path / "demo.kicad_sch"
    sch_file.write_text("(kicad_sch)\n", encoding="utf-8")
    monkeypatch.setattr(schematic, "get_config", lambda: SimpleNamespace(sch_file=sch_file))
    monkeypatch.setattr(schematic, "clear_ttl_cache", lambda: None)

    active = 0
    max_active = 0
    active_lock = threading.Lock()

    def append_marker(index: int) -> str:
        def mutator(current: str) -> str:
            nonlocal active, max_active
            with active_lock:
                active += 1
                max_active = max(max_active, active)
            try:
                time.sleep(0.01)
                return current + f'(marker "{index}")\n'
            finally:
                with active_lock:
                    active -= 1

        return schematic._transactional_write_to_schematic(mutator)

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(append_marker, range(40)))

    assert set(results) == {str(sch_file)}
    assert max_active == 1
    content = sch_file.read_text(encoding="utf-8")
    for index in range(40):
        assert content.count(f'(marker "{index}")') == 1
