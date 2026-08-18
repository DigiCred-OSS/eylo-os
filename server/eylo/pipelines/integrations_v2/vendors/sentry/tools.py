"""Curated Sentry tool implementations for the `integrations_v2` pipeline."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from eylo.modules.integrations_v2.domain.enums import ToolEffect

from ...contracts import VendorToolContext, VendorToolError
from ...registry import curated_tool
from .definition import EVENT_READ, EVENT_WRITE, PROJECT_READ, vendor

MAX_FRAMES = 20
MAX_BODY_CHARS = 4_000
_QUERIES = {
    "unresolved": "is:unresolved",
    "resolved": "is:resolved",
    "ignored": "is:ignored",
    "all": "",
}


class ListIssuesInput(BaseModel):
    organization: str = Field(min_length=1, description="Organization slug.")
    project: str = Field(min_length=1, description="Project slug.")
    state: str = Field(
        default="unresolved", description="unresolved, resolved, ignored, or all."
    )
    text: str | None = Field(default=None, description="Extra search terms.")
    limit: int = Field(default=25, ge=1, le=100)


class GetIssueInput(BaseModel):
    issue_id: str = Field(min_length=1, description="Numeric issue id.")
    include_stack_trace: bool = Field(default=True)


class ChangeIssueInput(BaseModel):
    issue_id: str = Field(min_length=1)


@curated_tool(
    vendor=vendor.vendor,
    name="list_issues",
    display_name="List Sentry Issues",
    description=(
        "List a project's issues — by default the unresolved ones — with how "
        "many times each has happened, how many users it has hit, and when it "
        "was last seen. That is what says whether something is worth acting on."
    ),
    input_model=ListIssuesInput,
    effect=ToolEffect.READ,
    scopes=(PROJECT_READ, EVENT_READ),
)
async def list_issues(
    payload: ListIssuesInput, ctx: VendorToolContext
) -> dict[str, Any]:
    state = payload.state.strip().casefold()
    if state not in _QUERIES:
        raise VendorToolError(
            "state_invalid", f"state must be one of: {', '.join(sorted(_QUERIES))}."
        )
    terms = [term for term in (_QUERIES[state], payload.text) if term]
    response = await ctx.read(
        f"/projects/{payload.organization}/{payload.project}/issues/",
        query={"query": " ".join(terms), "limit": payload.limit, "statsPeriod": "14d"},
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
    display_name="Get Sentry Issue",
    description=(
        "Read one issue with the stack trace from its most recent occurrence. "
        "Sentry keeps the trace on the event rather than the issue, nested "
        "several levels down and ordered with the crashing frame last; this "
        "returns application frames in reading order, innermost first."
    ),
    input_model=GetIssueInput,
    effect=ToolEffect.READ,
    scopes=(EVENT_READ,),
)
async def get_issue(payload: GetIssueInput, ctx: VendorToolContext) -> dict[str, Any]:
    issue = _object((await ctx.read(f"/issues/{payload.issue_id}/")).data)
    view = _issue_view(issue)

    if payload.include_stack_trace:
        event = _object(
            (await ctx.read(f"/issues/{payload.issue_id}/events/latest/")).data
        )
        view["last_event_at"] = event.get("dateCreated")
        view["stack_trace"] = _frames(event)
        view["exception"] = _exception_summary(event)
        view["tags"] = {
            str(tag.get("key")): tag.get("value")
            for tag in event.get("tags") or []
            if isinstance(tag, dict)
        }
    return view


@curated_tool(
    vendor=vendor.vendor,
    name="resolve_issue",
    display_name="Resolve Sentry Issue",
    description=(
        "Mark an issue as resolved, meaning the underlying bug is believed "
        "fixed. Sentry will reopen it automatically if it happens again. To "
        "silence something without claiming it is fixed, use ignore_issue."
    ),
    input_model=ChangeIssueInput,
    effect=ToolEffect.MUTATION,
    scopes=(EVENT_WRITE,),
)
async def resolve_issue(
    payload: ChangeIssueInput, ctx: VendorToolContext
) -> dict[str, Any]:
    response = await ctx.mutate(
        f"/issues/{payload.issue_id}/", method="PUT", json={"status": "resolved"}
    )
    _object(response.data)
    return {
        "issue_id": payload.issue_id,
        "status": "resolved",
        "reopens_if_seen_again": True,
    }


@curated_tool(
    vendor=vendor.vendor,
    name="ignore_issue",
    display_name="Ignore Sentry Issue",
    description=(
        "Mute an issue so it stops appearing and alerting, without claiming it "
        "is fixed. Use resolve_issue when the bug has actually been dealt with."
    ),
    input_model=ChangeIssueInput,
    effect=ToolEffect.MUTATION,
    scopes=(EVENT_WRITE,),
)
async def ignore_issue(
    payload: ChangeIssueInput, ctx: VendorToolContext
) -> dict[str, Any]:
    response = await ctx.mutate(
        f"/issues/{payload.issue_id}/", method="PUT", json={"status": "ignored"}
    )
    _object(response.data)
    return {"issue_id": payload.issue_id, "status": "ignored", "still_recorded": True}


def _frames(event: dict[str, Any]) -> list[dict[str, Any]]:
    """Dig the stack frames out of the event's entries and put them in order."""
    for entry in event.get("entries") or []:
        if not isinstance(entry, dict) or entry.get("type") != "exception":
            continue
        values = (entry.get("data") or {}).get("values") or []
        for value in values:
            if not isinstance(value, dict):
                continue
            frames = (value.get("stacktrace") or {}).get("frames") or []
            picked = [f for f in frames if isinstance(f, dict)]
            # Sentry orders frames oldest-first; the crash is the last one.
            picked.reverse()
            in_app = [f for f in picked if f.get("inApp")]
            chosen = in_app or picked
            return [
                {
                    "function": frame.get("function"),
                    "file": frame.get("filename"),
                    "line": frame.get("lineNo"),
                    "in_app": bool(frame.get("inApp")),
                    "context": frame.get("context")
                    and _clip(str(frame.get("context"))),
                }
                for frame in chosen[:MAX_FRAMES]
            ]
    return []


