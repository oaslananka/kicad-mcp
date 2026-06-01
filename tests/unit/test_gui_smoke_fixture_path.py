from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType


def _load_gui_smoke_module() -> ModuleType:
    module_path = Path(__file__).resolve().parents[1] / "gui" / "test_kicad_gui_live_context.py"
    spec = importlib.util.spec_from_file_location("test_kicad_gui_live_context", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load GUI smoke test module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_issue_186_gui_smoke_uses_shared_fixture_corpus() -> None:
    gui_smoke = _load_gui_smoke_module()
    expected_root = (
        gui_smoke.REPO_ROOT
        / "packages"
        / "kicad-fixtures"
        / "fixtures"
        / gui_smoke.GUI_SMOKE_FIXTURE_ID
    )

    assert gui_smoke.FIXTURE_ROOT == expected_root
    assert gui_smoke.FIXTURE_ROOT.is_dir()
    assert (gui_smoke.FIXTURE_ROOT / "clean-led-kicad10.kicad_pro").is_file()
