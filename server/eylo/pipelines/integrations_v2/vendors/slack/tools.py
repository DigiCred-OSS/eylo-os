"""Curated Slack tools.

`post_message` takes the channel *name* a person would say and resolves it to
an id, which is the lookup an agent would otherwise spend a whole tool call on.
`read_channel` goes further and resolves the user ids in the returned messages
into display names, so the model gets a transcript it can quote rather than a
wall of `U024BE7LH`.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from eylo.modules.integrations_v2.domain.enums import ToolEffect

from ...contracts import VendorToolContext, VendorToolError
from ...registry import curated_tool
from .definition import (
    CHANNELS_HISTORY,
    CHANNELS_READ,
    CHAT_WRITE,
    USERS_READ,
    USERS_READ_EMAIL,
    call,
    vendor,
)

_MAX_CHANNEL_PAGES = 10


class PostMessageInput(BaseModel):
    channel: str = Field(
        min_length=1,
        description="Channel name such as 'general' or '#general', or a channel id.",
    )
    text: str = Field(min_length=1, description="Message text, Slack mrkdwn.")
    thread_ts: str | None = Field(
        default=None,
        description="Reply inside this thread's parent timestamp.",
    )


class ReadChannelInput(BaseModel):
    channel: str = Field(
        min_length=1,
        description="Channel name such as 'general' or '#general', or a channel id.",
    )
    limit: int = Field(
        default=20, ge=1, le=200, description="How many recent messages to return."
    )


class ListChannelsInput(BaseModel):
    query: str | None = Field(
        default=None, description="Case-insensitive filter on channel name."
    )
    limit: int = Field(default=50, ge=1, le=200)


class FindUserInput(BaseModel):
    email: str = Field(min_length=3, description="Email address to look up.")


@curated_tool(
    vendor=vendor.vendor,
    name="list_channels",
    display_name="List Slack Channels",
    description=(
        "List public Slack channels the bot can see, optionally filtered by "
        "name. Use this when you need to know what channels exist; posting and "
        "reading accept a channel name directly and need no lookup first."
    ),
    input_model=ListChannelsInput,
    effect=ToolEffect.READ,
    scopes=(CHANNELS_READ,),
)
async def list_channels(
    payload: ListChannelsInput, ctx: VendorToolContext
) -> dict[str, Any]:
    channels = await _all_channels(ctx)
    needle = (payload.query or "").strip().casefold()
    matched = [
        channel
        for channel in channels
        if not needle or needle in str(channel.get("name", "")).casefold()
    ][: payload.limit]
    return {
        "channels": [
            {
                "id": channel.get("id"),
                "name": channel.get("name"),
                "is_private": channel.get("is_private"),
                "member_count": channel.get("num_members"),
                "topic": (channel.get("topic") or {}).get("value"),
            }
            for channel in matched
        ],
        "count": len(matched),
    }


@curated_tool(
    vendor=vendor.vendor,
    name="post_message",
    display_name="Post Slack Message",
    description=(
        "Post a message to a Slack channel by name or id. The channel name is "
        "resolved automatically, so 'general' works without looking up its id "
        "first. Set thread_ts to reply inside an existing thread."
    ),
    input_model=PostMessageInput,
    effect=ToolEffect.MUTATION,
    scopes=(CHAT_WRITE, CHANNELS_READ),
)
async def post_message(
    payload: PostMessageInput, ctx: VendorToolContext
) -> dict[str, Any]:
    channel_id = await _resolve_channel(ctx, payload.channel)
    body: dict[str, Any] = {"channel": channel_id, "text": payload.text}
    if payload.thread_ts:
        body["thread_ts"] = payload.thread_ts
    result = await call(ctx, "chat.postMessage", body, mutating=True)
    return {
        "channel_id": result.get("channel"),
        "ts": result.get("ts"),
        "permalink_hint": f"{result.get('channel')}/{result.get('ts')}",
    }


@curated_tool(
    vendor=vendor.vendor,
    name="read_channel",
    display_name="Read Slack Channel",
    description=(
        "Read recent messages from a Slack channel by name or id. Author ids "
        "are resolved to display names, so the result reads as a transcript "
        "rather than raw user ids needing a second lookup."
    ),
    input_model=ReadChannelInput,
    effect=ToolEffect.READ,
    scopes=(CHANNELS_HISTORY, CHANNELS_READ, USERS_READ),
)
async def read_channel(
    payload: ReadChannelInput, ctx: VendorToolContext
) -> dict[str, Any]:
    channel_id = await _resolve_channel(ctx, payload.channel)
    history = await call(
        ctx,
        "conversations.history",
        {"channel": channel_id, "limit": payload.limit},
    )
    messages = [m for m in history.get("messages", []) if isinstance(m, dict)]
    names = await _display_names(
        ctx, {str(m.get("user")) for m in messages if m.get("user")}
    )
    return {
        "channel_id": channel_id,
        "messages": [
            {
                "ts": message.get("ts"),
                "author": names.get(str(message.get("user")), message.get("user")),
                "text": message.get("text"),
                "thread_ts": message.get("thread_ts"),
                "reply_count": message.get("reply_count"),
            }
            for message in messages
        ],
        "count": len(messages),
    }


@curated_tool(
    vendor=vendor.vendor,
    name="find_user_by_email",
    display_name="Find Slack User By Email",
    description=(
        "Look up a Slack user by email address and return their id, display "
        "name, and whether the account is active."
    ),
    input_model=FindUserInput,
    effect=ToolEffect.READ,
    scopes=(USERS_READ, USERS_READ_EMAIL),
)
async def find_user_by_email(
    payload: FindUserInput, ctx: VendorToolContext
) -> dict[str, Any]:
    result = await call(ctx, "users.lookupByEmail", {"email": payload.email})
    user = result.get("user")
    if not isinstance(user, dict):
        raise VendorToolError("user_not_found", "Slack returned no user.")
    profile = user.get("profile") or {}
    return {
        "id": user.get("id"),
        "name": user.get("name"),
        "real_name": profile.get("real_name") or user.get("real_name"),
        "email": profile.get("email"),
        "is_bot": user.get("is_bot"),
        "deleted": user.get("deleted"),
    }


async def _resolve_channel(ctx: VendorToolContext, channel: str) -> str:
    """Accept a channel id or a name, and return an id.

    Slack ids start with C/G/D and never contain lowercase words, so an input
    that already looks like an id is passed through untouched rather than
    costing a channel listing.
    """
    candidate = channel.strip().lstrip("#")
    if _looks_like_channel_id(candidate):
        return candidate
    wanted = candidate.casefold()
    for entry in await _all_channels(ctx):
        if str(entry.get("name", "")).casefold() == wanted:
            return str(entry["id"])
    raise VendorToolError(
        "channel_not_found",
        f"No Slack channel named '{channel}' is visible to this connection.",
    )


def _looks_like_channel_id(value: str) -> bool:
    return (
        len(value) >= 9
        and value[0] in {"C", "G", "D"}
        and value.upper() == value
        and value.isalnum()
    )


async def _all_channels(ctx: VendorToolContext) -> list[dict[str, Any]]:
    """Page through visible channels, bounded so one call cannot run away."""
    channels: list[dict[str, Any]] = []
    cursor: str | None = None
    for _page in range(_MAX_CHANNEL_PAGES):
        body: dict[str, Any] = {"limit": 200, "exclude_archived": True}
        if cursor:
            body["cursor"] = cursor
        result = await call(ctx, "conversations.list", body)
        channels.extend(
            entry for entry in result.get("channels", []) if isinstance(entry, dict)
        )
        cursor = ((result.get("response_metadata") or {}).get("next_cursor")) or None
        if not cursor:
            break
    return channels


async def _display_names(ctx: VendorToolContext, user_ids: set[str]) -> dict[str, str]:
    """Resolve author ids to names in one call rather than one call per author."""
    if not user_ids:
        return {}
    result = await call(ctx, "users.list", {"limit": 200})
    names: dict[str, str] = {}
    for member in result.get("members", []):
        if not isinstance(member, dict):
            continue
        member_id = str(member.get("id"))
        if member_id in user_ids:
            profile = member.get("profile") or {}
            names[member_id] = (
                profile.get("display_name")
                or profile.get("real_name")
                or member.get("name")
                or member_id
            )
    return names


__all__ = [
    "find_user_by_email",
    "list_channels",
    "post_message",
    "read_channel",
]
