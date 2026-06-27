"""SWIG/pcbnew import guard (issue #192).

KiCad's legacy SWIG Python bindings (``pcbnew`` module) have been deprecated
since KiCad 9 and are slated for removal. This server relies exclusively on
``kicad-cli`` (headless) and the IPC API (``kipy``). Importing ``pcbnew``
would silently bind us to a deprecated, version-locked API.

This test greps the production source tree and fails if any file imports
``pcbnew`` directly, ensuring the guard is enforced as part of CI.
"""

from __future__ import annotations

import re
from pathlib import Path

_SRC_ROOT = Path(__file__).parent.parent.parent / "src" / "kicad_mcp"

_SWIG_IMPORT_RE = re.compile(
    r"^\s*(?:import\s+pcbnew|from\s+pcbnew\s+import)",
    re.MULTILINE,
)


def test_no_swig_pcbnew_imports() -> None:
    """Fail if any production source file imports the deprecated pcbnew SWIG module."""
    offenders: list[str] = []
    for py_file in sorted(_SRC_ROOT.rglob("*.py")):
        text = py_file.read_text(encoding="utf-8", errors="ignore")
        if _SWIG_IMPORT_RE.search(text):
            # Docstring mentions are fine; actual import statements are not.
            for lineno, line in enumerate(text.splitlines(), start=1):
                if _SWIG_IMPORT_RE.match(line) and not line.strip().startswith("#"):
                    offenders.append(f"{py_file.relative_to(_SRC_ROOT)}:{lineno}: {line.strip()}")

    assert not offenders, (
        "Found forbidden pcbnew SWIG imports (deprecated since KiCad 9, "
        "slated for removal in KiCad 11). Use kicad-cli or kipy IPC instead:\n"
        + "\n".join(f"  {o}" for o in offenders)
    )
