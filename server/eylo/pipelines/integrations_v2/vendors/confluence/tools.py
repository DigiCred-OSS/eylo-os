"""Curated Confluence tool implementations for the `integrations_v2` pipeline."""

from __future__ import annotations

import html
import re
from typing import Any

from pydantic import BaseModel, Field

from eylo.modules.integrations_v2.domain.enums import ToolEffect

from ...contracts import VendorToolContext, VendorToolError
from ...registry import curated_tool
from .definition import READ_CONTENT, READ_SPACE, WRITE_CONTENT, vendor

V2 = "/api/v2"
SEARCH = "/rest/api/search"
_TAG = re.compile(r"<[^>]+>")


class SearchPagesInput(BaseModel):
    text: str | None = Field(
        default=None, description="Free text matched against page title and body."
    )
    space_key: str | None = Field(
        default=None, description="Restrict to one space by key, such as ENG."
    )
    title: str | None = Field(default=None, description="Exact page title.")
    cql: str | None = Field(
        default=None, description="Raw CQL. Overrides the simple filters."
    )
    limit: int = Field(default=25, ge=1, le=100)


class GetPageInput(BaseModel):
    page_id: str = Field(min_length=1, description="Numeric page id.")


class CreatePageInput(BaseModel):
    space_key: str = Field(min_length=1, description="Space key such as ENG.")
    title: str = Field(min_length=1, description="Page title.")
    body: str = Field(default="", description="Page body as plain text.")
    parent_page_id: str | None = Field(
        default=None, description="Create as a child of this page."
    )


class UpdatePageInput(BaseModel):
    page_id: str = Field(min_length=1, description="Numeric page id.")
    body: str = Field(min_length=1, description="Replacement body as plain text.")
    title: str | None = Field(default=None, description="New title, if changing it.")


class ListSpacesInput(BaseModel):
    query: str | None = Field(default=None, description="Filter on space name or key.")
    limit: int = Field(default=50, ge=1, le=250)


@curated_tool(
    vendor=vendor.vendor,
    name="list_spaces",
    display_name="List Confluence Spaces",
    description=(
        "List Confluence spaces with their keys and names. Other tools accept a "
        "space key directly, so this is only needed to discover what exists."
    ),
    input_model=ListSpacesInput,
    effect=ToolEffect.READ,
    scopes=(READ_SPACE,),
)
async def list_spaces(
    payload: ListSpacesInput, ctx: VendorToolContext
) -> dict[str, Any]:
    response = await ctx.read(f"{V2}/spaces", query={"limit": payload.limit})
    spaces = _results(response.data)
    needle = (payload.query or "").strip().casefold()
    matched = [
        space
        for space in spaces
        if not needle
        or needle in str(space.get("name", "")).casefold()
        or needle in str(space.get("key", "")).casefold()
    ]
    return {
        "spaces": [
            {
                "id": space.get("id"),
                "key": space.get("key"),
                "name": space.get("name"),
                "type": space.get("type"),
            }
            for space in matched
        ],
        "count": len(matched),
    }


@curated_tool(
    vendor=vendor.vendor,
    name="search_pages",
    display_name="Search Confluence Pages",
    description=(
        "Search Confluence pages. Supply raw CQL, or use the simple filters "
        "(free text, space key, exact title) and the CQL is built for you. "
        "Returns titles, spaces, and links without needing a second fetch."
    ),
    input_model=SearchPagesInput,
    effect=ToolEffect.READ,
    scopes=(READ_CONTENT,),
)
async def search_pages(
    payload: SearchPagesInput, ctx: VendorToolContext
) -> dict[str, Any]:
    cql = payload.cql.strip() if payload.cql else _build_cql(payload)
    if not cql:
        raise VendorToolError(
            "search_too_broad",
            "Supply CQL or at least one filter; an unbounded search is refused.",
        )
    response = await ctx.read(SEARCH, query={"cql": cql, "limit": payload.limit})
    results = _object(response.data).get("results") or []
    pages = [entry for entry in results if isinstance(entry, dict)]
    return {
        "cql": cql,
        "pages": [
            {
                "id": (entry.get("content") or {}).get("id"),
                "title": entry.get("title")
                or (entry.get("content") or {}).get("title"),
                "space": ((entry.get("resultGlobalContainer") or {}).get("title")),
                "excerpt": _plain_text(entry.get("excerpt")),
                "last_modified": entry.get("lastModified"),
            }
            for entry in pages
        ],
        "count": len(pages),
    }


@curated_tool(
    vendor=vendor.vendor,
    name="get_page",
    display_name="Get Confluence Page",
    description=(
        "Read one Confluence page by id. The body is returned as plain text "
        "rather than storage-format markup, so it can be quoted directly."
    ),
    input_model=GetPageInput,
    effect=ToolEffect.READ,
    scopes=(READ_CONTENT,),
)
async def get_page(payload: GetPageInput, ctx: VendorToolContext) -> dict[str, Any]:
    response = await ctx.read(
        f"{V2}/pages/{payload.page_id}", query={"body-format": "storage"}
    )
    return _page_view(_object(response.data))


