"""Curated GitLab tools.

GitLab identifies a project either by a numeric id nobody knows, or by its
`group/subgroup/name` path — which must be **URL-encoded**, slashes and all, to
survive being placed in the path segment. `/projects/acme/api/issues` is a
404 that reads like a permissions problem; `/projects/acme%2Fapi/issues` works.
That single encoding step is the most common way to fail at this API, and
`_project` does it here.

The rest is assembly. GitLab keeps an issue's discussion at a separate
endpoint, and merge request approvals at a third, so `get_issue` and
`get_merge_request` fetch and merge them.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from pydantic import BaseModel, Field

from eylo.modules.integrations_v2.domain.enums import ToolEffect

from ...contracts import VendorToolContext, VendorToolError
from ...registry import curated_tool
from .definition import vendor

MAX_BODY_CHARS = 6_000
MAX_NOTES = 20
_STATES = ("opened", "closed", "all")
_MR_STATES = ("opened", "closed", "merged", "all")


class SearchIssuesInput(BaseModel):
    project: str = Field(
        min_length=1, description="Project path such as acme/api, or its numeric id."
    )
    text: str | None = Field(default=None, description="Free text to match.")
    state: str = Field(default="opened", description="opened, closed, or all.")
    labels: list[str] | None = None
    assignee_username: str | None = None
    limit: int = Field(default=20, ge=1, le=100)


class GetIssueInput(BaseModel):
    project: str = Field(min_length=1)
    issue_iid: int = Field(ge=1, description="Issue number as shown in the project.")
    include_comments: bool = Field(default=True)


class CreateIssueInput(BaseModel):
    project: str = Field(min_length=1)
    title: str = Field(min_length=1)
    description: str | None = Field(default=None, description="Markdown body.")
    labels: list[str] | None = None
    assignee_usernames: list[str] | None = None


class AddCommentInput(BaseModel):
    project: str = Field(min_length=1)
    issue_iid: int = Field(ge=1)
    body: str = Field(min_length=1, description="Markdown comment.")


class ListMergeRequestsInput(BaseModel):
    project: str = Field(min_length=1)
    state: str = Field(default="opened", description="opened, closed, merged, or all.")
    target_branch: str | None = None
    limit: int = Field(default=20, ge=1, le=100)


class GetMergeRequestInput(BaseModel):
    project: str = Field(min_length=1)
    merge_request_iid: int = Field(ge=1)
    include_changes: bool = Field(default=True)


@curated_tool(
    vendor=vendor.vendor,
    name="search_issues",
    display_name="Search GitLab Issues",
    description=(
        "Find issues in a project by state, label, assignee, or free text. The "
        "project is named the way it appears in its URL — acme/api — and the "
        "encoding GitLab requires is handled here."
    ),
    input_model=SearchIssuesInput,
    effect=ToolEffect.READ,
)
async def search_issues(
    payload: SearchIssuesInput, ctx: VendorToolContext
) -> dict[str, Any]:
    state = _state(payload.state, _STATES)
    query: dict[str, Any] = {"per_page": payload.limit, "order_by": "updated_at"}
    if state != "all":
        query["state"] = state
    if payload.text:
        query["search"] = payload.text
    if payload.labels:
        query["labels"] = ",".join(payload.labels)
    if payload.assignee_username:
        query["assignee_username"] = payload.assignee_username

    response = await ctx.read(
        f"/projects/{_project(payload.project)}/issues", query=query
    )
    issues = _list(response.data)
    return {
        "project": payload.project,
        "issues": [_issue_view(issue) for issue in issues],
        "count": len(issues),
    }


@curated_tool(
    vendor=vendor.vendor,
    name="get_issue",
    display_name="Get GitLab Issue",
    description=(
        "Read one issue together with its comment thread. GitLab calls "
        "comments notes and keeps them at a separate endpoint; system notes "
        "recording label and assignee changes are filtered out, so only what "
        "people wrote comes back."
    ),
    input_model=GetIssueInput,
    effect=ToolEffect.READ,
)
async def get_issue(payload: GetIssueInput, ctx: VendorToolContext) -> dict[str, Any]:
    project = _project(payload.project)
    issue = _object(
        (await ctx.read(f"/projects/{project}/issues/{payload.issue_iid}")).data
    )
    view = _issue_view(issue)
    view["description"] = _clip(issue.get("description"))
    if payload.include_comments:
        notes = await ctx.read(
            f"/projects/{project}/issues/{payload.issue_iid}/notes",
            query={"per_page": MAX_NOTES, "sort": "asc"},
        )
        view["comments"] = [
            {
                "author": (note.get("author") or {}).get("username"),
                "body": _clip(note.get("body")),
                "created_at": note.get("created_at"),
            }
            for note in _list(notes.data)
            if not note.get("system")
        ]
    return view


@curated_tool(
    vendor=vendor.vendor,
    name="create_issue",
    display_name="Create GitLab Issue",
    description=(
        "Open an issue with a title, markdown description, labels, and "
        "assignees given by username. Returns the issue's project-scoped "
        "number and web link."
    ),
    input_model=CreateIssueInput,
    effect=ToolEffect.MUTATION,
)
async def create_issue(
    payload: CreateIssueInput, ctx: VendorToolContext
) -> dict[str, Any]:
    body: dict[str, Any] = {"title": payload.title}
    if payload.description:
        body["description"] = payload.description
    if payload.labels:
        body["labels"] = ",".join(payload.labels)
    if payload.assignee_usernames:
        body["assignee_usernames"] = payload.assignee_usernames
    response = await ctx.mutate(
        f"/projects/{_project(payload.project)}/issues", json=body
    )
    return _issue_view(_object(response.data))


@curated_tool(
    vendor=vendor.vendor,
    name="add_comment",
    display_name="Comment on GitLab Issue",
    description="Add a markdown comment to an issue. Participants are notified.",
    input_model=AddCommentInput,
    effect=ToolEffect.MUTATION,
)
async def add_comment(
    payload: AddCommentInput, ctx: VendorToolContext
) -> dict[str, Any]:
    response = await ctx.mutate(
        f"/projects/{_project(payload.project)}/issues/{payload.issue_iid}/notes",
        json={"body": payload.body},
    )
    note = _object(response.data)
    return {
        "id": note.get("id"),
        "issue_iid": payload.issue_iid,
        "author": (note.get("author") or {}).get("username"),
        "created_at": note.get("created_at"),
    }


@curated_tool(
    vendor=vendor.vendor,
    name="list_merge_requests",
    display_name="List GitLab Merge Requests",
    description=(
        "List a project's merge requests, optionally narrowed to those "
        "targeting one branch. Each entry reports its branches, draft state, "
        "and whether it has merged."
    ),
    input_model=ListMergeRequestsInput,
    effect=ToolEffect.READ,
)
async def list_merge_requests(
    payload: ListMergeRequestsInput, ctx: VendorToolContext
) -> dict[str, Any]:
    state = _state(payload.state, _MR_STATES)
    query: dict[str, Any] = {"per_page": payload.limit, "order_by": "updated_at"}
    if state != "all":
        query["state"] = state
    if payload.target_branch:
        query["target_branch"] = payload.target_branch
    response = await ctx.read(
        f"/projects/{_project(payload.project)}/merge_requests", query=query
    )
    requests = _list(response.data)
    return {
        "project": payload.project,
        "merge_requests": [_merge_request_view(item) for item in requests],
        "count": len(requests),
    }


@curated_tool(
    vendor=vendor.vendor,
    name="get_merge_request",
    display_name="Get GitLab Merge Request",
    description=(
        "Read a merge request together with the files it changes and whether "
        "it can merge cleanly. GitLab splits the summary and the diff across "
        "two endpoints; both are fetched here."
    ),
    input_model=GetMergeRequestInput,
    effect=ToolEffect.READ,
)
async def get_merge_request(
    payload: GetMergeRequestInput, ctx: VendorToolContext
) -> dict[str, Any]:
    project = _project(payload.project)
    request = _object(
        (
            await ctx.read(
                f"/projects/{project}/merge_requests/{payload.merge_request_iid}"
            )
        ).data
    )
    view = _merge_request_view(request)
    view["description"] = _clip(request.get("description"))
    view["merge_status"] = request.get("detailed_merge_status") or request.get(
        "merge_status"
    )
    view["has_conflicts"] = request.get("has_conflicts")

    if payload.include_changes:
        changes = _object(
            (
                await ctx.read(
                    f"/projects/{project}/merge_requests/"
                    f"{payload.merge_request_iid}/changes"
                )
            ).data
        )
        files = [c for c in changes.get("changes") or [] if isinstance(c, dict)]
        view["files"] = [
            {
                "path": item.get("new_path"),
                "new_file": item.get("new_file"),
                "deleted_file": item.get("deleted_file"),
                "renamed_file": item.get("renamed_file"),
            }
            for item in files
        ]
        view["changed_files"] = len(files)
    return view


def _project(value: str) -> str:
    """URL-encode a project path so its slashes survive the path segment.

    This is the step that makes or breaks every GitLab call: `acme/api` has to
    reach the server as `acme%2Fapi`, or it is read as extra path segments.
    """
    candidate = value.strip().strip("/")
    if candidate.startswith("https://"):
        parts = [part for part in candidate.split("/") if part]
        candidate = "/".join(parts[2:]) if len(parts) > 2 else ""
    if not candidate:
        raise VendorToolError(
            "project_invalid",
            f"'{value}' is not a GitLab project. Use group/name, e.g. acme/api.",
        )
    if candidate.isdigit():
        return candidate
    return quote(candidate, safe="")


def _state(value: str, allowed: tuple[str, ...]) -> str:
    state = value.strip().casefold()
    if state not in allowed:
        raise VendorToolError(
            "state_invalid", f"State must be one of: {', '.join(allowed)}."
        )
    return state


def _issue_view(issue: dict[str, Any]) -> dict[str, Any]:
    assignees = [a for a in issue.get("assignees") or [] if isinstance(a, dict)]
    return {
        "iid": issue.get("iid"),
        "title": issue.get("title"),
        "state": issue.get("state"),
        "author": (issue.get("author") or {}).get("username"),
        "labels": issue.get("labels") or [],
        "assignees": [a.get("username") for a in assignees],
        "milestone": (issue.get("milestone") or {}).get("title"),
        "due_date": issue.get("due_date"),
        "created_at": issue.get("created_at"),
        "updated_at": issue.get("updated_at"),
        "closed_at": issue.get("closed_at"),
        "web_link": issue.get("web_url"),
    }


def _merge_request_view(request: dict[str, Any]) -> dict[str, Any]:
    return {
        "iid": request.get("iid"),
        "title": request.get("title"),
        "state": request.get("state"),
        "author": (request.get("author") or {}).get("username"),
        "source_branch": request.get("source_branch"),
        "target_branch": request.get("target_branch"),
        "draft": request.get("draft"),
        "merged": request.get("state") == "merged",
        "merged_at": request.get("merged_at"),
        "created_at": request.get("created_at"),
        "updated_at": request.get("updated_at"),
        "web_link": request.get("web_url"),
    }


def _clip(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    return value[:MAX_BODY_CHARS]


def _list(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        # GitLab reports failures as {"message": ...} or {"error": ...}.
        _object(payload)
        raise VendorToolError(
            "vendor_response_invalid", "GitLab returned an object where a list was due."
        )
    if not isinstance(payload, list):
        raise VendorToolError(
            "vendor_response_invalid", "GitLab returned an unexpected response."
        )
    return [item for item in payload if isinstance(item, dict)]


def _object(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise VendorToolError(
            "vendor_response_invalid", "GitLab returned a non-object response."
        )
    for key in ("message", "error"):
        value = payload.get(key)
        if value is not None and "id" not in payload and "iid" not in payload:
            raise VendorToolError("vendor_rejected", str(value)[:500])
    return payload


__all__ = [
    "add_comment",
    "create_issue",
    "get_issue",
    "get_merge_request",
    "list_merge_requests",
    "search_issues",
]
