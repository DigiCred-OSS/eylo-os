"""Curated Pipedrive tool implementations for the `integrations_v2` pipeline."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from eylo.modules.integrations_v2.domain.enums import ToolEffect

from ...contracts import VendorToolContext, VendorToolError
from ...registry import curated_tool
from .definition import vendor

MAX_NOTE_CHARS = 6_000


class FindPersonInput(BaseModel):
    email: str = Field(min_length=1, description="Email address to search for.")


class ListDealsInput(BaseModel):
    status: str = Field(
        default="open", description="open, won, lost, deleted, or all_not_deleted."
    )
    person_email: str | None = Field(
        default=None, description="Only deals for this person."
    )
    limit: int = Field(default=25, ge=1, le=100)


class CreateDealInput(BaseModel):
    title: str = Field(min_length=1, description="What the deal is.")
    value: float | None = Field(default=None, description="Deal value as a number.")
    currency: str | None = Field(
        default=None, description="Three-letter code, e.g. GBP."
    )
    person_email: str | None = Field(
        default=None, description="Attach to this person, if they exist."
    )
    stage: str | None = Field(default=None, description="Pipeline stage name.")


class MoveDealStageInput(BaseModel):
    deal_id: int = Field(ge=1)
    stage: str = Field(min_length=1, description="Target stage name, e.g. Negotiation.")


class AddNoteInput(BaseModel):
    content: str = Field(min_length=1, description="Note text.")
    deal_id: int | None = Field(default=None, description="Attach to this deal.")
    person_email: str | None = Field(
        default=None, description="Attach to this person instead."
    )


@curated_tool(
    vendor=vendor.vendor,
    name="find_person",
    display_name="Find Pipedrive Person",
    description=(
        "Look a person up by email and report their id, name, organization, "
        "phone numbers, and how many open and closed deals they have. The id "
        "is what deals and notes attach to."
    ),
    input_model=FindPersonInput,
    effect=ToolEffect.READ,
)
async def find_person(
    payload: FindPersonInput, ctx: VendorToolContext
) -> dict[str, Any]:
    person = await _person_or_none(ctx, payload.email)
    if person is None:
        return {"found": False, "email": payload.email}
    return {"found": True, **_person_view(person)}


@curated_tool(
    vendor=vendor.vendor,
    name="list_deals",
    display_name="List Pipedrive Deals",
    description=(
        "List deals, optionally only those belonging to one person. Each deal "
        "reports its value with currency and its stage by name rather than by "
        "the numeric id Pipedrive stores, so what comes back is readable "
        "without a second lookup."
    ),
    input_model=ListDealsInput,
    effect=ToolEffect.READ,
)
async def list_deals(payload: ListDealsInput, ctx: VendorToolContext) -> dict[str, Any]:
    query: dict[str, Any] = {"status": payload.status, "limit": payload.limit}
    person_name = None
    if payload.person_email:
        person = await _person_or_none(ctx, payload.person_email)
        if person is None:
            return {"deals": [], "count": 0, "person_found": False}
        query["person_id"] = person.get("id")
        person_name = person.get("name")

    deals = _collection(await ctx.read("/deals", query=query))
    stages = await _stage_names(ctx)
    return {
        "person": person_name,
        "deals": [_deal_view(deal, stages) for deal in deals],
        "count": len(deals),
    }


@curated_tool(
    vendor=vendor.vendor,
    name="create_deal",
    display_name="Create Pipedrive Deal",
    description=(
        "Open a deal, optionally attached to a person given by email and "
        "placed in a stage named rather than numbered. Returns the deal's id "
        "and the stage it landed in."
    ),
    input_model=CreateDealInput,
    effect=ToolEffect.MUTATION,
)
async def create_deal(
    payload: CreateDealInput, ctx: VendorToolContext
) -> dict[str, Any]:
    body: dict[str, Any] = {"title": payload.title}
    if payload.value is not None:
        body["value"] = payload.value
    if payload.currency:
        body["currency"] = payload.currency.upper()
    if payload.person_email:
        person = await _person_or_none(ctx, payload.person_email)
        if person is None:
            raise VendorToolError(
                "person_not_found",
                f"No person in Pipedrive has the email '{payload.person_email}'.",
            )
        body["person_id"] = person.get("id")
    if payload.stage:
        body["stage_id"] = await _stage_id(ctx, payload.stage)

    created = _payload(await ctx.mutate("/deals", json=body))
    if not isinstance(created, dict):
        raise VendorToolError(
            "vendor_response_invalid", "Pipedrive did not return the new deal."
        )
    return _deal_view(created, await _stage_names(ctx))


@curated_tool(
    vendor=vendor.vendor,
    name="move_deal_stage",
    display_name="Move Pipedrive Deal",
    description=(
        "Move a deal to a different pipeline stage, named rather than "
        "numbered. If the name does not match a stage, the error lists the "
        "stages that exist."
    ),
    input_model=MoveDealStageInput,
    effect=ToolEffect.MUTATION,
)
async def move_deal_stage(
    payload: MoveDealStageInput, ctx: VendorToolContext
) -> dict[str, Any]:
    stage_id = await _stage_id(ctx, payload.stage)
    updated = _payload(
        await ctx.mutate(
            f"/deals/{payload.deal_id}", method="PUT", json={"stage_id": stage_id}
        )
    )
    if not isinstance(updated, dict):
        raise VendorToolError(
            "vendor_response_invalid", "Pipedrive did not return the updated deal."
        )
    return _deal_view(updated, await _stage_names(ctx))


@curated_tool(
    vendor=vendor.vendor,
    name="add_note",
    display_name="Add Pipedrive Note",
    description=(
        "Log a note against a deal or a person. Notes are how conversation "
        "history reaches the CRM, so this is the tool for recording what was "
        "said or agreed."
    ),
    input_model=AddNoteInput,
    effect=ToolEffect.MUTATION,
)
async def add_note(payload: AddNoteInput, ctx: VendorToolContext) -> dict[str, Any]:
    body: dict[str, Any] = {"content": payload.content[:MAX_NOTE_CHARS]}
    if payload.deal_id:
        body["deal_id"] = payload.deal_id
    elif payload.person_email:
        person = await _person_or_none(ctx, payload.person_email)
        if person is None:
            raise VendorToolError(
                "person_not_found",
                f"No person in Pipedrive has the email '{payload.person_email}'.",
            )
        body["person_id"] = person.get("id")
    else:
        raise VendorToolError(
            "target_missing", "Give a deal_id or a person_email to attach the note to."
        )

    note = _payload(await ctx.mutate("/notes", json=body))
    return {
        "note_id": note.get("id") if isinstance(note, dict) else None,
        "deal_id": body.get("deal_id"),
        "person_id": body.get("person_id"),
        "added": True,
    }


async def _person_or_none(ctx: VendorToolContext, email: str) -> dict[str, Any] | None:
    response = await ctx.read(
        "/persons/search",
        query={
            "term": email.strip(),
            "fields": "email",
            "exact_match": True,
            "limit": 5,
        },
    )
    data = _payload(response)
    items = (data or {}).get("items") if isinstance(data, dict) else None
    for item in items or []:
        if isinstance(item, dict) and isinstance(item.get("item"), dict):
            return item["item"]
    return None


async def _stage_names(ctx: VendorToolContext) -> dict[int, str]:
    """Stage ids mean nothing on their own; map them to what people call them."""
    stages = _collection(await ctx.read("/stages"))
    return {
        int(stage["id"]): str(stage.get("name"))
        for stage in stages
        if isinstance(stage.get("id"), int)
    }


async def _stage_id(ctx: VendorToolContext, stage: str) -> int:
    wanted = stage.strip().casefold()
    names = await _stage_names(ctx)
    for stage_id, name in names.items():
        if name.casefold() == wanted:
            return stage_id
    available = ", ".join(sorted(names.values()))
    raise VendorToolError(
        "stage_not_found", f"No stage named '{stage}'. Available: {available}."
    )


def _person_view(person: dict[str, Any]) -> dict[str, Any]:
    emails = [e for e in person.get("email") or [] if isinstance(e, dict)]
    phones = [p for p in person.get("phone") or [] if isinstance(p, dict)]
    organization = person.get("organization") or person.get("org_id")
    return {
        "id": person.get("id"),
        "name": person.get("name"),
        "emails": [e.get("value") for e in emails],
        "phones": [p.get("value") for p in phones],
        "organization": (
            organization.get("name") if isinstance(organization, dict) else organization
        ),
        "open_deals": person.get("open_deals_count"),
        "closed_deals": person.get("closed_deals_count"),
    }


def _deal_view(deal: dict[str, Any], stages: dict[int, str]) -> dict[str, Any]:
    stage_id = deal.get("stage_id")
    person = deal.get("person_id")
    return {
        "id": deal.get("id"),
        "title": deal.get("title"),
        "status": deal.get("status"),
        "value": deal.get("value"),
        "currency": deal.get("currency"),
        "formatted_value": (
            f"{deal.get('value')} {deal.get('currency')}"
            if deal.get("value") is not None and deal.get("currency")
            else None
        ),
        "stage": stages.get(stage_id) if isinstance(stage_id, int) else None,
        "stage_id": stage_id,
        "person": person.get("name") if isinstance(person, dict) else person,
        "expected_close": deal.get("expected_close_date"),
        "won_at": deal.get("won_time"),
        "lost_reason": deal.get("lost_reason"),
        "updated_at": deal.get("update_time"),
    }


def _collection(response: Any) -> list[dict[str, Any]]:
    data = _payload(response)
    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, dict)]


def _payload(response: Any) -> Any:
    """Read Pipedrive's `success` envelope, which reports failure at HTTP 200."""
    body = getattr(response, "data", response)
    if not isinstance(body, dict):
        raise VendorToolError(
            "vendor_response_invalid", "Pipedrive returned a non-object response."
        )
    if body.get("success") is False:
        message = (
            body.get("error")
            or body.get("error_info")
            or "Pipedrive rejected the request."
        )
        raise VendorToolError("vendor_rejected", str(message)[:500])
    return body.get("data")


__all__ = [
    "add_note",
    "create_deal",
    "find_person",
    "list_deals",
    "move_deal_stage",
]
