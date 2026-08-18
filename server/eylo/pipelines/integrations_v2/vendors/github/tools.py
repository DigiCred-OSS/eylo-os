"""Curated GitHub tool implementations for the `integrations_v2` pipeline."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from eylo.modules.integrations_v2.domain.enums import ToolEffect

from ...contracts import VendorToolContext, VendorToolError
from ...registry import curated_tool
from .definition import REPO, vendor

MAX_BODY_CHARS = 6_000
MAX_COMMENTS = 20
MAX_FILES = 50
_STATES = ("open", "closed", "all")


class SearchIssuesInput(BaseModel):
    repository: str = Field(
        default="",
        description="Repository as owner/name. Omit to search everything visible.",
    )
    text: str | None = Field(default=None, description="Free text to match.")
    state: str = Field(default="open", description="open, closed, or all.")
    labels: list[str] | None = Field(default=None, description="All must be present.")
    assignee: str | None = Field(default=None, description="GitHub username.")
    author: str | None = Field(default=None, description="GitHub username.")
    include_pull_requests: bool = Field(
        default=False,
        description="GitHub counts pull requests as issues; this keeps them out.",
    )
    limit: int = Field(default=20, ge=1, le=50)


class GetIssueInput(BaseModel):
    repository: str = Field(min_length=1, description="Repository as owner/name.")
    number: int = Field(ge=1, description="Issue number as shown in its URL.")
    include_comments: bool = Field(default=True)


class CreateIssueInput(BaseModel):
    repository: str = Field(min_length=1)
    title: str = Field(min_length=1)
    body: str | None = Field(default=None, description="Markdown description.")
    labels: list[str] | None = None
    assignees: list[str] | None = Field(default=None, description="GitHub usernames.")


class AddCommentInput(BaseModel):
    repository: str = Field(min_length=1)
    number: int = Field(ge=1, description="Issue or pull request number.")
    body: str = Field(min_length=1, description="Markdown comment.")


class ListPullRequestsInput(BaseModel):
    repository: str = Field(min_length=1)
    state: str = Field(default="open", description="open, closed, or all.")
    base_branch: str | None = Field(
        default=None, description="Only requests targeting this branch."
    )
    limit: int = Field(default=20, ge=1, le=50)


class GetPullRequestInput(BaseModel):
    repository: str = Field(min_length=1)
    number: int = Field(ge=1)
    include_files: bool = Field(default=True)
    include_reviews: bool = Field(default=True)


class CreatePullRequestInput(BaseModel):
    repository: str = Field(min_length=1)
    title: str = Field(min_length=1)
    head_branch: str = Field(min_length=1, description="Branch holding the changes.")
    base_branch: str = Field(default="main", description="Branch to merge into.")
    body: str | None = None
    draft: bool = Field(default=False)


@curated_tool(
    vendor=vendor.vendor,
    name="search_issues",
    display_name="Search GitHub Issues",
    description=(
        "Find issues by repository, state, label, assignee, author, or free "
        "text, without writing GitHub's search syntax. Pull requests are "
        "excluded unless asked for, since GitHub otherwise returns them mixed "
        "in with issues."
    ),
    input_model=SearchIssuesInput,
    effect=ToolEffect.READ,
    scopes=(REPO,),
)
async def search_issues(
    payload: SearchIssuesInput, ctx: VendorToolContext
) -> dict[str, Any]:
    state = _state(payload.state)
    terms: list[str] = []
    if payload.repository:
        terms.append(f"repo:{_repository(payload.repository)}")
    if not payload.include_pull_requests:
        terms.append("is:issue")
    if state != "all":
        terms.append(f"state:{state}")
    for label in payload.labels or []:
        terms.append(f'label:"{label}"')
    if payload.assignee:
        terms.append(f"assignee:{payload.assignee}")
    if payload.author:
        terms.append(f"author:{payload.author}")
    if payload.text:
        terms.append(payload.text)
    if not terms:
        raise VendorToolError(
            "search_unbounded",
            "Give at least a repository or some text to search for.",
        )

    query = " ".join(terms)
    response = await ctx.read(
        "/search/issues",
        query={"q": query, "per_page": payload.limit, "sort": "updated"},
    )
    body = _object(response.data)
    items = [item for item in body.get("items") or [] if isinstance(item, dict)]
    return {
        "issues": [_issue_view(item) for item in items],
        "count": len(items),
        "total_matches": body.get("total_count"),
        "query": query,
    }


@curated_tool(
    vendor=vendor.vendor,
    name="get_issue",
    display_name="Get GitHub Issue",
    description=(
        "Read one issue together with its comment thread, so the discussion "
        "arrives with the issue rather than costing a second call. Labels, "
        "assignees, and state are included."
    ),
    input_model=GetIssueInput,
    effect=ToolEffect.READ,
    scopes=(REPO,),
)
async def get_issue(payload: GetIssueInput, ctx: VendorToolContext) -> dict[str, Any]:
    repository = _repository(payload.repository)
    issue = _object(
        (await ctx.read(f"/repos/{repository}/issues/{payload.number}")).data
    )
    view = _issue_view(issue)
    view["body"] = _clip(issue.get("body"))
    if payload.include_comments:
        response = await ctx.read(
            f"/repos/{repository}/issues/{payload.number}/comments",
            query={"per_page": MAX_COMMENTS},
        )
        view["comments"] = [_comment_view(item) for item in _list(response.data)]
    return view


@curated_tool(
    vendor=vendor.vendor,
    name="create_issue",
    display_name="Create GitHub Issue",
    description=(
        "Open an issue with a title, markdown body, labels, and assignees. "
        "Returns the new issue's number and web link."
    ),
    input_model=CreateIssueInput,
    effect=ToolEffect.MUTATION,
    scopes=(REPO,),
)
async def create_issue(
    payload: CreateIssueInput, ctx: VendorToolContext
) -> dict[str, Any]:
    repository = _repository(payload.repository)
    body: dict[str, Any] = {"title": payload.title}
    if payload.body:
        body["body"] = payload.body
    if payload.labels:
        body["labels"] = payload.labels
    if payload.assignees:
        body["assignees"] = payload.assignees
    response = await ctx.mutate(f"/repos/{repository}/issues", json=body)
    return _issue_view(_object(response.data))


@curated_tool(
    vendor=vendor.vendor,
    name="add_comment",
    display_name="Comment on GitHub Issue",
    description=(
        "Add a markdown comment to an issue or pull request. GitHub numbers "
        "both in one sequence, so the same tool serves either."
    ),
    input_model=AddCommentInput,
    effect=ToolEffect.MUTATION,
    scopes=(REPO,),
)
async def add_comment(
    payload: AddCommentInput, ctx: VendorToolContext
) -> dict[str, Any]:
    repository = _repository(payload.repository)
    response = await ctx.mutate(
        f"/repos/{repository}/issues/{payload.number}/comments",
        json={"body": payload.body},
    )
    return _comment_view(_object(response.data))


@curated_tool(
    vendor=vendor.vendor,
    name="list_pull_requests",
    display_name="List GitHub Pull Requests",
    description=(
        "List a repository's pull requests, optionally narrowed to those "
        "targeting one branch. Each entry reports its branches, draft state, "
        "and whether it has merged."
    ),
    input_model=ListPullRequestsInput,
    effect=ToolEffect.READ,
    scopes=(REPO,),
)
async def list_pull_requests(
    payload: ListPullRequestsInput, ctx: VendorToolContext
) -> dict[str, Any]:
    repository = _repository(payload.repository)
    query: dict[str, Any] = {
        "state": _state(payload.state),
        "per_page": payload.limit,
        "sort": "updated",
        "direction": "desc",
    }
    if payload.base_branch:
        query["base"] = payload.base_branch
    response = await ctx.read(f"/repos/{repository}/pulls", query=query)
    items = _list(response.data)
    return {
        "repository": repository,
        "pull_requests": [_pull_view(item) for item in items],
        "count": len(items),
    }


@curated_tool(
    vendor=vendor.vendor,
    name="get_pull_request",
    display_name="Get GitHub Pull Request",
    description=(
        "Read a pull request together with the files it changes and the "
        "reviews left on it. GitHub splits these across three endpoints; this "
        "returns the whole picture at once, which is what deciding anything "
        "about a pull request actually needs."
    ),
    input_model=GetPullRequestInput,
    effect=ToolEffect.READ,
    scopes=(REPO,),
)
async def get_pull_request(
    payload: GetPullRequestInput, ctx: VendorToolContext
) -> dict[str, Any]:
    repository = _repository(payload.repository)
    pull = _object((await ctx.read(f"/repos/{repository}/pulls/{payload.number}")).data)
    view = _pull_view(pull)
    view["body"] = _clip(pull.get("body"))
    view["additions"] = pull.get("additions")
    view["deletions"] = pull.get("deletions")
    view["changed_files"] = pull.get("changed_files")
    view["mergeable"] = pull.get("mergeable")

    if payload.include_files:
        response = await ctx.read(
            f"/repos/{repository}/pulls/{payload.number}/files",
            query={"per_page": MAX_FILES},
        )
        view["files"] = [
            {
                "filename": item.get("filename"),
                "status": item.get("status"),
                "additions": item.get("additions"),
                "deletions": item.get("deletions"),
            }
            for item in _list(response.data)
        ]
    if payload.include_reviews:
        response = await ctx.read(
            f"/repos/{repository}/pulls/{payload.number}/reviews",
            query={"per_page": MAX_COMMENTS},
        )
        reviews = _list(response.data)
        view["reviews"] = [
            {
                "reviewer": (item.get("user") or {}).get("login"),
                "state": item.get("state"),
                "submitted_at": item.get("submitted_at"),
            }
            for item in reviews
        ]
        view["approved"] = any(
            str(item.get("state")).upper() == "APPROVED" for item in reviews
        )
    return view


@curated_tool(
    vendor=vendor.vendor,
    name="create_pull_request",
    display_name="Create GitHub Pull Request",
    description=(
        "Open a pull request from one branch into another. Both branches must "
        "already exist. Returns the new pull request's number and web link."
    ),
    input_model=CreatePullRequestInput,
    effect=ToolEffect.MUTATION,
    scopes=(REPO,),
)
async def create_pull_request(
    payload: CreatePullRequestInput, ctx: VendorToolContext
) -> dict[str, Any]:
    repository = _repository(payload.repository)
    body: dict[str, Any] = {
        "title": payload.title,
        "head": payload.head_branch,
        "base": payload.base_branch,
        "draft": payload.draft,
    }
    if payload.body:
        body["body"] = payload.body
    response = await ctx.mutate(f"/repos/{repository}/pulls", json=body)
    return _pull_view(_object(response.data))


def _repository(value: str) -> str:
    """Accept `owner/name`, which is how people write a repository."""
    candidate = value.strip().strip("/")
    if candidate.startswith("https://"):
        # Tolerate a pasted URL rather than failing on something recognisable.
        parts = [part for part in candidate.split("/") if part]
        candidate = "/".join(parts[-2:]) if len(parts) >= 2 else ""
    pieces = candidate.split("/")
    if len(pieces) != 2 or not all(piece.strip() for piece in pieces):
        raise VendorToolError(
            "repository_invalid",
            f"'{value}' is not a repository. Use owner/name, e.g. acme/api.",
        )
    return f"{pieces[0]}/{pieces[1]}"


def _state(value: str) -> str:
    state = value.strip().casefold()
    if state not in _STATES:
        raise VendorToolError(
            "state_invalid", f"State must be one of: {', '.join(_STATES)}."
        )
    return state


def _issue_view(issue: dict[str, Any]) -> dict[str, Any]:
    labels = [label for label in issue.get("labels") or [] if isinstance(label, dict)]
    assignees = [a for a in issue.get("assignees") or [] if isinstance(a, dict)]
    return {
        "number": issue.get("number"),
        "title": issue.get("title"),
        "state": issue.get("state"),
        "author": (issue.get("user") or {}).get("login"),
        "labels": [label.get("name") for label in labels],
        "assignees": [a.get("login") for a in assignees],
        "comment_count": issue.get("comments"),
        "created_at": issue.get("created_at"),
        "updated_at": issue.get("updated_at"),
        "closed_at": issue.get("closed_at"),
        "web_link": issue.get("html_url"),
        "is_pull_request": "pull_request" in issue,
    }


def _pull_view(pull: dict[str, Any]) -> dict[str, Any]:
    return {
        "number": pull.get("number"),
        "title": pull.get("title"),
        "state": pull.get("state"),
        "author": (pull.get("user") or {}).get("login"),
        "head_branch": (pull.get("head") or {}).get("ref"),
        "base_branch": (pull.get("base") or {}).get("ref"),
        "draft": pull.get("draft"),
        "merged": pull.get("merged_at") is not None,
        "merged_at": pull.get("merged_at"),
        "created_at": pull.get("created_at"),
        "updated_at": pull.get("updated_at"),
        "web_link": pull.get("html_url"),
    }


def _comment_view(comment: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": comment.get("id"),
        "author": (comment.get("user") or {}).get("login"),
        "body": _clip(comment.get("body")),
        "created_at": comment.get("created_at"),
        "web_link": comment.get("html_url"),
    }


def _clip(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    return value[:MAX_BODY_CHARS]


def _list(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict) and isinstance(payload.get("message"), str):
        raise VendorToolError("vendor_rejected", str(payload["message"])[:500])
    if not isinstance(payload, list):
        raise VendorToolError(
            "vendor_response_invalid", "GitHub returned an unexpected response."
        )
    return [item for item in payload if isinstance(item, dict)]


def _object(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise VendorToolError(
            "vendor_response_invalid", "GitHub returned a non-object response."
        )
    # GitHub reports failures as a plain `message` rather than an error object.
    if "message" in payload and "id" not in payload and "number" not in payload:
        raise VendorToolError("vendor_rejected", str(payload["message"])[:500])
    return payload


__all__ = [
    "add_comment",
    "create_issue",
    "create_pull_request",
    "get_issue",
    "get_pull_request",
    "list_pull_requests",
    "search_issues",
]
