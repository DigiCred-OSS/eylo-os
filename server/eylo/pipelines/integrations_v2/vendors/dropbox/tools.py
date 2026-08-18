"""Curated Dropbox tool implementations for the `integrations_v2` pipeline."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from eylo.modules.integrations_v2.domain.enums import ToolEffect

from ...contracts import VendorToolContext, VendorToolError
from ...registry import curated_tool
from .definition import FILES_READ, FILES_WRITE, SHARING_WRITE, vendor

MAX_RESULTS = 100


class ListFolderInput(BaseModel):
    path: str = Field(
        default="/", description="Folder path, e.g. /Work. Use / for the root."
    )
    recursive: bool = Field(default=False)
    limit: int = Field(default=50, ge=1, le=MAX_RESULTS)


class SearchFilesInput(BaseModel):
    query: str = Field(min_length=1, description="Text to match in file names.")
    path: str = Field(default="/", description="Folder to search within.")
    file_extensions: list[str] | None = Field(
        default=None, description="Limit to these extensions, e.g. ['pdf', 'docx']."
    )
    limit: int = Field(default=25, ge=1, le=MAX_RESULTS)


class CreateFolderInput(BaseModel):
    path: str = Field(min_length=1, description="Full path of the new folder.")


class MoveInput(BaseModel):
    from_path: str = Field(min_length=1)
    to_path: str = Field(min_length=1, description="Including the new name.")


class ShareInput(BaseModel):
    path: str = Field(min_length=1, description="File or folder to share.")


class DeleteInput(BaseModel):
    path: str = Field(min_length=1)


@curated_tool(
    vendor=vendor.vendor,
    name="list_folder",
    display_name="List Dropbox Folder",
    description=(
        "List what is in a folder. Use / for the root — Dropbox itself needs "
        "an empty string there, which is handled here. Each entry says whether "
        "it is a file or a folder, and files report their size and when they "
        "changed."
    ),
    input_model=ListFolderInput,
    effect=ToolEffect.READ,
    scopes=(FILES_READ,),
)
async def list_folder(
    payload: ListFolderInput, ctx: VendorToolContext
) -> dict[str, Any]:
    response = await ctx.read(
        "/files/list_folder",
        method="POST",
        json={
            "path": _path(payload.path),
            "recursive": payload.recursive,
            "limit": payload.limit,
        },
    )
    body = _object(response.data)
    entries = [e for e in body.get("entries") or [] if isinstance(e, dict)]
    return {
        "path": payload.path,
        "entries": [_entry_view(entry) for entry in entries],
        "count": len(entries),
        "more_available": bool(body.get("has_more")),
    }


@curated_tool(
    vendor=vendor.vendor,
    name="search_files",
    display_name="Search Dropbox",
    description=(
        "Find files and folders by name, optionally within a folder and "
        "limited to certain extensions. Dropbox buries the real entry two "
        "levels inside each result; this returns them flattened."
    ),
    input_model=SearchFilesInput,
    effect=ToolEffect.READ,
    scopes=(FILES_READ,),
)
async def search_files(
    payload: SearchFilesInput, ctx: VendorToolContext
) -> dict[str, Any]:
    options: dict[str, Any] = {
        "path": _path(payload.path),
        "max_results": payload.limit,
        "filename_only": True,
    }
    if payload.file_extensions:
        options["file_extensions"] = [
            extension.lstrip(".").casefold() for extension in payload.file_extensions
        ]
    response = await ctx.read(
        "/files/search_v2",
        method="POST",
        json={"query": payload.query, "options": options},
    )
    body = _object(response.data)
    matches = [m for m in body.get("matches") or [] if isinstance(m, dict)]
    entries = []
    for match in matches:
        # Dropbox wraps the entry twice: matches[].metadata.metadata.
        wrapper = match.get("metadata")
        inner = wrapper.get("metadata") if isinstance(wrapper, dict) else None
        if isinstance(inner, dict):
            entries.append(_entry_view(inner))
    return {"results": entries, "count": len(entries), "query": payload.query}


@curated_tool(
    vendor=vendor.vendor,
    name="create_folder",
    display_name="Create Dropbox Folder",
    description=(
        "Create a folder at the given path. Parent folders are created as "
        "needed. If the name is taken, Dropbox is asked to pick a free one "
        "rather than failing."
    ),
    input_model=CreateFolderInput,
    effect=ToolEffect.MUTATION,
    scopes=(FILES_WRITE,),
)
async def create_folder(
    payload: CreateFolderInput, ctx: VendorToolContext
) -> dict[str, Any]:
    response = await ctx.mutate(
        "/files/create_folder_v2",
        json={"path": _path(payload.path), "autorename": True},
    )
    metadata = _object(response.data).get("metadata") or {}
    return _entry_view(metadata if isinstance(metadata, dict) else {})


@curated_tool(
    vendor=vendor.vendor,
    name="move",
    display_name="Move or Rename in Dropbox",
    description=(
        "Move a file or folder to a new path. Renaming is the same operation "
        "with a new final path segment. The destination path must include the "
        "name, not just the folder."
    ),
    input_model=MoveInput,
    effect=ToolEffect.MUTATION,
    scopes=(FILES_WRITE,),
)
async def move(payload: MoveInput, ctx: VendorToolContext) -> dict[str, Any]:
    response = await ctx.mutate(
        "/files/move_v2",
        json={
            "from_path": _path(payload.from_path),
            "to_path": _path(payload.to_path),
            "autorename": True,
        },
    )
    metadata = _object(response.data).get("metadata") or {}
    view = _entry_view(metadata if isinstance(metadata, dict) else {})
    view["moved_from"] = payload.from_path
    return view


@curated_tool(
    vendor=vendor.vendor,
    name="create_share_link",
    display_name="Create Dropbox Share Link",
    description=(
        "Get a shareable link for a file or folder. Dropbox refuses to create "
        "a second link when one already exists, so an existing link is "
        "returned instead of failing — which is what the caller wanted either "
        "way. The link is viewable by anyone who has it."
    ),
    input_model=ShareInput,
    effect=ToolEffect.MUTATION,
    scopes=(SHARING_WRITE,),
)
async def create_share_link(
    payload: ShareInput, ctx: VendorToolContext
) -> dict[str, Any]:
    path = _path(payload.path)
    try:
        response = await ctx.mutate(
            "/sharing/create_shared_link_with_settings", json={"path": path}
        )
        link = _object(response.data)
    except VendorToolError as error:
        if "shared_link_already_exists" not in str(error):
            raise
        existing = await ctx.read(
            "/sharing/list_shared_links",
            method="POST",
            json={"path": path, "direct_only": True},
        )
        links = [
            item
            for item in _object(existing.data).get("links") or []
            if isinstance(item, dict)
        ]
        if not links:
            raise
        link = links[0]
    return {
        "path": payload.path,
        "url": link.get("url"),
        "name": link.get("name"),
        "visibility": (
            (link.get("link_permissions") or {}).get("resolved_visibility") or {}
        ).get(".tag"),
    }


@curated_tool(
    vendor=vendor.vendor,
    name="delete",
    display_name="Delete from Dropbox",
    description=(
        "Move a file or folder to Dropbox's deleted items, where it stays "
        "restorable for thirty days on a standard account. Permanent deletion "
        "is not offered."
    ),
    input_model=DeleteInput,
    effect=ToolEffect.MUTATION,
    scopes=(FILES_WRITE,),
)
async def delete(payload: DeleteInput, ctx: VendorToolContext) -> dict[str, Any]:
    response = await ctx.mutate("/files/delete_v2", json={"path": _path(payload.path)})
    metadata = _object(response.data).get("metadata") or {}
    view = _entry_view(metadata if isinstance(metadata, dict) else {})
    view["deleted"] = True
    view["recoverable_for_days"] = 30
    return view


def _path(value: str) -> str:
    """Dropbox addresses the root as an empty string, never as "/"."""
    candidate = value.strip()
    if candidate in {"", "/"}:
        return ""
    if not candidate.startswith("/"):
        candidate = f"/{candidate}"
    return candidate.rstrip("/") or ""


def _entry_view(entry: dict[str, Any]) -> dict[str, Any]:
    kind = str(entry.get(".tag", ""))
    return {
        "name": entry.get("name"),
        "path": entry.get("path_display") or entry.get("path_lower"),
        "id": entry.get("id"),
        "is_folder": kind == "folder",
        "size_bytes": entry.get("size"),
        "modified_at": entry.get("server_modified"),
        "revision": entry.get("rev"),
    }


def _object(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise VendorToolError(
            "vendor_response_invalid", "Dropbox returned a non-object response."
        )
    # Dropbox reports failures as {"error_summary": "...", "error": {...}}.
    summary = payload.get("error_summary")
    if isinstance(summary, str) and summary:
        raise VendorToolError("vendor_rejected", summary[:500])
    return payload


__all__ = [
    "create_folder",
    "create_share_link",
    "delete",
    "list_folder",
    "move",
    "search_files",
]
