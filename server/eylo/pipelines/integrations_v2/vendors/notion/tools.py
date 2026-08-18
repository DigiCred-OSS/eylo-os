"""Curated Notion tool implementations for the `integrations_v2` pipeline."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from eylo.modules.integrations_v2.domain.enums import ToolEffect

from ...contracts import VendorToolContext, VendorToolError
from ...registry import curated_tool
from .definition import vendor

MAX_TEXT_CHARS = 20_000
MAX_BLOCKS = 100
_MAX_DEPTH = 3

# Block types worth rendering, and how their text is prefixed.
_BLOCK_PREFIX = {
    "heading_1": "# ",
    "heading_2": "## ",
    "heading_3": "### ",
    "bulleted_list_item": "- ",
    "numbered_list_item": "1. ",
    "quote": "> ",
    "callout": "> ",
    "toggle": "",
    "paragraph": "",
    "code": "",
    "to_do": "",
}


class SearchInput(BaseModel):
    query: str | None = Field(
        default=None, description="Text to match in page and database titles."
    )
    only: str | None = Field(
        default=None, description="Restrict to 'page' or 'database'."
    )
    limit: int = Field(default=20, ge=1, le=50)


class ReadPageInput(BaseModel):
    page_id: str = Field(
        min_length=1, description="Page id, or the id at the end of its URL."
    )


class CreatePageInput(BaseModel):
    title: str = Field(min_length=1)
    parent_id: str = Field(
        min_length=1, description="Id of the parent page or database."
    )
    parent_is_database: bool = Field(
        default=False,
        description="Set when the parent is a database rather than a page.",
    )
    body: str | None = Field(
        default=None, description="Opening content, one paragraph per line."
    )


class AppendToPageInput(BaseModel):
    page_id: str = Field(min_length=1)
    text: str = Field(min_length=1, description="Text to add, one paragraph per line.")


class QueryDatabaseInput(BaseModel):
    database_id: str = Field(min_length=1)
    property_name: str | None = Field(
        default=None, description="Property to filter on, by its name."
    )
    equals: str | None = Field(default=None, description="Match this value exactly.")
    contains: str | None = Field(
        default=None, description="Match values containing this."
    )
    limit: int = Field(default=25, ge=1, le=100)


@curated_tool(
    vendor=vendor.vendor,
    name="search",
    display_name="Search Notion",
    description=(
        "Find pages and databases the integration can see, by title. Notion "
        "only surfaces content explicitly shared with the integration, so an "
        "empty result usually means the page has not been shared with it."
    ),
    input_model=SearchInput,
    effect=ToolEffect.READ,
)
async def search(payload: SearchInput, ctx: VendorToolContext) -> dict[str, Any]:
    body: dict[str, Any] = {"page_size": payload.limit}
    if payload.query:
        body["query"] = payload.query
    if payload.only:
        kind = payload.only.strip().casefold()
        if kind not in {"page", "database"}:
            raise VendorToolError(
                "filter_invalid", "only must be 'page' or 'database'."
            )
        body["filter"] = {"property": "object", "value": kind}
    response = await ctx.read("/search", method="POST", json=body)
    results = _results(response.data)
    return {
        "results": [_entry_view(item) for item in results],
        "count": len(results),
    }


@curated_tool(
    vendor=vendor.vendor,
    name="read_page",
    display_name="Read Notion Page",
    description=(
        "Read a page's content as text. Notion stores it as a tree of blocks "
        "whose text is split into styled runs; this walks the tree and returns "
        "readable markdown, keeping headings, bullets, and to-do state. Nested "
        "content is followed a few levels deep."
    ),
    input_model=ReadPageInput,
    effect=ToolEffect.READ,
)
async def read_page(payload: ReadPageInput, ctx: VendorToolContext) -> dict[str, Any]:
    page_id = _identifier(payload.page_id)
    page = _object((await ctx.read(f"/pages/{page_id}")).data)
    lines = await _block_lines(ctx, page_id, depth=0)
    text = "\n".join(lines).strip()
    return {
        "page_id": page.get("id"),
        "title": _title_of(page),
        "text": text[:MAX_TEXT_CHARS],
        "truncated": len(text) > MAX_TEXT_CHARS,
        "web_link": page.get("url"),
        "last_edited": page.get("last_edited_time"),
    }


@curated_tool(
    vendor=vendor.vendor,
    name="create_page",
    display_name="Create Notion Page",
    description=(
        "Create a page under an existing page or database, optionally with "
        "opening content. Notion sets a title differently depending on which "
        "kind of parent it has; this handles both, so only the parent's id and "
        "kind are needed."
    ),
    input_model=CreatePageInput,
    effect=ToolEffect.MUTATION,
)
async def create_page(
    payload: CreatePageInput, ctx: VendorToolContext
) -> dict[str, Any]:
    parent_id = _identifier(payload.parent_id)
    title_runs = [{"text": {"content": payload.title}}]
    if payload.parent_is_database:
        # A database page's title lives in the database's own title property,
        # which is always named "title" on the API even when displayed
        # otherwise.
        body: dict[str, Any] = {
            "parent": {"database_id": parent_id},
            "properties": {"title": {"title": title_runs}},
        }
    else:
        body = {
            "parent": {"page_id": parent_id},
            "properties": {"title": {"title": title_runs}},
        }
    if payload.body:
        body["children"] = _paragraphs(payload.body)
    created = _object((await ctx.mutate("/pages", json=body)).data)
    return {
        "page_id": created.get("id"),
        "title": _title_of(created),
        "web_link": created.get("url"),
        "body_written": bool(payload.body),
    }


@curated_tool(
    vendor=vendor.vendor,
    name="append_to_page",
    display_name="Append to Notion Page",
    description=(
        "Add text to the end of a page. Each line becomes its own paragraph "
        "block, which is the structure Notion stores; plain text is enough."
    ),
    input_model=AppendToPageInput,
    effect=ToolEffect.MUTATION,
)
async def append_to_page(
    payload: AppendToPageInput, ctx: VendorToolContext
) -> dict[str, Any]:
    page_id = _identifier(payload.page_id)
    blocks = _paragraphs(payload.text)
    response = await ctx.mutate(
        f"/blocks/{page_id}/children",
        method="PATCH",
        json={"children": blocks},
    )
    _object(response.data)
    return {
        "page_id": page_id,
        "blocks_added": len(blocks),
    }


@curated_tool(
    vendor=vendor.vendor,
    name="query_database",
    display_name="Query Notion Database",
    description=(
        "List rows from a database, optionally filtered on one property by "
        "exact match or by containment. Notion's filters are typed per "
        "property, so the property's type is looked up here rather than having "
        "to be known. Each row comes back as plain values."
    ),
    input_model=QueryDatabaseInput,
    effect=ToolEffect.READ,
)
async def query_database(
    payload: QueryDatabaseInput, ctx: VendorToolContext
) -> dict[str, Any]:
    database_id = _identifier(payload.database_id)
    body: dict[str, Any] = {"page_size": payload.limit}

    if payload.property_name:
        if payload.equals is None and payload.contains is None:
            raise VendorToolError(
                "filter_incomplete",
                "Give equals or contains alongside property_name.",
            )
        schema = _object((await ctx.read(f"/databases/{database_id}")).data)
        properties = schema.get("properties") or {}
        definition = properties.get(payload.property_name)
        if not isinstance(definition, dict):
            available = ", ".join(sorted(str(key) for key in properties))
            raise VendorToolError(
                "property_not_found",
                f"No property named '{payload.property_name}'. Available: {available}.",
            )
        body["filter"] = _filter_for(
            payload.property_name,
            str(definition.get("type", "")),
            equals=payload.equals,
            contains=payload.contains,
        )

    response = await ctx.read(
        f"/databases/{database_id}/query", method="POST", json=body
    )
    rows = _results(response.data)
    return {
        "database_id": database_id,
        "rows": [
            {
                "page_id": row.get("id"),
                "web_link": row.get("url"),
                "properties": _flatten_properties(row.get("properties") or {}),
            }
            for row in rows
        ],
        "count": len(rows),
    }


def _filter_for(
    name: str, property_type: str, *, equals: str | None, contains: str | None
) -> dict[str, Any]:
    """Notion's filter body differs per property type; pick the right shape."""
    value = equals if equals is not None else contains
    operator = "equals" if equals is not None else "contains"

    if property_type in {"title", "rich_text", "url", "email", "phone_number"}:
        return {"property": name, property_type: {operator: value}}
    if property_type == "select":
        return {"property": name, "select": {"equals": value}}
    if property_type == "multi_select":
        return {"property": name, "multi_select": {"contains": value}}
    if property_type == "status":
        return {"property": name, "status": {"equals": value}}
    if property_type == "checkbox":
        return {
            "property": name,
            "checkbox": {
                "equals": str(value).strip().casefold() in {"true", "yes", "1"}
            },
        }
    if property_type == "number":
        try:
            return {"property": name, "number": {"equals": float(str(value))}}
        except ValueError as error:
            raise VendorToolError(
                "filter_invalid", f"'{value}' is not a number for property '{name}'."
            ) from error
    raise VendorToolError(
        "filter_unsupported",
        f"Filtering a '{property_type}' property is not supported by this tool.",
    )


