"""Agent handoff contracts."""

from __future__ import annotations

from uuid import UUID

from pydantic import Field

from .common import FrozenFrameworkModel, JsonObject


class HandoffSpec(FrozenFrameworkModel):
    """Tool-like declaration for switching active agents."""

    name: str
    description: str
    target_agent_id: UUID
    input_schema: JsonObject = Field(default_factory=dict)
    is_enabled: bool = True
    metadata: JsonObject = Field(default_factory=dict)


class HandoffResult(FrozenFrameworkModel):
    """Outcome of a handoff tool call."""

    from_agent_id: UUID
    to_agent_id: UUID | None = None
    message: str
    is_error: bool = False
    metadata: JsonObject = Field(default_factory=dict)
