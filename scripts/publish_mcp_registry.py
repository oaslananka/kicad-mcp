#!/usr/bin/env python3
"""Publish or dry-run MCP registry metadata."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from validate_mcp_manifest import ManifestValidationError, validate_manifest_file

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "server.json"
SUPPORTED_TARGETS = frozenset({"official", "generic", "smithery", "glama", "pulsemcp"})
NOT_CONFIGURED = (
    "MCP registry publish API is not configured; set MCP_REGISTRY_URL or implement target adapter."
)


class PublishError(RuntimeError):
    """Raised when registry publishing cannot complete."""


def _env_bool(name: str, *, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().casefold() in {"1", "true", "yes", "on"}


def _target() -> str:
    target = os.environ.get("MCP_REGISTRY_TARGET", "official").strip().casefold()
    if target not in SUPPORTED_TARGETS:
        supported = ", ".join(sorted(SUPPORTED_TARGETS))
        raise PublishError(
            f"Unsupported MCP_REGISTRY_TARGET {target!r}; expected one of: {supported}."
        )
    return target


def _payload(target: str, manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "target": target,
        "manifest": manifest,
    }


def _publish_official() -> None:
    publisher = shutil.which("mcp-publisher")
    if publisher is None:
        raise PublishError(
            "mcp-publisher is required for official MCP registry publishing. "
            "Install the pinned release in CI or set MCP_REGISTRY_URL for a generic adapter."
        )
    if os.environ.get("GITHUB_ACTIONS") == "true":
        login = subprocess.run(
            [publisher, "login", "github-oidc"],
            cwd=ROOT,
            check=False,
        )
        if login.returncode != 0:
            raise PublishError("mcp-publisher login github-oidc failed.")
    publish = subprocess.run([publisher, "publish"], cwd=ROOT, check=False)
    if publish.returncode != 0:
        raise PublishError("mcp-publisher publish failed.")


def _post_json(url: str, token: str, payload: dict[str, Any]) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise PublishError("MCP_REGISTRY_URL must be an https URL.")
    data = json.dumps(payload).encode("utf-8")
    request = Request(  # noqa: S310 - scheme and host are validated above.
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=30) as response:  # noqa: S310 - request URL is validated.
            if response.status < 200 or response.status >= 300:
                raise PublishError(f"MCP registry publish failed with HTTP {response.status}.")
    except HTTPError as exc:
        raise PublishError(f"MCP registry publish failed with HTTP {exc.code}.") from exc
    except URLError as exc:
        raise PublishError(f"MCP registry publish failed: {exc.reason}") from exc


def publish_manifest(manifest_path: Path, *, dry_run: bool) -> dict[str, Any]:
    """Validate and publish the manifest, or return the dry-run payload."""
    manifest = validate_manifest_file(manifest_path)
    target = _target()
    payload = _payload(target, manifest)

    if dry_run:
        return {"dry_run": True, **payload}

    if target == "official" and not os.environ.get("MCP_REGISTRY_URL"):
        _publish_official()
        return {"dry_run": False, "target": target, "published": True}

    url = os.environ.get("MCP_REGISTRY_URL", "").strip()
    token = os.environ.get("MCP_REGISTRY_TOKEN", "").strip()
    if not url:
        raise PublishError(NOT_CONFIGURED)
    if not token:
        raise PublishError("MCP_REGISTRY_TOKEN is required for real MCP registry publishing.")
    _post_json(url, token, payload)
    return {"dry_run": False, "target": target, "published": True}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST), help="Manifest path.")
    parser.add_argument("--dry-run", action="store_true", help="Print payload without publishing.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    dry_run = args.dry_run or _env_bool("MCP_REGISTRY_DRY_RUN")
    try:
        result = publish_manifest(Path(args.manifest), dry_run=dry_run)
    except (OSError, json.JSONDecodeError, ManifestValidationError, PublishError) as exc:
        print(f"MCP registry publish failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
