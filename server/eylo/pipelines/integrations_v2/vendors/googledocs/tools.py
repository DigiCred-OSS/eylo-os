"""Curated Google Docs tool implementations for the `integrations_v2` pipeline."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from eylo.modules.integrations_v2.domain.enums import ToolEffect

from ...contracts import VendorToolContext, VendorToolError
from ...registry import curated_tool
from .definition import DOCUMENTS, vendor

MAX_TEXT_CHARS = 20_000
_HEADING_PREFIX = {
    "TITLE": "# ",
    "HEADING_1": "# ",
    "HEADING_2": "## ",
    "HEADING_3": "### ",
    "HEADING_4": "#### ",
    "HEADING_5": "##### ",
    "HEADING_6": "###### ",
}


class ReadDocumentInput(BaseModel):
    document_id: str = Field(
        min_length=1,
        description="Document id — the long identifier in its URL, or from Drive search.",
    )


class CreateDocumentInput(BaseModel):
    title: str = Field(min_length=1)
    body: str | None = Field(
        default=None, description="Opening content. Written immediately after creation."
    )


class AppendTextInput(BaseModel):
    document_id: str = Field(min_length=1)
    text: str = Field(min_length=1, description="Text to add at the end.")
    start_on_new_line: bool = Field(
        default=True, description="Begin with a line break so it does not run on."
    )


class ReplaceTextInput(BaseModel):
    document_id: str = Field(min_length=1)
    find: str = Field(min_length=1, description="Exact text to look for.")
    replace_with: str = Field(description="Replacement text. Empty removes the match.")
    match_case: bool = Field(default=True)


@curated_tool(
    vendor=vendor.vendor,
    name="read_document",
    display_name="Read Google Doc",
    description=(
        "Read a document's full text. The API returns a nested structure of "
        "paragraphs and text runs; this flattens it into readable text, marks "
        "headings with # prefixes so the outline survives, and includes table "
        "contents. Long documents are truncated and marked as such."
    ),
    input_model=ReadDocumentInput,
    effect=ToolEffect.READ,
    scopes=(DOCUMENTS,),
)
async def read_document(
    payload: ReadDocumentInput, ctx: VendorToolContext
) -> dict[str, Any]:
    document = _object((await ctx.read(f"/documents/{payload.document_id}")).data)
    text = _flatten(document)
    return {
        "document_id": document.get("documentId"),
        "title": document.get("title"),
        "text": text[:MAX_TEXT_CHARS],
        "truncated": len(text) > MAX_TEXT_CHARS,
        "character_count": len(text),
    }


@curated_tool(
    vendor=vendor.vendor,
    name="create_document",
    display_name="Create Google Doc",
    description=(
        "Create a document, optionally with its opening content already "
        "written. Google's API cannot accept content at creation time, so this "
        "creates the document and writes the body in one step. Returns the id "
        "and its editing link."
    ),
    input_model=CreateDocumentInput,
    effect=ToolEffect.MUTATION,
    scopes=(DOCUMENTS,),
)
async def create_document(
    payload: CreateDocumentInput, ctx: VendorToolContext
) -> dict[str, Any]:
    created = _object(
        (await ctx.mutate("/documents", json={"title": payload.title})).data
    )
    document_id = str(created.get("documentId") or "")
    if not document_id:
        raise VendorToolError(
            "vendor_response_invalid", "Google did not return a document id."
        )
    if payload.body:
        # Index 1 is the first writable position; index 0 is the body itself.
        await ctx.mutate(
            f"/documents/{document_id}:batchUpdate",
            json={
                "requests": [
                    {
                        "insertText": {
                            "location": {"index": 1},
                            "text": payload.body,
                        }
                    }
                ]
            },
        )
    return {
        "document_id": document_id,
        "title": created.get("title"),
        "web_link": f"https://docs.google.com/document/d/{document_id}/edit",
        "body_written": bool(payload.body),
    }


@curated_tool(
    vendor=vendor.vendor,
    name="append_text",
    display_name="Append to Google Doc",
    description=(
        "Add text to the end of a document. The end position is worked out "
        "here by reading the document's structure first, which is the step "
        "raw API calls get wrong."
    ),
    input_model=AppendTextInput,
    effect=ToolEffect.MUTATION,
    scopes=(DOCUMENTS,),
)
async def append_text(
    payload: AppendTextInput, ctx: VendorToolContext
) -> dict[str, Any]:
    document = _object((await ctx.read(f"/documents/{payload.document_id}")).data)
    index = _end_index(document)
    text = f"\n{payload.text}" if payload.start_on_new_line else payload.text
    await ctx.mutate(
        f"/documents/{payload.document_id}:batchUpdate",
        json={
            "requests": [{"insertText": {"location": {"index": index}, "text": text}}]
        },
    )
    return {
        "document_id": payload.document_id,
        "title": document.get("title"),
        "inserted_at_index": index,
        "characters_added": len(text),
    }


@curated_tool(
    vendor=vendor.vendor,
    name="replace_text",
    display_name="Replace Text in Google Doc",
    description=(
        "Replace every occurrence of some text throughout a document, "
        "including inside tables and headers. Useful for filling a template. "
        "Reports how many occurrences changed, so an empty result is visible "
        "rather than silent."
    ),
    input_model=ReplaceTextInput,
    effect=ToolEffect.MUTATION,
    scopes=(DOCUMENTS,),
)
async def replace_text(
    payload: ReplaceTextInput, ctx: VendorToolContext
) -> dict[str, Any]:
    response = await ctx.mutate(
        f"/documents/{payload.document_id}:batchUpdate",
        json={
            "requests": [
                {
                    "replaceAllText": {
                        "containsText": {
                            "text": payload.find,
                            "matchCase": payload.match_case,
                        },
                        "replaceText": payload.replace_with,
                    }
                }
            ]
        },
    )
    result = _object(response.data)
    replies = [r for r in result.get("replies") or [] if isinstance(r, dict)]
    occurrences = 0
    if replies:
        occurrences = int(
            (replies[0].get("replaceAllText") or {}).get("occurrencesChanged", 0) or 0
        )
    return {
        "document_id": payload.document_id,
        "occurrences_changed": occurrences,
        "found": occurrences > 0,
    }


def _flatten(document: dict[str, Any]) -> str:
    """Walk the structural-element tree and recover readable text."""
    body = document.get("body") or {}
    lines: list[str] = []
    for element in body.get("content") or []:
        lines.extend(_element_lines(element))
    return "\n".join(lines).strip()


def _element_lines(element: Any) -> list[str]:
    if not isinstance(element, dict):
        return []

    paragraph = element.get("paragraph")
    if isinstance(paragraph, dict):
        text = "".join(
            str((run.get("textRun") or {}).get("content", ""))
            for run in paragraph.get("elements") or []
            if isinstance(run, dict)
        ).rstrip("\n")
        style = (paragraph.get("paragraphStyle") or {}).get("namedStyleType")
        prefix = _HEADING_PREFIX.get(str(style), "")
        return [f"{prefix}{text}"] if text else [""]

    table = element.get("table")
    if isinstance(table, dict):
        rows: list[str] = []
        for row in table.get("tableRows") or []:
            if not isinstance(row, dict):
                continue
            cells: list[str] = []
            for cell in row.get("tableCells") or []:
                if not isinstance(cell, dict):
                    continue
                inner: list[str] = []
                for child in cell.get("content") or []:
                    inner.extend(_element_lines(child))
                cells.append(" ".join(part for part in inner if part).strip())
            rows.append(" | ".join(cells))
        return rows

    table_of_contents = element.get("tableOfContents")
    if isinstance(table_of_contents, dict):
        lines: list[str] = []
        for child in table_of_contents.get("content") or []:
            lines.extend(_element_lines(child))
        return lines

    return []


def _end_index(document: dict[str, Any]) -> int:
    """Last writable position in the body.

    Google reports an `endIndex` one past the final character, and inserting
    there is rejected, so the insertion point is one less. A document with no
    content at all starts writable at index 1.
    """
    content = (document.get("body") or {}).get("content") or []
    end = 1
    for element in content:
        if isinstance(element, dict) and isinstance(element.get("endIndex"), int):
            end = max(end, int(element["endIndex"]))
    return max(1, end - 1)


def _object(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise VendorToolError(
            "vendor_response_invalid", "Google Docs returned a non-object response."
        )
    error = payload.get("error")
    if isinstance(error, dict):
        raise VendorToolError(
            "vendor_rejected",
            str(error.get("message", "Google rejected the request."))[:500],
        )
    return payload


__all__ = ["append_text", "create_document", "read_document", "replace_text"]
