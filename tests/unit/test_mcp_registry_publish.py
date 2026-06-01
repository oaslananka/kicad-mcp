from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load_publisher() -> object:
    validator_script = ROOT / "scripts" / "validate_mcp_manifest.py"
    validator_spec = importlib.util.spec_from_file_location(
        "validate_mcp_manifest", validator_script
    )
    assert validator_spec is not None
    assert validator_spec.loader is not None
    validator_module = importlib.util.module_from_spec(validator_spec)
    sys.modules["validate_mcp_manifest"] = validator_module
    validator_spec.loader.exec_module(validator_module)

    script = ROOT / "scripts" / "publish_mcp_registry.py"
    spec = importlib.util.spec_from_file_location("publish_mcp_registry", script)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_publish_adapter_defaults_to_official_server_manifest() -> None:
    module = _load_publisher()

    assert module.DEFAULT_MANIFEST == ROOT / "server.json"


def test_publish_adapter_dry_run_success(monkeypatch) -> None:
    module = _load_publisher()
    monkeypatch.setenv("MCP_REGISTRY_TARGET", "generic")
    monkeypatch.delenv("MCP_REGISTRY_URL", raising=False)
    monkeypatch.delenv("MCP_REGISTRY_TOKEN", raising=False)

    result = module.publish_manifest(ROOT / "mcp.json", dry_run=True)

    assert result["dry_run"] is True
    assert result["target"] == "generic"
    assert result["manifest"]["name"] == "io.github.oaslananka/kicad-mcp-pro"


def test_publish_adapter_fails_without_token_on_real_publish(monkeypatch) -> None:
    module = _load_publisher()
    monkeypatch.setenv("MCP_REGISTRY_TARGET", "generic")
    monkeypatch.setenv("MCP_REGISTRY_URL", "https://registry.example.test/publish")
    monkeypatch.delenv("MCP_REGISTRY_TOKEN", raising=False)

    try:
        module.publish_manifest(ROOT / "mcp.json", dry_run=False)
    except module.PublishError as exc:
        assert "MCP_REGISTRY_TOKEN is required" in str(exc)
    else:
        raise AssertionError("expected PublishError")


def test_publish_adapter_fails_without_url_for_generic_target(monkeypatch) -> None:
    module = _load_publisher()
    monkeypatch.setenv("MCP_REGISTRY_TARGET", "generic")
    monkeypatch.setenv("MCP_REGISTRY_TOKEN", "token")
    monkeypatch.delenv("MCP_REGISTRY_URL", raising=False)

    try:
        module.publish_manifest(ROOT / "mcp.json", dry_run=False)
    except module.PublishError as exc:
        assert str(exc) == module.NOT_CONFIGURED
    else:
        raise AssertionError("expected PublishError")


def test_publish_adapter_fails_for_invalid_manifest(tmp_path: Path, monkeypatch) -> None:
    module = _load_publisher()
    monkeypatch.setenv("MCP_REGISTRY_TARGET", "generic")
    path = tmp_path / "mcp.json"
    manifest = json.loads((ROOT / "mcp.json").read_text(encoding="utf-8"))
    manifest.pop("packages")
    path.write_text(json.dumps(manifest), encoding="utf-8")

    try:
        module.publish_manifest(path, dry_run=True)
    except module.ManifestValidationError as exc:
        assert "packages must be a non-empty list." in exc.errors
    else:
        raise AssertionError("expected ManifestValidationError")
