"""Data contracts for the `agents` domain."""

from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from eylo.common.schemas import (
    EyloBaseModelSchema,
    EyloBaseOrganizationModelSchema,
    EyloBaseSchema,
)
from eylo.modules.agents.models import AgentKind, AgentStatus
from eylo.modules.llm_configs.schemas import LLMOverridesSchema


class AgentBase(EyloBaseOrganizationModelSchema):
    name: str = Field(..., max_length=100)
    slug: str = Field(..., max_length=100)
    llm_provider_config_id: UUID | None = None
    llm_provider_config_revision: int | None = Field(default=None, gt=0)
    email_provider_config_id: UUID | None = None
    email_provider_config_revision: int | None = Field(default=None, gt=0)
    webrtc_provider_config_id: UUID | None = None
    webrtc_provider_config_revision: int | None = Field(default=None, gt=0)
    voice_config_id: UUID | None = None
    voice_config_revision: int | None = Field(default=None, gt=0)
    llm_overrides: LLMOverridesSchema = Field(default_factory=LLMOverridesSchema)
    reranking_provider_config_id: UUID | None = None
    reranking_provider_config_revision: int | None = Field(default=None, gt=0)
    memory_provider_config_id: UUID | None = None
    memory_provider_config_revision: int | None = Field(default=None, gt=0)
    allow_file_uploads: bool = False
    file_upload_embedding_provider_config_id: UUID | None = None
    file_upload_embedding_provider_config_revision: int | None = Field(
        default=None, gt=0
    )
    instruction_template_id: UUID | None = None
    description: Optional[str] = None
    webhook: Optional[str] = None
    status: AgentStatus = Field(AgentStatus.DRAFT, description="Status of the agent.")
    kind: AgentKind = Field(
        AgentKind.CONVERSATIONAL, description="Conversational or background agent."
    )
    implementation: Optional[str] = Field(
        None,
        description=(
            "Registry slug naming first-party code for a background agent. "
            "Null means prompt-only."
        ),
    )
    organization_id: UUID = Field(..., description="Organization ID for the agent.")
    prompt: Optional[dict] = Field(
        None, description="Prompt configuration for the agent."
    )
    lifecycle: str = "draft"
    published_revision: int | None = Field(default=None, gt=0)
    draft_version: int = Field(default=1, gt=0)
    draft_dirty: bool = True


class AgentCreate(EyloBaseSchema):
    organization_id: UUID
    kind: AgentKind = AgentKind.CONVERSATIONAL
    implementation: Optional[str] = None
    llm_provider_config_id: UUID | None = None
    email_provider_config_id: UUID | None = None
    webrtc_provider_config_id: UUID | None = None
    voice_config_id: UUID | None = None
    voice_config_revision: int | None = Field(default=None, gt=0)
    llm_overrides: LLMOverridesSchema = Field(default_factory=LLMOverridesSchema)
    reranking_provider_config_id: UUID | None = None
    memory_provider_config_id: UUID | None = None
    allow_file_uploads: bool = False
    file_upload_embedding_provider_config_id: UUID | None = None
    instruction_template_id: UUID | None = None
    name: str = Field(..., max_length=100)
    description: Optional[str] = None
    prompt: Optional[dict] = None


class AgentUpdate(EyloBaseSchema):
    id: UUID | None = None
    organization_id: UUID | None = None
    name: Optional[str] = Field(None, max_length=100)
    llm_provider_config_id: UUID | None = None
    llm_provider_config_revision: int | None = Field(default=None, gt=0)
    email_provider_config_id: UUID | None = None
    email_provider_config_revision: int | None = Field(default=None, gt=0)
    webrtc_provider_config_id: UUID | None = None
    webrtc_provider_config_revision: int | None = Field(default=None, gt=0)
    voice_config_id: UUID | None = None
    voice_config_revision: int | None = Field(default=None, gt=0)
    llm_overrides: LLMOverridesSchema | None = None
    reranking_provider_config_id: UUID | None = None
    reranking_provider_config_revision: int | None = Field(default=None, gt=0)
    memory_provider_config_id: UUID | None = None
    memory_provider_config_revision: int | None = Field(default=None, gt=0)
    allow_file_uploads: bool = False
    file_upload_embedding_provider_config_id: UUID | None = None
    file_upload_embedding_provider_config_revision: int | None = Field(
        default=None, gt=0
    )
    instruction_template_id: UUID | None = None
    description: Optional[str] = None
    # `kind` is deliberately absent: flipping it after creation would strand
    # whatever the old kind allowed — swarm memberships for a conversational
    # agent, attachments for a background one — and the validation that
    # rejected those combinations runs at write time, not retroactively.
    implementation: Optional[str] = None
    prompt: Optional[dict] = None
    expected_draft_version: int | None = Field(default=None, gt=0)


class AgentInDb(AgentBase):
    class Config:
        from_attributes = True


class AgentToolBase(EyloBaseModelSchema):
    agent_id: UUID = Field(..., description="Agent ID for the tool.")
    tool_id: UUID = Field(..., description="Tool ID for the agent.")
    tool_revision: int = Field(..., gt=0, description="Exact tool revision.")
    organization_id: UUID = Field(..., description="Shared organization scope.")


class AgentToolCreate(BaseModel):
    agent_id: UUID = Field(..., description="Agent ID for the tool.")
    tool_id: UUID = Field(..., description="Tool ID for the agent.")
    tool_revision: int = Field(..., gt=0, description="Exact tool revision.")
    organization_id: UUID = Field(..., description="Shared organization scope.")


class AgentToolInDb(AgentToolBase):
    class Config:
        from_attributes = True


class AgentBackgroundAgentCreate(BaseModel):
    background_agent_id: UUID = Field(..., description="The background agent.")
    expected_draft_version: int = Field(..., gt=0)


class AgentBackgroundAgentUpdate(BaseModel):
    enabled: bool = Field(..., description="Whether this attachment dispatches.")
    expected_draft_version: int = Field(..., gt=0)


class AgentBackgroundAgentInDb(EyloBaseModelSchema):
    agent_id: UUID
    background_agent_id: UUID
    enabled: bool = False

    class Config:
        from_attributes = True
