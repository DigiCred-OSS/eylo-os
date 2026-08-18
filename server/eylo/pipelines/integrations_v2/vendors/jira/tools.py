"""Curated Jira tools.

`create_issue` is the composition that earns its keep: an agent supplies a
project key and an issue type by name, and the tool resolves both, converts the
description into Atlassian Document Format, and creates the issue. Done through
the raw API that is three calls plus knowing that a plain string description is
rejected.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from eylo.modules.integrations_v2.domain.enums import ToolEffect

from ...contracts import VendorToolContext, VendorToolError
from ...registry import curated_tool
from .definition import READ_JIRA_WORK, WRITE_JIRA_WORK, vendor


class SearchIssuesInput(BaseModel):
    jql: str | None = Field(
        default=None,
        description="Raw JQL. Omit it and use the simple filters below instead.",
    )
    project_key: str | None = Field(
        default=None, description="Project key such as PLT."
    )
    text: str | None = Field(
        default=None, description="Free text matched against summary and description."
    )
    status: str | None = Field(default=None, description="Status name such as 'Done'.")
    assignee_email: str | None = Field(default=None)
    limit: int = Field(default=25, ge=1, le=100)


class GetIssueInput(BaseModel):
    issue_key: str = Field(min_length=1, description="Issue key such as PLT-123.")


class CreateIssueInput(BaseModel):
    project_key: str = Field(min_length=1, description="Project key such as PLT.")
    summary: str = Field(min_length=1, description="Issue summary.")
    issue_type: str = Field(
        default="Task",
        description="Issue type name such as Task, Bug, or Story.",
    )
    description: str | None = Field(
        default=None, description="Issue description as plain text."
    )
    assignee_email: str | None = Field(default=None)
    labels: list[str] | None = Field(default=None)


class AddCommentInput(BaseModel):
    issue_key: str = Field(min_length=1, description="Issue key such as PLT-123.")
    body: str = Field(min_length=1, description="Comment text as plain text.")


@curated_tool(
    vendor=vendor.vendor,
    name="search_issues",
    display_name="Search Jira Issues",
    description=(
        "Search Jira issues. Supply raw JQL, or use the simple filters "
        "(project key, free text, status, assignee email) and the JQL is built "
        "for you. Returns issues with status, assignee, and type resolved."
    ),
    input_model=SearchIssuesInput,
    effect=ToolEffect.READ,
    scopes=(READ_JIRA_WORK,),
)
async def search_issues(
    payload: SearchIssuesInput, ctx: VendorToolContext
) -> dict[str, Any]:
    jql = payload.jql.strip() if payload.jql else _build_jql(payload)
    if not jql:
        raise VendorToolError(
            "search_too_broad",
            "Supply JQL or at least one filter; an unbounded search is refused.",
        )
    response = await ctx.read(
        "/search/jql",
        method="POST",
        json={
            "jql": jql,
            "maxResults": payload.limit,
            "fields": [
                "summary",
                "status",
                "assignee",
                "issuetype",
                "created",
                "updated",
            ],
        },
    )
    body = _object(response.data)
    issues = [i for i in body.get("issues", []) if isinstance(i, dict)]
    return {
        "jql": jql,
        "issues": [_issue_view(issue) for issue in issues],
        "count": len(issues),
    }


@curated_tool(
    vendor=vendor.vendor,
    name="get_issue",
    display_name="Get Jira Issue",
    description=(
        "Read one Jira issue by key, including its description as plain text "
        "rather than Atlassian Document Format."
    ),
    input_model=GetIssueInput,
    effect=ToolEffect.READ,
    scopes=(READ_JIRA_WORK,),
)
async def get_issue(payload: GetIssueInput, ctx: VendorToolContext) -> dict[str, Any]:
    response = await ctx.read(f"/issue/{payload.issue_key}")
    view = _issue_view(_object(response.data))
    fields = _object(response.data).get("fields") or {}
    view["description"] = _adf_to_text(fields.get("description"))
    return view


@curated_tool(
    vendor=vendor.vendor,
    name="create_issue",
    display_name="Create Jira Issue",
    description=(
        "Create a Jira issue from a project key and an issue type name. The "
        "project and type are resolved automatically, the description is "
        "converted to Atlassian Document Format, and an assignee email is "
        "looked up if supplied."
    ),
    input_model=CreateIssueInput,
    effect=ToolEffect.MUTATION,
    scopes=(WRITE_JIRA_WORK, READ_JIRA_WORK),
)
async def create_issue(
    payload: CreateIssueInput, ctx: VendorToolContext
) -> dict[str, Any]:
    project_id, type_id = await _resolve_project_and_type(
        ctx, payload.project_key, payload.issue_type
    )
    fields: dict[str, Any] = {
        "project": {"id": project_id},
        "issuetype": {"id": type_id},
        "summary": payload.summary,
    }
    if payload.description:
        fields["description"] = _text_to_adf(payload.description)
    if payload.labels:
        fields["labels"] = payload.labels
    if payload.assignee_email:
        fields["assignee"] = {
            "id": await _resolve_account_id(ctx, payload.assignee_email)
        }

    response = await ctx.mutate("/issue", method="POST", json={"fields": fields})
    created = _object(response.data)
    key = created.get("key")
    if not key:
        raise VendorToolError("vendor_rejected", "Jira did not return an issue key.")
    return {"key": key, "id": created.get("id"), "summary": payload.summary}


@curated_tool(
    vendor=vendor.vendor,
    name="add_comment",
    display_name="Comment On Jira Issue",
    description=(
        "Add a comment to a Jira issue. Plain text is converted to Atlassian "
        "Document Format, which the raw API requires."
    ),
    input_model=AddCommentInput,
    effect=ToolEffect.MUTATION,
    scopes=(WRITE_JIRA_WORK,),
)
async def add_comment(
    payload: AddCommentInput, ctx: VendorToolContext
) -> dict[str, Any]:
    response = await ctx.mutate(
        f"/issue/{payload.issue_key}/comment",
        method="POST",
        json={"body": _text_to_adf(payload.body)},
    )
    created = _object(response.data)
    return {
        "id": created.get("id"),
        "issue_key": payload.issue_key,
        "created": created.get("created"),
    }


async def _resolve_project_and_type(
    ctx: VendorToolContext, project_key: str, issue_type: str
) -> tuple[str, str]:
    """One call resolves both: Jira returns issue types inside the project."""
    response = await ctx.read(
        f"/project/{project_key.strip().upper()}", query={"expand": "issueTypes"}
    )
    project = _object(response.data)
    project_id = project.get("id")
    if not project_id:
        raise VendorToolError(
            "project_not_found", f"No Jira project with key '{project_key}'."
        )
    wanted = issue_type.strip().casefold()
    for entry in project.get("issueTypes", []):
        if isinstance(entry, dict) and str(entry.get("name", "")).casefold() == wanted:
            return str(project_id), str(entry["id"])
    available = ", ".join(
        str(e.get("name")) for e in project.get("issueTypes", []) if isinstance(e, dict)
    )
    raise VendorToolError(
        "issue_type_not_found",
        f"Project '{project_key}' has no issue type '{issue_type}'. Available: {available}.",
    )


async def _resolve_account_id(ctx: VendorToolContext, email: str) -> str:
    response = await ctx.read("/user/search", query={"query": email})
    users = response.data if isinstance(response.data, list) else []
    for user in users:
        if isinstance(user, dict) and user.get("accountId"):
            return str(user["accountId"])
    raise VendorToolError("user_not_found", f"No Jira user matches '{email}'.")


def _build_jql(payload: SearchIssuesInput) -> str:
    clauses: list[str] = []
    if payload.project_key:
        clauses.append(f'project = "{payload.project_key.strip().upper()}"')
    if payload.status:
        clauses.append(f'status = "{payload.status.strip()}"')
    if payload.assignee_email:
        clauses.append(f'assignee = "{payload.assignee_email.strip()}"')
    if payload.text:
        clauses.append(f'text ~ "{payload.text.strip()}"')
    return " AND ".join(clauses) + (" ORDER BY updated DESC" if clauses else "")


def _issue_view(issue: dict[str, Any]) -> dict[str, Any]:
    fields = issue.get("fields") or {}
    status = fields.get("status") or {}
    assignee = fields.get("assignee") or {}
    issue_type = fields.get("issuetype") or {}
    return {
        "key": issue.get("key"),
        "id": issue.get("id"),
        "summary": fields.get("summary"),
        "status": status.get("name"),
        "type": issue_type.get("name"),
        "assignee_name": assignee.get("displayName"),
        "assignee_email": assignee.get("emailAddress"),
        "created": fields.get("created"),
        "updated": fields.get("updated"),
    }


def _text_to_adf(text: str) -> dict[str, Any]:
    """Wrap plain text in the minimal Atlassian Document Format envelope.

    Jira's v3 API rejects a plain string here. Every curated Jira tool that
    writes prose goes through this so no caller has to know that.
    """
    return {
        "type": "doc",
        "version": 1,
        "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": line}]}
            if line
            else {"type": "paragraph"}
            for line in text.split("\n")
        ],
    }


def _adf_to_text(document: Any) -> str | None:
    """Flatten Atlassian Document Format back to readable text."""
    if document is None:
        return None
    if isinstance(document, str):
        return document
    if not isinstance(document, dict):
        return None
    parts: list[str] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            if node.get("type") == "text" and isinstance(node.get("text"), str):
                parts.append(node["text"])
            for child in node.get("content", []) or []:
                walk(child)
            if node.get("type") == "paragraph":
                parts.append("\n")
        elif isinstance(node, list):
            for child in node:
                walk(child)

    walk(document)
    return "".join(parts).strip() or None


def _object(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise VendorToolError(
            "vendor_response_invalid", "Jira returned a non-object response."
        )
    if payload.get("errorMessages"):
        raise VendorToolError(
            "vendor_rejected", "; ".join(str(m) for m in payload["errorMessages"])[:500]
        )
    return payload


__all__ = ["add_comment", "create_issue", "get_issue", "search_issues"]
