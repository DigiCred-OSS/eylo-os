"""Curated Intercom tool implementations for the `integrations_v2` pipeline."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from eylo.modules.integrations_v2.domain.enums import ToolEffect

from ...contracts import VendorToolContext, VendorToolError
from ...registry import curated_tool
from .definition import vendor

MAX_BODY_CHARS = 6_000
MAX_PARTS = 50
# Part types that carry something a person said, as opposed to state changes.
_SPEECH = frozenset({"comment", "note"})


class FindContactInput(BaseModel):
    email: str = Field(min_length=1, description="Contact's email address.")


class SearchConversationsInput(BaseModel):
    contact_email: str | None = Field(
        default=None, description="Only this person's conversations."
    )
    state: str | None = Field(default=None, description="One of open, closed, snoozed.")
    limit: int = Field(default=20, ge=1, le=50)


class GetConversationInput(BaseModel):
    conversation_id: str = Field(min_length=1)


class ReplyToConversationInput(BaseModel):
    conversation_id: str = Field(min_length=1)
    body: str = Field(min_length=1, description="Reply text. HTML is accepted.")
    visible_to_customer: bool = Field(
        description=(
            "Required. True sends the reply to the customer; false leaves an "
            "internal note. There is no default because a message sent to a "
            "customer cannot be recalled."
        )
    )
    admin_id: str = Field(
        min_length=1, description="Id of the teammate the reply is sent as."
    )


class AddNoteInput(BaseModel):
    conversation_id: str = Field(min_length=1)
    body: str = Field(min_length=1)
    admin_id: str = Field(min_length=1, description="Teammate the note is from.")


@curated_tool(
    vendor=vendor.vendor,
    name="find_contact",
    display_name="Find Intercom Contact",
    description=(
        "Look a person up by email. Returns their Intercom id, name, when they "
        "were last seen, and their company — the id is what every other "
        "conversation lookup needs."
    ),
    input_model=FindContactInput,
    effect=ToolEffect.READ,
)
async def find_contact(
    payload: FindContactInput, ctx: VendorToolContext
) -> dict[str, Any]:
    contact = await _contact_by_email(ctx, payload.email)
    if contact is None:
        return {"found": False, "email": payload.email}
    view = _contact_view(contact)
    view["found"] = True
    return view


@curated_tool(
    vendor=vendor.vendor,
    name="search_conversations",
    display_name="Search Intercom Conversations",
    description=(
        "Find conversations, optionally only a given person's — name them by "
        "email and the contact lookup happens here. Each result reports its "
        "state, who it is assigned to, and when it was last updated."
    ),
    input_model=SearchConversationsInput,
    effect=ToolEffect.READ,
)
async def search_conversations(
    payload: SearchConversationsInput, ctx: VendorToolContext
) -> dict[str, Any]:
    filters: list[dict[str, Any]] = []
    if payload.contact_email:
        contact = await _contact_by_email(ctx, payload.contact_email)
        if contact is None:
            return {"conversations": [], "count": 0, "contact_found": False}
        filters.append(
            {"field": "contact_ids", "operator": "=", "value": contact.get("id")}
        )
    if payload.state:
        state = payload.state.strip().casefold()
        if state not in {"open", "closed", "snoozed"}:
            raise VendorToolError(
                "state_invalid", "state must be open, closed, or snoozed."
            )
        filters.append({"field": "state", "operator": "=", "value": state})
    if not filters:
        raise VendorToolError(
            "search_unbounded", "Give a contact email or a state to search by."
        )

    response = await ctx.read(
        "/conversations/search",
        method="POST",
        json={
            "query": (
                filters[0]
                if len(filters) == 1
                else {"operator": "AND", "value": filters}
            ),
            "pagination": {"per_page": payload.limit},
        },
    )
    body = _object(response.data)
    items = [c for c in body.get("conversations") or [] if isinstance(c, dict)]
    return {
        "conversations": [_conversation_view(item) for item in items],
        "count": len(items),
        "total_matches": body.get("total_count"),
    }


@curated_tool(
    vendor=vendor.vendor,
    name="get_conversation",
    display_name="Get Intercom Conversation",
    description=(
        "Read a conversation with its whole message history in order. "
        "Intercom stores the opening message separately from later replies and "
        "mixes state changes in with them; this returns just what was said, "
        "each message labelled by author and by whether the customer saw it."
    ),
    input_model=GetConversationInput,
    effect=ToolEffect.READ,
)
async def get_conversation(
    payload: GetConversationInput, ctx: VendorToolContext
) -> dict[str, Any]:
    conversation = _object(
        (
            await ctx.read(
                f"/conversations/{payload.conversation_id}",
                query={"display_as": "plaintext"},
            )
        ).data
    )
    view = _conversation_view(conversation)

    messages: list[dict[str, Any]] = []
    source = conversation.get("source")
    if isinstance(source, dict):
        messages.append(
            {
                "author": _author(source.get("author")),
                "body": _clip(source.get("body")),
                "visible_to_customer": True,
                "created_at": conversation.get("created_at"),
                "is_opening_message": True,
            }
        )

    parts = (conversation.get("conversation_parts") or {}).get("conversation_parts")
    for part in (parts or [])[:MAX_PARTS]:
        if not isinstance(part, dict):
            continue
        part_type = str(part.get("part_type", ""))
        if part_type not in _SPEECH:
            # Assignments, closes and opens are state, not conversation.
            continue
        messages.append(
            {
                "author": _author(part.get("author")),
                "body": _clip(part.get("body")),
                "visible_to_customer": part_type == "comment",
                "created_at": part.get("created_at"),
                "is_opening_message": False,
            }
        )

    view["messages"] = messages
    view["message_count"] = len(messages)
    return view


@curated_tool(
    vendor=vendor.vendor,
    name="reply_to_conversation",
    display_name="Reply to Intercom Conversation",
    description=(
        "Reply to a conversation as a teammate. Set visible_to_customer to "
        "true to send the message to the customer, or false to leave an "
        "internal note. The argument is required because the two are one field "
        "apart in the API and only one of them is recoverable."
    ),
    input_model=ReplyToConversationInput,
    effect=ToolEffect.MUTATION,
)
async def reply_to_conversation(
    payload: ReplyToConversationInput, ctx: VendorToolContext
) -> dict[str, Any]:
    return await _reply(
        ctx,
        conversation_id=payload.conversation_id,
        body=payload.body,
        admin_id=payload.admin_id,
        message_type="comment" if payload.visible_to_customer else "note",
    )


@curated_tool(
    vendor=vendor.vendor,
    name="add_note",
    display_name="Add Intercom Internal Note",
    description=(
        "Leave an internal note on a conversation. The customer never sees it. "
        "This is the safe way to record context; use reply_to_conversation "
        "when the customer should actually be answered."
    ),
    input_model=AddNoteInput,
    effect=ToolEffect.MUTATION,
)
async def add_note(payload: AddNoteInput, ctx: VendorToolContext) -> dict[str, Any]:
    return await _reply(
        ctx,
        conversation_id=payload.conversation_id,
        body=payload.body,
        admin_id=payload.admin_id,
        message_type="note",
    )


async def _reply(
    ctx: VendorToolContext,
    *,
    conversation_id: str,
    body: str,
    admin_id: str,
    message_type: str,
) -> dict[str, Any]:
    response = await ctx.mutate(
        f"/conversations/{conversation_id}/reply",
        json={
            "type": "admin",
            "admin_id": admin_id,
            "message_type": message_type,
            "body": body,
        },
    )
    replied = _object(response.data)
    return {
        "conversation_id": replied.get("id") or conversation_id,
        "message_type": message_type,
        "visible_to_customer": message_type == "comment",
        "state": replied.get("state"),
    }


async def _contact_by_email(
    ctx: VendorToolContext, email: str
) -> dict[str, Any] | None:
    response = await ctx.read(
        "/contacts/search",
        method="POST",
        json={
            "query": {"field": "email", "operator": "=", "value": email.strip()},
            "pagination": {"per_page": 1},
        },
    )
    results = _object(response.data).get("data") or []
    for item in results:
        if isinstance(item, dict):
            return item
    return None


def _contact_view(contact: dict[str, Any]) -> dict[str, Any]:
    companies = (contact.get("companies") or {}).get("data") or []
    return {
        "id": contact.get("id"),
        "name": contact.get("name"),
        "email": contact.get("email"),
        "phone": contact.get("phone"),
        "role": contact.get("role"),
        "last_seen_at": contact.get("last_seen_at"),
        "created_at": contact.get("created_at"),
        "company_count": len(companies),
    }


def _conversation_view(conversation: dict[str, Any]) -> dict[str, Any]:
    contacts = (conversation.get("contacts") or {}).get("contacts") or []
    return {
        "id": conversation.get("id"),
        "title": conversation.get("title"),
        "state": conversation.get("state"),
        "open": conversation.get("open"),
        "read": conversation.get("read"),
        "priority": conversation.get("priority"),
        "assignee_id": (conversation.get("admin_assignee_id")),
        "contact_ids": [c.get("id") for c in contacts if isinstance(c, dict)],
        "created_at": conversation.get("created_at"),
        "updated_at": conversation.get("updated_at"),
    }


def _author(author: Any) -> dict[str, Any] | None:
    if not isinstance(author, dict):
        return None
    return {
        "type": author.get("type"),
        "name": author.get("name"),
        "email": author.get("email"),
    }


def _clip(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    return value[:MAX_BODY_CHARS]


def _object(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise VendorToolError(
            "vendor_response_invalid", "Intercom returned a non-object response."
        )
    if payload.get("type") == "error.list":
        errors = payload.get("errors") or []
        first = errors[0] if errors and isinstance(errors[0], dict) else {}
        raise VendorToolError(
            "vendor_rejected",
            str(first.get("message", "Intercom rejected the request."))[:500],
        )
    return payload


__all__ = [
    "add_note",
    "find_contact",
    "get_conversation",
    "reply_to_conversation",
    "search_conversations",
]
