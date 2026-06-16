"""The error-code catalog stays in sync with the code (work order P1-T8).

Every ``KiCadMcpError`` subclass code (plus the two literal fallback codes) must be
documented in ``docs/errors.md``, so the catalog can never silently drift from the
actual error model.
"""

from __future__ import annotations

import inspect
from pathlib import Path

from kicad_mcp import errors

CATALOG_PATH = Path(__file__).resolve().parents[2] / "docs" / "errors.md"
# Codes that are not exception classes but are emitted as stable payload codes.
_LITERAL_CODES = ("INTERNAL_ERROR", "CONFIGURATION_ERROR")


def _domain_error_codes() -> set[str]:
    codes: set[str] = set()
    for obj in vars(errors).values():
        if inspect.isclass(obj) and issubclass(obj, errors.KiCadMcpError):
            codes.add(obj.code)
    return codes


def test_every_error_code_is_documented() -> None:
    catalog = CATALOG_PATH.read_text(encoding="utf-8")
    expected = _domain_error_codes() | set(_LITERAL_CODES)
    missing = sorted(code for code in expected if f"`{code}`" not in catalog)
    assert not missing, f"Error codes missing from docs/errors.md: {missing}"


def test_catalog_does_not_document_unknown_codes() -> None:
    import re

    catalog = CATALOG_PATH.read_text(encoding="utf-8")
    # Codes are rendered as `UPPER_SNAKE` table cells; collect them from the table rows.
    documented = set(re.findall(r"\| `([A-Z][A-Z_]+)` \|", catalog))
    known = _domain_error_codes() | set(_LITERAL_CODES)
    unknown = sorted(documented - known)
    assert not unknown, f"docs/errors.md documents codes not in errors.py: {unknown}"
