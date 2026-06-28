"""Atheris fuzz target for shared KiCad S-expression helpers.

Run locally with:

    uv run --all-extras --with atheris==3.1.0 python fuzz/fuzz_sexpr.py -runs=512
"""

from __future__ import annotations

import sys

import atheris  # type: ignore[import-not-found]

with atheris.instrument_imports():
    from kicad_mcp.utils.sexpr import (
        _escape_sexpr_string,
        _extract_block,
        _sexpr_string,
        _unescape_sexpr_string,
    )

_MAX_CHARS = 4096


def _normalize_newlines(value: str) -> str:
    return value.replace("\r\n", "\n").replace("\r", "\n")


def TestOneInput(data: bytes) -> None:  # noqa: N802 - Atheris/libFuzzer entry point
    """Exercise S-expression escaping, unescaping, and block extraction."""
    text = data.decode("utf-8", errors="replace")[:_MAX_CHARS]

    escaped = _escape_sexpr_string(text)
    if _unescape_sexpr_string(escaped) != _normalize_newlines(text):
        raise AssertionError("S-expression escape/unescape round-trip changed text")

    quoted = _sexpr_string(text)
    if not (quoted.startswith('"') and quoted.endswith('"')):
        raise AssertionError("S-expression string renderer did not quote output")

    for start in {0, text.find("("), max(0, len(text) // 2)}:
        if start >= 0 and start < len(text):
            _extract_block(text, start)


def main() -> None:
    """Run the fuzz target."""
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