async def _block_lines(
    ctx: VendorToolContext, block_id: str, *, depth: int
) -> list[str]:
    """Walk a block subtree, rendering each block's text runs."""
    if depth > _MAX_DEPTH:
        return []
    response = await ctx.read(
        f"/blocks/{block_id}/children", query={"page_size": MAX_BLOCKS}
    )
    lines: list[str] = []
    for block in _results(response.data):
        block_type = str(block.get("type", ""))
        content = block.get(block_type)
        if not isinstance(content, dict):
            continue
        text = _runs_to_text(content.get("rich_text"))
        if block_type == "to_do":
            marker = "[x]" if content.get("checked") else "[ ]"
            text = f"- {marker} {text}"
        else:
            prefix = _BLOCK_PREFIX.get(block_type)
            if prefix is None:
                continue
            text = f"{prefix}{text}"
        indent = "  " * depth
        if text.strip():
            lines.append(f"{indent}{text}")
        if block.get("has_children"):
            lines.extend(await _block_lines(ctx, str(block.get("id")), depth=depth + 1))
    return lines


def _paragraphs(text: str) -> list[dict[str, Any]]:
    """One paragraph block per line, which is how Notion stores prose."""
    lines = [line for line in text.split("\n")]
    return [
        {
            "object": "block",
            "type": "paragraph",
            "paragraph": {"rich_text": [{"text": {"content": line}}] if line else []},
        }
        for line in lines[:MAX_BLOCKS]
    ]


