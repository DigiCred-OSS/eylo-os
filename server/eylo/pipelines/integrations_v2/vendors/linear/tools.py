"""Curated Linear tools.

These are the shape the whole V2 effort exists for. `create_issue` accepts the
team *name* and assignee *email* an agent already has from the conversation and
resolves them to Linear ids itself; `remove_issue_label` reads the issue,
computes the remaining labels, and writes them back. Each is one tool call
where the raw API would have cost two or three plus the model's reasoning about
intermediate JSON.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from eylo.modules.integrations_v2.domain.enums import ToolEffect

from ...contracts import VendorToolContext, VendorToolError
from ...registry import curated_tool
from . import client
from .definition import vendor
from .scopes import ISSUES_CREATE, READ, WRITE

_ISSUE_FIELDS = """
  id
  identifier
  title
  description
  url
  priority
  priorityLabel
  state { id name type }
  assignee { id name email }
  team { id name key }
  labels { nodes { id name } }
  createdAt
  updatedAt
"""


class ListIssuesInput(BaseModel):
    team_name: str | None = Field(
        default=None,
        description="Restrict to one team by its name, for example 'Platform'.",
    )
    assignee_email: str | None = Field(
        default=None,
        description="Restrict to issues assigned to this person's email address.",
    )
    limit: int = Field(
        default=25,
        ge=1,
        le=100,
        description="Maximum number of issues to return.",
    )


class CreateIssueInput(BaseModel):
    title: str = Field(min_length=1, description="Issue title.")
    team_name: str = Field(
        min_length=1,
        description="Name of the team the issue belongs to, for example 'Platform'.",
    )
    description: str | None = Field(
        default=None,
        description="Issue body in Markdown.",
    )
    assignee_email: str | None = Field(
        default=None,
        description="Email address of the person to assign the issue to.",
    )
    priority: int | None = Field(
        default=None,
        ge=0,
        le=4,
        description="0 none, 1 urgent, 2 high, 3 medium, 4 low.",
    )


class RemoveIssueLabelInput(BaseModel):
    issue_id: str = Field(
        min_length=1,
        description="Issue id or identifier such as 'PLT-123'.",
    )
    label_name: str = Field(
        min_length=1,
        description="Name of the label to remove from the issue.",
    )


@curated_tool(
    vendor=vendor.vendor,
    name="list_issues",
    display_name="List Linear Issues",
    description=(
        "List non-archived Linear issues, optionally narrowed to one team by "
        "name or one assignee by email address. Returns issues with their "
        "state, assignee, team, and labels already resolved, so no follow-up "
        "lookup is needed."
    ),
    input_model=ListIssuesInput,
    effect=ToolEffect.READ,
    scopes=(READ,),
)
async def list_issues(
    payload: ListIssuesInput,
    ctx: VendorToolContext,
) -> dict[str, Any]:
    filters: dict[str, Any] = {}
    if payload.team_name:
        filters["team"] = {"name": {"eqIgnoreCase": payload.team_name}}
    if payload.assignee_email:
        filters["assignee"] = {"email": {"eqIgnoreCase": payload.assignee_email}}

    document = f"""
      query Issues($first: Int, $filter: IssueFilter) {{
        issues(first: $first, filter: $filter) {{
          nodes {{{_ISSUE_FIELDS}}}
        }}
      }}
    """
    data = await client.query(
        ctx,
        document,
        {"first": payload.limit, "filter": filters or None},
    )
    issues = [_issue_view(node) for node in client.nodes(data, "issues")]
    return {"issues": issues, "count": len(issues)}


@curated_tool(
    vendor=vendor.vendor,
    name="create_issue",
    display_name="Create Linear Issue",
    description=(
        "Create a Linear issue from a team name and, optionally, an assignee "
        "email address. Both are resolved to Linear ids automatically, so the "
        "team and person can be named the way a person would say them rather "
        "than looked up first."
    ),
    input_model=CreateIssueInput,
    effect=ToolEffect.MUTATION,
    scopes=(ISSUES_CREATE,),
)
async def create_issue(
    payload: CreateIssueInput,
    ctx: VendorToolContext,
) -> dict[str, Any]:
    team_id = await _resolve_team_id(ctx, payload.team_name)
    assignee_id = (
        await _resolve_user_id(ctx, payload.assignee_email)
        if payload.assignee_email
        else None
    )

    document = f"""
      mutation IssueCreate($input: IssueCreateInput!) {{
        issueCreate(input: $input) {{
          success
          issue {{{_ISSUE_FIELDS}}}
        }}
      }}
    """
    issue_input: dict[str, Any] = {"title": payload.title, "teamId": team_id}
    if payload.description is not None:
        issue_input["description"] = payload.description
    if assignee_id is not None:
        issue_input["assigneeId"] = assignee_id
    if payload.priority is not None:
        issue_input["priority"] = payload.priority

    data = await client.mutate(ctx, document, {"input": issue_input})
    result = data.get("issueCreate")
    if not isinstance(result, dict) or not result.get("success"):
        raise VendorToolError("vendor_rejected", "Linear did not create the issue.")
    return _issue_view(result.get("issue"))


@curated_tool(
    vendor=vendor.vendor,
    name="remove_issue_label",
    display_name="Remove Label From Linear Issue",
    description=(
        "Remove one label from a Linear issue by label name. Reads the issue's "
        "current labels, removes the named one, and writes the remainder back "
        "in a single step. Reports clearly when the issue does not carry that "
        "label rather than silently succeeding."
    ),
    input_model=RemoveIssueLabelInput,
    effect=ToolEffect.MUTATION,
    scopes=(WRITE,),
)
async def remove_issue_label(
    payload: RemoveIssueLabelInput,
    ctx: VendorToolContext,
) -> dict[str, Any]:
    document = f"""
      query Issue($id: String!) {{
        issue(id: $id) {{{_ISSUE_FIELDS}}}
      }}
    """
    data = await client.query(ctx, document, {"id": payload.issue_id})
    issue = data.get("issue")
    if not isinstance(issue, dict):
        raise VendorToolError("issue_not_found", "Linear issue was not found.")

    labels = client.nodes(issue, "labels")
    wanted = payload.label_name.strip().casefold()
    remaining = [
        label
        for label in labels
        if str(label.get("name", "")).strip().casefold() != wanted
    ]
    if len(remaining) == len(labels):
        raise VendorToolError(
            "label_not_present",
            f"Issue does not carry the label '{payload.label_name}'.",
        )

    update = f"""
      mutation IssueUpdate($id: String!, $input: IssueUpdateInput!) {{
        issueUpdate(id: $id, input: $input) {{
          success
          issue {{{_ISSUE_FIELDS}}}
        }}
      }}
    """
    updated = await client.mutate(
        ctx,
        update,
        {
            "id": str(issue.get("id")),
            "input": {"labelIds": [str(label.get("id")) for label in remaining]},
        },
    )
    result = updated.get("issueUpdate")
    if not isinstance(result, dict) or not result.get("success"):
        raise VendorToolError("vendor_rejected", "Linear did not update the issue.")
    return _issue_view(result.get("issue"))


async def _resolve_team_id(ctx: VendorToolContext, team_name: str) -> str:
    document = """
      query Teams($name: String!) {
        teams(filter: { name: { eqIgnoreCase: $name } }, first: 2) {
          nodes { id name key }
        }
      }
    """
    data = await client.query(ctx, document, {"name": team_name})
    teams = client.nodes(data, "teams")
    if not teams:
        raise VendorToolError("team_not_found", f"No Linear team named '{team_name}'.")
    if len(teams) > 1:
        raise VendorToolError(
            "team_ambiguous",
            f"More than one Linear team matches '{team_name}'.",
        )
    return str(teams[0]["id"])


async def _resolve_user_id(ctx: VendorToolContext, email: str) -> str:
    document = """
      query Users($email: String!) {
        users(filter: { email: { eqIgnoreCase: $email } }, first: 2) {
          nodes { id name email }
        }
      }
    """
    data = await client.query(ctx, document, {"email": email})
    users = client.nodes(data, "users")
    if not users:
        raise VendorToolError("user_not_found", f"No Linear user with email '{email}'.")
    return str(users[0]["id"])


def _issue_view(issue: Any) -> dict[str, Any]:
    """Project one Linear issue into the flat shape agents actually use."""
    if not isinstance(issue, dict):
        raise VendorToolError(
            "vendor_response_invalid",
            "Linear returned no issue for the operation.",
        )
    state = issue.get("state") if isinstance(issue.get("state"), dict) else {}
    assignee = issue.get("assignee") if isinstance(issue.get("assignee"), dict) else {}
    team = issue.get("team") if isinstance(issue.get("team"), dict) else {}
    return {
        "id": issue.get("id"),
        "identifier": issue.get("identifier"),
        "title": issue.get("title"),
        "description": issue.get("description"),
        "url": issue.get("url"),
        "priority": issue.get("priorityLabel"),
        "state": state.get("name"),
        "assignee_name": assignee.get("name"),
        "assignee_email": assignee.get("email"),
        "team_name": team.get("name"),
        "labels": [label.get("name") for label in client.nodes(issue, "labels")],
        "created_at": issue.get("createdAt"),
        "updated_at": issue.get("updatedAt"),
    }


__all__ = ["create_issue", "list_issues", "remove_issue_label"]
