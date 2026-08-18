"""Curated Google Tasks tools.

Every Tasks endpoint is addressed by a task-list id that nobody knows offhand,
so a raw flow is always two calls: list the lists, find the one called "Work",
then act. These tools accept the list *name* and resolve it, and default to the
account's first list when none is named.

Google also stores due dates as RFC 3339 timestamps while only honouring the
date part. `create_task` accepts a plain date and does that conversion, rather
than leaving a caller to discover that a time was silently discarded.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from eylo.modules.integrations_v2.domain.enums import ToolEffect

from ...contracts import VendorToolContext, VendorToolError
from ...registry import curated_tool
from .definition import TASKS, vendor

COMPLETED = "completed"
NEEDS_ACTION = "needsAction"


class ListTaskListsInput(BaseModel):
    pass


class ListTasksInput(BaseModel):
    task_list: str = Field(
        default="", description="Task list name or id. Defaults to the first list."
    )
    include_completed: bool = Field(default=False)
    due_before: str | None = Field(
        default=None, description="Only tasks due before this date (YYYY-MM-DD)."
    )
    limit: int = Field(default=50, ge=1, le=100)


class CreateTaskInput(BaseModel):
    title: str = Field(min_length=1)
    task_list: str = Field(default="", description="Task list name or id.")
    notes: str | None = Field(default=None, description="Longer detail on the task.")
    due: str | None = Field(
        default=None,
        description="Due date as YYYY-MM-DD. Google records the date only.",
    )
    parent_task_id: str | None = Field(
        default=None, description="Make this a subtask of an existing task."
    )


class CompleteTaskInput(BaseModel):
    task_id: str = Field(min_length=1)
    task_list: str = Field(default="", description="Task list name or id.")


class DeleteTaskInput(BaseModel):
    task_id: str = Field(min_length=1)
    task_list: str = Field(default="", description="Task list name or id.")


@curated_tool(
    vendor=vendor.vendor,
    name="list_task_lists",
    display_name="List Google Task Lists",
    description=(
        "List the account's task lists with their names and ids. Other tools "
        "accept a list name directly, so this is only needed to discover what "
        "exists."
    ),
    input_model=ListTaskListsInput,
    effect=ToolEffect.READ,
    scopes=(TASKS,),
)
async def list_task_lists(
    payload: ListTaskListsInput, ctx: VendorToolContext
) -> dict[str, Any]:
    lists = await _task_lists(ctx)
    return {
        "task_lists": [
            {"id": item.get("id"), "name": item.get("title")} for item in lists
        ],
        "count": len(lists),
    }


@curated_tool(
    vendor=vendor.vendor,
    name="list_tasks",
    display_name="List Google Tasks",
    description=(
        "List tasks in a list, addressed by name. Completed tasks are hidden "
        "unless asked for, and a due_before date narrows the result to what is "
        "coming up. Subtasks report the task they belong to."
    ),
    input_model=ListTasksInput,
    effect=ToolEffect.READ,
    scopes=(TASKS,),
)
async def list_tasks(payload: ListTasksInput, ctx: VendorToolContext) -> dict[str, Any]:
    list_id, list_name = await _resolve_list(ctx, payload.task_list)
    query: dict[str, Any] = {
        "maxResults": payload.limit,
        "showCompleted": payload.include_completed,
        "showHidden": payload.include_completed,
    }
    if payload.due_before:
        query["dueMax"] = _rfc3339(payload.due_before)
    response = await ctx.read(f"/lists/{list_id}/tasks", query=query)
    items = _items(response.data)
    return {
        "task_list": list_name,
        "task_list_id": list_id,
        "tasks": [_task_view(item) for item in items],
        "count": len(items),
    }


@curated_tool(
    vendor=vendor.vendor,
    name="create_task",
    display_name="Create Google Task",
    description=(
        "Add a task to a list named rather than identified. The due date is "
        "given as a plain YYYY-MM-DD date; Google stores dates only and "
        "ignores any time of day. Give parent_task_id to create a subtask."
    ),
    input_model=CreateTaskInput,
    effect=ToolEffect.MUTATION,
    scopes=(TASKS,),
)
async def create_task(
    payload: CreateTaskInput, ctx: VendorToolContext
) -> dict[str, Any]:
    list_id, list_name = await _resolve_list(ctx, payload.task_list)
    body: dict[str, Any] = {"title": payload.title, "status": NEEDS_ACTION}
    if payload.notes:
        body["notes"] = payload.notes
    if payload.due:
        body["due"] = _rfc3339(payload.due)
    query = {"parent": payload.parent_task_id} if payload.parent_task_id else None
    response = await ctx.mutate(f"/lists/{list_id}/tasks", json=body, query=query)
    view = _task_view(_object(response.data))
    view["task_list"] = list_name
    return view


@curated_tool(
    vendor=vendor.vendor,
    name="complete_task",
    display_name="Complete Google Task",
    description=(
        "Mark a task as done. The list may be named rather than identified. "
        "Completing a task is reversible in the Google Tasks interface."
    ),
    input_model=CompleteTaskInput,
    effect=ToolEffect.MUTATION,
    scopes=(TASKS,),
)
async def complete_task(
    payload: CompleteTaskInput, ctx: VendorToolContext
) -> dict[str, Any]:
    list_id, list_name = await _resolve_list(ctx, payload.task_list)
    response = await ctx.mutate(
        f"/lists/{list_id}/tasks/{payload.task_id}",
        method="PATCH",
        json={"status": COMPLETED},
    )
    view = _task_view(_object(response.data))
    view["task_list"] = list_name
    return view


@curated_tool(
    vendor=vendor.vendor,
    name="delete_task",
    display_name="Delete Google Task",
    description=(
        "Remove a task from its list. Prefer complete_task when the work was "
        "actually done, so the record of it survives."
    ),
    input_model=DeleteTaskInput,
    effect=ToolEffect.MUTATION,
    scopes=(TASKS,),
)
async def delete_task(
    payload: DeleteTaskInput, ctx: VendorToolContext
) -> dict[str, Any]:
    list_id, list_name = await _resolve_list(ctx, payload.task_list)
    await ctx.mutate(f"/lists/{list_id}/tasks/{payload.task_id}", method="DELETE")
    return {
        "task_id": payload.task_id,
        "task_list": list_name,
        "task_list_id": list_id,
        "deleted": True,
    }


async def _task_lists(ctx: VendorToolContext) -> list[dict[str, Any]]:
    response = await ctx.read("/users/@me/lists", query={"maxResults": 100})
    return _items(response.data)


async def _resolve_list(ctx: VendorToolContext, task_list: str) -> tuple[str, str]:
    """Accept a list name or id; fall back to the account's first list."""
    lists = await _task_lists(ctx)
    if not lists:
        raise VendorToolError(
            "task_list_missing", "This account has no task lists to work with."
        )
    candidate = task_list.strip()
    if not candidate:
        first = lists[0]
        return str(first.get("id")), str(first.get("title"))

    wanted = candidate.casefold()
    for item in lists:
        if str(item.get("id")) == candidate:
            return candidate, str(item.get("title"))
        if str(item.get("title", "")).casefold() == wanted:
            return str(item.get("id")), str(item.get("title"))
    available = ", ".join(str(item.get("title")) for item in lists)
    raise VendorToolError(
        "task_list_not_found",
        f"No task list named '{task_list}'. Available: {available}.",
    )


