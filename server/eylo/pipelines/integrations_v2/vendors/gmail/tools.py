"""Curated Gmail tool implementations for the `integrations_v2` pipeline."""

from __future__ import annotations

import base64
from email.message import EmailMessage
from email.utils import getaddresses
from typing import Any

from pydantic import BaseModel, Field

from eylo.modules.integrations_v2.domain.enums import ToolEffect

from ...contracts import VendorToolContext, VendorToolError
from ...registry import curated_tool
from .definition import GMAIL_COMPOSE, GMAIL_MODIFY, GMAIL_SEND, vendor

ME = "users/me"
MAX_BODY_CHARS = 8_000
_METADATA_HEADERS = ("From", "To", "Cc", "Subject", "Date")

# Gmail's built-in labels. They are addressed by these exact ids, and unlike
# user labels they never appear under a different name.
_SYSTEM_LABELS = frozenset(
    {
        "CHAT",
        "DRAFT",
        "IMPORTANT",
        "INBOX",
        "SENT",
        "SPAM",
        "STARRED",
        "TRASH",
        "UNREAD",
        "CATEGORY_PERSONAL",
        "CATEGORY_SOCIAL",
        "CATEGORY_PROMOTIONS",
        "CATEGORY_UPDATES",
        "CATEGORY_FORUMS",
    }
)


class SearchMessagesInput(BaseModel):
    query: str | None = Field(
        default=None,
        description=(
            "Gmail search expression, e.g. 'from:ana@acme.com is:unread' or "
            "'subject:invoice after:2026/07/01'. Omit to list recent mail."
        ),
    )
    limit: int = Field(
        default=10,
        ge=1,
        le=25,
        description="How many messages to return. Each one costs a lookup.",
    )
    include_spam_trash: bool = Field(default=False)


class ReadMessageInput(BaseModel):
    message_id: str = Field(min_length=1)


class ReadThreadInput(BaseModel):
    thread_id: str = Field(
        min_length=1,
        description="Thread id. Every message result carries the one it belongs to.",
    )
    max_messages: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Return at most this many of the most recent messages.",
    )


class SendMessageInput(BaseModel):
    to: list[str] = Field(min_length=1, description="Recipient email addresses.")
    subject: str = Field(min_length=1)
    body: str = Field(description="Plain text body.")
    cc: list[str] | None = None
    bcc: list[str] | None = None
    html_body: str | None = Field(
        default=None,
        description="Optional HTML alternative. Clients that can render it prefer it.",
    )


class ReplyToThreadInput(BaseModel):
    thread_id: str = Field(min_length=1)
    body: str = Field(description="Plain text reply body.")
    reply_all: bool = Field(
        default=False,
        description=(
            "Also copy everyone the last message reached, excluding this "
            "account. Defaults to replying to the sender alone."
        ),
    )
    html_body: str | None = None


class CreateDraftInput(BaseModel):
    to: list[str] = Field(min_length=1)
    subject: str = Field(min_length=1)
    body: str
    cc: list[str] | None = None
    thread_id: str | None = Field(
        default=None, description="Attach the draft to an existing thread."
    )


class ModifyLabelsInput(BaseModel):
    message_id: str = Field(min_length=1)
    add: list[str] | None = Field(
        default=None,
        description=(
            "Label names or ids to apply. Use STARRED to star, IMPORTANT to "
            "flag, or any user label by its name."
        ),
    )
    remove: list[str] | None = Field(
        default=None,
        description=(
            "Label names or ids to strip. Remove UNREAD to mark as read, or "
            "INBOX to archive."
        ),
    )
    create_missing: bool = Field(
        default=False,
        description="Create any label in 'add' that does not exist yet.",
    )


class TrashMessageInput(BaseModel):
    message_id: str = Field(min_length=1)


