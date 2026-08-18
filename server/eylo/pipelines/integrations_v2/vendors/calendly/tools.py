"""Curated Calendly tools.

Calendly identifies everything by full URI — a user is
`https://api.calendly.com/users/AAAA`, and almost every endpoint requires one
as a query parameter. So the first call in any raw Calendly flow is always
`/users/me`, purely to learn a string that never changes for the connection.

These tools make that call themselves. A caller asks "what meetings are
booked?" and gets an answer, rather than having to fetch an identity first.

Event uuids are equally awkward: they appear inside URIs, but cancellation
wants the bare uuid in a path. Both forms are accepted everywhere.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from eylo.modules.integrations_v2.domain.enums import ToolEffect

from ...contracts import VendorToolContext, VendorToolError
from ...registry import curated_tool
from .definition import vendor

_STATUSES = ("active", "canceled")


class GetAccountInput(BaseModel):
    pass


class ListEventTypesInput(BaseModel):
    include_inactive: bool = Field(default=False)


class ListScheduledEventsInput(BaseModel):
    status: str = Field(default="active", description="active or canceled.")
    min_start_time: str | None = Field(
        default=None, description="ISO 8601; only meetings starting after this."
    )
    max_start_time: str | None = Field(
        default=None, description="ISO 8601 upper bound."
    )
    limit: int = Field(default=20, ge=1, le=100)


class GetEventInviteesInput(BaseModel):
    event: str = Field(min_length=1, description="Event uuid or its full URI.")


class CancelEventInput(BaseModel):
    event: str = Field(min_length=1, description="Event uuid or its full URI.")
    reason: str | None = Field(
        default=None, description="Shown to the invitee in the cancellation notice."
    )


@curated_tool(
    vendor=vendor.vendor,
    name="get_account",
    display_name="Get Calendly Account",
    description=(
        "Report whose Calendly account this connection acts as: name, email, "
        "scheduling page, and timezone. The other tools resolve this "
        "themselves, so this is mainly for confirming the connection."
    ),
    input_model=GetAccountInput,
    effect=ToolEffect.READ,
)
async def get_account(
    payload: GetAccountInput, ctx: VendorToolContext
) -> dict[str, Any]:
    user = await _current_user(ctx)
    return {
        "name": user.get("name"),
        "email": user.get("email"),
        "scheduling_url": user.get("scheduling_url"),
        "timezone": user.get("timezone"),
        "uri": user.get("uri"),
    }


@curated_tool(
    vendor=vendor.vendor,
    name="list_event_types",
    display_name="List Calendly Booking Links",
    description=(
        "List the booking links this account offers, with each one's name, "
        "duration, and the URL someone would use to book it. This is what to "
        "give a person who wants to schedule something. Inactive links are "
        "hidden unless asked for."
    ),
    input_model=ListEventTypesInput,
    effect=ToolEffect.READ,
)
async def list_event_types(
    payload: ListEventTypesInput, ctx: VendorToolContext
) -> dict[str, Any]:
    user = await _current_user(ctx)
    response = await ctx.read(
        "/event_types", query={"user": user.get("uri"), "count": 100}
    )
    types = _collection(response.data)
    if not payload.include_inactive:
        types = [t for t in types if t.get("active")]
    return {
        "booking_links": [
            {
                "name": item.get("name"),
                "duration_minutes": item.get("duration"),
                "booking_url": item.get("scheduling_url"),
                "kind": item.get("kind"),
                "active": item.get("active"),
                "description": item.get("description_plain"),
            }
            for item in types
        ],
        "count": len(types),
    }


@curated_tool(
    vendor=vendor.vendor,
    name="list_scheduled_events",
    display_name="List Calendly Meetings",
    description=(
        "List meetings booked on this account, newest first, with their start "
        "and end times, location, and how many people are attending. Narrow by "
        "a time window to answer 'what is booked this week'."
    ),
    input_model=ListScheduledEventsInput,
    effect=ToolEffect.READ,
)
async def list_scheduled_events(
    payload: ListScheduledEventsInput, ctx: VendorToolContext
) -> dict[str, Any]:
    status = payload.status.strip().casefold()
    if status not in _STATUSES:
        raise VendorToolError(
            "status_invalid", f"status must be one of: {', '.join(_STATUSES)}."
        )
    user = await _current_user(ctx)
    query: dict[str, Any] = {
        "user": user.get("uri"),
        "status": status,
        "count": payload.limit,
        "sort": "start_time:desc",
    }
    if payload.min_start_time:
        query["min_start_time"] = payload.min_start_time
    if payload.max_start_time:
        query["max_start_time"] = payload.max_start_time

    response = await ctx.read("/scheduled_events", query=query)
    events = _collection(response.data)
    return {
        "meetings": [_event_view(event) for event in events],
        "count": len(events),
    }


@curated_tool(
    vendor=vendor.vendor,
    name="get_event_invitees",
    display_name="Get Calendly Meeting Invitees",
    description=(
        "List who booked a meeting, with their name, email, timezone, and any "
        "answers they gave to the booking questions — which is usually where "
        "the actual context lives."
    ),
    input_model=GetEventInviteesInput,
    effect=ToolEffect.READ,
)
async def get_event_invitees(
    payload: GetEventInviteesInput, ctx: VendorToolContext
) -> dict[str, Any]:
    uuid = _uuid(payload.event)
    response = await ctx.read(
        f"/scheduled_events/{uuid}/invitees", query={"count": 100}
    )
    invitees = _collection(response.data)
    return {
        "event_uuid": uuid,
        "invitees": [
            {
                "name": invitee.get("name"),
                "email": invitee.get("email"),
                "timezone": invitee.get("timezone"),
                "status": invitee.get("status"),
                "answers": [
                    {
                        "question": answer.get("question"),
                        "answer": answer.get("answer"),
                    }
                    for answer in invitee.get("questions_and_answers") or []
                    if isinstance(answer, dict)
                ],
                "cancel_url": invitee.get("cancel_url"),
                "reschedule_url": invitee.get("reschedule_url"),
            }
            for invitee in invitees
        ],
        "count": len(invitees),
    }


@curated_tool(
    vendor=vendor.vendor,
    name="cancel_event",
    display_name="Cancel Calendly Meeting",
    description=(
        "Cancel a booked meeting. Calendly emails the invitee, and the reason "
        "given here appears in that notice, so it is worth writing something "
        "a person would want to read."
    ),
    input_model=CancelEventInput,
    effect=ToolEffect.MUTATION,
)
async def cancel_event(
    payload: CancelEventInput, ctx: VendorToolContext
) -> dict[str, Any]:
    uuid = _uuid(payload.event)
    body: dict[str, Any] = {}
    if payload.reason:
        body["reason"] = payload.reason
    response = await ctx.mutate(
        f"/scheduled_events/{uuid}/cancellation", json=body or {"reason": ""}
    )
    resource = _object(response.data).get("resource") or {}
    return {
        "event_uuid": uuid,
        "cancelled": True,
        "cancelled_by": resource.get("canceled_by"),
        "reason": resource.get("reason"),
        "invitee_notified": True,
    }


async def _current_user(ctx: VendorToolContext) -> dict[str, Any]:
    """Calendly needs the account's own URI on almost every call."""
    response = await ctx.read("/users/me")
    resource = _object(response.data).get("resource")
    if not isinstance(resource, dict):
        raise VendorToolError(
            "vendor_response_invalid", "Calendly did not identify this connection."
        )
    return resource


