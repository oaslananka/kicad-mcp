"""Shared helpers for KiCad S-expression text handling."""

from __future__ import annotations


def _escape_sexpr_string(value: str) -> str:
    """Escape a Python string for inclusion in a KiCad S-expression."""
    return (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .replace("\n", "\\n")
    )


def _sexpr_string(value: str) -> str:
    """Wrap an escaped KiCad S-expression string in quotes."""
    return f'"{_escape_sexpr_string(value)}"'


def _unescape_sexpr_string(value: str) -> str:
    """Unescape a KiCad S-expression string payload."""
    chars: list[str] = []
    escaped = False
    for char in value:
        if escaped:
            chars.append("\n" if char == "n" else char)
            escaped = False
        elif char == "\\":
            escaped = True
        else:
            chars.append(char)
    if escaped:
        chars.append("\\")
    return "".join(chars)


def _extract_block(content: str, start: int) -> tuple[str, int]:
    """Extract a balanced S-expression block starting at ``start``."""
    depth = 0
    in_string = False
    escaped = False
    for index, char in enumerate(content[start:]):
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
        elif char == '"':
            in_string = True
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return content[start : start + index + 1], index + 1
    return "", 0


__all__ = [
    "_escape_sexpr_string",
    "_extract_block",
    "_sexpr_string",
    "_unescape_sexpr_string",
]
