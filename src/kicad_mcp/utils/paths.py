"""Compatibility wrapper for workspace-safe path helpers."""

from __future__ import annotations

from ..path_safety import assert_within, normalize_workspace_root, relative_subpath, resolve_under

__all__ = ["assert_within", "normalize_workspace_root", "relative_subpath", "resolve_under"]
