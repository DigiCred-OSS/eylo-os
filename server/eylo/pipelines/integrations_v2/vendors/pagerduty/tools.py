"""Curated PagerDuty tools, read-only.

Answering "who do I wake up about this?" from the raw API takes three calls:
find the service, read its escalation policy, then resolve the on-call
schedules attached to it. `who_is_on_call` does that in one, and answers with
names and emails rather than resource ids.

Writes are absent for a concrete reason: every PagerDuty mutation requires a
`From` header naming the acting user's email, which is per-installation
configuration this contract has no place to put. See the vendor definition.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from eylo.modules.integrations_v2.domain.enums import ToolEffect

from ...contracts import VendorToolContext, VendorToolError
from ...registry import curated_tool
from .definition import vendor

MAX_BODY_CHARS = 4_000
_STATUSES = ("triggered", "acknowledged", "resolved")
_URGENCIES = ("high", "low")


class ListIncidentsInput(BaseModel):
    statuses: list[str] | None = Field(
        default=None, description="Any of triggered, acknowledged, resolved."
    )
    urgency: str | None = Field(default=None, description="high or low.")
    service_name: str | None = Field(
        default=None, description="Only incidents on this service."
    )
    limit: int = Field(default=25, ge=1, le=100)


class GetIncidentInput(BaseModel):
    incident_id: str = Field(min_length=1, description="Incident id or its number.")
    include_notes: bool = Field(default=True)


class WhoIsOnCallInput(BaseModel):
    service_name: str | None = Field(
        default=None,
        description="Service to check. Omit for every current on-call shift.",
    )


class ListServicesInput(BaseModel):
    limit: int = Field(default=50, ge=1, le=100)


@curated_tool(
    vendor=vendor.vendor,
    name="list_incidents",
    display_name="List PagerDuty Incidents",
    description=(
        "List incidents, by default everything still open. Narrow by status, "
        "urgency, or service name. Each incident reports its title, service, "
        "urgency, who it is assigned to, and how long it has been running."
    ),
    input_model=ListIncidentsInput,
    effect=ToolEffect.READ,
)
async def list_incidents(
    payload: ListIncidentsInput, ctx: VendorToolContext
) -> dict[str, Any]:
    statuses = [
        _one_of(status, _STATUSES, "status") for status in payload.statuses or []
    ] or ["triggered", "acknowledged"]
    query: dict[str, Any] = {
        "statuses[]": statuses,
        "limit": payload.limit,
        "sort_by": "created_at:desc",
    }
    if payload.urgency:
        query["urgencies[]"] = [_one_of(payload.urgency, _URGENCIES, "urgency")]
    if payload.service_name:
        query["service_ids[]"] = [await _service_id(ctx, payload.service_name)]

    response = await ctx.read("/incidents", query=query)
    incidents = _items(response.data, "incidents")
    return {
        "incidents": [_incident_view(item) for item in incidents],
        "count": len(incidents),
        "statuses": statuses,
    }


@curated_tool(
    vendor=vendor.vendor,
    name="get_incident",
    display_name="Get PagerDuty Incident",
    description=(
        "Read one incident with its full detail and, by default, the notes "
        "responders have left on it — which is where the actual story of what "
        "happened lives."
    ),
    input_model=GetIncidentInput,
    effect=ToolEffect.READ,
)
async def get_incident(
    payload: GetIncidentInput, ctx: VendorToolContext
) -> dict[str, Any]:
    body = _object((await ctx.read(f"/incidents/{payload.incident_id}")).data)
    incident = body.get("incident")
    if not isinstance(incident, dict):
        raise VendorToolError("incident_not_found", "PagerDuty returned no incident.")
    view = _incident_view(incident)
    view["description"] = _clip(incident.get("description"))
    view["resolve_reason"] = incident.get("resolve_reason")

    if payload.include_notes:
        notes = await ctx.read(f"/incidents/{payload.incident_id}/notes")
        view["notes"] = [
            {
                "content": _clip(note.get("content")),
                "author": (note.get("user") or {}).get("summary"),
                "created_at": note.get("created_at"),
            }
            for note in _items(notes.data, "notes")
        ]
    return view


@curated_tool(
    vendor=vendor.vendor,
    name="who_is_on_call",
    display_name="Who Is On Call",
    description=(
        "Report who is on call right now, with their name and email and the "
        "escalation level they sit at. Given a service name, this resolves the "
        "service, its escalation policy, and the people currently covering it "
        "— three lookups the caller would otherwise have to chain."
    ),
    input_model=WhoIsOnCallInput,
    effect=ToolEffect.READ,
)
async def who_is_on_call(
    payload: WhoIsOnCallInput, ctx: VendorToolContext
) -> dict[str, Any]:
    query: dict[str, Any] = {"limit": 50, "include[]": ["users"]}
    service_name = None
    if payload.service_name:
        service = await _service(ctx, payload.service_name)
        service_name = service.get("name")
        policy = service.get("escalation_policy") or {}
        policy_id = policy.get("id")
        if not policy_id:
            raise VendorToolError(
                "escalation_policy_missing",
                f"Service '{payload.service_name}' has no escalation policy.",
            )
        query["escalation_policy_ids[]"] = [policy_id]

    response = await ctx.read("/oncalls", query=query)
    oncalls = _items(response.data, "oncalls")
    people = []
    seen: set[str] = set()
    for entry in oncalls:
        user = entry.get("user") or {}
        email = str(user.get("email") or user.get("summary") or "")
        key = f"{email}:{entry.get('escalation_level')}"
        if key in seen:
            continue
        seen.add(key)
        people.append(
            {
                "name": user.get("summary"),
                "email": user.get("email"),
                "escalation_level": entry.get("escalation_level"),
                "policy": (entry.get("escalation_policy") or {}).get("summary"),
                "shift_end": entry.get("end"),
            }
        )
    people.sort(key=lambda p: p.get("escalation_level") or 99)
    return {"service": service_name, "on_call": people, "count": len(people)}


@curated_tool(
    vendor=vendor.vendor,
    name="list_services",
    display_name="List PagerDuty Services",
    description=(
        "List the services PagerDuty monitors, with their current status and "
        "escalation policy. Other tools accept a service name directly, so "
        "this is mainly for discovering what exists."
    ),
    input_model=ListServicesInput,
    effect=ToolEffect.READ,
)
async def list_services(
    payload: ListServicesInput, ctx: VendorToolContext
) -> dict[str, Any]:
    services = await _services(ctx, payload.limit)
    return {
        "services": [
            {
                "id": service.get("id"),
                "name": service.get("name"),
                "status": service.get("status"),
                "escalation_policy": (service.get("escalation_policy") or {}).get(
                    "summary"
                ),
            }
            for service in services
        ],
        "count": len(services),
    }


async def _services(ctx: VendorToolContext, limit: int = 100) -> list[dict[str, Any]]:
    response = await ctx.read("/services", query={"limit": limit})
    return _items(response.data, "services")


async def _service(ctx: VendorToolContext, name: str) -> dict[str, Any]:
    wanted = name.strip().casefold()
    services = await _services(ctx)
    for service in services:
        if str(service.get("name", "")).casefold() == wanted:
            return service
        if str(service.get("id")) == name.strip():
            return service
    available = ", ".join(str(s.get("name")) for s in services[:20])
    raise VendorToolError(
        "service_not_found", f"No service named '{name}'. Available: {available}."
    )


async def _service_id(ctx: VendorToolContext, name: str) -> str:
    return str((await _service(ctx, name)).get("id"))


def _incident_view(incident: dict[str, Any]) -> dict[str, Any]:
    assignments = [a for a in incident.get("assignments") or [] if isinstance(a, dict)]
    return {
        "id": incident.get("id"),
        "number": incident.get("incident_number"),
        "title": incident.get("title"),
        "status": incident.get("status"),
        "urgency": incident.get("urgency"),
        "service": (incident.get("service") or {}).get("summary"),
        "assigned_to": [(a.get("assignee") or {}).get("summary") for a in assignments],
        "escalation_policy": (incident.get("escalation_policy") or {}).get("summary"),
        "created_at": incident.get("created_at"),
        "last_status_change": incident.get("last_status_change_at"),
        "web_link": incident.get("html_url"),
    }


def _one_of(value: str, allowed: tuple[str, ...], label: str) -> str:
    candidate = value.strip().casefold()
    if candidate not in allowed:
        raise VendorToolError(
            f"{label}_invalid", f"{label} must be one of: {', '.join(allowed)}."
        )
    return candidate


def _clip(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    return value[:MAX_BODY_CHARS]


def _items(payload: Any, key: str) -> list[dict[str, Any]]:
    body = _object(payload)
    return [item for item in body.get(key) or [] if isinstance(item, dict)]


def _object(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise VendorToolError(
            "vendor_response_invalid", "PagerDuty returned a non-object response."
        )
    error = payload.get("error")
    if isinstance(error, dict):
        raise VendorToolError(
            "vendor_rejected",
            str(error.get("message", "PagerDuty rejected the request."))[:500],
        )
    return payload


__all__ = ["get_incident", "list_incidents", "list_services", "who_is_on_call"]
