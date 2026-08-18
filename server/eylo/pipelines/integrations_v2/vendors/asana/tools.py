"""Curated Asana tool implementations for the `integrations_v2` pipeline."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from eylo.modules.integrations_v2.domain.enums import ToolEffect

from ...contracts import VendorToolContext, VendorToolError
from ...registry import curated_tool
from .definition import vendor

MAX_BODY_CHARS = 6_000
_TASK_FIELDS = (
    "name,notes,completed,completed_at,due_on,created_at,modified_at,"
    "assignee.name,assignee.email,projects.name,tags.name,permalink_url"
)


class ListProjectsInput(BaseModel):
    workspace: str = Field(
        default="", description="Workspace name or gid. Defaults to the first one."
    )
    limit: int = Field(default=50, ge=1, le=100)


class SearchTasksInput(BaseModel):
    project: str = Field(
        default="", description="Project name or gid. Omit to search assigned work."
    )
    assignee_email: str | None = Field(
        default=None, description="Only tasks assigned to this person."
    )
    include_completed: bool = Field(default=False)
    limit: int = Field(default=25, ge=1, le=100)


class GetTaskInput(BaseModel):
    task_id: str = Field(min_length=1, description="Task gid, or its permalink URL.")
    include_comments: bool = Field(default=True)


class CreateTaskInput(BaseModel):
    name: str = Field(min_length=1, description="What the task is.")
    project: str = Field(default="", description="Project name or gid.")
    notes: str | None = Field(default=None, description="Longer description.")
    assignee_email: str | None = Field(default=None)
    due_on: str | None = Field(default=None, description="Due date as YYYY-MM-DD.")


class CompleteTaskInput(BaseModel):
    task_id: str = Field(min_length=1)


class AddCommentInput(BaseModel):
    task_id: str = Field(min_length=1)
    body: str = Field(min_length=1, description="Comment text.")


@curated_tool(
    vendor=vendor.vendor,
    name="list_projects",
    display_name="List Asana Projects",
    description=(
        "List the projects in a workspace, with their names and gids. Other "
        "tools accept a project name directly, so this is mainly for "
        "discovering what exists. Defaults to the first workspace the token "
        "can see."
    ),
    input_model=ListProjectsInput,
    effect=ToolEffect.READ,
)
async def list_projects(
    payload: ListProjectsInput, ctx: VendorToolContext
) -> dict[str, Any]:
    workspace_gid, workspace_name = await _resolve_workspace(ctx, payload.workspace)
    response = await ctx.read(
        "/projects",
        query={
            "workspace": workspace_gid,
            "limit": payload.limit,
            "archived": False,
            "opt_fields": "name,archived,color,notes",
        },
    )
    projects = _data(response.data)
    return {
        "workspace": workspace_name,
        "projects": [
            {"gid": p.get("gid"), "name": p.get("name"), "notes": _clip(p.get("notes"))}
            for p in projects
        ],
        "count": len(projects),
    }


@curated_tool(
    vendor=vendor.vendor,
    name="search_tasks",
    display_name="Search Asana Tasks",
    description=(
        "List tasks in a project named rather than identified, or the tasks "
        "assigned to someone given by email. Completed work is hidden unless "
        "asked for. Each task reports its assignee, due date, and permalink."
    ),
    input_model=SearchTasksInput,
    effect=ToolEffect.READ,
)
async def search_tasks(
    payload: SearchTasksInput, ctx: VendorToolContext
) -> dict[str, Any]:
    query: dict[str, Any] = {"limit": payload.limit, "opt_fields": _TASK_FIELDS}
    if not payload.include_completed:
        # Asana wants a timestamp here; "now" means "nothing completed yet".
        query["completed_since"] = "now"

    project_name = None
    if payload.project:
        project_gid, project_name = await _resolve_project(ctx, payload.project)
        query["project"] = project_gid
    elif payload.assignee_email:
        workspace_gid, _ = await _resolve_workspace(ctx, "")
        query["assignee"] = payload.assignee_email
        query["workspace"] = workspace_gid
    else:
        raise VendorToolError(
            "search_unbounded",
            "Give a project, or an assignee's email, to search within.",
        )

    response = await ctx.read("/tasks", query=query)
    tasks = _data(response.data)
    return {
        "project": project_name,
        "tasks": [_task_view(task) for task in tasks],
        "count": len(tasks),
    }


@curated_tool(
    vendor=vendor.vendor,
    name="get_task",
    display_name="Get Asana Task",
    description=(
        "Read one task in full together with its comment history. Asana keeps "
        "comments at a separate endpoint and mixes them with automated "
        "activity records; only what people actually wrote is returned."
    ),
    input_model=GetTaskInput,
    effect=ToolEffect.READ,
)
async def get_task(payload: GetTaskInput, ctx: VendorToolContext) -> dict[str, Any]:
    task_gid = _task_gid(payload.task_id)
    response = await ctx.read(f"/tasks/{task_gid}", query={"opt_fields": _TASK_FIELDS})
    view = _task_view(_object(_envelope(response.data)))

    if payload.include_comments:
        stories = await ctx.read(
            f"/tasks/{task_gid}/stories",
            query={"opt_fields": "text,created_at,created_by.name,type"},
        )
        view["comments"] = [
            {
                "author": (story.get("created_by") or {}).get("name"),
                "body": _clip(story.get("text")),
                "created_at": story.get("created_at"),
            }
            for story in _data(stories.data)
            # Asana records assignments and status changes as stories too.
            if story.get("type") == "comment"
        ]
    return view


@curated_tool(
    vendor=vendor.vendor,
    name="create_task",
    display_name="Create Asana Task",
    description=(
        "Create a task in a project named rather than identified, optionally "
        "assigned to someone by email and due on a plain date. Asana requires "
        "a workspace when no project is given; the first available one is used."
    ),
    input_model=CreateTaskInput,
    effect=ToolEffect.MUTATION,
)
async def create_task(
    payload: CreateTaskInput, ctx: VendorToolContext
) -> dict[str, Any]:
    body: dict[str, Any] = {"name": payload.name}
    if payload.notes:
        body["notes"] = payload.notes
    if payload.assignee_email:
        body["assignee"] = payload.assignee_email
    if payload.due_on:
        body["due_on"] = payload.due_on

    if payload.project:
        project_gid, _ = await _resolve_project(ctx, payload.project)
        body["projects"] = [project_gid]
    else:
        workspace_gid, _ = await _resolve_workspace(ctx, "")
        body["workspace"] = workspace_gid

    response = await ctx.mutate(
        "/tasks", json={"data": body}, query={"opt_fields": _TASK_FIELDS}
    )
    return _task_view(_object(_envelope(response.data)))


@curated_tool(
    vendor=vendor.vendor,
    name="complete_task",
    display_name="Complete Asana Task",
    description=(
        "Mark a task as done. Reversible in Asana's own interface, and the "
        "task keeps its history."
    ),
    input_model=CompleteTaskInput,
    effect=ToolEffect.MUTATION,
)
async def complete_task(
    payload: CompleteTaskInput, ctx: VendorToolContext
) -> dict[str, Any]:
    task_gid = _task_gid(payload.task_id)
    response = await ctx.mutate(
        f"/tasks/{task_gid}",
        method="PUT",
        json={"data": {"completed": True}},
        query={"opt_fields": _TASK_FIELDS},
    )
    return _task_view(_object(_envelope(response.data)))


@curated_tool(
    vendor=vendor.vendor,
    name="add_comment",
    display_name="Comment on Asana Task",
    description="Add a comment to a task. Everyone following the task is notified.",
    input_model=AddCommentInput,
    effect=ToolEffect.MUTATION,
)
async def add_comment(
    payload: AddCommentInput, ctx: VendorToolContext
) -> dict[str, Any]:
    task_gid = _task_gid(payload.task_id)
    response = await ctx.mutate(
        f"/tasks/{task_gid}/stories", json={"data": {"text": payload.body}}
    )
    story = _object(_envelope(response.data))
    return {
        "task_id": task_gid,
        "comment_id": story.get("gid"),
        "created_at": story.get("created_at"),
    }


async def _resolve_workspace(ctx: VendorToolContext, workspace: str) -> tuple[str, str]:
    response = await ctx.read("/workspaces", query={"opt_fields": "name"})
    workspaces = _data(response.data)
    if not workspaces:
        raise VendorToolError(
            "workspace_missing", "This token can see no Asana workspaces."
        )
    candidate = workspace.strip()
    if not candidate:
        first = workspaces[0]
        return str(first.get("gid")), str(first.get("name"))
    wanted = candidate.casefold()
    for item in workspaces:
        if (
            str(item.get("gid")) == candidate
            or str(item.get("name", "")).casefold() == wanted
        ):
            return str(item.get("gid")), str(item.get("name"))
    available = ", ".join(str(item.get("name")) for item in workspaces)
    raise VendorToolError(
        "workspace_not_found",
        f"No workspace named '{workspace}'. Available: {available}.",
    )


async def _resolve_project(ctx: VendorToolContext, project: str) -> tuple[str, str]:
    """Accept a project name or gid, so a numeric id never has to be known."""
    candidate = project.strip()
    if candidate.isdigit():
        return candidate, candidate
    workspace_gid, _ = await _resolve_workspace(ctx, "")
    response = await ctx.read(
        "/projects",
        query={"workspace": workspace_gid, "limit": 100, "opt_fields": "name"},
    )
    projects = _data(response.data)
    wanted = candidate.casefold()
    matches = [p for p in projects if str(p.get("name", "")).casefold() == wanted]
    if len(matches) == 1:
        return str(matches[0].get("gid")), str(matches[0].get("name"))
    if len(matches) > 1:
        raise VendorToolError(
            "project_ambiguous",
            f"More than one project is named '{project}'. Give its gid instead.",
        )
    available = ", ".join(str(p.get("name")) for p in projects[:20])
    raise VendorToolError(
        "project_not_found", f"No project named '{project}'. Available: {available}."
    )


def _task_gid(value: str) -> str:
    """Accept a gid or a pasted permalink, which ends in the gid."""
    candidate = value.strip().rstrip("/")
    if candidate.startswith("https://"):
        candidate = candidate.rsplit("/", 1)[-1]
    if not candidate:
        raise VendorToolError("task_invalid", f"'{value}' is not an Asana task.")
    return candidate


def _task_view(task: dict[str, Any]) -> dict[str, Any]:
    assignee = task.get("assignee") or {}
    projects = [p for p in task.get("projects") or [] if isinstance(p, dict)]
    tags = [t for t in task.get("tags") or [] if isinstance(t, dict)]
    return {
        "gid": task.get("gid"),
        "name": task.get("name"),
        "notes": _clip(task.get("notes")),
        "completed": task.get("completed"),
        "completed_at": task.get("completed_at"),
        "due_on": task.get("due_on"),
        "assignee": assignee.get("name"),
        "assignee_email": assignee.get("email"),
        "projects": [p.get("name") for p in projects],
        "tags": [t.get("name") for t in tags],
        "created_at": task.get("created_at"),
        "modified_at": task.get("modified_at"),
        "web_link": task.get("permalink_url"),
    }


def _clip(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    return value[:MAX_BODY_CHARS]


def _envelope(payload: Any) -> Any:
    """Every Asana response nests its content under `data`."""
    if isinstance(payload, dict) and "data" in payload:
        return payload["data"]
    return payload


def _data(payload: Any) -> list[dict[str, Any]]:
    _object(payload)
    inner = _envelope(payload)
    if not isinstance(inner, list):
        return []
    return [item for item in inner if isinstance(item, dict)]


def _object(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise VendorToolError(
            "vendor_response_invalid", "Asana returned a non-object response."
        )
    errors = payload.get("errors")
    if isinstance(errors, list) and errors:
        first = errors[0] if isinstance(errors[0], dict) else {}
        raise VendorToolError(
            "vendor_rejected",
            str(first.get("message", "Asana rejected the request."))[:500],
        )
    return payload


__all__ = [
    "add_comment",
    "complete_task",
    "create_task",
    "get_task",
    "list_projects",
    "search_tasks",
]
