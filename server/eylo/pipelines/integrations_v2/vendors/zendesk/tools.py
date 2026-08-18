"""Curated Zendesk tool implementations for the `integrations_v2` pipeline."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from eylo.modules.integrations_v2.domain.enums import ToolEffect

from ...contracts import VendorToolContext, VendorToolError
from ...registry import curated_tool
from .definition import vendor

MAX_BODY_CHARS = 6_000
MAX_COMMENTS = 30
_STATUSES = ("new", "open", "pending", "hold", "solved", "closed")
_PRIORITIES = ("low", "normal", "high", "urgent")


class SearchTicketsInput(BaseModel):
    text: str | None = Field(default=None, description="Free text to match.")
    status: str | None = Field(
        default=None,
        description="One of new, open, pending, hold, solved, closed.",
    )
    requester_email: str | None = Field(
        default=None, description="Person who raised the ticket."
    )
    assignee_email: str | None = Field(
        default=None, description="Agent the ticket is assigned to."
    )
    tags: list[str] | None = None
    limit: int = Field(default=25, ge=1, le=100)


class GetTicketInput(BaseModel):
    ticket_id: int = Field(ge=1)
    include_comments: bool = Field(default=True)


class CreateTicketInput(BaseModel):
    subject: str = Field(min_length=1)
    description: str = Field(min_length=1, description="The first comment's body.")
    requester_email: str | None = Field(
        default=None,
        description="Person the ticket is for. Created in Zendesk if unknown.",
    )
    requester_name: str | None = Field(
        default=None, description="Used only when creating a new requester."
    )
    priority: str | None = Field(default=None, description="low, normal, high, urgent.")
    tags: list[str] | None = None


class AddCommentInput(BaseModel):
    ticket_id: int = Field(ge=1)
    body: str = Field(min_length=1)
    public: bool = Field(
        description=(
            "Required. True emails the comment to the customer; false leaves "
            "an internal note only other agents can see. There is no default "
            "because the difference is not recoverable."
        )
    )


class UpdateTicketInput(BaseModel):
    ticket_id: int = Field(ge=1)
    status: str | None = Field(
        default=None, description="new, open, pending, hold, solved, closed."
    )
    priority: str | None = Field(default=None, description="low, normal, high, urgent.")
    assignee_email: str | None = Field(default=None, description="Agent to assign to.")
    tags: list[str] | None = Field(default=None, description="Replaces existing tags.")


class FindUserInput(BaseModel):
    email: str = Field(min_length=1)


@curated_tool(
    vendor=vendor.vendor,
    name="search_tickets",
    display_name="Search Zendesk Tickets",
    description=(
        "Find tickets by status, requester, assignee, tag, or free text, "
        "without writing Zendesk's search syntax. People are named by email "
        "and resolved here. Results carry subject, status, priority, and "
        "requester."
    ),
    input_model=SearchTicketsInput,
    effect=ToolEffect.READ,
)
async def search_tickets(
    payload: SearchTicketsInput, ctx: VendorToolContext
) -> dict[str, Any]:
    terms = ["type:ticket"]
    if payload.status:
        terms.append(f"status:{_one_of(payload.status, _STATUSES, 'status')}")
    if payload.requester_email:
        terms.append(f"requester:{payload.requester_email}")
    if payload.assignee_email:
        terms.append(f"assignee:{payload.assignee_email}")
    for tag in payload.tags or []:
        terms.append(f"tags:{tag}")
    if payload.text:
        terms.append(payload.text)

    query = " ".join(terms)
    response = await ctx.read(
        "/search.json", query={"query": query, "per_page": payload.limit}
    )
    body = _object(response.data)
    results = [item for item in body.get("results") or [] if isinstance(item, dict)]
    return {
        "tickets": [_ticket_view(item) for item in results],
        "count": len(results),
        "total_matches": body.get("count"),
        "query": query,
    }


@curated_tool(
    vendor=vendor.vendor,
    name="get_ticket",
    display_name="Get Zendesk Ticket",
    description=(
        "Read one ticket together with its full conversation. Each comment "
        "reports whether it was public — visible to the customer — or an "
        "internal note, which is what tells you what the customer has actually "
        "been told."
    ),
    input_model=GetTicketInput,
    effect=ToolEffect.READ,
)
async def get_ticket(payload: GetTicketInput, ctx: VendorToolContext) -> dict[str, Any]:
    ticket = _object((await ctx.read(f"/tickets/{payload.ticket_id}.json")).data).get(
        "ticket"
    )
    if not isinstance(ticket, dict):
        raise VendorToolError("ticket_not_found", "That ticket does not exist.")
    view = _ticket_view(ticket)
    view["description"] = _clip(ticket.get("description"))

    if payload.include_comments:
        response = await ctx.read(
            f"/tickets/{payload.ticket_id}/comments.json",
            query={"per_page": MAX_COMMENTS},
        )
        comments = _object(response.data).get("comments") or []
        view["comments"] = [
            {
                "id": comment.get("id"),
                "author_id": comment.get("author_id"),
                "body": _clip(comment.get("plain_body") or comment.get("body")),
                "public": comment.get("public"),
                "created_at": comment.get("created_at"),
            }
            for comment in comments
            if isinstance(comment, dict)
        ]
    return view


@curated_tool(
    vendor=vendor.vendor,
    name="create_ticket",
    display_name="Create Zendesk Ticket",
    description=(
        "Raise a ticket. The requester is given by email and is created in "
        "Zendesk if not already known, so a person's numeric id never has to "
        "be looked up first."
    ),
    input_model=CreateTicketInput,
    effect=ToolEffect.MUTATION,
)
async def create_ticket(
    payload: CreateTicketInput, ctx: VendorToolContext
) -> dict[str, Any]:
    ticket: dict[str, Any] = {
        "subject": payload.subject,
        "comment": {"body": payload.description},
    }
    if payload.requester_email:
        # Zendesk creates or links the requester from this object, which is
        # why no separate user lookup is needed.
        requester: dict[str, Any] = {"email": payload.requester_email}
        if payload.requester_name:
            requester["name"] = payload.requester_name
        ticket["requester"] = requester
    if payload.priority:
        ticket["priority"] = _one_of(payload.priority, _PRIORITIES, "priority")
    if payload.tags:
        ticket["tags"] = payload.tags

    response = await ctx.mutate("/tickets.json", json={"ticket": ticket})
    created = _object(response.data).get("ticket")
    if not isinstance(created, dict):
        raise VendorToolError(
            "vendor_response_invalid", "Zendesk did not return the new ticket."
        )
    return _ticket_view(created)


@curated_tool(
    vendor=vendor.vendor,
    name="add_comment",
    display_name="Comment on Zendesk Ticket",
    description=(
        "Add a comment to a ticket. Set public to true to reply to the "
        "customer — Zendesk emails them — or false to leave an internal note "
        "only agents can see. This argument is required precisely because "
        "sending a note to a customer by accident cannot be undone."
    ),
    input_model=AddCommentInput,
    effect=ToolEffect.MUTATION,
)
async def add_comment(
    payload: AddCommentInput, ctx: VendorToolContext
) -> dict[str, Any]:
    response = await ctx.mutate(
        f"/tickets/{payload.ticket_id}.json",
        method="PUT",
        json={"ticket": {"comment": {"body": payload.body, "public": payload.public}}},
    )
    updated = _object(response.data).get("ticket") or {}
    return {
        "ticket_id": payload.ticket_id,
        "public": payload.public,
        "emailed_customer": payload.public,
        "status": updated.get("status") if isinstance(updated, dict) else None,
    }


@curated_tool(
    vendor=vendor.vendor,
    name="update_ticket",
    display_name="Update Zendesk Ticket",
    description=(
        "Change a ticket's status, priority, assignee, or tags. The assignee "
        "is given by email and resolved here. Anything omitted is left alone, "
        "except tags, which replace what was there."
    ),
    input_model=UpdateTicketInput,
    effect=ToolEffect.MUTATION,
)
async def update_ticket(
    payload: UpdateTicketInput, ctx: VendorToolContext
) -> dict[str, Any]:
    ticket: dict[str, Any] = {}
    if payload.status:
        ticket["status"] = _one_of(payload.status, _STATUSES, "status")
    if payload.priority:
        ticket["priority"] = _one_of(payload.priority, _PRIORITIES, "priority")
    if payload.tags is not None:
        ticket["tags"] = payload.tags
    if payload.assignee_email:
        user = await _user_by_email(ctx, payload.assignee_email)
        if user is None:
            raise VendorToolError(
                "assignee_not_found",
                f"No Zendesk user with email '{payload.assignee_email}'.",
            )
        ticket["assignee_id"] = user.get("id")
    if not ticket:
        raise VendorToolError(
            "no_change_requested", "Give at least one field to change."
        )

    response = await ctx.mutate(
        f"/tickets/{payload.ticket_id}.json", method="PUT", json={"ticket": ticket}
    )
    updated = _object(response.data).get("ticket")
    if not isinstance(updated, dict):
        raise VendorToolError(
            "vendor_response_invalid", "Zendesk did not return the updated ticket."
        )
    return _ticket_view(updated)


@curated_tool(
    vendor=vendor.vendor,
    name="find_user",
    display_name="Find Zendesk User",
    description=(
        "Look up a person by email, returning their id, name, role, and "
        "whether they are suspended. Other tools accept an email directly, so "
        "this is mainly for confirming who someone is."
    ),
    input_model=FindUserInput,
    effect=ToolEffect.READ,
)
async def find_user(payload: FindUserInput, ctx: VendorToolContext) -> dict[str, Any]:
    user = await _user_by_email(ctx, payload.email)
    if user is None:
        return {"found": False, "email": payload.email}
    return {
        "found": True,
        "id": user.get("id"),
        "name": user.get("name"),
        "email": user.get("email"),
        "role": user.get("role"),
        "suspended": user.get("suspended"),
        "created_at": user.get("created_at"),
    }


async def _user_by_email(ctx: VendorToolContext, email: str) -> dict[str, Any] | None:
    response = await ctx.read("/users/search.json", query={"query": email})
    users = _object(response.data).get("users") or []
    for user in users:
        if isinstance(user, dict) and str(user.get("email", "")).casefold() == (
            email.strip().casefold()
        ):
            return user
    return None


def _one_of(value: str, allowed: tuple[str, ...], field: str) -> str:
    candidate = value.strip().casefold()
    if candidate not in allowed:
        raise VendorToolError(
            f"{field}_invalid", f"{field} must be one of: {', '.join(allowed)}."
        )
    return candidate


def _ticket_view(ticket: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": ticket.get("id"),
        "subject": ticket.get("subject"),
        "status": ticket.get("status"),
        "priority": ticket.get("priority"),
        "requester_id": ticket.get("requester_id"),
        "assignee_id": ticket.get("assignee_id"),
        "tags": ticket.get("tags") or [],
        "created_at": ticket.get("created_at"),
        "updated_at": ticket.get("updated_at"),
        "via": (ticket.get("via") or {}).get("channel"),
    }


def _clip(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    return value[:MAX_BODY_CHARS]


def _object(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise VendorToolError(
            "vendor_response_invalid", "Zendesk returned a non-object response."
        )
    error = payload.get("error")
    if error is not None:
        detail = payload.get("description") or payload.get("details") or error
        raise VendorToolError("vendor_rejected", str(detail)[:500])
    return payload


__all__ = [
    "add_comment",
    "create_ticket",
    "find_user",
    "get_ticket",
    "search_tickets",
    "update_ticket",
]
