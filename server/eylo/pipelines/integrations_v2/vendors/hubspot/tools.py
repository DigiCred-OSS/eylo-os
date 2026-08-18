"""Curated HubSpot tool implementations for the `integrations_v2` pipeline."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from eylo.modules.integrations_v2.domain.enums import ToolEffect

from ...contracts import VendorToolContext, VendorToolError
from ...registry import curated_tool
from .definition import CONTACTS_READ, CONTACTS_WRITE, DEALS_READ, DEALS_WRITE, vendor

_CONTACT_PROPERTIES = (
    "email",
    "firstname",
    "lastname",
    "phone",
    "company",
    "jobtitle",
    "lifecyclestage",
    "hs_lead_status",
    "createdate",
)
_DEAL_PROPERTIES = (
    "dealname",
    "amount",
    "dealstage",
    "pipeline",
    "closedate",
    "hs_deal_stage_probability",
)


class FindContactInput(BaseModel):
    email: str | None = Field(default=None, description="Exact email address.")
    name_contains: str | None = Field(
        default=None, description="Part of a first or last name."
    )
    limit: int = Field(default=10, ge=1, le=50)


class CreateContactInput(BaseModel):
    email: str = Field(min_length=1)
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None
    company: str | None = None
    job_title: str | None = None


class UpdateContactInput(BaseModel):
    contact_id: str = Field(min_length=1, description="HubSpot's contact id.")
    email: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None
    company: str | None = None
    lifecycle_stage: str | None = Field(
        default=None, description="e.g. lead, marketingqualifiedlead, customer."
    )


class ListDealsInput(BaseModel):
    contact_email: str | None = Field(
        default=None, description="Only deals associated with this person."
    )
    limit: int = Field(default=20, ge=1, le=50)


class CreateDealInput(BaseModel):
    name: str = Field(min_length=1)
    amount: float | None = Field(default=None, ge=0)
    stage_id: str | None = Field(
        default=None, description="Deal stage id. Omit for the pipeline default."
    )
    close_date: str | None = Field(default=None, description="ISO 8601 date.")
    contact_email: str | None = Field(
        default=None, description="Associate the deal with this person."
    )


class AddNoteInput(BaseModel):
    contact_email: str = Field(min_length=1, description="Person to log against.")
    body: str = Field(min_length=1, description="The note's text.")


@curated_tool(
    vendor=vendor.vendor,
    name="find_contact",
    display_name="Find HubSpot Contact",
    description=(
        "Look a person up by exact email or by part of their name, without "
        "building HubSpot's nested search filters. Returns their id and the "
        "properties worth knowing — company, job title, lifecycle stage — so "
        "a second read is rarely needed."
    ),
    input_model=FindContactInput,
    effect=ToolEffect.READ,
    scopes=(CONTACTS_READ,),
)
async def find_contact(
    payload: FindContactInput, ctx: VendorToolContext
) -> dict[str, Any]:
    if not payload.email and not payload.name_contains:
        raise VendorToolError(
            "search_unbounded", "Give an email address or part of a name."
        )
    if payload.email:
        groups = [_group("email", "EQ", payload.email.strip())]
    else:
        # HubSpot has no OR across properties within one group, so first and
        # last name go in separate groups, which HubSpot ORs together.
        groups = [
            _group("firstname", "CONTAINS_TOKEN", payload.name_contains),
            _group("lastname", "CONTAINS_TOKEN", payload.name_contains),
        ]
    results = await _search(ctx, "contacts", groups, _CONTACT_PROPERTIES, payload.limit)
    return {
        "contacts": [_contact_view(item) for item in results],
        "count": len(results),
    }


@curated_tool(
    vendor=vendor.vendor,
    name="create_contact",
    display_name="Create HubSpot Contact",
    description=(
        "Add a person to the CRM. HubSpot rejects a duplicate email, and that "
        "is reported as a clear conflict rather than a raw error, so the "
        "sensible next step is to find the existing contact."
    ),
    input_model=CreateContactInput,
    effect=ToolEffect.MUTATION,
    scopes=(CONTACTS_WRITE,),
)
async def create_contact(
    payload: CreateContactInput, ctx: VendorToolContext
) -> dict[str, Any]:
    properties = _properties(
        email=payload.email,
        firstname=payload.first_name,
        lastname=payload.last_name,
        phone=payload.phone,
        company=payload.company,
        jobtitle=payload.job_title,
    )
    response = await ctx.mutate(
        "/crm/v3/objects/contacts", json={"properties": properties}
    )
    return _contact_view(_object(response.data))


@curated_tool(
    vendor=vendor.vendor,
    name="update_contact",
    display_name="Update HubSpot Contact",
    description=(
        "Change a contact's properties. Only the fields given are sent, so "
        "everything else is left as it was. Use find_contact first to get the "
        "contact's id."
    ),
    input_model=UpdateContactInput,
    effect=ToolEffect.MUTATION,
    scopes=(CONTACTS_WRITE,),
)
async def update_contact(
    payload: UpdateContactInput, ctx: VendorToolContext
) -> dict[str, Any]:
    properties = _properties(
        email=payload.email,
        firstname=payload.first_name,
        lastname=payload.last_name,
        phone=payload.phone,
        company=payload.company,
        lifecyclestage=payload.lifecycle_stage,
    )
    if not properties:
        raise VendorToolError(
            "no_change_requested", "Give at least one property to change."
        )
    response = await ctx.mutate(
        f"/crm/v3/objects/contacts/{payload.contact_id}",
        method="PATCH",
        json={"properties": properties},
    )
    return _contact_view(_object(response.data))


@curated_tool(
    vendor=vendor.vendor,
    name="list_deals",
    display_name="List HubSpot Deals",
    description=(
        "List deals with their stage and pipeline resolved to readable names "
        "rather than the internal ids HubSpot stores. Give a contact's email "
        "to see only the deals associated with that person."
    ),
    input_model=ListDealsInput,
    effect=ToolEffect.READ,
    scopes=(DEALS_READ, CONTACTS_READ),
)
async def list_deals(payload: ListDealsInput, ctx: VendorToolContext) -> dict[str, Any]:
    labels = await _stage_labels(ctx)

    if payload.contact_email:
        contact = await _contact_by_email(ctx, payload.contact_email)
        if contact is None:
            return {"deals": [], "count": 0, "contact_found": False}
        response = await ctx.read(
            f"/crm/v3/objects/contacts/{contact.get('id')}/associations/deals",
            query={"limit": payload.limit},
        )
        ids = [
            str(item.get("toObjectId") or item.get("id"))
            for item in _results(response.data)
            if item.get("toObjectId") or item.get("id")
        ]
        deals = []
        for deal_id in ids[: payload.limit]:
            detail = await ctx.read(
                f"/crm/v3/objects/deals/{deal_id}",
                query={"properties": ",".join(_DEAL_PROPERTIES)},
            )
            deals.append(_object(detail.data))
        return {
            "deals": [_deal_view(deal, labels) for deal in deals],
            "count": len(deals),
            "contact_found": True,
        }

    response = await ctx.read(
        "/crm/v3/objects/deals",
        query={"limit": payload.limit, "properties": ",".join(_DEAL_PROPERTIES)},
    )
    deals = _results(response.data)
    return {
        "deals": [_deal_view(deal, labels) for deal in deals],
        "count": len(deals),
    }


@curated_tool(
    vendor=vendor.vendor,
    name="create_deal",
    display_name="Create HubSpot Deal",
    description=(
        "Open a deal, optionally associated with a person given by email. The "
        "association is made here, which HubSpot otherwise requires as a "
        "separate call against an association endpoint."
    ),
    input_model=CreateDealInput,
    effect=ToolEffect.MUTATION,
    scopes=(DEALS_WRITE, CONTACTS_READ),
)
async def create_deal(
    payload: CreateDealInput, ctx: VendorToolContext
) -> dict[str, Any]:
    properties = _properties(
        dealname=payload.name,
        amount=str(payload.amount) if payload.amount is not None else None,
        dealstage=payload.stage_id,
        closedate=payload.close_date,
    )
    body: dict[str, Any] = {"properties": properties}

    contact_id = None
    if payload.contact_email:
        contact = await _contact_by_email(ctx, payload.contact_email)
        if contact is None:
            raise VendorToolError(
                "contact_not_found",
                f"No HubSpot contact with email '{payload.contact_email}'.",
            )
        contact_id = contact.get("id")
        body["associations"] = [
            {
                "to": {"id": contact_id},
                # 3 is HubSpot's built-in deal-to-contact association type.
                "types": [
                    {"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 3}
                ],
            }
        ]

    response = await ctx.mutate("/crm/v3/objects/deals", json=body)
    view = _deal_view(_object(response.data), await _stage_labels(ctx))
    view["associated_contact_id"] = contact_id
    return view


@curated_tool(
    vendor=vendor.vendor,
    name="add_note",
    display_name="Log a HubSpot Note",
    description=(
        "Log a note against a person, given by email. HubSpot models a note as "
        "an engagement that must be created and then associated; both happen "
        "here. The note appears on the contact's timeline."
    ),
    input_model=AddNoteInput,
    effect=ToolEffect.MUTATION,
    scopes=(CONTACTS_WRITE,),
)
async def add_note(payload: AddNoteInput, ctx: VendorToolContext) -> dict[str, Any]:
    contact = await _contact_by_email(ctx, payload.contact_email)
    if contact is None:
        raise VendorToolError(
            "contact_not_found",
            f"No HubSpot contact with email '{payload.contact_email}'.",
        )
    response = await ctx.mutate(
        "/crm/v3/objects/notes",
        json={
            "properties": {"hs_note_body": payload.body},
            "associations": [
                {
                    "to": {"id": contact.get("id")},
                    # 202 is note-to-contact.
                    "types": [
                        {
                            "associationCategory": "HUBSPOT_DEFINED",
                            "associationTypeId": 202,
                        }
                    ],
                }
            ],
        },
    )
    note = _object(response.data)
    return {
        "note_id": note.get("id"),
        "contact_id": contact.get("id"),
        "contact_email": payload.contact_email,
        "logged": True,
    }


async def _search(
    ctx: VendorToolContext,
    object_type: str,
    filter_groups: list[dict[str, Any]],
    properties: tuple[str, ...],
    limit: int,
) -> list[dict[str, Any]]:
    response = await ctx.read(
        f"/crm/v3/objects/{object_type}/search",
        method="POST",
        json={
            "filterGroups": filter_groups,
            "properties": list(properties),
            "limit": limit,
        },
    )
    return _results(response.data)


async def _contact_by_email(
    ctx: VendorToolContext, email: str
) -> dict[str, Any] | None:
    found = await _search(
        ctx, "contacts", [_group("email", "EQ", email.strip())], _CONTACT_PROPERTIES, 1
    )
    return found[0] if found else None


async def _stage_labels(ctx: VendorToolContext) -> dict[str, str]:
    """Map HubSpot's opaque pipeline and stage ids to their display labels."""
    response = await ctx.read("/crm/v3/pipelines/deals")
    labels: dict[str, str] = {}
    for pipeline in _results(response.data):
        pipeline_id = str(pipeline.get("id"))
        labels[pipeline_id] = str(pipeline.get("label") or pipeline_id)
        for stage in pipeline.get("stages") or []:
            if isinstance(stage, dict):
                stage_id = str(stage.get("id"))
                labels[stage_id] = str(stage.get("label") or stage_id)
    return labels


