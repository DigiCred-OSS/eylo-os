"""Curated Typeform tools.

A Typeform response is a list of answers keyed by *field id*, with the value
under a key named after the answer's type — `{"field": {"id": "abc"}, "type":
"text", "text": "..."}`. The question those ids refer to lives in a completely
separate document, the form definition. So reading submissions raw means
fetching the form, building an id-to-question map, and then decoding each
answer by its own type tag.

`list_responses` does all of that and returns question-and-answer pairs.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from eylo.modules.integrations_v2.domain.enums import ToolEffect

from ...contracts import VendorToolContext, VendorToolError
from ...registry import curated_tool
from .definition import FORMS_READ, RESPONSES_READ, vendor

MAX_TEXT_CHARS = 4_000


class ListFormsInput(BaseModel):
    search: str | None = Field(default=None, description="Match forms by title.")
    limit: int = Field(default=25, ge=1, le=200)


class GetFormInput(BaseModel):
    form_id: str = Field(min_length=1, description="Form id from its URL.")


class ListResponsesInput(BaseModel):
    form_id: str = Field(min_length=1)
    completed_only: bool = Field(
        default=True, description="Exclude partial submissions."
    )
    since: str | None = Field(
        default=None, description="ISO 8601; only responses submitted after this."
    )
    limit: int = Field(default=25, ge=1, le=100)


@curated_tool(
    vendor=vendor.vendor,
    name="list_forms",
    display_name="List Typeforms",
    description=(
        "List the forms this account can see, with their titles, ids, and "
        "public links. The id is what reading responses needs."
    ),
    input_model=ListFormsInput,
    effect=ToolEffect.READ,
    scopes=(FORMS_READ,),
)
async def list_forms(payload: ListFormsInput, ctx: VendorToolContext) -> dict[str, Any]:
    query: dict[str, Any] = {"page_size": payload.limit}
    if payload.search:
        query["search"] = payload.search
    response = await ctx.read("/forms", query=query)
    body = _object(response.data)
    items = [item for item in body.get("items") or [] if isinstance(item, dict)]
    return {
        "forms": [
            {
                "id": form.get("id"),
                "title": form.get("title"),
                "public_link": (form.get("_links") or {}).get("display"),
                "last_updated": form.get("last_updated_at"),
            }
            for form in items
        ],
        "count": len(items),
        "total": body.get("total_items"),
    }


@curated_tool(
    vendor=vendor.vendor,
    name="get_form",
    display_name="Get Typeform Questions",
    description=(
        "Read a form's questions in order, with each one's type and whether it "
        "is required. Useful for understanding what a set of responses will "
        "contain before reading them."
    ),
    input_model=GetFormInput,
    effect=ToolEffect.READ,
    scopes=(FORMS_READ,),
)
async def get_form(payload: GetFormInput, ctx: VendorToolContext) -> dict[str, Any]:
    form = _object((await ctx.read(f"/forms/{payload.form_id}")).data)
    fields = [f for f in form.get("fields") or [] if isinstance(f, dict)]
    return {
        "id": form.get("id"),
        "title": form.get("title"),
        "public_link": (form.get("_links") or {}).get("display"),
        "questions": [
            {
                "id": field.get("id"),
                "question": field.get("title"),
                "type": field.get("type"),
                "required": (field.get("validations") or {}).get("required", False),
                "choices": [
                    choice.get("label")
                    for choice in (field.get("properties") or {}).get("choices") or []
                    if isinstance(choice, dict)
                ]
                or None,
            }
            for field in fields
        ],
        "question_count": len(fields),
    }


@curated_tool(
    vendor=vendor.vendor,
    name="list_responses",
    display_name="List Typeform Responses",
    description=(
        "Read a form's submissions as question-and-answer pairs. Typeform "
        "returns answers keyed by field id with the value hidden under a "
        "type-named key, and keeps the questions in a separate document; both "
        "are fetched and joined here, so each response reads as it would on "
        "paper."
    ),
    input_model=ListResponsesInput,
    effect=ToolEffect.READ,
    scopes=(RESPONSES_READ, FORMS_READ),
)
async def list_responses(
    payload: ListResponsesInput, ctx: VendorToolContext
) -> dict[str, Any]:
    # The questions live on the form, not on the responses.
    form = _object((await ctx.read(f"/forms/{payload.form_id}")).data)
    questions = {
        str(field.get("id")): str(field.get("title"))
        for field in form.get("fields") or []
        if isinstance(field, dict)
    }

    query: dict[str, Any] = {
        "page_size": payload.limit,
        "completed": "true" if payload.completed_only else "false",
    }
    if payload.since:
        query["since"] = payload.since
    response = await ctx.read(f"/forms/{payload.form_id}/responses", query=query)
    body = _object(response.data)
    items = [item for item in body.get("items") or [] if isinstance(item, dict)]

    return {
        "form_id": payload.form_id,
        "form_title": form.get("title"),
        "responses": [
            {
                "response_id": item.get("response_id"),
                "submitted_at": item.get("submitted_at"),
                "completed": item.get("response_type") == "completed"
                or bool(item.get("submitted_at")),
                "answers": _answers(item.get("answers"), questions),
                "metadata": {
                    "browser": (item.get("metadata") or {}).get("browser"),
                    "platform": (item.get("metadata") or {}).get("platform"),
                },
                "hidden_fields": item.get("hidden") or {},
            }
            for item in items
        ],
        "count": len(items),
        "total": body.get("total_items"),
    }


def _answers(answers: Any, questions: dict[str, str]) -> list[dict[str, Any]]:
    """Decode each answer by its own type tag and pair it with its question."""
    paired: list[dict[str, Any]] = []
    for answer in answers or []:
        if not isinstance(answer, dict):
            continue
        field_id = str((answer.get("field") or {}).get("id", ""))
        kind = str(answer.get("type", ""))
        raw = answer.get(kind)
        paired.append(
            {
                "question": questions.get(field_id, f"<field {field_id}>"),
                "answer": _value(kind, raw),
                "type": kind,
            }
        )
    return paired


def _value(kind: str, raw: Any) -> Any:
    if kind == "choice" and isinstance(raw, dict):
        return raw.get("label") or raw.get("other")
    if kind == "choices" and isinstance(raw, dict):
        labels = list(raw.get("labels") or [])
        if raw.get("other"):
            labels.append(raw["other"])
        return labels
    if kind in {"file_url", "url", "email", "phone_number"}:
        return raw
    if isinstance(raw, str):
        return raw[:MAX_TEXT_CHARS]
    return raw


def _object(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise VendorToolError(
            "vendor_response_invalid", "Typeform returned a non-object response."
        )
    if payload.get("code") and payload.get("description"):
        raise VendorToolError("vendor_rejected", str(payload["description"])[:500])
    return payload


__all__ = ["get_form", "list_forms", "list_responses"]