def _uuid(value: str) -> str:
    """Accept a bare uuid or a full Calendly URI, which ends in one."""
    candidate = value.strip().rstrip("/")
    if "/" in candidate:
        candidate = candidate.rsplit("/", 1)[-1]
    if not candidate:
        raise VendorToolError("event_invalid", f"'{value}' is not a Calendly event.")
    return candidate


def _event_view(event: dict[str, Any]) -> dict[str, Any]:
    location = event.get("location")
    memberships = [
        m for m in event.get("event_memberships") or [] if isinstance(m, dict)
    ]
    return {
        "uuid": _uuid(str(event.get("uri") or "")),
        "name": event.get("name"),
        "status": event.get("status"),
        "start_time": event.get("start_time"),
        "end_time": event.get("end_time"),
        "location": (
            location.get("location") or location.get("type")
            if isinstance(location, dict)
            else location
        ),
        "invitee_count": (event.get("invitees_counter") or {}).get("active"),
        "hosts": [m.get("user_email") for m in memberships],
        "created_at": event.get("created_at"),
    }


def _collection(payload: Any) -> list[dict[str, Any]]:
    body = _object(payload)
    return [item for item in body.get("collection") or [] if isinstance(item, dict)]


def _object(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise VendorToolError(
            "vendor_response_invalid", "Calendly returned a non-object response."
        )
    if payload.get("title") and payload.get("message"):
        raise VendorToolError("vendor_rejected", str(payload["message"])[:500])
    return payload


__all__ = [
    "cancel_event",
    "get_account",
    "get_event_invitees",
    "list_event_types",
    "list_scheduled_events",
]