@curated_tool(
    vendor=vendor.vendor,
    name="search_messages",
    display_name="Search Gmail",
    description=(
        "Search the mailbox using Gmail's own query syntax and return matching "
        "messages with sender, recipients, subject, date, and snippet already "
        "extracted from their headers. Operators such as from:, to:, subject:, "
        "is:unread, has:attachment, before: and after: all work."
    ),
    input_model=SearchMessagesInput,
    effect=ToolEffect.READ,
    scopes=(GMAIL_MODIFY,),
)
async def search_messages(
    payload: SearchMessagesInput, ctx: VendorToolContext
) -> dict[str, Any]:
    query: dict[str, Any] = {
        "maxResults": payload.limit,
        "includeSpamTrash": payload.include_spam_trash,
    }
    if payload.query:
        query["q"] = payload.query
    listing = _object((await ctx.read(f"/{ME}/messages", query=query)).data)
    stubs = [
        item for item in listing.get("messages", []) or [] if isinstance(item, dict)
    ]

    # The list endpoint returns ids only, so each message costs one lookup.
    # `limit` is capped low for exactly this reason.
    messages = []
    for stub in stubs:
        message_id = stub.get("id")
        if not message_id:
            continue
        detail = _object(
            (
                await ctx.read(
                    f"/{ME}/messages/{message_id}",
                    query={
                        "format": "metadata",
                        "metadataHeaders": list(_METADATA_HEADERS),
                    },
                )
            ).data
        )
        messages.append(_message_view(detail, include_body=False))
    return {"messages": messages, "count": len(messages)}


@curated_tool(
    vendor=vendor.vendor,
    name="read_message",
    display_name="Read Gmail Message",
    description=(
        "Read one message in full. The body is decoded from its MIME parts and "
        "returned as plain text, with attachment names and sizes listed "
        "separately. Very long bodies are truncated and marked as such."
    ),
    input_model=ReadMessageInput,
    effect=ToolEffect.READ,
    scopes=(GMAIL_MODIFY,),
)
async def read_message(
    payload: ReadMessageInput, ctx: VendorToolContext
) -> dict[str, Any]:
    detail = _object(
        (
            await ctx.read(
                f"/{ME}/messages/{payload.message_id}", query={"format": "full"}
            )
        ).data
    )
    return _message_view(detail, include_body=True)


@curated_tool(
    vendor=vendor.vendor,
    name="read_thread",
    display_name="Read Gmail Thread",
    description=(
        "Read a whole conversation in order, with every message's body decoded. "
        "This is the tool to reach for before replying: one call returns the "
        "context that would otherwise take one lookup per message."
    ),
    input_model=ReadThreadInput,
    effect=ToolEffect.READ,
    scopes=(GMAIL_MODIFY,),
)
async def read_thread(
    payload: ReadThreadInput, ctx: VendorToolContext
) -> dict[str, Any]:
    thread = await _thread(ctx, payload.thread_id)
    messages = _thread_messages(thread)
    recent = messages[-payload.max_messages :]
    return {
        "thread_id": payload.thread_id,
        "messages": [_message_view(item, include_body=True) for item in recent],
        "count": len(recent),
        "total_in_thread": len(messages),
    }


@curated_tool(
    vendor=vendor.vendor,
    name="send_message",
    display_name="Send Gmail Message",
    description=(
        "Send a new email. Recipients and body are given as plain values; the "
        "compliant MIME message and its encoding are built here, so no message "
        "source has to be assembled. Use reply_to_thread instead when "
        "responding to existing mail, so the reply threads correctly."
    ),
    input_model=SendMessageInput,
    effect=ToolEffect.MUTATION,
    scopes=(GMAIL_SEND,),
)
async def send_message(
    payload: SendMessageInput, ctx: VendorToolContext
) -> dict[str, Any]:
    raw = _build_mime(
        to=payload.to,
        subject=payload.subject,
        body=payload.body,
        cc=payload.cc,
        bcc=payload.bcc,
        html_body=payload.html_body,
    )
    response = await ctx.mutate(f"/{ME}/messages/send", json={"raw": raw})
    return _sent_view(_object(response.data))


