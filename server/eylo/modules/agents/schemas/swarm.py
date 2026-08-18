"""Data contracts for the `agents` domain."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import Field

from eylo.common.schemas import (
    EyloBaseModelSchema,
    EyloBaseOrganizationModelSchema,
    EyloBaseSchema,
)


class AgentSwarmBase(EyloBaseOrganizationModelSchema):
    name: str = Field(..., max_length=100)
    slug: str = Field(..., max_length=100)
    description: Optional[str] = None
    organization_id: UUID = Field(
        ..., description="Organization ID for the agent swarm."
    )
    lifecycle: str = "draft"
    published_revision: int | None = Field(default=None, gt=0)
    draft_version: int = Field(default=1, gt=0)
    draft_dirty: bool = True


class AgentSwarmCreate(EyloBaseSchema):
    organization_id: UUID
    name: str = Field(..., max_length=100)
    description: Optional[str] = None


class AgentSwarmUpdate(EyloBaseSchema):
    id: UUID
    organization_id: UUID
    name: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    expected_draft_version: int = Field(..., gt=0)


class AgentSwarmInDb(AgentSwarmBase):
    class Config:
        from_attributes = True


# Mapping between agents and swarms


class AgentSwarmMappingBase(EyloBaseOrganizationModelSchema):
    agent_id: UUID = Field(..., description="Agent ID for the mapping.")
    swarm_id: UUID = Field(..., description="Swarm ID for the mapping.")
    organization_id: UUID = Field(..., description="Organization ID for the mapping.")
    agent_description: Optional[str] = Field(
        None, description="Swarm-specific description for the agent."
    )


class AgentSwarmMappingCreate(EyloBaseSchema):
    agent_id: UUID
    swarm_id: UUID
    organization_id: UUID
    agent_description: Optional[str] = None
    expected_draft_version: int = Field(..., gt=0)


class AgentSwarmMappingInDb(AgentSwarmMappingBase):
    class Config:
        from_attributes = True


class AgentSwarmRevisionInDb(EyloBaseOrganizationModelSchema):
    swarm_id: UUID
    revision: int = Field(..., gt=0)
    name: str
    slug: str
    description: str | None = None
    availability: str
    published_at: datetime
    published_by: UUID | None = None
    revoked_at: datetime | None = None
    revoked_by: UUID | None = None
    revocation_reason: str | None = None
    cancellation_requested_at: datetime | None = None

    class Config:
        from_attributes = True


class AgentSwarmRevisionMemberInDb(EyloBaseModelSchema):
    organization_id: UUID
    swarm_id: UUID
    swarm_revision: int = Field(..., gt=0)
    agent_id: UUID
    agent_revision: int = Field(..., gt=0)
    agent_description: str | None = None

    class Config:
        from_attributes = True