def _exception_summary(event: dict[str, Any]) -> dict[str, Any] | None:
    for entry in event.get("entries") or []:
        if not isinstance(entry, dict) or entry.get("type") != "exception":
            continue
        values = (entry.get("data") or {}).get("values") or []
        for value in values:
            if isinstance(value, dict):
                return {"type": value.get("type"), "value": _clip(value.get("value"))}
    return None


def _issue_view(issue: dict[str, Any]) -> dict[str, Any]:
    metadata = issue.get("metadata") or {}
    return {
        "id": issue.get("id"),
        "title": issue.get("title"),
        "culprit": issue.get("culprit"),
        "type": metadata.get("type") if isinstance(metadata, dict) else None,
        "value": _clip(metadata.get("value")) if isinstance(metadata, dict) else None,
        "status": issue.get("status"),
        "level": issue.get("level"),
        "event_count": issue.get("count"),
        "users_affected": issue.get("userCount"),
        "first_seen": issue.get("firstSeen"),
        "last_seen": issue.get("lastSeen"),
        "web_link": issue.get("permalink"),
    }


def _clip(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    return value[:MAX_BODY_CHARS]


def _list(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        _object(payload)
        return []
    if not isinstance(payload, list):
        raise VendorToolError(
            "vendor_response_invalid", "Sentry returned an unexpected response."
        )
    return [item for item in payload if isinstance(item, dict)]


def _object(payload: Any) -> dict[str, Any]:
    if payload is None:
        return {}
    if not isinstance(payload, dict):
        raise VendorToolError(
            "vendor_response_invalid", "Sentry returned a non-object response."
        )
    detail = payload.get("detail")
    if isinstance(detail, str) and "id" not in payload:
        raise VendorToolError("vendor_rejected", detail[:500])
    return payload


__all__ = ["get_issue", "ignore_issue", "list_issues", "resolve_issue"]