@curated_tool(
    vendor=vendor.vendor,
    name="reply_to_thread",
    display_name="Reply to Gmail Thread",
    description=(
        "Reply to an existing conversation. Reads the thread, addresses the "
        "reply to the last sender, carries the Message-ID, In-Reply-To and "
        "References headers across, and prefixes the subject with Re: so mail "
        "clients file it under the same conversation. Set reply_all to copy "
        "everyone the last message reached."
    ),
    input_model=ReplyToThreadInput,
    effect=ToolEffect.MUTATION,
    scopes=(GMAIL_SEND, GMAIL_MODIFY),
)
async def reply_to_thread(
    payload: ReplyToThreadInput, ctx: VendorToolContext
) -> dict[str, Any]:
    thread = await _thread(ctx, payload.thread_id)
    messages = _thread_messages(thread)
    if not messages:
        raise VendorToolError("thread_empty", "That thread contains no messages.")

    last = messages[-1]
    headers = _headers(last)
    sender = headers.get("reply-to") or headers.get("from")
    if not sender:
        raise VendorToolError(
            "reply_target_unknown",
            "The last message in this thread has no sender to reply to.",
        )

    to = [sender]
    cc: list[str] = []
    if payload.reply_all:
        # Everyone the last message reached, minus this account and the person
        # already in To — otherwise the reply copies the sender twice.
        me = await _account_address(ctx)
        already = {_address(sender)} | ({me} if me else set())
        for candidate in _addresses(headers.get("to"), headers.get("cc")):
            if candidate and candidate not in already:
                already.add(candidate)
                cc.append(candidate)

    raw = _build_mime(
        to=to,
        subject=_reply_subject(headers.get("subject")),
        body=payload.body,
        cc=cc or None,
        html_body=payload.html_body,
        in_reply_to=headers.get("message-id"),
        references=_references(headers),
    )
    response = await ctx.mutate(
        f"/{ME}/messages/send", json={"raw": raw, "threadId": payload.thread_id}
    )
    view = _sent_view(_object(response.data))
    view["replied_to"] = sender
    view["copied"] = cc
    return view


@curated_tool(
    vendor=vendor.vendor,
    name="create_draft",
    display_name="Create Gmail Draft",
    description=(
        "Compose a message and leave it in Drafts without sending it. Useful "
        "when a person should review the wording first. Give a thread_id to "
        "attach the draft to an existing conversation."
    ),
    input_model=CreateDraftInput,
    effect=ToolEffect.MUTATION,
    scopes=(GMAIL_COMPOSE,),
)
async def create_draft(
    payload: CreateDraftInput, ctx: VendorToolContext
) -> dict[str, Any]:
    raw = _build_mime(
        to=payload.to, subject=payload.subject, body=payload.body, cc=payload.cc
    )
    message: dict[str, Any] = {"raw": raw}
    if payload.thread_id:
        message["threadId"] = payload.thread_id
    response = await ctx.mutate(f"/{ME}/drafts", json={"message": message})
    draft = _object(response.data)
    return {
        "draft_id": draft.get("id"),
        "message_id": (draft.get("message") or {}).get("id"),
        "thread_id": (draft.get("message") or {}).get("threadId"),
        "sent": False,
    }


@curated_tool(
    vendor=vendor.vendor,
    name="modify_labels",
    display_name="Change Gmail Labels",
    description=(
        "Apply and remove labels on a message by name, resolving names to ids "
        "here. This is how mail is filed: remove UNREAD to mark as read, "
        "remove INBOX to archive, add STARRED to star, or add any user label. "
        "If a name does not exist the error lists the labels that do."
    ),
    input_model=ModifyLabelsInput,
    effect=ToolEffect.MUTATION,
    scopes=(GMAIL_MODIFY,),
)
async def modify_labels(
    payload: ModifyLabelsInput, ctx: VendorToolContext
) -> dict[str, Any]:
    if not payload.add and not payload.remove:
        raise VendorToolError(
            "no_change_requested", "Give at least one label to add or remove."
        )
    add_ids = await _resolve_labels(
        ctx, payload.add, create_missing=payload.create_missing
    )
    remove_ids = await _resolve_labels(ctx, payload.remove, create_missing=False)
    response = await ctx.mutate(
        f"/{ME}/messages/{payload.message_id}/modify",
        json={"addLabelIds": add_ids, "removeLabelIds": remove_ids},
    )
    updated = _object(response.data)
    return {
        "message_id": updated.get("id"),
        "thread_id": updated.get("threadId"),
        "labels": updated.get("labelIds") or [],
    }


