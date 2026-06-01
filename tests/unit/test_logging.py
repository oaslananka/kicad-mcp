from __future__ import annotations

import json
import logging
from pathlib import Path

import structlog

from kicad_mcp.utils.logging import redact_sensitive_keys, setup_logging


def test_redact_sensitive_keys_masks_secret_like_fields() -> None:
    payload = redact_sensitive_keys(
        None,  # type: ignore[arg-type]
        "info",
        {
            "event": "startup",
            "auth_token": "abc",
            "apiKey": "xyz",
            "password_hint": "nope",
            "safe": "ok",
        },
    )

    assert payload["event"] == "startup"
    assert payload["safe"] == "ok"
    assert payload["auth_token"] == "***REDACTED***"  # noqa: S105 - redaction sentinel
    assert payload["apiKey"] == "***REDACTED***"  # noqa: S105 - redaction sentinel
    assert payload["password_hint"] == "***REDACTED***"  # noqa: S105 - redaction sentinel


def test_json_logging_uses_schema_and_redacts_paths_payloads(capsys, tmp_path: Path) -> None:
    setup_logging("INFO", "json")

    structlog.get_logger("logging-schema-test").error(
        "tool_call_failed",
        project_dir=str(tmp_path / "private-project"),
        auth_token="synthetic-token",  # noqa: S106 - redaction fixture
        payload="x" * 4096,
        tool="run_drc",
        error=RuntimeError("missing project"),
    )

    rendered = json.loads(capsys.readouterr().err.strip().splitlines()[-1])
    assert rendered["event"] == "tool_call_failed"
    assert rendered["level"] == "error"
    assert rendered["logger"] == "logging-schema-test"
    assert rendered["tool"] == "run_drc"
    assert rendered["ts"]
    assert rendered["request_id"] is None
    assert rendered["mcp_session_id"] is None
    assert rendered["latency_ms"] is None
    assert rendered["project_dir"] == "***REDACTED_PATH***"
    assert rendered["auth_token"] == "***REDACTED***"  # noqa: S105 - redaction sentinel
    assert rendered["payload"].startswith("***TRUNCATED***")
    assert rendered["error"] == {"type": "RuntimeError", "message": "missing project"}


def test_setup_logging_rotates_bounded_json_log_file(tmp_path: Path) -> None:
    log_file = tmp_path / "server.log"
    setup_logging(
        "INFO",
        "json",
        log_file=log_file,
        log_max_bytes=256,
        log_backup_count=2,
    )
    event_logger = structlog.get_logger("rotation-test")

    for index in range(24):
        event_logger.info("rotation_probe", index=index, payload="x" * 192)

    for handler in logging.getLogger().handlers:
        handler.flush()

    assert log_file.exists()
    assert Path(f"{log_file}.1").exists()
    assert Path(f"{log_file}.2").exists()
    assert not Path(f"{log_file}.3").exists()
