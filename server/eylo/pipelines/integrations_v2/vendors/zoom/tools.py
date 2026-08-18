"""Curated Zoom tool implementations for the `integrations_v2` pipeline."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from eylo.modules.integrations_v2.domain.enums import ToolEffect

from ...contracts import VendorToolContext, VendorToolError
from ...registry import curated_tool
from .definition import MEETING_READ, MEETING_WRITE, USER_READ, vendor

_SCHEDULED = 2
_LIST_TYPES = ("scheduled", "upcoming", "previous_meetings")


class ListMeetingsInput(BaseModel):
    which: str = Field(
        default="upcoming",
        description="upcoming, scheduled, or previous_meetings.",
    )
    limit: int = Field(default=20, ge=1, le=100)


class CreateMeetingInput(BaseModel):
    topic: str = Field(min_length=1, description="What the meeting is about.")
    start_time: str = Field(
        min_length=1, description="ISO 8601 start, e.g. 2026-09-01T14:00:00."
    )
    duration_minutes: int = Field(default=30, ge=1, le=1440)
    timezone: str | None = Field(
        default=None, description="IANA timezone such as Europe/London."
    )
    agenda: str | None = None
    waiting_room: bool = Field(default=True)


class GetMeetingInput(BaseModel):
    meeting_id: str = Field(min_length=1, description="Numeric meeting id.")


class CancelMeetingInput(BaseModel):
    meeting_id: str = Field(min_length=1)
    notify_attendees: bool = Field(default=True)


@curated_tool(
    vendor=vendor.vendor,
    name="list_meetings",
    display_name="List Zoom Meetings",
    description=(
        "List this account's meetings — what is coming up, everything "
        "scheduled, or what has already happened. Each entry carries its "
        "start time, duration, and join link."
    ),
    input_model=ListMeetingsInput,
    effect=ToolEffect.READ,
    scopes=(MEETING_READ, USER_READ),
)
async def list_meetings(
    payload: ListMeetingsInput, ctx: VendorToolContext
) -> dict[str, Any]:
    which = payload.which.strip().casefold()
    if which not in _LIST_TYPES:
        raise VendorToolError(
            "which_invalid", f"which must be one of: {', '.join(_LIST_TYPES)}."
        )
    response = await ctx.read(
        "/users/me/meetings", query={"type": which, "page_size": payload.limit}
    )
    body = _object(response.data)
    meetings = [m for m in body.get("meetings") or [] if isinstance(m, dict)]
    return {
        "meetings": [_meeting_view(meeting) for meeting in meetings],
        "count": len(meetings),
        "total": body.get("total_records"),
    }


@curated_tool(
    vendor=vendor.vendor,
    name="create_meeting",
    display_name="Schedule Zoom Meeting",
    description=(
        "Schedule a meeting from a start time and a duration in minutes, and "
        "get back the join link and passcode. Give an IANA timezone if the "
        "start time is local rather than UTC — without one Zoom treats a bare "
        "timestamp as GMT, which is how meetings end up an hour out."
    ),
    input_model=CreateMeetingInput,
    effect=ToolEffect.MUTATION,
    scopes=(MEETING_WRITE,),
)
async def create_meeting(
    payload: CreateMeetingInput, ctx: VendorToolContext
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "topic": payload.topic,
        "type": _SCHEDULED,
        "start_time": _start_time(payload.start_time, payload.timezone),
        "duration": payload.duration_minutes,
        "settings": {"waiting_room": payload.waiting_room},
    }
    if payload.timezone:
        body["timezone"] = payload.timezone
    if payload.agenda:
        body["agenda"] = payload.agenda

    response = await ctx.mutate("/users/me/meetings", json=body)
    return _meeting_view(_object(response.data))


@curated_tool(
    vendor=vendor.vendor,
    name="get_meeting",
    display_name="Get Zoom Meeting",
    description=(
        "Read one meeting's details, including its join link, passcode, "
        "agenda, and host. Useful for re-sending an invitation."
    ),
    input_model=GetMeetingInput,
    effect=ToolEffect.READ,
    scopes=(MEETING_READ,),
)
async def get_meeting(
    payload: GetMeetingInput, ctx: VendorToolContext
) -> dict[str, Any]:
    response = await ctx.read(f"/meetings/{payload.meeting_id}")
    return _meeting_view(_object(response.data))


@curated_tool(
    vendor=vendor.vendor,
    name="cancel_meeting",
    display_name="Cancel Zoom Meeting",
    description=(
        "Cancel a scheduled meeting. Registrants are emailed by Zoom unless "
        "that is turned off. The join link stops working immediately."
    ),
    input_model=CancelMeetingInput,
    effect=ToolEffect.MUTATION,
    scopes=(MEETING_WRITE,),
)
async def cancel_meeting(
    payload: CancelMeetingInput, ctx: VendorToolContext
) -> dict[str, Any]:
    await ctx.mutate(
        f"/meetings/{payload.meeting_id}",
        method="DELETE",
        query={
            "schedule_for_reminder": payload.notify_attendees,
            "cancel_meeting_reminder": payload.notify_attendees,
        },
    )
    return {
        "meeting_id": payload.meeting_id,
        "cancelled": True,
        "attendees_notified": payload.notify_attendees,
    }


def _start_time(value: str, timezone_name: str | None) -> str:
    """Format a start time the way Zoom actually reads it.

    With a timezone, Zoom wants a local time and no offset. Without one, it
    reads the value as GMT and expects the trailing `Z` to say so.
    """
    text = value.strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as error:
        raise VendorToolError(
            "time_invalid", f"'{value}' is not a valid ISO 8601 timestamp."
        ) from error
    naive = parsed.replace(tzinfo=None)
    if timezone_name:
        return naive.strftime("%Y-%m-%dT%H:%M:%S")
    if parsed.tzinfo is not None:
        from datetime import timezone as _tz

        return parsed.astimezone(_tz.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return naive.strftime("%Y-%m-%dT%H:%M:%SZ")


def _meeting_view(meeting: dict[str, Any]) -> dict[str, Any]:
    settings = meeting.get("settings") or {}
    return {
        "id": str(meeting.get("id")) if meeting.get("id") is not None else None,
        "topic": meeting.get("topic"),
        "start_time": meeting.get("start_time"),
        "duration_minutes": meeting.get("duration"),
        "timezone": meeting.get("timezone"),
        "join_url": meeting.get("join_url"),
        "passcode": meeting.get("password"),
        "agenda": meeting.get("agenda"),
        "host_email": meeting.get("host_email"),
        "status": meeting.get("status"),
        "waiting_room": settings.get("waiting_room")
        if isinstance(settings, dict)
        else None,
    }


def _object(payload: Any) -> dict[str, Any]:
    if payload is None:
        # A successful DELETE returns no body.
        return {}
    if not isinstance(payload, dict):
        raise VendorToolError(
            "vendor_response_invalid", "Zoom returned a non-object response."
        )
    # Zoom reports failures as {"code": N, "message": "..."}.
    if payload.get("code") is not None and payload.get("message"):
        raise VendorToolError("vendor_rejected", str(payload["message"])[:500])
    return payload


__all__ = [
    "cancel_meeting",
    "create_meeting",
    "get_meeting",
    "list_meetings",
]
