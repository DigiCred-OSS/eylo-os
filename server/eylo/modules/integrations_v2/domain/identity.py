"""Deterministic identity for curated tools.

A curated tool's contract lives in code, so its organization-scoped row can be
addressed before it exists. Deriving the id from the organization and the wire
id lets an agent bind a tool that has never been materialized, and lets the
service materialize it later under the id the binding already used.

This mirrors `system_tool_id` in `modules/tools/services/tool_register.py`,
which solves the same problem for in-process system tools.
"""

from __future__ import annotations

from uuid import UUID, uuid5

CURATED_TOOL_NAMESPACE = UUID("2f9d1a44-6c3e-5b7a-9e21-4c8d0f6b7a15")


def curated_tool_id(wire_id: str, organization_id: UUID) -> UUID:
    """Return the stable row id for one curated tool inside one organization."""
    normalized = wire_id.strip()
    if not normalized:
        raise ValueError("Curated tool wire id is required.")
    return uuid5(CURATED_TOOL_NAMESPACE, f"{organization_id}:{normalized}")


__all__ = ["CURATED_TOOL_NAMESPACE", "curated_tool_id"]
