"""Data contracts for the `conversations` domain."""

import logging
from datetime import datetime, timezone
from enum import Enum
from functools import lru_cache
from typing import Annotated, Any, Dict, List, Literal, Optional, Self, Tuple
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from eylo.common.contracts.tool_availability import (
    ToolAvailabilityFacts,
    missing_tool_requirements,
)
from eylo.common.schemas import (
    EyloBaseApiSchema,
    EyloBaseOrganizationModelSchema,
    EyloBaseRequestSchema,
    EyloBaseSchema,
    PaginatedResponseSchema,
)
from eylo.common.utils.toon_serde import toon_encode
from eylo.modules.agents.schemas.indb import AgentInDb
from eylo.modules.contacts.schemas.indb import ContactInDb
from eylo.modules.conversations.constants import HANDOFF_TOOL_PREFIX
from eylo.modules.conversations.models.conversations import (
    ConversationChannels,
    ConversationStatus,
)
from eylo.modules.conversations.schemas.message_content import (
    IMAGE_URL_CONTENT_TYPE,
    TEXT_CONTENT_TYPE,
    ImageUrlPayload,
)
from eylo.modules.conversations.schemas.messages import (
    MessageContentKind,
    MessageInDb,
    MessageKind,
)
from eylo.modules.conversations.schemas.participants import (
    ParticipantInDb,
    ParticipantKind,
)
from eylo.modules.tools.models import ToolKind
from eylo.modules.tools.schemas.indb import ToolInDb
from eylo.modules.tools.schemas.platform import PlatformTool, PlatformToolInputSchema

logger = logging.getLogger(__name__)

# ====================== Conversation Schemas ======================


class ConversationBase(EyloBaseOrganizationModelSchema):
    id: UUID
    organization_id: UUID
    channel: ConversationChannels = Field(default=ConversationChannels.CHAT)
    status: ConversationStatus = Field(default=ConversationStatus.ACTIVE)
    title: Optional[str] = Field(...)
    has_triggered_title_generation: Optional[bool] = Field(default=False)
    ended_at: Optional[datetime] = None
    swarm_id: UUID | None = None
    swarm_revision: int | None = Field(default=None, gt=0)
    # Conversation meta is intentionally integrator-owned: public/integration
    # clients can attach arbitrary context when starting a conversation, so this
    # cannot be narrowed to a closed schema without breaking valid integrations.
    meta: Optional[Dict[str, Any]] = Field(default_factory=dict)


class ConversationCreate(EyloBaseSchema):
    organization_id: UUID
    external_id: Optional[str] = None
    channel: ConversationChannels = Field(default=ConversationChannels.CHAT)
    status: ConversationStatus = Field(default=ConversationStatus.ACTIVE)
    title: Optional[str] = None
    swarm_id: UUID | None = None
    swarm_revision: int | None = Field(default=None, gt=0)
    # Integrator-owned context; see ConversationBase.meta.
    meta: Optional[Dict[str, Any]] = None


class ConversationUpdate(EyloBaseSchema):
    """Schema for updating an existing conversation."""

    channel: Optional[ConversationChannels] = Field(None)
    status: Optional[ConversationStatus] = Field(None)
    end_time: Optional[datetime] = None
    # Integrator-owned context; see ConversationBase.meta.
    meta: Optional[Dict[str, Any]] = None
    title: Optional[str] = Field(None)


class ConversationInDb(ConversationBase):
    model_config = ConfigDict(from_attributes=True)


# ====================== Request Models ======================


class ConversationInitialMessageContent(EyloBaseRequestSchema):
    type: Literal["text", "image_url"] = TEXT_CONTENT_TYPE
    text: str | None = None
    image_url: ImageUrlPayload | None = None

    @model_validator(mode="after")
    def validate_content_shape(self) -> Self:
        if self.type == TEXT_CONTENT_TYPE and self.text is None:
            raise ValueError("text content blocks require text")
        if self.type == IMAGE_URL_CONTENT_TYPE and self.image_url is None:
            raise ValueError("image_url content blocks require image_url")
        return self


class ConversationInitialMessage(EyloBaseRequestSchema):
    content: list[ConversationInitialMessageContent]