def _task_view(task: dict[str, Any]) -> dict[str, Any]:
    due = task.get("due")
    return {
        "id": task.get("id"),
        "title": task.get("title"),
        "notes": task.get("notes"),
        # Google returns a full timestamp but only the date is meaningful.
        "due": str(due)[:10] if isinstance(due, str) else None,
        "completed": task.get("status") == COMPLETED,
        "completed_at": task.get("completed"),
        "parent_task_id": task.get("parent"),
        "updated_at": task.get("updated"),
    }


def _rfc3339(value: str) -> str:
    """Google wants a full timestamp even though it honours only the date."""
    text = value.strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as error:
        raise VendorToolError(
            "date_invalid", f"'{value}' is not a valid date. Use YYYY-MM-DD."
        ) from error
    return f"{parsed.date().isoformat()}T00:00:00.000Z"


def _items(payload: Any) -> list[dict[str, Any]]:
    body = _object(payload)
    return [item for item in body.get("items", []) or [] if isinstance(item, dict)]


def _object(payload: Any) -> dict[str, Any]:
    if payload is None:
        # A successful DELETE returns no body.
        return {}
    if not isinstance(payload, dict):
        raise VendorToolError(
            "vendor_response_invalid", "Google Tasks returned a non-object response."
        )
    error = payload.get("error")
    if isinstance(error, dict):
        raise VendorToolError(
            "vendor_rejected",
            str(error.get("message", "Google rejected the request."))[:500],
        )
    return payload


__all__ = [
    "complete_task",
    "create_task",
    "delete_task",
    "list_task_lists",
    "list_tasks",
]
