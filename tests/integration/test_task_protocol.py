"""Integration tests for the MCP Tasks protocol via build_server()."""

from __future__ import annotations

import pytest
from mcp.types import (
    CancelTaskRequest,
    CancelTaskRequestParams,
    CancelTaskResult,
    GetTaskRequest,
    GetTaskRequestParams,
    GetTaskResult,
    ListTasksRequest,
    ListTasksResult,
    ServerResult,
)

from kicad_mcp.execution.tasks import TaskManager
from kicad_mcp.server import build_server


def _unwrap(result: ServerResult) -> object:
    """Unwrap a ServerResult to get the inner payload."""
    return result.root


@pytest.fixture
def task_server(monkeypatch: pytest.MonkeyPatch) -> object:
    """Build a server with the experimental Tasks extension enabled."""
    monkeypatch.setenv("KICAD_MCP_ENABLE_TASKS", "1")
    monkeypatch.setenv("KICAD_MCP_PROFILE", "pcb")
    return build_server()


# =========================================================================
# Server wiring verification
# =========================================================================


def test_server_has_task_manager_when_enabled(task_server: object) -> None:
    assert hasattr(task_server, "_task_manager")
    assert isinstance(task_server._task_manager, TaskManager)


def test_server_has_task_support(task_server: object) -> None:
    lowlevel = task_server._mcp_server
    assert lowlevel.experimental.task_support is not None


def test_task_manager_is_live_instance(task_server: object) -> None:
    tm = task_server._task_manager
    assert hasattr(tm, "start")
    assert hasattr(tm, "cancel")
    assert hasattr(tm, "list_tasks")
    assert hasattr(tm, "get")


# =========================================================================
# Protocol handler integration
# =========================================================================


@pytest.mark.anyio
async def test_list_tasks_handler_returns_empty_initially(task_server: object) -> None:
    handler = task_server._mcp_server.request_handlers.get(ListTasksRequest)
    assert handler is not None

    result = await handler(ListTasksRequest(method="tasks/list", params={}))
    payload = _unwrap(result)

    assert isinstance(payload, ListTasksResult)
    assert payload.tasks == []


@pytest.mark.anyio
async def test_get_task_handler_for_unknown_task(task_server: object) -> None:
    handler = task_server._mcp_server.request_handlers.get(GetTaskRequest)
    assert handler is not None

    result = await handler(
        GetTaskRequest(
            method="tasks/get",
            params=GetTaskRequestParams(taskId="nonexistent-id"),
        )
    )
    payload = _unwrap(result)

    assert isinstance(payload, GetTaskResult)
    assert payload.taskId == "nonexistent-id"
    assert payload.status == "working"
    assert "not found" in (payload.statusMessage or "").lower()


@pytest.mark.anyio
async def test_cancel_task_handler_for_unknown_task(task_server: object) -> None:
    handler = task_server._mcp_server.request_handlers.get(CancelTaskRequest)
    assert handler is not None

    result = await handler(
        CancelTaskRequest(
            method="tasks/cancel",
            params=CancelTaskRequestParams(taskId="nonexistent-id"),
        )
    )
    payload = _unwrap(result)

    assert isinstance(payload, CancelTaskResult)
    assert payload.taskId == "nonexistent-id"
    assert payload.status == "working"
    assert "not found" in (payload.statusMessage or "").lower()


# =========================================================================
# End-to-end task lifecycle via protocol handlers
# =========================================================================


@pytest.mark.anyio
async def test_full_task_lifecycle_via_handlers(task_server: object) -> None:
    tm = task_server._task_manager

    # Arrange: create a task via the underlying manager
    task = await tm.start("integration-test", ttl_s=30)
    assert task.status == "working"

    list_handler = task_server._mcp_server.request_handlers.get(ListTasksRequest)
    get_handler = task_server._mcp_server.request_handlers.get(GetTaskRequest)
    cancel_handler = task_server._mcp_server.request_handlers.get(CancelTaskRequest)

    # Act: list tasks — should include our task
    sr = await list_handler(ListTasksRequest(method="tasks/list", params={}))
    list_result: ListTasksResult = _unwrap(sr)  # type: ignore[assignment]
    assert len(list_result.tasks) >= 1
    assert task.taskId in {t.taskId for t in list_result.tasks}

    # Act: get the task — should be "working"
    sr = await get_handler(
        GetTaskRequest(
            method="tasks/get",
            params=GetTaskRequestParams(taskId=task.taskId),
        )
    )
    get_result: GetTaskResult = _unwrap(sr)  # type: ignore[assignment]
    assert get_result.taskId == task.taskId
    assert get_result.status == "working"

    # Act: cancel the task
    sr = await cancel_handler(
        CancelTaskRequest(
            method="tasks/cancel",
            params=CancelTaskRequestParams(taskId=task.taskId),
        )
    )
    cancel_result: CancelTaskResult = _unwrap(sr)  # type: ignore[assignment]
    assert cancel_result.taskId == task.taskId
    assert cancel_result.status == "cancelled"

    # Verify: get after cancel shows cancelled
    sr = await get_handler(
        GetTaskRequest(
            method="tasks/get",
            params=GetTaskRequestParams(taskId=task.taskId),
        )
    )
    get_after: GetTaskResult = _unwrap(sr)  # type: ignore[assignment]
    assert get_after.status == "cancelled"