@curated_tool(
    vendor=vendor.vendor,
    name="create_page",
    display_name="Create Confluence Page",
    description=(
        "Create a Confluence page in a space named by its key, such as ENG. "
        "The space id is resolved automatically and the body is converted from "
        "plain text to storage format."
    ),
    input_model=CreatePageInput,
    effect=ToolEffect.MUTATION,
    scopes=(WRITE_CONTENT, READ_SPACE),
)
async def create_page(
    payload: CreatePageInput, ctx: VendorToolContext
) -> dict[str, Any]:
    space_id = await _resolve_space_id(ctx, payload.space_key)
    body: dict[str, Any] = {
        "spaceId": space_id,
        "status": "current",
        "title": payload.title,
        "body": _text_to_storage(payload.body),
    }
    if payload.parent_page_id:
        body["parentId"] = payload.parent_page_id
    response = await ctx.mutate(f"{V2}/pages", method="POST", json=body)
    return _page_view(_object(response.data))


@curated_tool(
    vendor=vendor.vendor,
    name="update_page",
    display_name="Update Confluence Page",
    description=(
        "Replace the body of a Confluence page, and optionally its title. The "
        "current version is read and incremented automatically, which "
        "Confluence requires and rejects the edit without."
    ),
    input_model=UpdatePageInput,
    effect=ToolEffect.MUTATION,
    scopes=(WRITE_CONTENT, READ_CONTENT),
)
async def update_page(
    payload: UpdatePageInput, ctx: VendorToolContext
) -> dict[str, Any]:
    current = _object((await ctx.read(f"{V2}/pages/{payload.page_id}")).data)
    version = current.get("version") or {}
    number = version.get("number")
    if not isinstance(number, int):
        raise VendorToolError(
            "page_version_unknown",
            "Confluence did not report the page's current version.",
        )
    response = await ctx.mutate(
        f"{V2}/pages/{payload.page_id}",
        method="PUT",
        json={
            "id": payload.page_id,
            "status": "current",
            "title": payload.title or current.get("title"),
            "body": _text_to_storage(payload.body),
            "version": {"number": number + 1},
        },
    )
    return _page_view(_object(response.data))


async def _resolve_space_id(ctx: VendorToolContext, space_key: str) -> str:
    wanted = space_key.strip()
    response = await ctx.read(f"{V2}/spaces", query={"keys": wanted, "limit": 2})
    spaces = _results(response.data)
    for space in spaces:
        if str(space.get("key", "")).casefold() == wanted.casefold():
            return str(space["id"])
    raise VendorToolError(
        "space_not_found", f"No Confluence space with key '{space_key}'."
    )


def _build_cql(payload: SearchPagesInput) -> str:
    clauses = ["type = page"]
    if payload.space_key:
        clauses.append(f'space = "{payload.space_key.strip().upper()}"')
    if payload.title:
        clauses.append(f'title = "{payload.title.strip()}"')
    if payload.text:
        clauses.append(f'text ~ "{payload.text.strip()}"')
    if len(clauses) == 1:
        return ""
    return " AND ".join(clauses) + " ORDER BY lastmodified DESC"


def _page_view(page: dict[str, Any]) -> dict[str, Any]:
    version = page.get("version") or {}
    return {
        "id": page.get("id"),
        "title": page.get("title"),
        "space_id": page.get("spaceId"),
        "status": page.get("status"),
        "version": version.get("number"),
        "body": _plain_text(
            ((page.get("body") or {}).get("storage") or {}).get("value")
        ),
        "link": ((page.get("_links") or {}).get("webui")),
    }


def _text_to_storage(text: str) -> dict[str, Any]:
    """Convert plain text into Confluence storage format.

    Escaped before wrapping: storage format is XHTML, so an unescaped `<` in
    user text would either break the document or inject markup.
    """
    paragraphs = [
        f"<p>{html.escape(line)}</p>" if line.strip() else "<p />"
        for line in text.split("\n")
    ]
    return {"representation": "storage", "value": "".join(paragraphs) or "<p />"}


def _plain_text(markup: Any) -> str | None:
    """Flatten storage-format or excerpt markup back to readable text."""
    if not isinstance(markup, str):
        return None
    stripped = _TAG.sub(" ", markup)
    return re.sub(r"\s+", " ", html.unescape(stripped)).strip() or None


def _results(payload: Any) -> list[dict[str, Any]]:
    body = _object(payload)
    return [item for item in body.get("results", []) or [] if isinstance(item, dict)]


def _object(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise VendorToolError(
            "vendor_response_invalid", "Confluence returned a non-object response."
        )
    errors = payload.get("errors")
    if isinstance(errors, list) and errors:
        first = errors[0] if isinstance(errors[0], dict) else {}
        raise VendorToolError(
            "vendor_rejected",
            str(
                first.get("title")
                or first.get("detail")
                or "Confluence rejected the request."
            )[:500],
        )
    return payload


__all__ = [
    "create_page",
    "get_page",
    "list_spaces",
    "search_pages",
    "update_page",
]
