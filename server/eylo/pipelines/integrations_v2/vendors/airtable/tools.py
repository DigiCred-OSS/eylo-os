"""Curated Airtable tools.

Airtable's filtering is a formula language. Matching one field exactly means
writing `{Status}="Open"`, with braces around the field name, double quotes
around the value, and single quotes escaped by doubling — get any of it wrong
and Airtable returns an empty list rather than an error, which reads as "no
matching records".

`list_records` takes a field name and a value and writes that formula.

Records also arrive as `{"id": ..., "createdTime": ..., "fields": {...}}`, so
the values a caller wants are always one level down. They are lifted here, with
the id kept alongside.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from eylo.modules.integrations_v2.domain.enums import ToolEffect

from ...contracts import VendorToolContext, VendorToolError
from ...registry import curated_tool
from .definition import vendor

MAX_RECORDS = 100


class ListBasesInput(BaseModel):
    pass


class ListTablesInput(BaseModel):
    base_id: str = Field(min_length=1, description="Base id, starting app.")


class ListRecordsInput(BaseModel):
    base_id: str = Field(min_length=1)
    table: str = Field(min_length=1, description="Table name or id.")
    where_field: str | None = Field(
        default=None, description="Field name to filter on."
    )
    equals: str | None = Field(default=None, description="Value it must equal.")
    contains: str | None = Field(default=None, description="Value it must contain.")
    view: str | None = Field(default=None, description="Restrict to a named view.")
    limit: int = Field(default=25, ge=1, le=MAX_RECORDS)


class CreateRecordInput(BaseModel):
    base_id: str = Field(min_length=1)
    table: str = Field(min_length=1)
    fields: dict[str, Any] = Field(
        description="Values keyed by field name, e.g. {'Name': 'Ana', 'Status': 'Open'}."
    )


class UpdateRecordInput(BaseModel):
    base_id: str = Field(min_length=1)
    table: str = Field(min_length=1)
    record_id: str = Field(min_length=1, description="Record id, starting rec.")
    fields: dict[str, Any] = Field(description="Only the fields to change.")


@curated_tool(
    vendor=vendor.vendor,
    name="list_bases",
    display_name="List Airtable Bases",
    description=(
        "List the bases this token can reach, with their ids and names. The "
        "base id is what every other tool needs and it is not guessable."
    ),
    input_model=ListBasesInput,
    effect=ToolEffect.READ,
)
async def list_bases(payload: ListBasesInput, ctx: VendorToolContext) -> dict[str, Any]:
    response = await ctx.read("/meta/bases")
    bases = _items(response.data, "bases")
    return {
        "bases": [
            {
                "id": base.get("id"),
                "name": base.get("name"),
                "permission": base.get("permissionLevel"),
            }
            for base in bases
        ],
        "count": len(bases),
    }


@curated_tool(
    vendor=vendor.vendor,
    name="list_tables",
    display_name="List Airtable Tables",
    description=(
        "List a base's tables together with their field names and types. This "
        "is the schema — knowing the exact field names is what makes filtering "
        "and writing records work, since Airtable matches them literally."
    ),
    input_model=ListTablesInput,
    effect=ToolEffect.READ,
)
async def list_tables(
    payload: ListTablesInput, ctx: VendorToolContext
) -> dict[str, Any]:
    response = await ctx.read(f"/meta/bases/{payload.base_id}/tables")
    tables = _items(response.data, "tables")
    return {
        "base_id": payload.base_id,
        "tables": [
            {
                "id": table.get("id"),
                "name": table.get("name"),
                "fields": [
                    {"name": field.get("name"), "type": field.get("type")}
                    for field in table.get("fields") or []
                    if isinstance(field, dict)
                ],
                "views": [
                    view.get("name")
                    for view in table.get("views") or []
                    if isinstance(view, dict)
                ],
            }
            for table in tables
        ],
        "count": len(tables),
    }


@curated_tool(
    vendor=vendor.vendor,
    name="list_records",
    display_name="List Airtable Records",
    description=(
        "Read records from a table, optionally filtered on one field by exact "
        "match or containment — the formula Airtable needs is written here. "
        "Each record comes back as plain values with its id alongside, rather "
        "than nested under a fields envelope. Use list_tables first if the "
        "field names are not known."
    ),
    input_model=ListRecordsInput,
    effect=ToolEffect.READ,
)
async def list_records(
    payload: ListRecordsInput, ctx: VendorToolContext
) -> dict[str, Any]:
    query: dict[str, Any] = {"maxRecords": payload.limit, "pageSize": payload.limit}
    if payload.view:
        query["view"] = payload.view
    if payload.where_field:
        if payload.equals is None and payload.contains is None:
            raise VendorToolError(
                "filter_incomplete", "Give equals or contains alongside where_field."
            )
        query["filterByFormula"] = _formula(
            payload.where_field, equals=payload.equals, contains=payload.contains
        )

    response = await ctx.read(
        f"/{payload.base_id}/{_table(payload.table)}", query=query
    )
    records = _items(response.data, "records")
    return {
        "base_id": payload.base_id,
        "table": payload.table,
        "records": [_record_view(record) for record in records],
        "count": len(records),
        "filter": query.get("filterByFormula"),
    }


@curated_tool(
    vendor=vendor.vendor,
    name="create_record",
    display_name="Create Airtable Record",
    description=(
        "Add a record to a table. Give the values keyed by field name exactly "
        "as they appear in the table — Airtable rejects an unknown field "
        "rather than ignoring it, so list_tables is worth calling first."
    ),
    input_model=CreateRecordInput,
    effect=ToolEffect.MUTATION,
)
async def create_record(
    payload: CreateRecordInput, ctx: VendorToolContext
) -> dict[str, Any]:
    response = await ctx.mutate(
        f"/{payload.base_id}/{_table(payload.table)}",
        json={"fields": payload.fields, "typecast": True},
    )
    return _record_view(_object(response.data))


@curated_tool(
    vendor=vendor.vendor,
    name="update_record",
    display_name="Update Airtable Record",
    description=(
        "Change some of a record's fields. Only the fields given are sent, so "
        "everything else keeps its value."
    ),
    input_model=UpdateRecordInput,
    effect=ToolEffect.MUTATION,
)
async def update_record(
    payload: UpdateRecordInput, ctx: VendorToolContext
) -> dict[str, Any]:
    if not payload.fields:
        raise VendorToolError(
            "no_change_requested", "Give at least one field to change."
        )
    response = await ctx.mutate(
        f"/{payload.base_id}/{_table(payload.table)}/{payload.record_id}",
        method="PATCH",
        json={"fields": payload.fields, "typecast": True},
    )
    return _record_view(_object(response.data))


def _formula(field: str, *, equals: str | None, contains: str | None) -> str:
    """Write the filter formula Airtable expects, escaped correctly.

    A field name goes in braces and a value in double quotes. A stray quote in
    either would end the literal early, so both are escaped.
    """
    name = field.replace("}", "\\}")
    if equals is not None:
        return f'{{{name}}}="{_quote(equals)}"'
    return f'FIND(LOWER("{_quote(contains or "")}"), LOWER({{{name}}}))'


def _quote(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _table(value: str) -> str:
    """Table names travel in the path and often contain spaces."""
    return value.strip().replace("%", "%25").replace(" ", "%20").replace("/", "%2F")


def _record_view(record: dict[str, Any]) -> dict[str, Any]:
    fields = record.get("fields")
    return {
        "id": record.get("id"),
        "created_at": record.get("createdTime"),
        **(fields if isinstance(fields, dict) else {}),
    }


def _items(payload: Any, key: str) -> list[dict[str, Any]]:
    body = _object(payload)
    return [item for item in body.get(key) or [] if isinstance(item, dict)]


def _object(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise VendorToolError(
            "vendor_response_invalid", "Airtable returned a non-object response."
        )
    error = payload.get("error")
    if error is not None:
        message = (
            error.get("message") if isinstance(error, dict) else str(error)
        ) or "Airtable rejected the request."
        raise VendorToolError("vendor_rejected", str(message)[:500])
    return payload


__all__ = [
    "create_record",
    "list_bases",
    "list_records",
    "list_tables",
    "update_record",
]
