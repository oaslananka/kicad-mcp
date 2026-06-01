from __future__ import annotations

from kicad_mcp.i18n import (
    DEFAULT_LOCALE,
    SUPPORTED_LOCALES,
    localize,
    localized_message_variants,
    resolve_locale,
)
from kicad_mcp.server_info import get_server_info_contract


def test_i18n_resolves_supported_and_fallback_locales(monkeypatch) -> None:
    monkeypatch.setenv("KICAD_MCP_LOCALE", "tr-TR")
    assert resolve_locale() == "tr"

    monkeypatch.setenv("KICAD_MCP_LOCALE", "de-DE")
    assert resolve_locale() == DEFAULT_LOCALE
    assert SUPPORTED_LOCALES == frozenset({"en", "tr"})


def test_i18n_localizes_known_messages_and_preserves_unknown_messages() -> None:
    assert localize(
        "KiCad MCP Pro server for PCB and schematic workflows.", locale="tr"
    ).startswith("PCB ve şematik")
    assert localize("Unregistered message", locale="tr") == "Unregistered message"


def test_i18n_exposes_localized_message_variants() -> None:
    variants = localized_message_variants("KiCad MCP Pro server for PCB and schematic workflows.")

    assert variants["en"] == "KiCad MCP Pro server for PCB and schematic workflows."
    assert variants["tr"].startswith("PCB ve şematik")


def test_server_info_contract_exposes_localized_description(monkeypatch, sample_project) -> None:
    _ = sample_project
    monkeypatch.setenv("KICAD_MCP_LOCALE", "tr-TR")
    monkeypatch.setattr("kicad_mcp.server_info.get_kicad", lambda: object())
    monkeypatch.setattr("kicad_mcp.server_info.get_board", lambda: object())

    payload = get_server_info_contract(probe_live_context=False)

    assert (
        payload["description"]
        == localized_message_variants("KiCad MCP Pro server for PCB and schematic workflows.")["tr"]
    )
    assert payload["localizedDescriptions"] == localized_message_variants(
        "KiCad MCP Pro server for PCB and schematic workflows."
    )