@curated_tool(
    vendor=vendor.vendor,
    name="trash_message",
    display_name="Move Gmail Message to Trash",
    description=(
        "Move a message to Trash, where Gmail keeps it for thirty days and a "
        "person can restore it. This is reversible; permanent deletion is not "
        "offered by any curated tool."
    ),
    input_model=TrashMessageInput,
    effect=ToolEffect.MUTATION,
    scopes=(GMAIL_MODIFY,),
)
async def trash_message(
    payload: TrashMessageInput, ctx: VendorToolContext
) -> dict[str, Any]:
    response = await ctx.mutate(f"/{ME}/messages/{payload.message_id}/trash")
    trashed = _object(response.data)
    return {
        "message_id": trashed.get("id"),
        "thread_id": trashed.get("threadId"),
        "trashed": True,
        "recoverable_for_days": 30,
    }


async def _thread(ctx: VendorToolContext, thread_id: str) -> dict[str, Any]:
    return _object(
        (await ctx.read(f"/{ME}/threads/{thread_id}", query={"format": "full"})).data
    )


def _thread_messages(thread: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for item in thread.get("messages", []) or [] if isinstance(item, dict)]


async def _account_address(ctx: VendorToolContext) -> str | None:
    """This connection's own address, so a reply-all never copies itself."""
    profile = _object((await ctx.read(f"/{ME}/profile")).data)
    return _address(profile.get("emailAddress"))


async def _resolve_labels(
    ctx: VendorToolContext, names: list[str] | None, *, create_missing: bool
) -> list[str]:
    """Map label names to ids, accepting ids and system labels unchanged."""
    wanted = [name.strip() for name in names or [] if name and name.strip()]
    if not wanted:
        return []

    existing = _object((await ctx.read(f"/{ME}/labels")).data)
    labels = [
        item for item in existing.get("labels", []) or [] if isinstance(item, dict)
    ]
    by_id = {str(label.get("id")) for label in labels}
    by_name = {
        str(label.get("name", "")).casefold(): str(label.get("id")) for label in labels
    }

    resolved: list[str] = []
    for name in wanted:
        if name in _SYSTEM_LABELS or name in by_id:
            resolved.append(name)
            continue
        found = by_name.get(name.casefold())
        if found:
            resolved.append(found)
            continue
        if not create_missing:
            available = sorted(
                str(label.get("name"))
                for label in labels
                if label.get("type") == "user"
            )
            raise VendorToolError(
                "label_not_found",
                f"No label named '{name}'. Available: {', '.join(available) or 'none'}.",
            )
        created = _object(
            (
                await ctx.mutate(
                    f"/{ME}/labels",
                    json={
                        "name": name,
                        "labelListVisibility": "labelShow",
                        "messageListVisibility": "show",
                    },
                )
            ).data
        )
        resolved.append(str(created.get("id")))
    return resolved


def _build_mime(
    *,
    to: list[str],
    subject: str,
    body: str,
    cc: list[str] | None = None,
    bcc: list[str] | None = None,
    html_body: str | None = None,
    in_reply_to: str | None = None,
    references: str | None = None,
) -> str:
    """Build an RFC 2822 message and encode it the way Gmail's API expects.

    This is the ceremony the curated layer exists to absorb: the raw endpoint
    accepts only a base64url-encoded message source.
    """
    message = EmailMessage()
    message["To"] = ", ".join(to)
    message["Subject"] = subject
    if cc:
        message["Cc"] = ", ".join(cc)
    if bcc:
        message["Bcc"] = ", ".join(bcc)
    if in_reply_to:
        message["In-Reply-To"] = in_reply_to
    if references:
        message["References"] = references
    message.set_content(body)
    if html_body:
        message.add_alternative(html_body, subtype="html")
    return base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")


def _reply_subject(subject: str | None) -> str:
    text = (subject or "").strip()
    if not text:
        return "Re:"
    return text if text.casefold().startswith("re:") else f"Re: {text}"


