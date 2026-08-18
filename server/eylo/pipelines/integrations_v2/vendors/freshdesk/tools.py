"""Curated Freshdesk tool implementations for the `integrations_v2` pipeline."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from eylo.modules.integrations_v2.domain.enums import ToolEffect

from ...contracts import VendorToolContext, VendorToolError
from ...registry import curated_tool
from .definition import vendor

MAX_BODY_CHARS = 6_000

# Freshdesk's integer codes, which appear nowhere in its responses as words.
_STATUS_NAMES = {2: "open", 3: "pending", 4: "resolved", 5: "closed"}
_STATUS_CODES = {name: code for code, name in _STATUS_NAMES.items()}
_PRIORITY_NAMES = {1: "low", 2: "medium", 3: "high", 4: "urgent"}
_PRIORITY_CODES = {name: code for code, name in _PRIORITY_NAMES.items()}


class SearchTicketsInput(BaseModel):
    requester_email: str | None = Field(
        default=None, description="Only tickets raised by this person."
    )
    status: str | None = Field(
        default=None, description="open, pending, resolved, or closed."
    )
    priority: str | None = Field(
        default=None, description="low, medium, high, or urgent."
    )
    limit: int = Field(default=25, ge=1, le=100)


class GetTicketInput(BaseModel):
    ticket_id: int = Field(ge=1)
    include_conversation: bool = Field(default=True)


class CreateTicketInput(BaseModel):
    subject: str = Field(min_length=1)
    description: str = Field(min_length=1, description="Body; HTML is accepted.")
    requester_email: str = Field(min_length=1, description="Who the ticket is for.")
    priority: str = Field(default="medium", description="low, medium, high, urgent.")
    status: str = Field(default="open", description="open, pending, resolved, closed.")
    tags: list[str] | None = None


class ReplyInput(BaseModel):
    ticket_id: int = Field(ge=1)
    body: str = Field(min_length=1, description="Message text; HTML is accepted.")


class UpdateTicketInput(BaseModel):
    ticket_id: int = Field(ge=1)
    status: str | None = Field(
        default=None, description="open, pending, resolved, closed."
    )
    priority: str | None = Field(default=None, description="low, medium, high, urgent.")


@curated_tool(
    vendor=vendor.vendor,
    name="search_tickets",
    display_name="Search Freshdesk Tickets",
    description=(
        "Find tickets by requester, status, or priority, all given by name "
        "rather than by the integer codes Freshdesk stores. Results report "
        "status and priority as words."
    ),
    input_model=SearchTicketsInput,
    effect=ToolEffect.READ,
)
async def search_tickets(
    payload: SearchTicketsInput, ctx: VendorToolContext
) -> dict[str, Any]:
    clauses: list[str] = []
    if payload.status:
        clauses.append(f"status:{_code(payload.status, _STATUS_CODES, 'status')}")
    if payload.priority:
        clauses.append(
            f"priority:{_code(payload.priority, _PRIORITY_CODES, 'priority')}"
        )
    if payload.requester_email:
        clauses.append(f"email:'{payload.requester_email.strip()}'")

    if clauses:
        response = await ctx.read(
            "/search/tickets", query={"query": f'"{" AND ".join(clauses)}"'}
        )
        body = _object(response.data)
        tickets = [t for t in body.get("results") or [] if isinstance(t, dict)]
    else:
        response = await ctx.read("/tickets", query={"per_page": payload.limit})
        tickets = _list(response.data)

    tickets = tickets[: payload.limit]
    return {
        "tickets": [_ticket_view(ticket) for ticket in tickets],
        "count": len(tickets),
    }


@curated_tool(
    vendor=vendor.vendor,
    name="get_ticket",
    display_name="Get Freshdesk Ticket",
    description=(
        "Read one ticket together with its conversation. Each message says "
        "whether it was sent to the customer or kept as an internal note, "
        "which the raw payload only implies through two separate booleans."
    ),
    input_model=GetTicketInput,
    effect=ToolEffect.READ,
)
async def get_ticket(payload: GetTicketInput, ctx: VendorToolContext) -> dict[str, Any]:
    ticket = _object((await ctx.read(f"/tickets/{payload.ticket_id}")).data)
    view = _ticket_view(ticket)
    view["description"] = _clip(
        ticket.get("description_text") or ticket.get("description")
    )
    if payload.include_conversation:
        conversations = await ctx.read(
            f"/tickets/{payload.ticket_id}/conversations", query={"per_page": 30}
        )
        view["conversation"] = [
            {
                "body": _clip(item.get("body_text") or item.get("body")),
                "from": item.get("from_email"),
                "internal_note": bool(item.get("private")),
                "sent_to_customer": not bool(item.get("private")),
                "created_at": item.get("created_at"),
            }
            for item in _list(conversations.data)
        ]
    return view


@curated_tool(
    vendor=vendor.vendor,
    name="create_ticket",
    display_name="Create Freshdesk Ticket",
    description=(
        "Open a ticket on behalf of a customer given by email. Status and "
        "priority are given by name and converted to Freshdesk's codes here."
    ),
    input_model=CreateTicketInput,
    effect=ToolEffect.MUTATION,
)
async def create_ticket(
    payload: CreateTicketInput, ctx: VendorToolContext
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "subject": payload.subject,
        "description": payload.description,
        "email": payload.requester_email.strip(),
        "status": _code(payload.status, _STATUS_CODES, "status"),
        "priority": _code(payload.priority, _PRIORITY_CODES, "priority"),
    }
    if payload.tags:
        body["tags"] = payload.tags
    response = await ctx.mutate("/tickets", json=body)
    return _ticket_view(_object(response.data))


@curated_tool(
    vendor=vendor.vendor,
    name="reply_to_customer",
    display_name="Reply to Freshdesk Customer",
    description=(
        "Send a reply on a ticket. This is EMAILED TO THE CUSTOMER and cannot "
        "be unsent. To record something only colleagues should see, use "
        "add_private_note instead."
    ),
    input_model=ReplyInput,
    effect=ToolEffect.MUTATION,
)
async def reply_to_customer(
    payload: ReplyInput, ctx: VendorToolContext
) -> dict[str, Any]:
    response = await ctx.mutate(
        f"/tickets/{payload.ticket_id}/reply", json={"body": payload.body}
    )
    reply = _object(response.data)
    return {
        "ticket_id": payload.ticket_id,
        "conversation_id": reply.get("id"),
        "sent_to_customer": True,
        "created_at": reply.get("created_at"),
    }


@curated_tool(
    vendor=vendor.vendor,
    name="add_private_note",
    display_name="Add Freshdesk Private Note",
    description=(
        "Add an internal note to a ticket. This is NOT sent to the customer "
        "and is visible only to agents. To message the customer, use "
        "reply_to_customer instead."
    ),
    input_model=ReplyInput,
    effect=ToolEffect.MUTATION,
)
async def add_private_note(
    payload: ReplyInput, ctx: VendorToolContext
) -> dict[str, Any]:
    response = await ctx.mutate(
        f"/tickets/{payload.ticket_id}/notes",
        json={"body": payload.body, "private": True},
    )
    note = _object(response.data)
    return {
        "ticket_id": payload.ticket_id,
        "conversation_id": note.get("id"),
        "sent_to_customer": False,
        "created_at": note.get("created_at"),
    }


@curated_tool(
    vendor=vendor.vendor,
    name="update_ticket",
    display_name="Update Freshdesk Ticket",
    description=(
        "Change a ticket's status or priority, given by name. Resolving or "
        "closing a ticket may trigger Freshdesk's own satisfaction survey to "
        "the customer, depending on how the account is configured."
    ),
    input_model=UpdateTicketInput,
    effect=ToolEffect.MUTATION,
)
async def update_ticket(
    payload: UpdateTicketInput, ctx: VendorToolContext
) -> dict[str, Any]:
    body: dict[str, Any] = {}
    if payload.status:
        body["status"] = _code(payload.status, _STATUS_CODES, "status")
    if payload.priority:
        body["priority"] = _code(payload.priority, _PRIORITY_CODES, "priority")
    if not body:
        raise VendorToolError(
            "no_change_requested", "Give a status or a priority to change."
        )
    response = await ctx.mutate(
        f"/tickets/{payload.ticket_id}", method="PUT", json=body
    )
    return _ticket_view(_object(response.data))


def _code(value: str, table: dict[str, int], label: str) -> int:
    """Turn a human word into the integer Freshdesk stores."""
    name = value.strip().casefold()
    if name not in table:
        raise VendorToolError(
            f"{label}_invalid",
            f"{label} must be one of: {', '.join(sorted(table))}.",
        )
    return table[name]


def _ticket_view(ticket: dict[str, Any]) -> dict[str, Any]:
    status = ticket.get("status")
    priority = ticket.get("priority")
    return {
        "id": ticket.get("id"),
        "subject": ticket.get("subject"),
        "status": _STATUS_NAMES.get(status, status),
        "priority": _PRIORITY_NAMES.get(priority, priority),
        "requester_email": ticket.get("requester_id") and ticket.get("email"),
        "tags": ticket.get("tags") or [],
        "type": ticket.get("type"),
        "due_by": ticket.get("due_by"),
        "created_at": ticket.get("created_at"),
        "updated_at": ticket.get("updated_at"),
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
            "vendor_response_invalid", "Freshdesk returned an unexpected response."
        )
    return [item for item in payload if isinstance(item, dict)]


def _object(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise VendorToolError(
            "vendor_response_invalid", "Freshdesk returned a non-object response."
        )
    errors = payload.get("errors")
    if isinstance(errors, list) and errors:
        first = errors[0] if isinstance(errors[0], dict) else {}
        detail = first.get("message") or payload.get("description") or "rejected"
        raise VendorToolError("vendor_rejected", str(detail)[:500])
    return payload


__all__ = [
    "add_private_note",
    "create_ticket",
    "get_ticket",
    "reply_to_customer",
    "search_tickets",
    "update_ticket",
]