class ConversationParticipantProfileContactKind(str, Enum):
    EMAIL = "EMAIL"
    PHONE = "PHONE"


class ConversationParticipantProfile(EyloBaseRequestSchema):
    kind: ConversationParticipantProfileContactKind
    value: str


class ConversationParticipant(EyloBaseRequestSchema):
    kind: ParticipantKind
    id: Optional[UUID] = None
    external_id: Optional[str] = None
    profiles: Optional[List[ConversationParticipantProfile]] = None

    @model_validator(mode="after")
    def atleast_id_or_external_id(self) -> Self:
        if self.id is None and self.external_id is None:
            raise ValueError("At least one of <id> or <external_id> must be provided")
        if self.kind == ParticipantKind.AGENT and self.id is None:
            raise ValueError("Agent participants require an explicit agent id")
        return self


class ConversationStartRequest(EyloBaseRequestSchema):
    from_: ConversationParticipant = Field(alias="from")
    to_: ConversationParticipant = Field(alias="to")
    channel: ConversationChannels = ConversationChannels.CHAT
    message: ConversationInitialMessage | None
    context: Optional[Dict[str, Any]] = Field(default_factory=dict)
    external_id: Optional[str] = None
    swarm_id: UUID | None = Field(
        default=None,
        description=(
            "Stable swarm selected for this conversation. The platform pins its "
            "current published topology revision before creating the conversation."
        ),
    )


class ConversationDirection(str, Enum):
    """Enum for conversation direction."""

    INBOUND = "INBOUND"
    OUTBOUND = "OUTBOUND"


# ====================== Conversation Flow ======================


class AgentState(str, Enum):
    """Enum for agent state."""

    IDLE = "IDLE"
    BUSY = "BUSY"


