from __future__ import annotations

import builtins
import sys
import types
from pathlib import Path

from kicad_mcp import discovery


def test_candidate_cli_paths_cover_darwin_and_linux(monkeypatch) -> None:
    monkeypatch.setattr(discovery.platform, "system", lambda: "Darwin")
    darwin = discovery._candidate_cli_paths()
    assert darwin[0] == Path("/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli")

    monkeypatch.setattr(discovery.platform, "system", lambda: "Linux")
    linux = discovery._candidate_cli_paths()
    assert linux[0] == Path("/usr/bin/kicad-cli")
    assert Path("/flatpak/exports/bin/kicad-cli") in linux


def test_discover_via_kipy_import_error_and_success(monkeypatch, tmp_path: Path) -> None:
    original_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "kipy.kicad":
            raise ImportError("missing")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    assert discovery._discover_via_kipy() is None
    monkeypatch.setattr(builtins, "__import__", original_import)

    cli = tmp_path / "kicad-cli"
    cli.write_text("", encoding="utf-8")

    fake_pkg = types.ModuleType("kipy")
    fake_module = types.ModuleType("kipy.kicad")
    closed: list[str] = []

    class FakeKiCad:
        def __init__(self, *, headless: bool = False, timeout_ms: int = 0) -> None:
            assert headless is True
            assert timeout_ms == 1000

        def get_kicad_binary_path(self, name: str) -> str:
            assert name == "kicad-cli"
            return str(cli)

        def close(self) -> None:
            closed.append("closed")

    fake_module.KiCad = FakeKiCad
    monkeypatch.setitem(sys.modules, "kipy", fake_pkg)
    monkeypatch.setitem(sys.modules, "kipy.kicad", fake_module)

    assert discovery._discover_via_kipy() == cli
    assert closed == ["closed"]


def test_discover_via_kipy_handles_runtime_and_close_failures(monkeypatch) -> None:
    fake_pkg = types.ModuleType("kipy")
    fake_module = types.ModuleType("kipy.kicad")
    debug_events: list[str] = []

    class FakeKiCad:
        def __init__(self, *, headless: bool = False, timeout_ms: int = 0) -> None:
            _ = (headless, timeout_ms)

        def get_kicad_binary_path(self, _name: str) -> str:
            raise RuntimeError("broken")

        def close(self) -> None:
            raise RuntimeError("close failed")

    fake_module.KiCad = FakeKiCad
    monkeypatch.setitem(sys.modules, "kipy", fake_pkg)
    monkeypatch.setitem(sys.modules, "kipy.kicad", fake_module)
    monkeypatch.setattr(
        discovery.logger,
        "debug",
        lambda event, **kwargs: debug_events.append(event),
    )

    assert discovery._discover_via_kipy() is None
    assert debug_events == ["kipy_cli_discovery_failed", "kipy_headless_close_failed"]


def test_discover_kicad_cli_prefers_kipy_path_and_candidates(monkeypatch, tmp_path: Path) -> None:
    kipy_cli = tmp_path / "from-kipy"
    path_cli = tmp_path / "from-path"
    candidate_cli = tmp_path / "candidate"
    kipy_cli.write_text("", encoding="utf-8")
    path_cli.write_text("", encoding="utf-8")
    candidate_cli.write_text("", encoding="utf-8")

    monkeypatch.setattr(discovery, "_discover_via_kipy", lambda: kipy_cli)
    monkeypatch.setattr(discovery.shutil, "which", lambda _name: str(path_cli))
    monkeypatch.setattr(discovery, "_candidate_cli_paths", lambda: [candidate_cli])
    assert discovery.discover_kicad_cli() == kipy_cli

    monkeypatch.setattr(discovery, "_discover_via_kipy", lambda: None)
    assert discovery.discover_kicad_cli() == path_cli

    monkeypatch.setattr(discovery.shutil, "which", lambda _name: None)
    assert discovery.discover_kicad_cli() == candidate_cli

    missing_candidate = tmp_path / "missing-candidate"
    monkeypatch.setattr(discovery, "_candidate_cli_paths", lambda: [missing_candidate])
    assert discovery.discover_kicad_cli() == missing_candidate


def test_get_cli_capabilities_and_recent_projects_cover_fallbacks(
    monkeypatch,
    tmp_path: Path,
) -> None:
    missing_cli = tmp_path / "missing-kicad-cli"
    discovery.get_cli_capabilities.cache_clear()
    monkeypatch.setattr(discovery, "find_kicad_version", lambda _cli: "KiCad 10.0.1")
    assert discovery.get_cli_capabilities(missing_cli).version == "KiCad 10.0.1"

    monkeypatch.setattr(discovery.platform, "system", lambda: "Darwin")
    assert discovery.discover_library_paths(tmp_path / "cli") == {
        "root": None,
        "symbols": None,
        "footprints": None,
    }

    home = tmp_path / "home"
    config_dir = home / "Library" / "Preferences" / "kicad" / "10.0"
    config_dir.mkdir(parents=True)
    (config_dir / "kicad_common.json").write_text("{invalid json", encoding="utf-8")
    monkeypatch.setattr(discovery.Path, "home", lambda: home)
    assert discovery.find_recent_projects() == []

    assert discovery.scan_project_dir(tmp_path / "does-not-exist") == {
        "project": None,
        "pcb": None,
        "schematic": None,
    }