def _references(headers: dict[str, str]) -> str | None:
    """Chain this reply onto the conversation's existing reference list."""
    message_id = headers.get("message-id")
    existing = headers.get("references")
    parts = [part for part in (existing, message_id) if part]
    return " ".join(parts) or None


def _addresses(*values: str | None) -> list[str]:
    pairs = getaddresses([value for value in values if value])
    return [address.strip().casefold() for _, address in pairs if address]


def _address(value: str | None) -> str | None:
    found = _addresses(value)
    return found[0] if found else None


def _headers(message: dict[str, Any]) -> dict[str, str]:
    """Flatten Gmail's header list into a lowercased lookup."""
    payload = message.get("payload") or {}
    entries = [
        item for item in payload.get("headers", []) or [] if isinstance(item, dict)
    ]
    return {
        str(item.get("name", "")).casefold(): str(item.get("value", ""))
        for item in entries
    }


def _message_view(message: dict[str, Any], *, include_body: bool) -> dict[str, Any]:
    headers = _headers(message)
    view: dict[str, Any] = {
        "id": message.get("id"),
        "thread_id": message.get("threadId"),
        "from": headers.get("from"),
        "to": headers.get("to"),
        "cc": headers.get("cc"),
        "subject": headers.get("subject"),
        "date": headers.get("date"),
        "snippet": message.get("snippet"),
        "labels": message.get("labelIds") or [],
        "unread": "UNREAD" in (message.get("labelIds") or []),
    }
    if not include_body:
        return view

    text, html = _body_parts(message.get("payload") or {})
    chosen = text or html or ""
    view["body"] = chosen[:MAX_BODY_CHARS]
    view["body_truncated"] = len(chosen) > MAX_BODY_CHARS
    view["body_is_html"] = not text and bool(html)
    view["attachments"] = _attachments(message.get("payload") or {})
    return view


def _body_parts(payload: dict[str, Any]) -> tuple[str | None, str | None]:
    """Walk the MIME tree for the first plain-text and HTML bodies."""
    text: str | None = None
    html: str | None = None

    def walk(part: Any) -> None:
        nonlocal text, html
        if not isinstance(part, dict):
            return
        mime = str(part.get("mimeType", ""))
        data = (part.get("body") or {}).get("data")
        if isinstance(data, str) and data:
            if mime == "text/plain" and text is None:
                text = _decode(data)
            elif mime == "text/html" and html is None:
                html = _decode(data)
        for child in part.get("parts", []) or []:
            walk(child)

    walk(payload)
    return text, html


def _attachments(payload: dict[str, Any]) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []

    def walk(part: Any) -> None:
        if not isinstance(part, dict):
            return
        filename = part.get("filename")
        if filename:
            found.append(
                {
                    "filename": filename,
                    "mime_type": part.get("mimeType"),
                    "size_bytes": (part.get("body") or {}).get("size"),
                    "attachment_id": (part.get("body") or {}).get("attachmentId"),
                }
            )
        for child in part.get("parts", []) or []:
            walk(child)

    walk(payload)
    return found


def _decode(data: str) -> str:
    """Gmail encodes part bodies as base64url, unpadded."""
    try:
        padded = data + "=" * (-len(data) % 4)
        return base64.urlsafe_b64decode(padded).decode("utf-8", errors="replace")
    except (ValueError, TypeError):
        return ""


def _sent_view(message: dict[str, Any]) -> dict[str, Any]:
    return {
        "message_id": message.get("id"),
        "thread_id": message.get("threadId"),
        "labels": message.get("labelIds") or [],
        "sent": True,
    }


def _object(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise VendorToolError(
            "vendor_response_invalid", "Gmail returned a non-object response."
        )
    error = payload.get("error")
    if isinstance(error, dict):
        raise VendorToolError(
            "vendor_rejected",
            str(error.get("message", "Google rejected the request."))[:500],
        )
    return payload


__all__ = [
    "create_draft",
    "modify_labels",
    "read_message",
    "read_thread",
    "reply_to_thread",
    "search_messages",
    "send_message",
    "trash_message",
]
