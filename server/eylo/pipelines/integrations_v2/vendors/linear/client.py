"""Linear GraphQL helpers shared by curated Linear tools.

Linear answers a failed operation with HTTP 200 and a populated `errors` array,
so success has to be read out of the body rather than the status line. Doing it
once here is the reason curated tools can stay about business meaning.
"""

from __future__ import annotations

from typing import Any

from ...contracts import VendorToolContext, VendorToolError
from .definition import GRAPHQL_PATH


async def query(
    ctx: VendorToolContext,
    document: str,
    variables: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run a non-mutating GraphQL document and return its `data` object."""
    response = await ctx.read(
        GRAPHQL_PATH,
        method="POST",
        json={"query": document, "variables": variables or {}},
    )
    return _data(response.status_code, response.data)


async def mutate(
    ctx: VendorToolContext,
    document: str,
    variables: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run a mutating GraphQL document through the durable outbound owner."""
    response = await ctx.mutate(
        GRAPHQL_PATH,
        method="POST",
        json={"query": document, "variables": variables or {}},
    )
    return _data(response.status_code, response.data)


def _data(status_code: int, payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise VendorToolError(
            "vendor_response_invalid",
            "Linear returned a non-object response.",
        )
    errors = payload.get("errors")
    if errors:
        raise VendorToolError("vendor_rejected", _first_message(errors))
    if not 200 <= status_code < 300:
        raise VendorToolError(
            "vendor_rejected",
            f"Linear rejected the request with HTTP {status_code}.",
        )
    data = payload.get("data")
    if not isinstance(data, dict):
        raise VendorToolError(
            "vendor_response_invalid",
            "Linear returned no data for the operation.",
        )
    return data


def _first_message(errors: Any) -> str:
    if isinstance(errors, list) and errors:
        first = errors[0]
        if isinstance(first, dict):
            message = first.get("message")
            if isinstance(message, str) and message.strip():
                return message.strip()[:500]
    return "Linear rejected the request."


def nodes(container: Any, field: str) -> list[dict[str, Any]]:
    """Read a Linear connection's `nodes` list defensively."""
    holder = container.get(field) if isinstance(container, dict) else None
    values = holder.get("nodes") if isinstance(holder, dict) else None
    if not isinstance(values, list):
        return []
    return [item for item in values if isinstance(item, dict)]


__all__ = ["mutate", "nodes", "query"]
