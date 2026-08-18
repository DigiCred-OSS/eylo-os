"""Request and response shapes for AgentRun objectives and sandbox sessions."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from eylo.common.contracts.sandbox import SandboxAccess, SandboxState


class ObjectiveCreate(BaseModel):
    """Starting long-running work.

    Both bounds are here and both are required to have a value, because an
    objective with neither runs until someone notices. `max_steps` stops one
    that loops; `deadline` stops one that is merely slow, and they catch
    different failures.
    """

    model_config = ConfigDict(extra="forbid")

    agent_id: uuid.UUID
    goal: str = Field(
        min_length=1,
        description=(
            "What the agent is to achieve, in your words. Kept verbatim — it is "
            "the one thing that must not drift as the work goes on."
        ),
    )
    max_steps: int = Field(ge=1, le=200)
    deadline: datetime


class SandboxSessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: uuid.UUID
    provider: str
    image: str
    sandbox_provider_config_id: uuid.UUID
    sandbox_provider_config_revision: int
    grant_id: uuid.UUID | None
    grant_revision: int | None
    effective_policy: dict[str, object]
    state: SandboxState
    agent_id: uuid.UUID | None
    agent_run_id: uuid.UUID | None
    workspace: str
    expires_at: datetime
    last_used_at: datetime | None
    created_at: datetime
    # Deliberately absent: `vendor_id`. It is the container id, and an operator
    # who has it can reach the workspace outside everything this module
    # enforces. The kill switch is a route here, not a docker command.


class SandboxGrantCreate(BaseModel):
    """Bind an agent to one explicit ready no-egress sandbox config."""

    model_config = ConfigDict(extra="forbid")

    agent_id: uuid.UUID
    sandbox_provider_config_id: uuid.UUID
    access: Literal[SandboxAccess.RUN]
    max_sessions: int | None = Field(
        default=None,
        strict=True,
        ge=1,
        le=100,
        description=(
            "How many workspaces this agent may hold at once. Narrows the "
            "organization's limit; it cannot exceed it."
        ),
    )


class SandboxGrantRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: uuid.UUID
    organization_id: uuid.UUID
    agent_id: uuid.UUID
    access: SandboxAccess
    sandbox_provider_config_id: uuid.UUID
    sandbox_provider_config_revision: int
    revision: int
    max_sessions: int | None
    created_at: datetime
