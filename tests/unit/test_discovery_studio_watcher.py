from __future__ import annotations

import time

from kicad_mcp.config import get_config
from kicad_mcp.discovery import ensure_studio_project_watcher, stop_studio_project_watcher


def test_studio_project_watcher_auto_sets_project(tmp_path, monkeypatch) -> None:
    watch_root = tmp_path / "watch"
    project_dir = watch_root / "demo"
    project_dir.mkdir(parents=True)
    (project_dir / "demo.kicad_pro").write_text("{}", encoding="utf-8")
    (project_dir / "demo.kicad_pcb").write_text("(kicad_pcb)\n", encoding="utf-8")
    (project_dir / "demo.kicad_sch").write_text("(kicad_sch)\n", encoding="utf-8")

    monkeypatch.setattr("kicad_mcp.discovery.random.uniform", lambda _a, _b: 1.0)
    monkeypatch.setattr("kicad_mcp.discovery.logger.warning", lambda *_args, **_kwargs: None)

    stop_studio_project_watcher()
    ensure_studio_project_watcher(watch_root, poll_interval_seconds=0.05)
    (project_dir / "demo.kicad_pro").write_text('{"meta": {"version": 2}}', encoding="utf-8")

    try:
        deadline = time.time() + 2.0
        while time.time() < deadline:
            if get_config().project_dir == project_dir.resolve():
                break
            time.sleep(0.05)
        assert get_config().project_dir == project_dir.resolve()
    finally:
        stop_studio_project_watcher()
