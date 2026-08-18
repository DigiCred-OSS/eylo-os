"""Curated Google Drive tool implementations for the `integrations_v2` pipeline."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from eylo.modules.integrations_v2.domain.enums import ToolEffect

from ...contracts import VendorToolContext, VendorToolError
from ...registry import curated_tool
from .definition import DRIVE, vendor

FOLDER_MIME = "application/vnd.google-apps.folder"
_FILE_FIELDS = (
    "id,name,mimeType,modifiedTime,createdTime,size,webViewLink,parents,"
    "owners(emailAddress,displayName),trashed"
)
_LIST_FIELDS = f"files({_FILE_FIELDS}),nextPageToken"

# Friendly type names an agent can reason about, mapped to what Drive stores.
_TYPE_CLAUSES = {
    "document": "mimeType = 'application/vnd.google-apps.document'",
    "spreadsheet": "mimeType = 'application/vnd.google-apps.spreadsheet'",
    "presentation": "mimeType = 'application/vnd.google-apps.presentation'",
    "form": "mimeType = 'application/vnd.google-apps.form'",
    "folder": f"mimeType = '{FOLDER_MIME}'",
    "pdf": "mimeType = 'application/pdf'",
    "image": "mimeType contains 'image/'",
    "video": "mimeType contains 'video/'",
}
_ROLES = ("reader", "commenter", "writer")


class SearchFilesInput(BaseModel):
    name_contains: str | None = Field(
        default=None, description="Match files whose name contains this text."
    )
    file_type: str | None = Field(
        default=None,
        description=(
            "One of document, spreadsheet, presentation, form, folder, pdf, "
            "image, video. Omit for any type."
        ),
    )
    in_folder: str | None = Field(
        default=None, description="Folder id, or a folder name to resolve."
    )
    modified_after: str | None = Field(
        default=None, description="ISO 8601 timestamp; only newer files match."
    )
    shared_with_me: bool = Field(default=False)
    limit: int = Field(default=25, ge=1, le=100)


class GetFileInput(BaseModel):
    file_id: str = Field(min_length=1)


class CreateFolderInput(BaseModel):
    name: str = Field(min_length=1)
    parent: str | None = Field(
        default=None, description="Parent folder id or name. Defaults to My Drive."
    )


class ShareFileInput(BaseModel):
    file_id: str = Field(min_length=1)
    email: str | None = Field(
        default=None,
        description="Person to share with. Required unless sharing by link.",
    )
    role: str = Field(default="reader", description="One of reader, commenter, writer.")
    anyone_with_link: bool = Field(
        default=False,
        description=(
            "Make the file readable by anyone holding the link. This exposes "
            "it outside the organization, so it defaults to off."
        ),
    )
    notify: bool = Field(default=True, description="Send Google's notification email.")


class MoveFileInput(BaseModel):
    file_id: str = Field(min_length=1)
    destination_folder: str = Field(
        min_length=1, description="Destination folder id or name."
    )


class TrashFileInput(BaseModel):
    file_id: str = Field(min_length=1)


@curated_tool(
    vendor=vendor.vendor,
    name="search_files",
    display_name="Search Google Drive",
    description=(
        "Find files and folders by name, type, containing folder, or "
        "modification date, without writing Drive query syntax. A folder may "
        "be named rather than identified. Results include the web link, owner, "
        "and modification time, so a follow-up lookup is rarely needed. "
        "Trashed files are excluded."
    ),
    input_model=SearchFilesInput,
    effect=ToolEffect.READ,
    scopes=(DRIVE,),
)
async def search_files(
    payload: SearchFilesInput, ctx: VendorToolContext
) -> dict[str, Any]:
    clauses = ["trashed = false"]
    if payload.name_contains:
        clauses.append(f"name contains '{_escape(payload.name_contains)}'")
    if payload.file_type:
        clause = _TYPE_CLAUSES.get(payload.file_type.strip().casefold())
        if clause is None:
            raise VendorToolError(
                "file_type_unknown",
                f"Unknown file_type. Use one of: {', '.join(sorted(_TYPE_CLAUSES))}.",
            )
        clauses.append(clause)
    if payload.in_folder:
        folder_id = await _resolve_folder(ctx, payload.in_folder)
        clauses.append(f"'{_escape(folder_id)}' in parents")
    if payload.modified_after:
        clauses.append(f"modifiedTime > '{_escape(payload.modified_after)}'")
    if payload.shared_with_me:
        clauses.append("sharedWithMe = true")

    response = await ctx.read(
        "/files",
        query={
            "q": " and ".join(clauses),
            "pageSize": payload.limit,
            "fields": _LIST_FIELDS,
            "orderBy": "modifiedTime desc",
            "supportsAllDrives": True,
            "includeItemsFromAllDrives": True,
        },
    )
    files = _files(response.data)
    return {
        "files": [_file_view(item) for item in files],
        "count": len(files),
        "query": " and ".join(clauses),
    }


@curated_tool(
    vendor=vendor.vendor,
    name="get_file",
    display_name="Get Google Drive File",
    description=(
        "Look up one file or folder's details: name, type, size, owner, "
        "parents, and web link. Use the Google Docs or Google Sheets tools to "
        "read what is inside a document."
    ),
    input_model=GetFileInput,
    effect=ToolEffect.READ,
    scopes=(DRIVE,),
)
async def get_file(payload: GetFileInput, ctx: VendorToolContext) -> dict[str, Any]:
    response = await ctx.read(
        f"/files/{payload.file_id}",
        query={"fields": _FILE_FIELDS, "supportsAllDrives": True},
    )
    return _file_view(_object(response.data))


@curated_tool(
    vendor=vendor.vendor,
    name="create_folder",
    display_name="Create Google Drive Folder",
    description=(
        "Create a folder, optionally inside another folder named rather than "
        "identified. Returns the new folder's id and web link."
    ),
    input_model=CreateFolderInput,
    effect=ToolEffect.MUTATION,
    scopes=(DRIVE,),
)
async def create_folder(
    payload: CreateFolderInput, ctx: VendorToolContext
) -> dict[str, Any]:
    body: dict[str, Any] = {"name": payload.name, "mimeType": FOLDER_MIME}
    if payload.parent:
        body["parents"] = [await _resolve_folder(ctx, payload.parent)]
    response = await ctx.mutate(
        "/files",
        json=body,
        query={"fields": _FILE_FIELDS, "supportsAllDrives": True},
    )
    return _file_view(_object(response.data))


@curated_tool(
    vendor=vendor.vendor,
    name="share_file",
    display_name="Share Google Drive File",
    description=(
        "Grant access to a file or folder. Give an email address and a role of "
        "reader, commenter, or writer. Setting anyone_with_link instead makes "
        "the file readable by anyone who has the link, including people "
        "outside the organization."
    ),
    input_model=ShareFileInput,
    effect=ToolEffect.MUTATION,
    scopes=(DRIVE,),
)
async def share_file(payload: ShareFileInput, ctx: VendorToolContext) -> dict[str, Any]:
    role = payload.role.strip().casefold()
    if role not in _ROLES:
        raise VendorToolError(
            "role_invalid", f"Role must be one of: {', '.join(_ROLES)}."
        )
    if payload.anyone_with_link:
        body: dict[str, Any] = {"type": "anyone", "role": "reader"}
    elif payload.email:
        body = {"type": "user", "role": role, "emailAddress": payload.email}
    else:
        raise VendorToolError(
            "recipient_missing",
            "Give an email address, or set anyone_with_link to share by link.",
        )
    response = await ctx.mutate(
        f"/files/{payload.file_id}/permissions",
        json=body,
        query={
            "sendNotificationEmail": payload.notify and not payload.anyone_with_link,
            "supportsAllDrives": True,
            "fields": "id,type,role,emailAddress",
        },
    )
    granted = _object(response.data)
    return {
        "file_id": payload.file_id,
        "permission_id": granted.get("id"),
        "granted_to": granted.get("emailAddress") or granted.get("type"),
        "role": granted.get("role"),
        "public_link": bool(payload.anyone_with_link),
    }


@curated_tool(
    vendor=vendor.vendor,
    name="move_file",
    display_name="Move Google Drive File",
    description=(
        "Move a file or folder into another folder. Drive models this as "
        "editing the file's parent list, so this reads the current parents and "
        "swaps them in one step. The destination may be named rather than "
        "identified."
    ),
    input_model=MoveFileInput,
    effect=ToolEffect.MUTATION,
    scopes=(DRIVE,),
)
async def move_file(payload: MoveFileInput, ctx: VendorToolContext) -> dict[str, Any]:
    destination = await _resolve_folder(ctx, payload.destination_folder)
    current = _object(
        (
            await ctx.read(
                f"/files/{payload.file_id}",
                query={"fields": "id,name,parents", "supportsAllDrives": True},
            )
        ).data
    )
    previous = [str(parent) for parent in current.get("parents") or []]
    response = await ctx.mutate(
        f"/files/{payload.file_id}",
        method="PATCH",
        json={},
        query={
            "addParents": destination,
            "removeParents": ",".join(previous),
            "fields": _FILE_FIELDS,
            "supportsAllDrives": True,
        },
    )
    view = _file_view(_object(response.data))
    view["moved_from"] = previous
    return view


@curated_tool(
    vendor=vendor.vendor,
    name="trash_file",
    display_name="Move Google Drive File to Trash",
    description=(
        "Move a file or folder to Drive's trash, where it stays recoverable "
        "for thirty days. Permanent deletion is not offered."
    ),
    input_model=TrashFileInput,
    effect=ToolEffect.MUTATION,
    scopes=(DRIVE,),
)
async def trash_file(payload: TrashFileInput, ctx: VendorToolContext) -> dict[str, Any]:
    response = await ctx.mutate(
        f"/files/{payload.file_id}",
        method="PATCH",
        json={"trashed": True},
        query={"fields": "id,name,trashed", "supportsAllDrives": True},
    )
    trashed = _object(response.data)
    return {
        "file_id": trashed.get("id"),
        "name": trashed.get("name"),
        "trashed": bool(trashed.get("trashed")),
        "recoverable_for_days": 30,
    }


async def _resolve_folder(ctx: VendorToolContext, folder: str) -> str:
    """Accept a folder id or a folder name, so callers need not look ids up."""
    candidate = folder.strip()
    if not candidate:
        raise VendorToolError("folder_missing", "A folder id or name is required.")
    if candidate.casefold() in {"root", "my drive", "mydrive"}:
        return "root"
    # Drive ids contain no spaces and are long; a name lookup is the fallback.
    response = await ctx.read(
        "/files",
        query={
            "q": (
                f"mimeType = '{FOLDER_MIME}' and trashed = false "
                f"and name = '{_escape(candidate)}'"
            ),
            "pageSize": 2,
            "fields": "files(id,name)",
            "supportsAllDrives": True,
            "includeItemsFromAllDrives": True,
        },
    )
    matches = _files(response.data)
    if len(matches) == 1:
        return str(matches[0]["id"])
    if len(matches) > 1:
        raise VendorToolError(
            "folder_ambiguous",
            f"More than one folder is named '{folder}'. Give its id instead.",
        )
    if " " in candidate:
        raise VendorToolError(
            "folder_not_found", f"No folder named '{folder}' is visible."
        )
    return candidate


def _escape(value: str) -> str:
    """Drive query literals are single-quoted, so quotes and backslashes escape."""
    return value.replace("\\", "\\\\").replace("'", "\\'")


def _file_view(item: dict[str, Any]) -> dict[str, Any]:
    owners = [o for o in item.get("owners") or [] if isinstance(o, dict)]
    mime = str(item.get("mimeType", ""))
    return {
        "id": item.get("id"),
        "name": item.get("name"),
        "mime_type": mime,
        "is_folder": mime == FOLDER_MIME,
        "size_bytes": item.get("size"),
        "modified_at": item.get("modifiedTime"),
        "created_at": item.get("createdTime"),
        "web_link": item.get("webViewLink"),
        "parents": item.get("parents") or [],
        "owner": owners[0].get("emailAddress") if owners else None,
    }


def _files(payload: Any) -> list[dict[str, Any]]:
    body = _object(payload)
    return [item for item in body.get("files", []) or [] if isinstance(item, dict)]


def _object(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise VendorToolError(
            "vendor_response_invalid", "Google Drive returned a non-object response."
        )
    error = payload.get("error")
    if isinstance(error, dict):
        raise VendorToolError(
            "vendor_rejected",
            str(error.get("message", "Google rejected the request."))[:500],
        )
    return payload


__all__ = [
    "create_folder",
    "get_file",
    "move_file",
    "search_files",
    "share_file",
    "trash_file",
]
