"""Curated Google Calendar tool implementations for the `integrations_v2` pipeline."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from pydantic import BaseModel, Field

from eylo.modules.integrations_v2.domain.enums import ToolEffect

from ...contracts import VendorToolContext, VendorToolError
from ...registry import curated_tool
from .definition import CALENDAR, CALENDAR_EVENTS, vendor

PRIMARY = "primary"
_MAX_FREE_BUSY_CALENDARS = 20


class ListEventsInput(BaseModel):
    calendar: str = Field(
        default=PRIMARY,
        description="Calendar id, or its summary name. Defaults to the primary one.",
    )
    time_min: str | None = Field(
        default=None, description="ISO 8601 lower bound on start time."
    )
    time_max: str | None = Field(
        default=None, description="ISO 8601 upper bound on start time."
    )
    query: str | None = Field(default=None, description="Free text search.")
    limit: int = Field(default=25, ge=1, le=100)


class CreateEventInput(BaseModel):
    summary: str = Field(min_length=1, description="Event title.")
    start: str = Field(
        min_length=1, description="ISO 8601 start, e.g. 2026-08-12T14:00:00."
    )
    duration_minutes: int = Field(
        default=30, ge=1, le=1440, description="Length in minutes."
    )
    calendar: str = Field(default=PRIMARY, description="Calendar id or name.")
    timezone: str | None = Field(
        default=None, description="IANA timezone such as Europe/London."
    )
    description: str | None = None
    location: str | None = None
    attendee_emails: list[str] | None = Field(
        default=None, description="Email addresses to invite."
    )


class RescheduleEventInput(BaseModel):
    event_id: str = Field(min_length=1)
    new_start: str = Field(min_length=1, description="ISO 8601 new start time.")
    calendar: str = Field(default=PRIMARY)
    duration_minutes: int | None = Field(
        default=None,
        ge=1,
        le=1440,
        description="New length. Omit to keep the existing duration.",
    )


class CancelEventInput(BaseModel):
    event_id: str = Field(min_length=1)
    calendar: str = Field(default=PRIMARY)


class FindFreeTimeInput(BaseModel):
    time_min: str = Field(min_length=1, description="ISO 8601 window start.")
    time_max: str = Field(min_length=1, description="ISO 8601 window end.")
    calendars: list[str] | None = Field(
        default=None,
        description="Calendar ids or names. Defaults to the primary calendar.",
    )
    minimum_minutes: int = Field(
        default=30, ge=5, le=1440, description="Ignore gaps shorter than this."
    )


class ListCalendarsInput(BaseModel):
    query: str | None = Field(default=None, description="Filter on calendar name.")


@curated_tool(
    vendor=vendor.vendor,
    name="list_calendars",
    display_name="List Google Calendars",
    description=(
        "List calendars this account can see, with their ids, names, and "
        "timezones. Other tools accept a calendar name directly, so this is "
        "only needed to discover what exists."
    ),
    input_model=ListCalendarsInput,
    effect=ToolEffect.READ,
    scopes=(CALENDAR,),
)
async def list_calendars(
    payload: ListCalendarsInput, ctx: VendorToolContext
) -> dict[str, Any]:
    entries = await _calendar_entries(ctx)
    needle = (payload.query or "").strip().casefold()
    matched = [
        entry
        for entry in entries
        if not needle or needle in str(entry.get("summary", "")).casefold()
    ]
    return {
        "calendars": [
            {
                "id": entry.get("id"),
                "name": entry.get("summary"),
                "timezone": entry.get("timeZone"),
                "primary": bool(entry.get("primary")),
                "access_role": entry.get("accessRole"),
            }
            for entry in matched
        ],
        "count": len(matched),
    }


@curated_tool(
    vendor=vendor.vendor,
    name="list_events",
    display_name="List Calendar Events",
    description=(
        "List events on a calendar within an optional time window. Recurring "
        "events are expanded into instances and results are ordered by start "
        "time, so what comes back is the schedule as a person would read it."
    ),
    input_model=ListEventsInput,
    effect=ToolEffect.READ,
    scopes=(CALENDAR,),
)
async def list_events(
    payload: ListEventsInput, ctx: VendorToolContext
) -> dict[str, Any]:
    calendar_id = await _resolve_calendar(ctx, payload.calendar)
    query: dict[str, Any] = {
        "maxResults": payload.limit,
        "singleEvents": True,
        "orderBy": "startTime",
    }
    if payload.time_min:
        query["timeMin"] = _rfc3339(payload.time_min)
    if payload.time_max:
        query["timeMax"] = _rfc3339(payload.time_max)
    if payload.query:
        query["q"] = payload.query
    response = await ctx.read(f"/calendars/{calendar_id}/events", query=query)
    items = _items(response.data)
    return {
        "calendar_id": calendar_id,
        "events": [_event_view(item) for item in items],
        "count": len(items),
    }


@curated_tool(
    vendor=vendor.vendor,
    name="create_event",
    display_name="Create Calendar Event",
    description=(
        "Create a calendar event from a start time and a duration in minutes, "
        "so no end timestamp has to be computed. The calendar may be named "
        "rather than identified, and attendees are given as plain email "
        "addresses."
    ),
    input_model=CreateEventInput,
    effect=ToolEffect.MUTATION,
    scopes=(CALENDAR_EVENTS, CALENDAR),
)
async def create_event(
    payload: CreateEventInput, ctx: VendorToolContext
) -> dict[str, Any]:
    calendar_id = await _resolve_calendar(ctx, payload.calendar)
    start = _parse(payload.start)
    end = start + timedelta(minutes=payload.duration_minutes)
    body: dict[str, Any] = {
        "summary": payload.summary,
        "start": _time_field(start, payload.timezone),
        "end": _time_field(end, payload.timezone),
    }
    if payload.description:
        body["description"] = payload.description
    if payload.location:
        body["location"] = payload.location
    if payload.attendee_emails:
        body["attendees"] = [{"email": email} for email in payload.attendee_emails]
    response = await ctx.mutate(
        f"/calendars/{calendar_id}/events", method="POST", json=body
    )
    return _event_view(_object(response.data))


@curated_tool(
    vendor=vendor.vendor,
    name="reschedule_event",
    display_name="Reschedule Calendar Event",
    description=(
        "Move an existing event to a new start time, keeping its original "
        "duration unless a new one is given. Reads the event and writes it "
        "back in one step, so the duration never has to be recomputed."
    ),
    input_model=RescheduleEventInput,
    effect=ToolEffect.MUTATION,
    scopes=(CALENDAR_EVENTS, CALENDAR),
)
async def reschedule_event(
    payload: RescheduleEventInput, ctx: VendorToolContext
) -> dict[str, Any]:
    calendar_id = await _resolve_calendar(ctx, payload.calendar)
    current = _object(
        (await ctx.read(f"/calendars/{calendar_id}/events/{payload.event_id}")).data
    )
    existing_start = _event_time(current.get("start"))
    existing_end = _event_time(current.get("end"))
    if existing_start is None or existing_end is None:
        raise VendorToolError(
            "event_not_timed",
            "This event has no start and end time to shift.",
        )
    minutes = payload.duration_minutes or max(
        1, int((existing_end - existing_start).total_seconds() // 60)
    )
    new_start = _parse(payload.new_start)
    timezone_name = (current.get("start") or {}).get("timeZone")
    response = await ctx.mutate(
        f"/calendars/{calendar_id}/events/{payload.event_id}",
        method="PATCH",
        json={
            "start": _time_field(new_start, timezone_name),
            "end": _time_field(new_start + timedelta(minutes=minutes), timezone_name),
        },
    )
    return _event_view(_object(response.data))


@curated_tool(
    vendor=vendor.vendor,
    name="cancel_event",
    display_name="Cancel Calendar Event",
    description=(
        "Cancel and remove an event from a calendar. Attendees are notified by "
        "Google. The operation is idempotent."
    ),
    input_model=CancelEventInput,
    effect=ToolEffect.MUTATION,
    scopes=(CALENDAR_EVENTS, CALENDAR),
)
async def cancel_event(
    payload: CancelEventInput, ctx: VendorToolContext
) -> dict[str, Any]:
    calendar_id = await _resolve_calendar(ctx, payload.calendar)
    await ctx.mutate(
        f"/calendars/{calendar_id}/events/{payload.event_id}", method="DELETE"
    )
    return {"event_id": payload.event_id, "calendar_id": calendar_id, "cancelled": True}


@curated_tool(
    vendor=vendor.vendor,
    name="find_free_time",
    display_name="Find Free Time",
    description=(
        "Find free gaps across one or more calendars in a time window. Google "
        "reports busy blocks only; this returns the free intervals between "
        "them, merged across every calendar and filtered to a minimum length."
    ),
    input_model=FindFreeTimeInput,
    effect=ToolEffect.READ,
    scopes=(CALENDAR,),
)
async def find_free_time(
    payload: FindFreeTimeInput, ctx: VendorToolContext
) -> dict[str, Any]:
    names = payload.calendars or [PRIMARY]
    if len(names) > _MAX_FREE_BUSY_CALENDARS:
        raise VendorToolError(
            "too_many_calendars",
            f"At most {_MAX_FREE_BUSY_CALENDARS} calendars may be checked at once.",
        )
    calendar_ids = [await _resolve_calendar(ctx, name) for name in names]
    window_start = _parse(payload.time_min)
    window_end = _parse(payload.time_max)
    if window_end <= window_start:
        raise VendorToolError("window_invalid", "time_max must be after time_min.")

    response = await ctx.read(
        "/freeBusy",
        method="POST",
        json={
            "timeMin": _rfc3339(payload.time_min),
            "timeMax": _rfc3339(payload.time_max),
            "items": [{"id": calendar_id} for calendar_id in calendar_ids],
        },
    )
    calendars = _object(response.data).get("calendars") or {}
    busy: list[tuple[datetime, datetime]] = []
    for entry in calendars.values():
        for block in (entry or {}).get("busy", []) or []:
            start = _event_time({"dateTime": block.get("start")})
            end = _event_time({"dateTime": block.get("end")})
            if start and end:
                busy.append((start, end))

    free = _free_intervals(window_start, window_end, busy, payload.minimum_minutes)
    return {
        "calendars_checked": calendar_ids,
        "free_slots": [
            {
                "start": _isoformat_in_timezone(start, window_start),
                "end": _isoformat_in_timezone(end, window_start),
                "minutes": int((end - start).total_seconds() // 60),
            }
            for start, end in free
        ],
        "count": len(free),
    }


def _free_intervals(
    window_start: datetime,
    window_end: datetime,
    busy: list[tuple[datetime, datetime]],
    minimum_minutes: int,
) -> list[tuple[datetime, datetime]]:
    """Merge busy blocks across calendars, then return the gaps between them."""
    merged: list[list[datetime]] = []
    for start, end in sorted(busy):
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])

    free: list[tuple[datetime, datetime]] = []
    cursor = window_start
    for start, end in merged:
        if start > cursor:
            free.append((cursor, min(start, window_end)))
        cursor = max(cursor, end)
        if cursor >= window_end:
            break
    if cursor < window_end:
        free.append((cursor, window_end))
    minimum = timedelta(minutes=minimum_minutes)
    return [(s, e) for s, e in free if e - s >= minimum]


async def _calendar_entries(ctx: VendorToolContext) -> list[dict[str, Any]]:
    response = await ctx.read("/users/me/calendarList", query={"maxResults": 250})
    return _items(response.data)


async def _resolve_calendar(ctx: VendorToolContext, calendar: str) -> str:
    """Accept `primary`, a calendar id, or a calendar's display name."""
    candidate = calendar.strip()
    if not candidate or candidate == PRIMARY:
        return PRIMARY
    if "@" in candidate:
        return candidate
    wanted = candidate.casefold()
    for entry in await _calendar_entries(ctx):
        if str(entry.get("summary", "")).casefold() == wanted:
            return str(entry["id"])
    raise VendorToolError(
        "calendar_not_found",
        f"No calendar named '{calendar}' is visible to this connection.",
    )


