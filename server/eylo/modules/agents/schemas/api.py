"""Data contracts for the `agents` domain."""

from enum import Enum
from typing import List, Optional
from uuid import UUID

from pydantic import ConfigDict, Field

from eylo.common.schemas import (
    EyloBaseApiSchema,
    EyloBaseRequestSchema,
    EyloBaseResponseSchema,
    PaginatedResponseSchema,
)
from eylo.modules.agents.models import AgentKind, AgentStatus
from eylo.modules.llm_configs.schemas import LLMOverridesSchema
from eylo.modules.tools.schemas.api import ToolResponseSchema

from .indb import AgentInDb, AgentToolInDb
from .swarm import (
    AgentSwarmInDb,
    AgentSwarmMappingInDb,
    AgentSwarmRevisionInDb,
)


class AgentCreateRequestSchema(EyloBaseRequestSchema):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., max_length=100)
    description: Optional[str] = None
    kind: AgentKind = AgentKind.CONVERSATIONAL
    llm_provider_config_id: UUID | None = None
    email_provider_config_id: UUID | None = None
    webrtc_provider_config_id: UUID | None = None
    voice_config_id: UUID | None = None
    llm_overrides: LLMOverridesSchema = Field(default_factory=LLMOverridesSchema)
    reranking_provider_config_id: UUID | None = None
    memory_provider_config_id: UUID | None = None
    allow_file_uploads: bool = False
    file_upload_embedding_provider_config_id: UUID | None = None
    instruction_template_id: UUID | None = None


class AgentUpdateRequestSchema(EyloBaseRequestSchema):
    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    llm_provider_config_id: UUID | None = None
    email_provider_config_id: UUID | None = None
    webrtc_provider_config_id: UUID | None = None
    voice_config_id: UUID | None = None
    llm_overrides: LLMOverridesSchema | None = None
    reranking_provider_config_id: UUID | None = None
    memory_provider_config_id: UUID | None = None
    allow_file_uploads: bool = False
    file_upload_embedding_provider_config_id: UUID | None = None
    instruction_template_id: UUID | None = None
    expected_draft_version: int = Field(..., gt=0)


class AgentPublishRequestSchema(EyloBaseRequestSchema):
    expected_draft_version: int = Field(..., gt=0)


class AgentRevokeRequestSchema(EyloBaseRequestSchema):
    revision: int = Field(..., gt=0)
    reason: str = Field(..., min_length=1, max_length=2000)


class AgentResponseSchema(AgentInDb, EyloBaseResponseSchema):
    pass


class AgentVoiceStackState(str, Enum):
    NOT_PUBLISHED = "not_published"
    TEXT_ONLY = "text_only"
    DECOMPOSED = "decomposed"
    REALTIME = "realtime"


class AgentRevisionReferenceSchema(EyloBaseApiSchema):
    id: UUID
    revision: int = Field(gt=0)


class AgentEffectiveVoiceStackResponseSchema(EyloBaseApiSchema):
    """Exact voice authority copied into the Agent's published revision."""

    agent_id: UUID
    agent_revision: int | None = Field(default=None, gt=0)
    state: AgentVoiceStackState
    voice_config: AgentRevisionReferenceSchema | None = None
    webrtc_provider: AgentRevisionReferenceSchema | None = None
    stt_provider: AgentRevisionReferenceSchema | None = None
    tts_provider: AgentRevisionReferenceSchema | None = None
    realtime_provider: AgentRevisionReferenceSchema | None = None
    storage_provider: AgentRevisionReferenceSchema | None = None


class AgentToolResponse(AgentToolInDb, EyloBaseResponseSchema):
    agent_id: UUID
    tool_id: UUID


class AgentToolRequest(EyloBaseApiSchema):
    tool_id: UUID
    expected_draft_version: int = Field(..., gt=0)


class AgentWsResponseSchema(EyloBaseResponseSchema):
    name: str = Field(..., max_length=100)
    slug: str = Field(..., max_length=100)
    status: AgentStatus = Field(AgentStatus.DRAFT, description="Status of the agent.")
    organization_id: UUID = Field(..., description="Organization ID for the agent.")
    description: Optional[str] = Field(None, description="Description of the agent.")


class AgentsPaginated(PaginatedResponseSchema[AgentResponseSchema]):
    """Paginated list of agents."""

    data: List[AgentResponseSchema]


class AgentToolsResponseSchema(EyloBaseApiSchema):
    items: list[ToolResponseSchema]


# Agent Swarm
class AgentSwarmResponseSchema(AgentSwarmInDb, EyloBaseResponseSchema):
    pass


class AgentSwarmMappingResponseSchema(AgentSwarmMappingInDb, EyloBaseResponseSchema):
    pass


class AgentSwarmMappingCreateRequestSchema(EyloBaseApiSchema):
    agent_id: UUID
    agent_description: Optional[str] = None
    expected_draft_version: int = Field(..., gt=0)


class AgentSwarmMappingDeleteRequestSchema(EyloBaseApiSchema):
    agent_id: UUID
    expected_draft_version: int = Field(..., gt=0)


class AgentSwarmCreateRequestSchema(EyloBaseApiSchema):
    name: str = Field(..., max_length=100)
    description: Optional[str] = None


class AgentSwarmUpdateRequestSchema(EyloBaseApiSchema):
    name: str | None = Field(default=None, max_length=100)
    description: str | None = None
    expected_draft_version: int = Field(..., gt=0)


class AgentSwarmPublishRequestSchema(EyloBaseApiSchema):
    expected_draft_version: int = Field(..., gt=0)


class AgentSwarmRevokeRequestSchema(EyloBaseApiSchema):
    revision: int = Field(..., gt=0)
    reason: str = Field(..., min_length=1, max_length=2000)


class AgentSwarmRevisionResponseSchema(
    AgentSwarmRevisionInDb,
    EyloBaseResponseSchema,
):
    pass