def _group(property_name: str, operator: str, value: Any) -> dict[str, Any]:
    return {
        "filters": [
            {"propertyName": property_name, "operator": operator, "value": value}
        ]
    }


def _properties(**values: Any) -> dict[str, Any]:
    return {key: value for key, value in values.items() if value is not None}


def _contact_view(contact: dict[str, Any]) -> dict[str, Any]:
    properties = contact.get("properties") or {}
    name = " ".join(
        part
        for part in (properties.get("firstname"), properties.get("lastname"))
        if part
    )
    return {
        "id": contact.get("id"),
        "name": name or None,
        "email": properties.get("email"),
        "phone": properties.get("phone"),
        "company": properties.get("company"),
        "job_title": properties.get("jobtitle"),
        "lifecycle_stage": properties.get("lifecyclestage"),
        "lead_status": properties.get("hs_lead_status"),
        "created_at": properties.get("createdate"),
    }


def _deal_view(deal: dict[str, Any], labels: dict[str, str]) -> dict[str, Any]:
    properties = deal.get("properties") or {}
    stage_id = str(properties.get("dealstage") or "")
    pipeline_id = str(properties.get("pipeline") or "")
    return {
        "id": deal.get("id"),
        "name": properties.get("dealname"),
        "amount": properties.get("amount"),
        "stage": labels.get(stage_id, stage_id or None),
        "stage_id": stage_id or None,
        "pipeline": labels.get(pipeline_id, pipeline_id or None),
        "close_date": properties.get("closedate"),
        "probability": properties.get("hs_deal_stage_probability"),
    }


def _results(payload: Any) -> list[dict[str, Any]]:
    body = _object(payload)
    return [item for item in body.get("results") or [] if isinstance(item, dict)]


def _object(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise VendorToolError(
            "vendor_response_invalid", "HubSpot returned a non-object response."
        )
    status = payload.get("status")
    if status == "error":
        category = str(payload.get("category") or "")
        message = str(payload.get("message", "HubSpot rejected the request."))
        if category == "CONFLICT":
            raise VendorToolError("record_exists", message[:500])
        raise VendorToolError("vendor_rejected", message[:500])
    return payload


__all__ = [
    "add_note",
    "create_contact",
    "create_deal",
    "find_contact",
    "list_deals",
    "update_contact",
]