class ConversationContext(BaseModel):
    conversation: ConversationInDb
    participants: List[ParticipantInDb]
    messages: Optional[List[MessageInDb]] = []
    system_prompt: Optional[str] = None
    external_id: Optional[str] = None
    primary_contact: Optional[ContactInDb] = None
    primary_agent: Optional[AgentInDb] = None
    handoff_agents: Optional[List[AgentInDb]] = []
    handoff_agent_tools: Optional[Dict[UUID, List[ToolInDb]]] = {}
    agent_swarms: Optional[Dict[UUID, List[Tuple[UUID, Optional[str]]]]] = {}
    tools: List[ToolInDb] = []
    widget_interfaces_enabled: bool = False
    tool_availability: ToolAvailabilityFacts = Field(
        default_factory=ToolAvailabilityFacts
    )

    def filter_messages(
        self, kind: list[MessageKind] = [MessageKind.USER, MessageKind.ASSISTANT]
    ):
        return list(
            filter(
                lambda x: x.kind in kind,
                (self.messages or []),
            )
        )

    def get_primary_agent(self) -> Optional[ParticipantInDb]:
        participants: List[ParticipantInDb] = self.participants
        return next(
            (
                p
                for p in participants
                if p.entity_kind == ParticipantKind.AGENT and p.is_primary
            ),
            None,
        )

    def get_primary_contact(self) -> Optional[ParticipantInDb]:
        participants: List[ParticipantInDb] = self.participants
        return next(
            (
                p
                for p in participants
                if p.entity_kind == ParticipantKind.CONTACT and p.is_primary
            ),
            None,
        )

    def _json_to_md(self, data) -> str:
        return toon_encode(data)

    def contact_to_llm_context(self) -> str:
        prep_contact: Optional[ContactInDb] = self.primary_contact
        if not prep_contact:
            return ""
        return self._json_to_md(prep_contact.model_dump())

    def get_recent_handoff_tools(
        self, messages: Optional[List[MessageInDb]] = None
    ) -> List[str]:
        """Get list of handoff tools used in recent messages (since last USER message).

        This helps detect handoff loops by tracking which agents were recently handed off to.

        Args:
            messages: Optional list of messages to check. If None, uses self.messages

        Returns:
            List of handoff tool names used since last USER message

        """
        if messages is None:
            messages = self.messages or []

        tools_called_after_user_message = []

        for msg in reversed(messages):
            if not msg.content:
                continue

            if msg.kind == MessageKind.USER:
                break
            elif msg.kind == MessageKind.TOOL_USE:
                try:
                    # Use typed content access
                    parsed = msg.get_tool_use_content()
                    tool_name = parsed.content.name
                    if tool_name.startswith(HANDOFF_TOOL_PREFIX):
                        tools_called_after_user_message.append(tool_name)
                except (ValueError, AttributeError):
                    # Handle malformed content gracefully
                    logger.warning(
                        f"Failed to parse tool use content for message {msg.id}"
                    )

        return tools_called_after_user_message

    def enrich_last_user_message(
        self,
        messages: List[MessageInDb],
        include_contact_info: bool = True,
        include_handoff_warning: bool = True,
    ) -> List[MessageInDb]:
        """Enrich the last USER message with dynamic context.

        Adds helpful contextual information to the last user message:
        - Current UTC timestamp
        - User contact information (if available)
        - Handoff loop warning (if recent handoffs detected)

        This enrichment is done on a copy of the messages, not modifying the originals.

        Args:
            messages: List of messages (will not be modified)
            include_timestamp: Whether to add current timestamp
            include_contact_info: Whether to add user contact info
            include_handoff_warning: Whether to add handoff loop warning

        Returns:
            New list of messages with last USER message enriched

        """
        from eylo.modules.conversations.schemas.message_content import (
            UserMessageContent,
            WidgetResponseMessageContent,
        )

        if not messages:
            return messages

        # Find last USER message
        last_user_idx = None
        for i in range(len(messages) - 1, -1, -1):
            if messages[i].kind == MessageKind.USER:
                last_user_idx = i
                break

        if last_user_idx is None:
            return messages

        last_user_msg = messages[last_user_idx]

        # Build enrichment parts
        enrichment_parts = []

        if include_contact_info and self.primary_contact:
            enrichment_parts.append(
                f"\n\nUser Contact Information: {self.contact_to_llm_context()}"
            )

        if include_handoff_warning:
            recent_handoffs = self.get_recent_handoff_tools(messages)
            if recent_handoffs:
                enrichment_parts.append(
                    f"\n\nNOTE: List of recent handoffs: {', '.join(recent_handoffs)}. "
                    "Avoid immediate back-and-forth handoffs."
                )

        # If no enrichment needed, return original messages
        if not enrichment_parts:
            return messages

        # Create enriched message content
        try:
            parsed_content = last_user_msg.get_parsed_content()

            # Handle different content structures
            if isinstance(parsed_content, UserMessageContent):
                if isinstance(parsed_content.content, str):
                    # Simple string content - append enrichment
                    new_content = parsed_content.content + "".join(enrichment_parts)
                    enriched_content = UserMessageContent(
                        role="user", content=new_content
                    )
                elif isinstance(parsed_content.content, list):
                    # List of TextContent - don't modify complex structures
                    # Vendors can handle this in their adapters if needed
                    return messages
                else:
                    return messages
            elif isinstance(parsed_content, WidgetResponseMessageContent):
                enriched_content = UserMessageContent(
                    role="user",
                    content=parsed_content.get_text_content()
                    + "".join(enrichment_parts),
                )
            else:
                # Not a user message content - shouldn't happen but be safe
                return messages

            # Create new message with enriched content
            enriched_msg = MessageInDb.model_construct(
                **{
                    **last_user_msg.model_dump(),
                    "content": enriched_content,
                    "content_kind": "TEXT",
                }
            )

            # Return new list with enriched message
            new_messages = messages.copy()
            new_messages[last_user_idx] = enriched_msg
            return new_messages

        except (ValueError, AttributeError) as error:
            logger.warning(
                "Message content enrichment failed error_type=%s",
                type(error).__name__,
            )
            return messages

    def get_messages(
        self,
        skip_tool_messages: bool = False,
        enrich_context: bool = True,
        include_timestamp: bool = True,
        include_contact_info: bool = True,
        include_handoff_warning: bool = True,
    ) -> List[MessageInDb]:
        """Get conversation messages in platform-native format with optional enrichment.

        Returns messages sorted chronologically with basic validation.
        Optionally enriches the last user message with dynamic context.

        Does NOT perform vendor-specific formatting or validation -
        that's the adapter's responsibility.

        Args:
            skip_tool_messages: If True, excludes TOOL_USE and TOOL_RESULT messages
            enrich_context: If True, enriches last USER message with dynamic context
            include_timestamp: If True and enrich_context=True, adds current timestamp
            include_contact_info: If True and enrich_context=True, adds user contact info
            include_handoff_warning: If True and enrich_context=True, adds handoff warning

        Returns:
            List[MessageInDb]: Platform-native message objects, potentially enriched

        """
        messages = self.messages or []

        # Sort by creation time
        messages = sorted(messages, key=lambda m: m.created_at)

        # Basic domain validation only (not vendor-specific)
        messages = [
            m
            for m in messages
            if m.conversation_id and m.sender_participant_id and m.content
        ]

        # Assistant widget payloads are delivery artifacts for the client UI.
        # The LLM already produced them via a tool call, so they must not be fed
        # back into model history. Widget responses remain in history as USER turns.
        messages = [m for m in messages if m.content_kind != MessageContentKind.WIDGET]

        # Optional: skip tool messages if requested
        if skip_tool_messages:
            messages = [
                m
                for m in messages
                if m.kind not in (MessageKind.TOOL_USE, MessageKind.TOOL_RESULT)
            ]

        # Optional: enrich last user message with dynamic context
        if enrich_context:
            messages = self.enrich_last_user_message(
                messages,
                include_contact_info=include_contact_info,
                include_handoff_warning=include_handoff_warning,
            )

        logger.debug(
            f"Returning {len(messages)} messages for conversation {self.conversation.id}"
        )
        return messages

    def get_tools(self) -> List[ToolInDb]:
        """Get all tools (regular + handoff agents) in platform-native format.

        DB-assigned system tools are enriched at runtime (description, gating).
        System tools not passing their runtime gate are filtered out.

        Returns:
            List[ToolInDb]: Platform-native tool objects

        """

        def __hash(tool_id: UUID):
            return tool_id.hex[:8]

        def __compile_tool_name(tool: ToolInDb) -> str:
            return f"{tool.slug}__{__hash(tool.id)}"

        # Separate system tools from regular tools for different processing
        regular_tools = []
        system_tools = []
        for tool in list(self.tools or []):
            if tool.kind == ToolKind.SYSTEM:
                system_tools.append(tool)
            else:
                regular_tools.append(tool)

        # Munge names on regular tools
        for tool in regular_tools:
            tool.name = __compile_tool_name(tool)
            if isinstance(tool.llm_config, PlatformTool):
                tool.llm_config.name = __compile_tool_name(tool)
            else:
                logger.error("Invalid tool configuration tool_id=%s", tool.id)

        # Enrich and gate system tools
        enriched_system_tools = self._enrich_system_tools(system_tools)

        # Munge names on enriched system tools (same format as regular)
        for tool in enriched_system_tools:
            tool.name = __compile_tool_name(tool)
            if isinstance(tool.llm_config, PlatformTool):
                tool.llm_config.name = __compile_tool_name(tool)

        return [
            *regular_tools,
            *self._get_handoff_agent_tools(),
            *enriched_system_tools,
        ]

    def _enrich_system_tools(self, system_tools: List[ToolInDb]) -> List[ToolInDb]:
        """Apply runtime gating and description enrichment to DB-assigned system tools.

        Each system tool may have runtime conditions (feature flags, channel type)
        and may need dynamic description updates (e.g. available swarm agents).
        Tools that don't pass their gate are filtered out.

        Args:
            system_tools: System tools assigned to this agent via the DB.

        Returns:
            Tools that pass runtime gates, with enriched descriptions.

        """
        enriched = []
        for tool in system_tools:
            enriched_tool = self._enrich_single_system_tool(tool)
            if enriched_tool is not None:
                enriched.append(enriched_tool)
        return enriched

    def _enrich_single_system_tool(self, tool: ToolInDb) -> Optional[ToolInDb]:
        """Apply tool-specific runtime gate and description enrichment.

        Returns the enriched tool, or None if it should be filtered out.
        """
        slug = tool.slug

        from eylo.modules.tools.services.tool_register import system_tools_registry

        try:
            missing = missing_tool_requirements(
                system_tools_registry.requirements_for(slug),
                self.tool_availability,
            )
        except ValueError:
            logger.error("System tool is not registered slug=%s", slug)
            return None
        if not missing.available:
            logger.debug(
                "System tool unavailable slug=%s organization=%s agent=%s runtime=%s",
                slug,
                sorted(item.value for item in missing.organization_capabilities),
                sorted(item.value for item in missing.agent_capabilities),
                sorted(item.value for item in missing.runtime_facts),
            )
            return None

        if slug == "compound_render_widget":
            return self._enrich_compound_render_widget(tool)
        elif slug == "spawn_task_fnf":
            return self._enrich_spawn_task_fnf(tool)

        # Unknown system tools pass through as-is
        return tool

    def _enrich_compound_render_widget(self, tool: ToolInDb) -> Optional[ToolInDb]:
        """Gate by widget channel and enrich with dynamic widget catalog.

        NOTE: The DB-stored description (from the tool's docstring) is NEVER
        seen by the LLM. This method always overwrites both
        ``tool.llm_config.description`` and ``tool.description`` with the
        code-generated widget catalog description before the tool reaches
        any LLM vendor adapter.  The version is controlled by
        ``COMPOUND_WIDGET_TOOL_DESC_VERSION`` in settings.
        """
        if not self.widget_interfaces_enabled:
            return None

        from eylo.common.config import settings

        catalog_description, rich_input_schema = _get_widget_catalog_schema(
            version=settings.COMPOUND_WIDGET_TOOL_DESC_VERSION,
        )

        if isinstance(tool.llm_config, PlatformTool):
            tool.llm_config.description = catalog_description
            tool.llm_config.input_schema = PlatformToolInputSchema.model_validate(
                rich_input_schema
            )
        tool.description = catalog_description

        return tool

    def _enrich_spawn_task_fnf(self, tool: ToolInDb) -> Optional[ToolInDb]:
        """Gate by feature flag + handoff agents, enrich with swarm agent list."""
        from eylo.common.config import settings

        if not settings.ENABLE_SPAWN_TASK_FNF:
            return None

        if not self.handoff_agents:
            return None

        # Inject available swarm agent slugs into description
        agent_slugs = [a.slug for a in self.handoff_agents]
        agents_desc = ", ".join(f"`{s}`" for s in agent_slugs)
        swarm_suffix = (
            f"\n\nAvailable swarm agents: {agents_desc}. "
            f"Set swarm_id to one of these, or null for a bare LLM task."
        )

        if isinstance(tool.llm_config, PlatformTool):
            base_desc = tool.description or ""
            tool.llm_config.description = (base_desc + swarm_suffix).strip()
        tool.description = ((tool.description or "") + swarm_suffix).strip()

        return tool

    def _get_handoff_agent_tools(self) -> List[ToolInDb]:
        """Convert handoff agents to ToolInDb objects.

        Each agent that can be handed off to is represented as a tool.
        Returns platform-native ToolInDb objects.
        """

        def __compile_tool_name_description(tools: List[ToolInDb]) -> str:
            if not tools:
                return ""
            compiled_info = ""
            for tool in tools:
                if tool.description:
                    compiled_info += (
                        f"\nTool Name: {tool.name}\nDescription: {tool.description}\n"
                    )
            return f"Available Tools for the agent:\n{compiled_info}"

        def __get_agents_swarm_description(agent_id: UUID) -> Optional[str]:
            swarm_map = self.agent_swarms or {}
            description: str = ""
            for swarm in swarm_map:
                for aid, desc in swarm_map[swarm]:
                    if aid == agent_id and desc:
                        description += desc
            return description

        def __compile_agent_description(agent: AgentInDb, tools: List[ToolInDb]) -> str:
            desc_ = __get_agents_swarm_description(agent.id)
            description = (
                f"Agent `{agent.name}`, with slug `{agent.slug}` and id `{agent.id}` "
                f"is capable of \n\n{desc_ or agent.description or ''}.\n"
                f"Do not handoff to this agent if the user's request can be handled by you directly."
            )
            if tools:
                description = (
                    f"{description}. Agent has the following capabilities\n\n"
                    f"{__compile_tool_name_description(tools)}"
                )
            return description.strip()

        handoff_tools = []
        agents = self.handoff_agents or []

        for agent in agents:
            if self.primary_agent and agent.id == self.primary_agent.id:
                continue

            agent_tools = (
                self.handoff_agent_tools.get(agent.id, [])
                if self.handoff_agent_tools
                else []
            )

            # Create a PlatformTool for the handoff
            handoff_platform_tool = PlatformTool.model_construct(
                name=f"{HANDOFF_TOOL_PREFIX}{agent.slug}",
                description=__compile_agent_description(agent, agent_tools),
                input_schema=PlatformToolInputSchema.model_construct(
                    type="object",
                    properties={
                        "message": {
                            "type": "string",
                            "description": (
                                f"The message to handoff to agent {agent.name}.\n\n"
                                "Focus on the latest user request, user can have multiple pending requests, "
                                "highlight the latest request only.\n\n"
                                "Provide a summary of the necessary context."
                            ),
                        },
                        "handoff_loop_detected": {
                            "type": "boolean",
                            "description": (
                                "Indicates if a handoff loop was detected in recent messages. "
                                "Example: multiple consecutive handoffs."
                            ),
                        },
                    },
                    required=["message"],
                    additional_properties=False,
                    kind="handoff",
                ),
            )

            # Create ToolInDb using model_construct to bypass validation
            tool = ToolInDb.model_construct(
                id=agent.id,
                name=f"{HANDOFF_TOOL_PREFIX}{agent.slug}",
                slug=agent.slug,
                kind=ToolKind.LOCAL,
                display_name=f"Handoff to {agent.name}",
                description=__compile_agent_description(agent, agent_tools),
                llm_config=handoff_platform_tool,
                executor_config={},
                organization_id=self.conversation.organization_id,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            handoff_tools.append(tool)

        return handoff_tools


@lru_cache(maxsize=4)
def _get_widget_catalog_schema(version: int = 0) -> tuple:
    """Build and cache the compound widget tool description and input schema.

    The widget catalog is 100% code-derived (no DB or runtime state),
    so we cache per-version — only invalidated on process restart.
    """
    from eylo.modules.interfaces.services.schema_validator import (
        CompoundWidgetSchemaValidatorService,
    )

    validator = CompoundWidgetSchemaValidatorService()
    return validator.build_tool_description(
        version=version
    ), validator.build_tool_input_schema()


class ConversationMessageRequest(EyloBaseApiSchema):
    message: ConversationInitialMessage | None
    context: dict | None = None


# ====================== Conversation API Response ======================
class ConversationApiResponseSchema(ConversationInDb, EyloBaseApiSchema):
    pass


# ====================== Response Models ======================


class ConversationSort(str, Enum):
    TITLE = "title"
    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"
    ENDED_AT = "ended_at"


class ConversationSortDirection(str, Enum):
    ASC = "asc"
    DESC = "desc"


class ConversationsPaginated(PaginatedResponseSchema):
    """Paginated list of conversations."""

    data: List[ConversationApiResponseSchema]


class ConversationFilterSchema(EyloBaseApiSchema):
    conversation_ids: Annotated[Optional[list[UUID]], Field(None, max_length=100)] = (
        None
    )
    agent_id: Optional[UUID] = None
    query: str | None = Field(default=None, max_length=200)
    status: list[ConversationStatus] = Field(default_factory=list, max_length=3)
    channel: list[ConversationChannels] = Field(default_factory=list, max_length=6)
    sort: ConversationSort = ConversationSort.UPDATED_AT
    direction: ConversationSortDirection = ConversationSortDirection.DESC


class ConversationIntegrationResponseSchema(BaseModel):
    integration_id: UUID
    name: str
    status: str
    config_id: Optional[UUID] = None
    contact_id: Optional[UUID] = None
