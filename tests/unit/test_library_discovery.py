"""KiCad library-table (sym-lib-table / fp-lib-table) discovery (issue #78)."""

from __future__ import annotations

from pathlib import Path

import pytest

from kicad_mcp.tools.library import _parse_lib_table, _resolve_kicad_env


def test_resolve_kicad_env_substitutes_kiprjmod_and_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_dir = tmp_path / "proj"
    assert _resolve_kicad_env("${KIPRJMOD}/libs/X.kicad_sym", project_dir) == (
        f"{project_dir}/libs/X.kicad_sym"
    )
    monkeypatch.setenv("MY_LIB_DIR", "/opt/libs")
    assert _resolve_kicad_env("${MY_LIB_DIR}/X.kicad_sym", None) == "/opt/libs/X.kicad_sym"
    # An unknown variable is left untouched rather than expanded to empty.
    assert _resolve_kicad_env("${UNKNOWN_VAR_XYZ}/x", None) == "${UNKNOWN_VAR_XYZ}/x"


def test_parse_lib_table_resolves_kiprjmod_and_skips_non_kicad(tmp_path: Path) -> None:
    lib_dir = tmp_path / "libs"
    lib_dir.mkdir()
    sym = lib_dir / "ProjLib.kicad_sym"
    sym.write_text('(kicad_symbol_lib (symbol "R"))', encoding="utf-8")

    table = tmp_path / "sym-lib-table"
    table.write_text(
        "(sym_lib_table\n"
        '  (lib (name "ProjLib")(type "KiCad")'
        '(uri "${KIPRJMOD}/libs/ProjLib.kicad_sym")(options "")(descr ""))\n'
        '  (lib (name "Legacy")(type "Legacy")'
        '(uri "${KIPRJMOD}/libs/old.lib")(options "")(descr ""))\n'
        '  (lib (name "Missing")(type "KiCad")'
        '(uri "${KIPRJMOD}/libs/nope.kicad_sym")(options "")(descr ""))\n'
        ")",
        encoding="utf-8",
    )

    libs = _parse_lib_table(table, tmp_path)
    # KIPRJMOD-resolved KiCad lib is found; the Legacy type and the missing file are skipped.
    assert libs == {"ProjLib": sym}


def test_parse_lib_table_handles_unreadable_table(tmp_path: Path) -> None:
    assert _parse_lib_table(tmp_path / "does-not-exist", tmp_path) == {}
