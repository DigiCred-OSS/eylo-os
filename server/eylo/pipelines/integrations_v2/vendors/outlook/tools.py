"""Curated Outlook tools over Microsoft Graph.

Graph's mail shapes are nested three deep — a recipient is
`{"emailAddress": {"address": "a@b.com"}}` — and a body carries an explicit
content type. `send_message` and `reply_to_message` take plain addresses and
plain text and build that themselves, which is ceremony no agent should spend
tokens reproducing and frequently gets wrong.

Reading goes the other way: `search_messages` and `get_message` flatten the
nesting back into flat fields and convert HTML bodies to text.
"""

from __future__ import annotations

import html
import re
from typing import Any

from pydantic import BaseModel, Field

from eylo.modules.integrations_v2.domain.enums import ToolEffect

from ...contracts import VendorToolContext, VendorToolError
from ...registry import curated_tool
from .definition import MAIL_READ, MAIL_SEND, vendor

_TAG = re.compile(r"<[^>]+>")
_MESSAGE_FIELDS = (
    "id,subject,from,toRecipients,ccRecipients,receivedDateTime,"
    "isRead,hasAttachments,conversationId,webLink,bodyPreview"
)


class SearchMessagesInput(BaseModel):
    query: str | None = Field(
        default=None, description="Free text searched across the mailbox."
    )
    from_address: str | None = Field(
        default=None, description="Only messages from this sender."
    )
    unread_only: bool = Field(default=False, description="Restrict to unread messages.")
    limit: int = Field(default=25, ge=1, le=100)


class GetMessageInput(BaseModel):
    message_id: str = Field(min_length=1, description="Graph message id.")


class SendMessageInput(BaseModel):
    to: list[str] = Field(min_length=1, description="Recipient email addresses.")
    subject: str = Field(min_length=1, description="Message subject.")
    body: str = Field(min_length=1, description="Message body as plain text.")
    cc: list[str] | None = Field(default=None, description="Copy these addresses.")
    save_to_sent_items: bool = Field(default=True)


class ReplyToMessageInput(BaseModel):
    message_id: str = Field(min_length=1, description="Message to reply to.")
    body: str = Field(min_length=1, description="Reply text as plain text.")
    reply_all: bool = Field(
        default=False,
        description="Reply to every recipient rather than only the sender.",
    )


@curated_tool(
    vendor=vendor.vendor,
    name="search_messages",
    display_name="Search Outlook Messages",
    description=(
        "Search the mailbox by free text, sender, or unread state. Returns "
        "sender, recipients, and a preview already flattened, so a follow-up "
        "fetch is only needed for the full body."
    ),
    input_model=SearchMessagesInput,
    effect=ToolEffect.READ,
    scopes=(MAIL_READ,),
)
async def search_messages(
    payload: SearchMessagesInput, ctx: VendorToolContext
) -> dict[str, Any]:
    query: dict[str, Any] = {"$top": payload.limit, "$select": _MESSAGE_FIELDS}
    filters: list[str] = []
    if payload.from_address:
        filters.append(f"from/emailAddress/address eq '{_odata(payload.from_address)}'")
    if payload.unread_only:
        filters.append("isRead eq false")
    if payload.query:
        # Graph rejects $search combined with $orderby, and $filter with
        # $search only on some shapes; search wins when both are supplied.
        query["$search"] = f'"{_odata(payload.query)}"'
    else:
        query["$orderby"] = "receivedDateTime desc"
    if filters and "$search" not in query:
        query["$filter"] = " and ".join(filters)

    response = await ctx.read("/me/messages", query=query)
    items = _values(response.data)
    return {
        "messages": [_message_view(item) for item in items],
        "count": len(items),
    }


@curated_tool(
    vendor=vendor.vendor,
    name="get_message",
    display_name="Get Outlook Message",
    description=(
        "Read one message in full, with the body converted from HTML to plain "
        "text so it can be quoted directly."
    ),
    input_model=GetMessageInput,
    effect=ToolEffect.READ,
    scopes=(MAIL_READ,),
)
async def get_message(
    payload: GetMessageInput, ctx: VendorToolContext
) -> dict[str, Any]:
    response = await ctx.read(f"/me/messages/{payload.message_id}")
    message = _object(response.data)
    view = _message_view(message)
    body = message.get("body") or {}
    view["body"] = _plain_text(body.get("content"))
    return view


