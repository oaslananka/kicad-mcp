"""Regression guard for issue #187 — TestClient setup must stay warning-free.

``starlette.testclient`` emits a ``StarletteDeprecationWarning`` at import time
("Using ``httpx`` with ``starlette.testclient`` is deprecated; install
``httpx2`` instead.") whenever ``httpx2`` is not importable. Because that warning
fires once at module import and is then cached, capturing it inside a single
test is unreliable — by the time this module runs, another test has already
imported the client and the warning has been consumed.

Instead this guard asserts the precondition that suppresses the warning: the
test environment must provide ``httpx2``. ``httpx2`` is declared both in the
``dev`` optional-dependency extra and in the default ``dependency-groups.dev``
group, so any ``uv run`` invocation — bare or ``--all-extras`` — installs it and
keeps the full unit run free of the Starlette/httpx deprecation. If a future
change drops ``httpx2`` from the default test path, this test fails fast.
"""

from __future__ import annotations

import importlib.util


def test_httpx2_available_so_testclient_does_not_warn() -> None:
    spec = importlib.util.find_spec("httpx2")
    assert spec is not None, (
        "httpx2 is not importable in the test environment, so "
        "starlette.testclient falls back to httpx and emits a deprecation "
        "warning. Keep httpx2 in the default dependency-groups.dev group."
    )