def _runs_to_text(runs: Any) -> str:
    if not isinstance(runs, list):
        return ""
    return "".join(
        str(run.get("plain_text", "")) for run in runs if isinstance(run, dict)
    )


def _title_of(page: dict[str, Any]) -> str | None:
    for value in (page.get("properties") or {}).values():
        if isinstance(value, dict) and value.get("type") == "title":
            text = _runs_to_text(value.get("title"))
            if text:
                return text
    return None


def _flatten_properties(properties: dict[str, Any]) -> dict[str, Any]:
    """Reduce Notion's typed property envelopes to plain values."""
    flat: dict[str, Any] = {}
    for name, value in properties.items():
        if not isinstance(value, dict):
            continue
        kind = str(value.get("type", ""))
        raw = value.get(kind)
        if kind in {"title", "rich_text"}:
            flat[name] = _runs_to_text(raw)
        elif kind == "select":
            flat[name] = (raw or {}).get("name") if isinstance(raw, dict) else None
        elif kind == "status":
            flat[name] = (raw or {}).get("name") if isinstance(raw, dict) else None
        elif kind == "multi_select":
            flat[name] = [
                option.get("name") for option in raw or [] if isinstance(option, dict)
            ]
        elif kind == "people":
            flat[name] = [
                person.get("name") for person in raw or [] if isinstance(person, dict)
            ]
        elif kind == "date":
            flat[name] = (raw or {}).get("start") if isinstance(raw, dict) else None
        elif kind in {"number", "checkbox", "url", "email", "phone_number"}:
            flat[name] = raw
        elif kind == "formula":
            flat[name] = (
                (raw or {}).get(str((raw or {}).get("type", "")))
                if isinstance(raw, dict)
                else None
            )
        else:
            # Unknown types are reported by name rather than dropped silently.
            flat[name] = f"<{kind}>"
    return flat


def _entry_view(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": entry.get("id"),
        "object": entry.get("object"),
        "title": _title_of(entry) or _runs_to_text(entry.get("title")),
        "web_link": entry.get("url"),
        "last_edited": entry.get("last_edited_time"),
    }


def _identifier(value: str) -> str:
    """Accept a bare id, a dashed id, or an id pasted from a Notion URL."""
    candidate = value.strip().rstrip("/")
    if "/" in candidate or "?" in candidate:
        candidate = candidate.split("?", 1)[0].rsplit("/", 1)[-1]
        # A URL slug ends in the id, joined to the title by a final dash.
        if "-" in candidate and len(candidate.rsplit("-", 1)[-1]) == 32:
            candidate = candidate.rsplit("-", 1)[-1]
    if not candidate:
        raise VendorToolError("identifier_invalid", f"'{value}' is not a Notion id.")
    return candidate


def _results(payload: Any) -> list[dict[str, Any]]:
    body = _object(payload)
    return [item for item in body.get("results") or [] if isinstance(item, dict)]


def _object(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise VendorToolError(
            "vendor_response_invalid", "Notion returned a non-object response."
        )
    if payload.get("object") == "error":
        raise VendorToolError(
            "vendor_rejected",
            str(payload.get("message", "Notion rejected the request."))[:500],
        )
    return payload


__all__ = [
    "append_to_page",
    "create_page",
    "query_database",
    "read_page",
    "search",
]