def _event_view(event: dict[str, Any]) -> dict[str, Any]:
    attendees = [a for a in event.get("attendees", []) or [] if isinstance(a, dict)]
    return {
        "id": event.get("id"),
        "summary": event.get("summary"),
        "description": event.get("description"),
        "location": event.get("location"),
        "start": (event.get("start") or {}).get("dateTime")
        or (event.get("start") or {}).get("date"),
        "end": (event.get("end") or {}).get("dateTime")
        or (event.get("end") or {}).get("date"),
        "timezone": (event.get("start") or {}).get("timeZone"),
        "organizer": (event.get("organizer") or {}).get("email"),
        "attendees": [
            {"email": a.get("email"), "response": a.get("responseStatus")}
            for a in attendees
        ],
        "html_link": event.get("htmlLink"),
        "status": event.get("status"),
    }


def _time_field(moment: datetime, timezone_name: str | None) -> dict[str, Any]:
    field: dict[str, Any] = {"dateTime": moment.isoformat()}
    if timezone_name:
        field["timeZone"] = timezone_name
    return field


def _event_time(field: Any) -> datetime | None:
    if not isinstance(field, dict):
        return None
    value = field.get("dateTime") or field.get("date")
    if not isinstance(value, str):
        return None
    try:
        return _parse(value)
    except VendorToolError:
        return None


def _parse(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise VendorToolError(
            "time_invalid", f"'{value}' is not a valid ISO 8601 timestamp."
        ) from error


def _rfc3339(value: str) -> str:
    return _parse(value).isoformat()


def _isoformat_in_timezone(value: datetime, reference: datetime) -> str:
    if value.tzinfo is None or reference.tzinfo is None:
        return value.isoformat()
    return value.astimezone(reference.tzinfo).isoformat()


def _items(payload: Any) -> list[dict[str, Any]]:
    body = _object(payload)
    return [item for item in body.get("items", []) or [] if isinstance(item, dict)]


def _object(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise VendorToolError(
            "vendor_response_invalid", "Google Calendar returned a non-object response."
        )
    error = payload.get("error")
    if isinstance(error, dict):
        raise VendorToolError(
            "vendor_rejected",
            str(error.get("message", "Google rejected the request."))[:500],
        )
    return payload


__all__ = [
    "cancel_event",
    "create_event",
    "find_free_time",
    "list_calendars",
    "list_events",
    "reschedule_event",
]
