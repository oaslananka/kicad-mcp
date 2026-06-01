from __future__ import annotations

import sqlite3
from pathlib import Path

from kicad_mcp.resources.gate_history import GateHistory
from kicad_mcp.tools.validation import GateOutcome


def test_gate_history_records_trends_and_regressions(tmp_path: Path) -> None:
    history = GateHistory(tmp_path / "gate_history.db")
    history._init()

    history.record(GateOutcome("Schematic", "PASS", "ok"))
    history.record(GateOutcome("Schematic", "FAIL", "bad", ["wire missing"]))

    trend = history.trend("Schematic")

    assert trend[0]["status"] == "FAIL"
    assert trend[0]["issue_count"] == 1
    assert history.regression_check() == ["Schematic regressed from PASS to FAIL."]


def test_gate_history_schema_migration_sets_user_version(tmp_path: Path) -> None:
    db_path = tmp_path / "gate_history.db"
    with sqlite3.connect(db_path) as db:
        db.execute(
            """
            CREATE TABLE gate_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                gate_name TEXT NOT NULL,
                status TEXT NOT NULL,
                issue_count INTEGER NOT NULL,
                auto_fixed INTEGER NOT NULL,
                payload TEXT NOT NULL
            )
            """
        )
        db.execute("PRAGMA user_version = 0")

    history = GateHistory(db_path)
    history._init()

    with sqlite3.connect(db_path) as db:
        user_version = db.execute("PRAGMA user_version").fetchone()[0]

    assert user_version == 1