@curated_tool(
    vendor=vendor.vendor,
    name="send_message",
    display_name="Send Outlook Message",
    description=(
        "Send an email. Recipients are given as plain address strings and the "
        "body as plain text; the nested Graph message envelope is built here."
    ),
    input_model=SendMessageInput,
    effect=ToolEffect.MUTATION,
    scopes=(MAIL_SEND,),
)
async def send_message(
    payload: SendMessageInput, ctx: VendorToolContext
) -> dict[str, Any]:
    message: dict[str, Any] = {
        "subject": payload.subject,
        "body": {"contentType": "Text", "content": payload.body},
        "toRecipients": _recipients(payload.to),
    }
    if payload.cc:
        message["ccRecipients"] = _recipients(payload.cc)
    await ctx.mutate(
        "/me/sendMail",
        method="POST",
        json={"message": message, "saveToSentItems": payload.save_to_sent_items},
    )
    # Graph answers sendMail with 202 and an empty body; there is no id to
    # return, so report what was actually accepted rather than inventing one.
    return {
        "sent": True,
        "subject": payload.subject,
        "to": payload.to,
        "cc": payload.cc or [],
    }


@curated_tool(
    vendor=vendor.vendor,
    name="reply_to_message",
    display_name="Reply To Outlook Message",
    description=(
        "Reply to a message, optionally to everyone on it. Quoting and "
        "threading are handled by Outlook, so only the new text is needed."
    ),
    input_model=ReplyToMessageInput,
    effect=ToolEffect.MUTATION,
    scopes=(MAIL_SEND, MAIL_READ),
)
async def reply_to_message(
    payload: ReplyToMessageInput, ctx: VendorToolContext
) -> dict[str, Any]:
    action = "replyAll" if payload.reply_all else "reply"
    await ctx.mutate(
        f"/me/messages/{payload.message_id}/{action}",
        method="POST",
        json={"comment": payload.body},
    )
    return {
        "replied": True,
        "message_id": payload.message_id,
        "reply_all": payload.reply_all,
    }


def _recipients(addresses: list[str]) -> list[dict[str, Any]]:
    """Build Graph's nested recipient shape from plain addresses."""
    return [
        {"emailAddress": {"address": address.strip()}}
        for address in addresses
        if address and address.strip()
    ]


def _address(entry: Any) -> str | None:
    if not isinstance(entry, dict):
        return None
    mail = entry.get("emailAddress")
    return mail.get("address") if isinstance(mail, dict) else None


def _message_view(message: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": message.get("id"),
        "subject": message.get("subject"),
        "from": _address(message.get("from")),
        "to": [a for a in map(_address, message.get("toRecipients") or []) if a],
        "cc": [a for a in map(_address, message.get("ccRecipients") or []) if a],
        "received_at": message.get("receivedDateTime"),
        "is_read": message.get("isRead"),
        "has_attachments": message.get("hasAttachments"),
        "conversation_id": message.get("conversationId"),
        "preview": message.get("bodyPreview"),
        "web_link": message.get("webLink"),
    }


def _plain_text(content: Any) -> str | None:
    if not isinstance(content, str):
        return None
    stripped = _TAG.sub(" ", content)
    return re.sub(r"\s+", " ", html.unescape(stripped)).strip() or None


def _odata(value: str) -> str:
    """Escape a value for an OData literal; a bare quote would break the query."""
    return value.replace("'", "''")


def _values(payload: Any) -> list[dict[str, Any]]:
    body = _object(payload)
    return [item for item in body.get("value", []) or [] if isinstance(item, dict)]


def _object(payload: Any) -> dict[str, Any]:
    if payload is None:
        return {}
    if not isinstance(payload, dict):
        raise VendorToolError(
            "vendor_response_invalid", "Microsoft Graph returned a non-object response."
        )
    error = payload.get("error")
    if isinstance(error, dict):
        raise VendorToolError(
            "vendor_rejected",
            str(error.get("message", "Microsoft Graph rejected the request."))[:500],
        )
    return payload


__all__ = [
    "get_message",
    "reply_to_message",
    "search_messages",
    "send_message",
]
