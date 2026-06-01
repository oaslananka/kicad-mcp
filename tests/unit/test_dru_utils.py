from __future__ import annotations

import pytest

from kicad_mcp.utils.dru import (
    delete_rule,
    dump_dru,
    find_rule,
    iter_rule_nodes,
    parse_dru,
    rule_name,
    upsert_rule,
)


def test_parse_dru_handles_empty_content_and_invalid_root() -> None:
    assert parse_dru("") == ["rules"]
    with pytest.raises(ValueError, match="root"):
        parse_dru("(not_rules)")


def test_parse_dru_rejects_unterminated_and_unbalanced_content() -> None:
    with pytest.raises(ValueError, match="Unterminated string"):
        parse_dru('(rules (rule "broken))')
    with pytest.raises(ValueError, match="Unbalanced parentheses"):
        parse_dru("(rules (rule broken)")


def test_dump_and_mutate_dru_rules_round_trip() -> None:
    root = parse_dru("(rules)")
    rule = [
        "rule",
        "Length Match",
        ["condition", "A.NetName == 'USB_D+'"],
        ["constraint", "length", ["min", "10mm"], ["max", "12mm"]],
        ["severity", "warning"],
    ]

    upsert_rule(root, rule)
    serialized = dump_dru(root)
    reparsed = parse_dru(serialized)
    reparsed_rule = find_rule(reparsed, "Length Match")

    assert reparsed_rule is not None
    assert rule_name(reparsed_rule) == "Length Match"
    assert len(iter_rule_nodes(reparsed)) == 1
    assert delete_rule(reparsed, "Length Match") is True
    assert delete_rule(reparsed, "Length Match") is False


def test_rule_name_requires_named_rule_node() -> None:
    with pytest.raises(ValueError, match="quoted name"):
        rule_name(["rule"])
