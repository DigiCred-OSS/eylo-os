"""Map existing Eylo domain objects into framework primitives.

These helpers are deliberately small and one-way. They let the new framework
consume today's DB-backed conversation state without changing existing runners.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Protocol

from eylo.framework.agents.agent import AgentSpec
from eylo.framework.agents.common import FrameworkMetadata, JsonObject
from eylo.framework.agents.context import RunInput, RunMessage
from eylo.framework.agents.handoff import HandoffSpec
from eylo.framework.agents.model import ModelSettings
from eylo.framework.agents.tool import ToolExecutionMode, ToolKind, ToolSpec
from eylo.modules.conversations.schemas.message_content import (
    AssistantMessageContent,
    SystemMessageContent,
    TextMessageContentBlocks,
    UserMessageContent,
)
from eylo.modules.conversations.schemas.messages import (
    MessageContentKind,
    MessageKind,
    MessageMeta,
)

if TYPE_CHECKING:
    from eylo.modules.agents.schemas.indb import AgentInDb
    from eylo.modules.conversations.schemas.conversations import ConversationContext
    from eylo.modules.conversations.schemas.messages import MessageInDb
    from eylo.modules.tools.schemas.indb import ToolInDb


class ExistingAgentMetadata(FrameworkMetadata):
    """Metadata carried from existing agent records into framework specs."""

    slug: str
    status: str


class ExistingToolMetadata(FrameworkMetadata):
    """Identity shared by persisted and code-defined platform tools."""

    id: str
    slug: str
    mcp_server_id: str | None = None


class ExistingRevisionedToolMetadata(ExistingToolMetadata):
    """Identity for a persisted tool definition pinned to one revision."""

    revision: int


class ExistingCodeDefinedToolMetadata(ExistingToolMetadata):
    """Identity for executable code whose deployed catalog is authoritative."""

    definition_key: str


class ExistingRunInputMetadata(FrameworkMetadata):
    """Framework metadata derived from the current conversation context."""

    conversation_id: str
    organization_id: str | None = None
    external_id: str | None = None
    request_id: str | None = None
    widget_interfaces_enabled: bool
    transient_tool_message_count: int = 0


class ExistingToolCallMetadata(FrameworkMetadata):
    """Framework metadata for a persisted tool-use message."""

    id: str
    name: str
    arguments: JsonObject


class ExistingToolResultMetadata(FrameworkMetadata):
    """Framework metadata for a persisted tool-result message."""

    tool_call_id: str
    name: str | None = None
    is_error: bool
    content: object


class ExistingRunMessageMetadata(FrameworkMetadata):
    """Framework metadata derived from a persisted conversation message."""

    kind: MessageKind
    content_kind: MessageContentKind
    request_id: str | None = None
    meta: MessageMeta
    content_blocks: TextMessageContentBlocks | None = None
    tool_call: ExistingToolCallMetadata | None = None
    tool_result: ExistingToolResultMetadata | None = None


class AgentSpecContext(Protocol):
    """Small platform context required to build one framework agent spec."""

    @property
    def primary_agent(self) -> AgentInDb | None: ...

    @property
    def handoff_agents(self) -> Sequence[AgentInDb] | None: ...

    def get_tools(self) -> Sequence[ToolInDb]: ...


def agent_spec_from_context(context: AgentSpecContext) -> AgentSpec:
    """Build an ``AgentSpec`` from a fully hydrated conversation context."""
    if context.primary_agent is None:
        raise ValueError("ConversationContext has no primary_agent.")

    tools = tuple(tool_spec_from_indb(tool) for tool in context.get_tools())
    handoffs = tuple(
        HandoffSpec(
            name=f"transfer_to_{agent.slug}",
            description=agent.description or f"Transfer to {agent.name}.",
            target_agent_id=agent.id,
        )
        for agent in context.handoff_agents or ()
    )

    return agent_spec_from_indb(context.primary_agent, tools=tools, handoffs=handoffs)


def agent_spec_from_indb(
    agent: AgentInDb,
    *,
    tools: tuple[ToolSpec, ...] = (),
    handoffs: tuple[HandoffSpec, ...] = (),
) -> AgentSpec:
    """Build a framework agent config from an existing ``AgentInDb``."""
    from eylo.modules.agents.models import AgentStatus

    if agent.status is not AgentStatus.ACTIVE:
        raise ValueError("Only published agents can be executed.")
    if (
        agent.llm_provider_config_id is None
        or agent.llm_provider_config_revision is None
    ):
        raise ValueError("Published agent is missing pinned LLM authority.")
    overrides = agent.llm_overrides
    return AgentSpec(
        id=agent.id,
        organization_id=agent.organization_id,
        name=agent.name,
        instructions=agent.description or agent.name,
        model_settings=ModelSettings(
            provider_config_id=agent.llm_provider_config_id,
            provider_config_revision=agent.llm_provider_config_revision,
            model=overrides.model.value if overrides.model is not None else None,
            max_tokens=overrides.max_tokens,
            temperature=overrides.temperature,
            top_p=overrides.top_p,
            top_k=overrides.top_k,
            stop_sequences=overrides.stop_sequences,
        ),
        tools=tools,
        handoffs=handoffs,
        metadata=ExistingAgentMetadata(
            slug=agent.slug,
            status=getattr(agent.status, "value", str(agent.status)),
        ),
    )


def tool_spec_from_indb(tool: ToolInDb) -> ToolSpec:
    """Build a framework tool config from an existing ``ToolInDb``."""
    model_name = tool.llm_config.name
    if not model_name.strip():
        raise ValueError(f"Tool {tool.id} has no model-visible name.")
    return ToolSpec(
        name=model_name,
        description=tool.llm_config.description or tool.description,
        kind=_tool_kind_from_existing(tool.kind),
        input_schema=tool.get_input_schema(),
        execution_mode=_tool_execution_mode_from_existing(tool),
        metadata=_tool_metadata_from_existing(tool),
    )


def run_input_from_context(context: ConversationContext) -> RunInput:
    """Build LLM-visible input from a hydrated conversation context."""
    if context.primary_agent is None:
        raise ValueError("ConversationContext has no primary_agent.")

    agent = agent_spec_from_context(context)
    messages = tuple(
        run_message_from_indb(message) for message in context.get_messages()
    )

    return RunInput(
        instructions=context.system_prompt or agent.instructions,
        messages=messages,
        tools=agent.tools,
        metadata=ExistingRunInputMetadata(
            conversation_id=str(context.conversation.id),
            external_id=context.external_id,
            widget_interfaces_enabled=context.widget_interfaces_enabled,
        ),
    )


def run_message_from_indb(message: MessageInDb) -> RunMessage:
    """Convert an existing persisted message into framework-visible input."""
    tool_call_metadata: ExistingToolCallMetadata | None = None
    tool_result_metadata: ExistingToolResultMetadata | None = None
    content_blocks: TextMessageContentBlocks | None = None

    if message.kind == MessageKind.TOOL_USE:
        parsed = message.get_tool_use_content()
        tool_call_metadata = ExistingToolCallMetadata(
            id=parsed.content.id,
            name=parsed.content.name,
            arguments=parsed.content.input,
        )
    elif message.kind == MessageKind.TOOL_RESULT:
        parsed = message.get_tool_result_content()
        if parsed.content:
            result = parsed.content[0]
            tool_result_metadata = ExistingToolResultMetadata(
                tool_call_id=result.tool_use_id,
                name=result.name,
                is_error=result.is_error,
                content=result.content,
            )
    else:
        parsed = message.get_parsed_content()
        if isinstance(
            parsed,
            UserMessageContent | AssistantMessageContent | SystemMessageContent,
        ):
            content_blocks = parsed.content

    metadata = ExistingRunMessageMetadata(
        kind=message.kind,
        content_kind=message.content_kind,
        request_id=str(message.request_id) if message.request_id else None,
        meta=message.meta or MessageMeta(),
        content_blocks=content_blocks,
        tool_call=tool_call_metadata,
        tool_result=tool_result_metadata,
    )

    return RunMessage(
        id=message.id,
        role=_message_role(message.kind),
        content=message.get_text_content() or "",
        metadata=metadata,
    )


# Platform kind -> framework kind. The two enums are deliberately separate and
# are not being merged: the platform's stored kind uses upper-case DB values,
# while the framework's `ToolKind` is its own vocabulary
# and the framework may not import from `eylo.*` at all — Phase 16 enforces
# that with a test. This mapping is the one place they meet.
#
# In this module `ToolKind` is the framework enum; the platform enum is imported
# locally under the explicit `PlatformToolKind` name.
_PLATFORM_TO_FRAMEWORK_KIND = {
    "system": ToolKind.SYSTEM,
    "local": ToolKind.LOCAL,
    # MCP is an external call as far as the agent loop is concerned. It does not
    # get its own framework value: the framework describes tool *families*, not
    # transports, and teaching it one protocol name would invite the next one.
    # Which transport runs it is decided by the platform's own dispatch.
    "mcp": ToolKind.API,
    # Curated tools reach a vendor, but the agent loop calls them exactly like
    # any other in-process tool. Same reasoning as MCP above: the framework
    # describes families, and dispatch decides the transport.
    "curated": ToolKind.LOCAL,
}


def _tool_metadata_from_existing(tool: ToolInDb) -> ExistingToolMetadata:
    """Preserve either revision authority or deployed-code authority, never both."""
    from eylo.modules.tools.models import ToolKind as PlatformToolKind

    common = {
        "id": str(tool.id),
        "slug": tool.slug,
        "mcp_server_id": (
            str(tool.mcp_server_id) if tool.mcp_server_id else None
        ),
    }
    if tool.published_revision is not None:
        if tool.kind is PlatformToolKind.CURATED:
            raise ValueError("A curated tool cannot carry a persisted revision.")
        return ExistingRevisionedToolMetadata(
            **common,
            revision=tool.published_revision,
        )

    if tool.kind is PlatformToolKind.CURATED:
        if not tool.wire_id:
            raise ValueError("A curated tool requires its registry wire identity.")
        definition_key = tool.wire_id
    elif tool.kind is PlatformToolKind.SYSTEM:
        definition_key = tool.slug
    else:
        kind = getattr(tool.kind, "value", str(tool.kind))
        raise ValueError(f"Tool kind {kind!r} requires a published revision.")

    return ExistingCodeDefinedToolMetadata(
        **common,
        definition_key=definition_key,
    )


def _tool_kind_from_existing(kind: object) -> ToolKind:
    """Map one supported stored tool kind onto the framework vocabulary."""
    value = getattr(kind, "value", str(kind)).lower()
    mapped = _PLATFORM_TO_FRAMEWORK_KIND.get(value)
    if mapped is not None:
        return mapped
    raise ValueError(f"Stored tool kind {value!r} has no framework mapping.")


def _tool_execution_mode_from_existing(tool: ToolInDb) -> ToolExecutionMode:
    """Map the persisted exact policy onto the framework contract."""
    value = getattr(tool, "execution_mode", None)
    if isinstance(value, ToolExecutionMode):
        return value
    raw_value = getattr(value, "value", value)
    try:
        return ToolExecutionMode(raw_value)
    except (TypeError, ValueError) as error:
        raise ValueError(
            f"Tool {tool.id} has invalid execution mode {raw_value!r}."
        ) from error


def _message_role(kind: MessageKind) -> str:
    if kind == MessageKind.USER:
        return "user"
    if kind == MessageKind.ASSISTANT:
        return "assistant"
    if kind == MessageKind.SYSTEM:
        return "system"
    if kind == MessageKind.TOOL_RESULT:
        return "tool"
    return "assistant"
