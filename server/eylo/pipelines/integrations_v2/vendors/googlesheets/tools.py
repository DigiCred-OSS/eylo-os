"""Curated Google Sheets tool implementations for the `integrations_v2` pipeline."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from eylo.modules.integrations_v2.domain.enums import ToolEffect

from ...contracts import VendorToolContext, VendorToolError
from ...registry import curated_tool
from .definition import SPREADSHEETS, vendor

MAX_ROWS = 500
# Values typed by a person are interpreted the same way: "5" becomes a number
# and "=A1+1" becomes a formula, which is what a caller writing a sheet means.
_INPUT_OPTION = "USER_ENTERED"


class ListSheetsInput(BaseModel):
    spreadsheet_id: str = Field(
        min_length=1, description="Spreadsheet id — the long identifier in its URL."
    )


class ReadRowsInput(BaseModel):
    spreadsheet_id: str = Field(min_length=1)
    range: str = Field(
        default="",
        description=(
            "Sheet name, or A1 range such as 'Orders!A1:F50'. Omit to read the "
            "first sheet."
        ),
    )
    as_records: bool = Field(
        default=True,
        description=(
            "Treat the first row as column headers and return each later row "
            "keyed by them. Turn off to get raw positional cells."
        ),
    )
    limit: int = Field(default=100, ge=1, le=MAX_ROWS)


class AppendRowInput(BaseModel):
    spreadsheet_id: str = Field(min_length=1)
    sheet: str = Field(default="", description="Sheet name. Defaults to the first.")
    record: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Values keyed by column header, e.g. {'Name': 'Ana', 'Status': "
            "'Open'}. Missing columns are left blank."
        ),
    )
    values: list[Any] | None = Field(
        default=None,
        description="Positional cell values, used instead of record when given.",
    )


class UpdateCellsInput(BaseModel):
    spreadsheet_id: str = Field(min_length=1)
    range: str = Field(min_length=1, description="A1 range such as 'Orders!B2:C3'.")
    rows: list[list[Any]] = Field(
        min_length=1, description="Rows of cell values, matching the range's shape."
    )


class CreateSpreadsheetInput(BaseModel):
    title: str = Field(min_length=1)
    sheet_names: list[str] | None = Field(
        default=None, description="Names for the initial sheets."
    )
    headers: list[str] | None = Field(
        default=None, description="Header row written into the first sheet."
    )


class AddSheetInput(BaseModel):
    spreadsheet_id: str = Field(min_length=1)
    title: str = Field(min_length=1, description="Name for the new sheet.")


@curated_tool(
    vendor=vendor.vendor,
    name="list_sheets",
    display_name="List Sheets in a Spreadsheet",
    description=(
        "List the sheets (tabs) inside a spreadsheet with their names and "
        "sizes. Other tools accept a sheet name directly, so this is only "
        "needed to discover what exists."
    ),
    input_model=ListSheetsInput,
    effect=ToolEffect.READ,
    scopes=(SPREADSHEETS,),
)
async def list_sheets(
    payload: ListSheetsInput, ctx: VendorToolContext
) -> dict[str, Any]:
    info = await _spreadsheet(ctx, payload.spreadsheet_id)
    sheets = _sheets(info)
    return {
        "spreadsheet_id": payload.spreadsheet_id,
        "title": (info.get("properties") or {}).get("title"),
        "sheets": [
            {
                "name": (sheet.get("properties") or {}).get("title"),
                "sheet_id": (sheet.get("properties") or {}).get("sheetId"),
                "rows": (
                    (sheet.get("properties") or {}).get("gridProperties") or {}
                ).get("rowCount"),
                "columns": (
                    (sheet.get("properties") or {}).get("gridProperties") or {}
                ).get("columnCount"),
            }
            for sheet in sheets
        ],
        "count": len(sheets),
    }


@curated_tool(
    vendor=vendor.vendor,
    name="read_rows",
    display_name="Read Spreadsheet Rows",
    description=(
        "Read rows from a sheet. By default the first row is treated as column "
        "headers and every later row comes back keyed by them, so values are "
        "addressed by name instead of by position. Give a sheet name alone to "
        "read all of it, or an A1 range to read part."
    ),
    input_model=ReadRowsInput,
    effect=ToolEffect.READ,
    scopes=(SPREADSHEETS,),
)
async def read_rows(payload: ReadRowsInput, ctx: VendorToolContext) -> dict[str, Any]:
    target = payload.range.strip() or await _first_sheet_name(
        ctx, payload.spreadsheet_id
    )
    response = await ctx.read(
        f"/spreadsheets/{payload.spreadsheet_id}/values/{_quote(target)}",
        query={"majorDimension": "ROWS"},
    )
    grid = _rows(_object(response.data))
    if not payload.as_records:
        limited = grid[: payload.limit]
        return {"range": target, "rows": limited, "count": len(limited)}

    if not grid:
        return {"range": target, "headers": [], "records": [], "count": 0}
    headers = [str(cell) for cell in grid[0]]
    body = grid[1 : payload.limit + 1]
    records = [
        {
            header: (row[index] if index < len(row) else None)
            for index, header in enumerate(headers)
        }
        for row in body
    ]
    return {
        "range": target,
        "headers": headers,
        "records": records,
        "count": len(records),
        "more_rows_exist": len(grid) - 1 > len(records),
    }


@curated_tool(
    vendor=vendor.vendor,
    name="append_row",
    display_name="Append Spreadsheet Row",
    description=(
        "Add a row to the bottom of a sheet. Give the values keyed by column "
        "header and each one lands in the right column — the header row is "
        "read first, so column order never has to be known. Positional values "
        "may be given instead."
    ),
    input_model=AppendRowInput,
    effect=ToolEffect.MUTATION,
    scopes=(SPREADSHEETS,),
)
async def append_row(payload: AppendRowInput, ctx: VendorToolContext) -> dict[str, Any]:
    if payload.record is None and payload.values is None:
        raise VendorToolError(
            "row_missing", "Give either a record keyed by header, or positional values."
        )
    sheet = payload.sheet.strip() or await _first_sheet_name(
        ctx, payload.spreadsheet_id
    )

    if payload.values is not None:
        row: list[Any] = list(payload.values)
        headers: list[str] = []
        unknown: list[str] = []
    else:
        headers = await _headers(ctx, payload.spreadsheet_id, sheet)
        if not headers:
            raise VendorToolError(
                "headers_missing",
                f"Sheet '{sheet}' has no header row, so a record cannot be placed. "
                "Give positional values instead.",
            )
        wanted = {key.casefold(): value for key, value in payload.record.items()}
        row = [wanted.get(header.casefold()) for header in headers]
        unknown = [
            key
            for key in payload.record
            if key.casefold() not in {header.casefold() for header in headers}
        ]
        if unknown:
            raise VendorToolError(
                "column_not_found",
                f"No column named {', '.join(sorted(unknown))}. "
                f"Columns are: {', '.join(headers)}.",
            )

    response = await ctx.mutate(
        f"/spreadsheets/{payload.spreadsheet_id}/values/{_quote(sheet)}:append",
        json={"values": [row]},
        query={
            "valueInputOption": _INPUT_OPTION,
            "insertDataOption": "INSERT_ROWS",
            "includeValuesInResponse": True,
        },
    )
    result = _object(response.data)
    updates = result.get("updates") or {}
    return {
        "spreadsheet_id": payload.spreadsheet_id,
        "sheet": sheet,
        "updated_range": updates.get("updatedRange"),
        "cells_written": updates.get("updatedCells"),
        "headers": headers,
    }


@curated_tool(
    vendor=vendor.vendor,
    name="update_cells",
    display_name="Update Spreadsheet Cells",
    description=(
        "Overwrite a rectangular range with new values. The rows given must "
        "match the range's shape. Values are interpreted as if typed by a "
        "person, so numbers become numbers and text starting with = becomes a "
        "formula."
    ),
    input_model=UpdateCellsInput,
    effect=ToolEffect.MUTATION,
    scopes=(SPREADSHEETS,),
)
async def update_cells(
    payload: UpdateCellsInput, ctx: VendorToolContext
) -> dict[str, Any]:
    response = await ctx.mutate(
        f"/spreadsheets/{payload.spreadsheet_id}/values/{_quote(payload.range)}",
        method="PUT",
        json={"values": payload.rows},
        query={"valueInputOption": _INPUT_OPTION},
    )
    result = _object(response.data)
    return {
        "spreadsheet_id": payload.spreadsheet_id,
        "updated_range": result.get("updatedRange"),
        "rows_written": result.get("updatedRows"),
        "cells_written": result.get("updatedCells"),
    }


@curated_tool(
    vendor=vendor.vendor,
    name="create_spreadsheet",
    display_name="Create Spreadsheet",
    description=(
        "Create a spreadsheet, optionally naming its sheets and writing a "
        "header row into the first one so it is immediately usable with "
        "append_row. Returns the id and its editing link."
    ),
    input_model=CreateSpreadsheetInput,
    effect=ToolEffect.MUTATION,
    scopes=(SPREADSHEETS,),
)
async def create_spreadsheet(
    payload: CreateSpreadsheetInput, ctx: VendorToolContext
) -> dict[str, Any]:
    body: dict[str, Any] = {"properties": {"title": payload.title}}
    if payload.sheet_names:
        body["sheets"] = [
            {"properties": {"title": name}} for name in payload.sheet_names
        ]
    created = _object((await ctx.mutate("/spreadsheets", json=body)).data)
    spreadsheet_id = str(created.get("spreadsheetId") or "")
    if not spreadsheet_id:
        raise VendorToolError(
            "vendor_response_invalid", "Google did not return a spreadsheet id."
        )

    first = _sheets(created)
    first_name = (first[0].get("properties") or {}).get("title") if first else "Sheet1"
    if payload.headers:
        await ctx.mutate(
            f"/spreadsheets/{spreadsheet_id}/values/{_quote(str(first_name))}!A1",
            method="PUT",
            json={"values": [payload.headers]},
            query={"valueInputOption": _INPUT_OPTION},
        )
    return {
        "spreadsheet_id": spreadsheet_id,
        "title": (created.get("properties") or {}).get("title"),
        "sheets": [(s.get("properties") or {}).get("title") for s in first],
        "web_link": f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit",
        "headers_written": bool(payload.headers),
    }


@curated_tool(
    vendor=vendor.vendor,
    name="add_sheet",
    display_name="Add Sheet to Spreadsheet",
    description="Add a new sheet (tab) to an existing spreadsheet.",
    input_model=AddSheetInput,
    effect=ToolEffect.MUTATION,
    scopes=(SPREADSHEETS,),
)
async def add_sheet(payload: AddSheetInput, ctx: VendorToolContext) -> dict[str, Any]:
    response = await ctx.mutate(
        f"/spreadsheets/{payload.spreadsheet_id}:batchUpdate",
        json={"requests": [{"addSheet": {"properties": {"title": payload.title}}}]},
    )
    result = _object(response.data)
    replies = [r for r in result.get("replies") or [] if isinstance(r, dict)]
    properties = (replies[0].get("addSheet") or {}).get("properties") if replies else {}
    return {
        "spreadsheet_id": payload.spreadsheet_id,
        "sheet": (properties or {}).get("title", payload.title),
        "sheet_id": (properties or {}).get("sheetId"),
    }


async def _spreadsheet(ctx: VendorToolContext, spreadsheet_id: str) -> dict[str, Any]:
    response = await ctx.read(
        f"/spreadsheets/{spreadsheet_id}",
        query={"fields": "properties.title,sheets.properties"},
    )
    return _object(response.data)


async def _first_sheet_name(ctx: VendorToolContext, spreadsheet_id: str) -> str:
    sheets = _sheets(await _spreadsheet(ctx, spreadsheet_id))
    if not sheets:
        raise VendorToolError("sheet_missing", "This spreadsheet has no sheets.")
    return str((sheets[0].get("properties") or {}).get("title") or "Sheet1")


async def _headers(
    ctx: VendorToolContext, spreadsheet_id: str, sheet: str
) -> list[str]:
    """The sheet's first row, which is what makes records addressable by name."""
    response = await ctx.read(
        f"/spreadsheets/{spreadsheet_id}/values/{_quote(sheet)}!1:1"
    )
    rows = _rows(_object(response.data))
    return [str(cell) for cell in rows[0]] if rows else []


def _quote(value: str) -> str:
    """A1 ranges travel in the path, so a sheet name with a space must encode."""
    return (
        value.replace("%", "%25")
        .replace(" ", "%20")
        .replace("#", "%23")
        .replace("?", "%3F")
    )


def _rows(payload: dict[str, Any]) -> list[list[Any]]:
    values = payload.get("values")
    if not isinstance(values, list):
        return []
    return [row for row in values if isinstance(row, list)]


def _sheets(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return [sheet for sheet in payload.get("sheets") or [] if isinstance(sheet, dict)]


def _object(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise VendorToolError(
            "vendor_response_invalid", "Google Sheets returned a non-object response."
        )
    error = payload.get("error")
    if isinstance(error, dict):
        raise VendorToolError(
            "vendor_rejected",
            str(error.get("message", "Google rejected the request."))[:500],
        )
    return payload


__all__ = [
    "add_sheet",
    "append_row",
    "create_spreadsheet",
    "list_sheets",
    "read_rows",
    "update_cells",
]
