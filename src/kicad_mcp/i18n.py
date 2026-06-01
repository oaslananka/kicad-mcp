"""Small localization helpers for user-facing MCP server strings."""

from __future__ import annotations

import os
from collections.abc import Mapping

DEFAULT_LOCALE = "en"
SUPPORTED_LOCALES = frozenset({"en", "tr"})

SERVER_DESCRIPTION = "KiCad MCP Pro server for PCB and schematic workflows."

_TRANSLATIONS: dict[str, dict[str, str]] = {
    "tr": {
        SERVER_DESCRIPTION: "PCB ve şematik iş akışları için KiCad MCP Pro sunucusu.",
        "Inspect registered MCP tools.": "Kayıtlı MCP araçlarını inceleyin.",
        "Generate MCP client configuration snippets.": "MCP istemci yapılandırma parçaları üretin.",
        "Transport: stdio, http, sse, streamable-http": (
            "Taşıma: stdio, http, sse, streamable-http"
        ),
        "HTTP bind host": "HTTP bağlama sunucusu.",
        "HTTP bind port": "HTTP bağlama portu.",
        "Active KiCad project directory": "Etkin KiCad proje dizini.",
        "Log level": "Günlük seviyesi.",
        "Log format: text or json": "Günlük biçimi: text veya json.",
        "Rotating log file path": "Dönen günlük dosyası yolu.",
        "Enable experimental tools": "Deneysel araçları etkinleştir.",
        "Enable OpenTelemetry export": "OpenTelemetry dışa aktarımını etkinleştir.",
        "Emit machine-readable JSON.": "Makine tarafından okunabilir JSON üret.",
        "Use stable non-zero exit codes for degraded runtime states.": (
            "Bozulmuş çalışma zamanı durumları için kararlı sıfır dışı çıkış kodları kullan."
        ),
        "Report fast package and configuration health without requiring KiCad IPC.": (
            "KiCad IPC gerektirmeden paket ve yapılandırma sağlığını hızlıca raporla."
        ),
        "Run deeper diagnostics without treating unavailable KiCad as fatal.": (
            "Kullanılamayan KiCad'i ölümcül saymadan daha derin tanılama çalıştır."
        ),
    }
}


def resolve_locale(locale: str | None = None) -> str:
    """Return the supported locale code selected by argument or environment."""
    raw_locale = (locale or os.environ.get("KICAD_MCP_LOCALE") or DEFAULT_LOCALE).strip()
    normalized = raw_locale.replace("_", "-").casefold()
    primary = normalized.split("-", 1)[0]
    if primary in SUPPORTED_LOCALES:
        return primary
    return DEFAULT_LOCALE


def localize(message: str, *, locale: str | None = None) -> str:
    """Translate a message when a supported catalog contains it."""
    selected = resolve_locale(locale)
    if selected == DEFAULT_LOCALE:
        return message
    return _TRANSLATIONS.get(selected, {}).get(message, message)


def localized_message_variants(
    message: str,
    *,
    translations: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Return all currently shipped locale variants for a source message."""
    variants = {DEFAULT_LOCALE: message}
    for locale in sorted(SUPPORTED_LOCALES - {DEFAULT_LOCALE}):
        variants[locale] = (
            translations[locale]
            if translations is not None and locale in translations
            else localize(message, locale=locale)
        )
    return variants


def option_help(message: str) -> str:
    """Translate a Typer option help string using the current process locale."""
    return localize(message)
