"""Helpers for reading and writing KiCad ``.kicad_dru`` rule files."""

from __future__ import annotations

import re
from typing import cast

from .sexpr import _sexpr_string

type SExprAtom = str
type SExprNode = list[SExprValue]
type SExprValue = SExprAtom | SExprNode

_SAFE_ATOM = re.compile(r"^[A-Za-z0-9_+./:-]+$")


def _tokenize(content: str) -> list[str]:
    tokens: list[str] = []
    index = 0
    while index < len(content):
        char = content[index]
        if char.isspace():
            index += 1
            continue
        if char in {"(", ")"}:
            tokens.append(char)
            index += 1
            continue
        if char == '"':
            cursor = index + 1
            escaped = False
            buffer: list[str] = []
            while cursor < len(content):
                current = content[cursor]
                if escaped:
                    buffer.append(current)
                    escaped = False
                elif current == "\\":
                    escaped = True
                elif current == '"':
                    tokens.append("".join(buffer))
                    index = cursor + 1
                    break
                else:
                    buffer.append(current)
                cursor += 1
            else:
                raise ValueError("Unterminated string literal in .kicad_dru content.")
            continue
        cursor = index
        while (
            cursor < len(content)
            and not content[cursor].isspace()
            and content[cursor]
            not in {
                "(",
                ")",
            }
        ):
            cursor += 1
        tokens.append(content[index:cursor])
        index = cursor
    return tokens


def _parse_expression(tokens: list[str], start_index: int = 0) -> tuple[SExprValue, int]:
    current_item = tokens[start_index]
    if current_item != "(":
        return current_item, start_index + 1

    index = start_index + 1
    result: SExprNode = []
    while index < len(tokens):
        current_item = tokens[index]
        if current_item == ")":
            return result, index + 1
        child, index = _parse_expression(tokens, index)
        result.append(child)
    raise ValueError("Unbalanced parentheses in .kicad_dru content.")


def parse_dru(content: str) -> SExprNode:
    """Parse a KiCad ``.kicad_dru`` file into a simple S-expression tree."""
    tokens = _tokenize(content)
    if not tokens:
        return ["rules"]
    node, next_index = _parse_expression(tokens, 0)
    if next_index != len(tokens):
        raise ValueError("Unexpected trailing tokens in .kicad_dru content.")
    if not isinstance(node, list) or not node or node[0] != "rules":
        raise ValueError("A KiCad .kicad_dru file must have a root '(rules ...)' form.")
    return node


def _format_atom(value: str) -> str:
    return value if _SAFE_ATOM.fullmatch(value) else _sexpr_string(value)


def _dump_expression(node: SExprValue, indent: int = 0) -> str:
    if not isinstance(node, list):
        return _format_atom(node)
    if not node:
        return "()"

    prefix_parts: list[str] = []
    child_index = 0
    while child_index < len(node) and not isinstance(node[child_index], list):
        prefix_parts.append(_format_atom(cast(str, node[child_index])))
        child_index += 1

    indent_text = "  " * indent
    if child_index >= len(node):
        return f"{indent_text}({' '.join(prefix_parts)})"

    lines = [f"{indent_text}({' '.join(prefix_parts)}"]
    for child in node[child_index:]:
        if isinstance(child, list):
            lines.append(_dump_expression(child, indent + 1))
        else:
            lines[-1] += " " + _format_atom(child)
    lines[-1] += ")"
    return "\n".join(lines)


def dump_dru(node: SExprNode) -> str:
    """Serialize a parsed KiCad ``.kicad_dru`` tree."""
    return _dump_expression(node) + "\n"


def iter_rule_nodes(root: SExprNode) -> list[SExprNode]:
    """Return every ``(rule ...)`` node from the supplied ``(rules ...)`` tree."""
    return [child for child in root[1:] if isinstance(child, list) and child and child[0] == "rule"]


def rule_name(rule: SExprNode) -> str:
    """Return the name of a parsed ``(rule ...)`` node."""
    if len(rule) < 2 or isinstance(rule[1], list):
        raise ValueError("Rule nodes must include a quoted name.")
    return rule[1]


def find_rule(root: SExprNode, name: str) -> SExprNode | None:
    """Look up a rule by name."""
    return next((rule for rule in iter_rule_nodes(root) if rule_name(rule) == name), None)


def upsert_rule(root: SExprNode, rule: SExprNode) -> SExprNode:
    """Insert or replace a rule inside the parsed ``(rules ...)`` tree."""
    name = rule_name(rule)
    for index, child in enumerate(root[1:], start=1):
        if isinstance(child, list) and child and child[0] == "rule" and rule_name(child) == name:
            root[index] = rule
            return root
    root.append(rule)
    return root


def delete_rule(root: SExprNode, name: str) -> bool:
    """Delete a rule by name, returning ``True`` when one was removed."""
    for index, child in enumerate(root[1:], start=1):
        if isinstance(child, list) and child and child[0] == "rule" and rule_name(child) == name:
            del root[index]
            return True
    return False
