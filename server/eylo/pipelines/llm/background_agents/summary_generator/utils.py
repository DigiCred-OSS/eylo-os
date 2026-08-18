"""Utility functions for context management.

Helper functions for token counting, summarization, and context analysis.
Includes group-based message organization that mirrors the request grouping
used in the main LLM pipeline (see base.py sort_request_groups).
"""

import logging
from dataclasses import dataclass, field
from typing import List, Literal, Optional, Tuple
from uuid import UUID

from eylo.common.context_compaction import context_messages
from eylo.modules.agents.schemas.indb import AgentInDb
from eylo.modules.conversations.schemas.conversations import ConversationContext
from eylo.modules.conversations.schemas.messages import (
    MessageContentKind,
    MessageInDb,
    MessageKind,
)
from eylo.modules.llm_configs.catalog import LLMModels
from eylo.modules.llm_configs.domain import ResolvedLLM

from ..framework_prompt import run_background_prompt_agent
from .token_counter import get_token_counter

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Message grouping
# ---------------------------------------------------------------------------


@dataclass
class MessageGroup:
    """A chronological group of messages sharing the same request_id.

    SYSTEM messages (request_id=None) form standalone groups.
    Regular request groups contain [user, assistant, tool_use, tool_result, ...].
    """

    request_id: Optional[UUID]
    messages: List[MessageInDb] = field(default_factory=list)

    @property
    def is_summary(self) -> bool:
        """True when this group is a SYSTEM SUMMARY message."""
        return any(
            m.kind == MessageKind.SYSTEM
            and m.content_kind == MessageContentKind.SUMMARY
            for m in self.messages
        )

    @property
    def earliest_at(self):
        return min(m.created_at for m in self.messages)

    def flat_messages(self) -> List[MessageInDb]:
        return list(self.messages)


def group_messages_by_request(messages: List[MessageInDb]) -> List[MessageGroup]:
    """Organize messages into chronological request groups.

    Groups messages by ``request_id``.  Messages without a request_id
    (e.g. SYSTEM summaries) become standalone single-message groups
    inserted in chronological order.

    Returns:
        Chronologically ordered list of MessageGroup.

    """
    if not messages:
        return []

    sorted_msgs = sorted(messages, key=lambda m: (m.created_at, str(m.id)))

    grouped: dict[Optional[UUID], MessageGroup] = {}
    standalone: List[MessageGroup] = []

    for msg in sorted_msgs:
        if msg.request_id is None:
            standalone.append(MessageGroup(request_id=None, messages=[msg]))
        else:
            if msg.request_id not in grouped:
                grouped[msg.request_id] = MessageGroup(
                    request_id=msg.request_id, messages=[]
                )
            grouped[msg.request_id].messages.append(msg)

    all_groups = list(grouped.values()) + standalone
    all_groups.sort(
        key=lambda group: min(
            (message.created_at, str(message.id)) for message in group.messages
        )
    )
    return all_groups


def flatten_groups(groups: List[MessageGroup]) -> List[MessageInDb]:
    """Flatten a list of groups back into a chronological message list."""
    msgs: List[MessageInDb] = []
    for g in groups:
        msgs.extend(g.flat_messages())
    return msgs


def get_max_tokens_for_model(model: LLMModels) -> int:
    """Get maximum context window for a model.

    Uses LLMModels enum as source of truth for model limits.

    Args:
        model: Model name (string value from LLMModels enum)

    Returns:
        Maximum tokens for this model

    """
    # Model context windows mapped to LLMModels enum values
    # All Claude 3+ models: 200k tokens
    # Source: https://docs.anthropic.com/en/docs/about-claude/models
    model_limits: dict[LLMModels, int] = {
        # Anthropic Direct API - Claude 3.7 Sonnet
        LLMModels.ANTHROPIC_CLAUDE_3_7_SONNET: 200000,
        # Anthropic Direct API - Claude 3.5 Sonnet
        LLMModels.ANTHROPIC_CLAUDE_3_5_SONNET: 200000,
        # AWS Bedrock - Claude 4.5 Haiku
        # LLMModels.BEDROCK_GLOBAL_CLAUDE_4_5_HAIKU: 200000,
        # AWS Bedrock - Claude 3.7 Sonnet
        LLMModels.BEDROCK_CLAUDE_3_7_SONNET: 200000,
        LLMModels.BEDROCK_US_CLAUDE_3_7_SONNET: 200000,
        # AWS Bedrock - Claude 3.5 Sonnet
        LLMModels.BEDROCK_CLAUDE_3_5_SONNET: 200000,
        LLMModels.BEDROCK_US_CLAUDE_3_5_SONNET: 200000,
        LLMModels.BEDROCK_CLAUDE_3_5_SONNET_20240620: 200000,
        LLMModels.BEDROCK_US_CLAUDE_3_5_SONNET_20240620: 200000,
        # AWS Bedrock - Claude 3.5 Haiku
        LLMModels.BEDROCK_US_CLAUDE_3_5_HAIKU: 200000,
        # AWS Bedrock - Claude 3 Sonnet
        LLMModels.BEDROCK_US_CLAUDE_3_SONNET: 200000,
        # AWS Bedrock - Claude 3 Haiku
        LLMModels.BEDROCK_CLAUDE_3_HAIKU: 200000,
        LLMModels.BEDROCK_US_CLAUDE_3_HAIKU: 200000,
        # AWS Bedrock - Claude 3 Opus
        LLMModels.BEDROCK_US_CLAUDE_3_OPUS: 200000,
        # AWS Bedrock - Claude Sonnet 4
        LLMModels.BEDROCK_CLAUDE_SONNET_4: 200000,
        LLMModels.BEDROCK_GLOBAL_CLAUDE_SONNET_4: 200000,
        LLMModels.BEDROCK_US_CLAUDE_SONNET_4: 200000,
        # AWS Bedrock - Claude Sonnet 4.5
        LLMModels.BEDROCK_CLAUDE_SONNET_4_5: 200000,
        LLMModels.BEDROCK_GLOBAL_CLAUDE_SONNET_4_5: 200000,
        LLMModels.BEDROCK_US_CLAUDE_SONNET_4_5: 200000,
        # AWS Bedrock - Claude Opus 4
        LLMModels.BEDROCK_US_CLAUDE_OPUS_4: 200000,
        # AWS Bedrock - Claude Opus 4.1
        LLMModels.BEDROCK_CLAUDE_OPUS_4_1: 200000,
        LLMModels.BEDROCK_US_CLAUDE_OPUS_4_1: 200000,
        # OpenAI Models
        # Source: https://platform.openai.com/docs/models
        LLMModels.OPENAI_GPT_4O: 128000,
        LLMModels.OPENAI_GPT_4O_MINI: 128000,
        LLMModels.OPENAI_GPT_4_TURBO: 128000,
        LLMModels.OPENAI_GPT_4: 8192,
        LLMModels.OPENAI_GPT_3_5_TURBO: 16385,
        LLMModels.OPENAI_GPT_5_MINI: 128000,
        # Google Gemini Models
        # Source: https://ai.google.dev/gemini-api/docs/models/gemini
        LLMModels.GEMINI_2_0_FLASH_EXP: 1000000,
        LLMModels.GEMINI_2_0_FLASH: 1000000,
        LLMModels.GEMINI_1_5_PRO: 2000000,
        LLMModels.GEMINI_1_5_FLASH: 1000000,
    }

    # Try exact match
    if model in model_limits:
        return model_limits[model]

    # Fallback: try to find in LLMModels enum
    try:
        for llm_model in LLMModels:
            if llm_model.value == model:
                logger.warning(
                    f"Model {model} found in LLMModels but not in limits mapping. "
                    f"Using default: 200000 (Claude standard)"
                )
                return 200000  # Default to Claude context window
    except Exception as error:
        logger.debug(
            "Checking LLMModels enum failed error_type=%s",
            type(error).__name__,
        )

    # Default fallback for unknown models
    logger.warning(
        f"Unknown model '{model}' not found in LLMModels. "
        f"Using conservative default: 8192 tokens"
    )
    return 8192


async def count_conversation_tokens(
    ctx: ConversationContext,
    resolved: ResolvedLLM,
) -> int:
    """Count total tokens in conversation messages.

    Args:
        messages: List of conversation messages
        model: Model name
        vendor: Vendor name (OPENAI, ANTHROPIC, GEMINI)

    Returns:
        Total token count

    """
    messages = context_messages(ctx.messages or [])
    compacted_context = ctx.model_copy(update={"messages": messages})
    model = resolved.generation.model
    vendor = resolved.provider
    try:
        counter = get_token_counter(vendor=vendor, model=model)
        tokens = counter.count_context_tokens(compacted_context)
        return sum(tokens.values())
    except Exception as error:
        logger.error(
            "Counting conversation tokens failed error_type=%s",
            type(error).__name__,
        )
        # Fallback: rough estimate (1 token ≈ 4 characters)
        # `get_text_content()` rather than `str(msg.content.content)`: content
        # is a list of typed blocks, so `str()` counts the repr scaffolding
        # (`[TextContent(type='text', text=...)]`) as if it were prompt text
        # and over-estimates every message on this fallback path.
        total_chars = sum(
            len(msg.get_text_content()) if msg.content else 0 for msg in messages
        )
        estimated_tokens = total_chars // 4
        logger.warning(
            f"Using character-based estimate: {estimated_tokens} tokens for {len(messages)} messages"
        )
        return estimated_tokens


def _count_groups_since_last_summary(
    groups: List[MessageGroup],
) -> Tuple[int, Optional[int]]:
    """Count user-initiated groups since the last SUMMARY group.

    Only groups with a ``request_id`` (user turns) are counted.
    Standalone SYSTEM groups are ignored because
    they are system-generated and shouldn't inflate the trigger count.

    Returns:
        (count_since_summary, index_of_last_summary_or_None)

    """
    last_summary_idx: Optional[int] = None
    for i in range(len(groups) - 1, -1, -1):
        if groups[i].is_summary:
            last_summary_idx = i
            break

    def _is_user_initiated(g: MessageGroup) -> bool:
        return g.request_id is not None

    if last_summary_idx is None:
        return len([g for g in groups if _is_user_initiated(g)]), None

    groups_after = groups[last_summary_idx + 1 :]
    return len([g for g in groups_after if _is_user_initiated(g)]), last_summary_idx


def should_trigger_context_management(
    current_tokens: int,
    max_tokens: int,
    tokens_threshold: float = 0.7,
    messages: Optional[List[MessageInDb]] = None,
    group_threshold: int = 20,
) -> Tuple[bool, Literal["tokens", "groups"]]:
    """Decide whether context management should run."""
    # --- Token-based trigger ---
    if max_tokens <= 0:
        return False, "tokens"

    utilization = current_tokens / max_tokens
    token_trigger = utilization >= tokens_threshold

    logger.debug(
        f"Token utilization: {utilization * 100:.1f}% "
        f"(threshold: {tokens_threshold * 100:.1f}%) -> "
        f"{'TRIGGER' if token_trigger else 'SKIP'}"
    )

    if token_trigger:
        return True, "tokens"

    # --- Group-based trigger ---
    messages = messages or []
    if not messages:
        return False, "tokens"

    groups = group_messages_by_request(messages)
    groups_since, _ = _count_groups_since_last_summary(groups)

    logger.debug(
        f"Request groups since last summary: {groups_since} "
        f"(threshold: {group_threshold})"
    )

    if groups_since >= group_threshold:
        logger.debug(
            f"Group count {groups_since} >= threshold {group_threshold} -> TRIGGER"
        )
        return True, "groups"

    return False, "groups"


async def summarize_messages_with_llm(
    messages: List[MessageInDb],
    conversation_id: UUID,
    agent: AgentInDb,
    resolved: ResolvedLLM,
    prior_summary: str | None = None,
) -> Optional[str]:
    """Use LLM to generate a concise summary of messages.

    Args:
        messages: Messages to summarize
        conversation_id: For logging context

    Returns:
        Summary text

    """
    # Build conversation text
    message_lines = []
    for message in messages:
        # Skip SYSTEM messages in summary (they're metadata)
        if message.kind == MessageKind.SYSTEM:
            continue

        # Use the common text extraction method
        text = message.get_text_content()

        if text:
            message_lines.append(f"{message.kind.name}: {text}")

    conversation_text = "\n".join(message_lines)
    if prior_summary:
        conversation_text = (
            "## Prior compacted summary\n"
            f"{prior_summary}\n\n"
            "## Newly compacted conversation\n"
            f"{conversation_text}"
        )

    if not conversation_text:
        logger.warning(f"No content to summarize for conversation {conversation_id}")
        return "No previous conversation content."

    # Call LLM for summarization
    try:
        system_prompt = """# Conversation Summarization Agent

## Role & Purpose
You are a summarization agent that creates structured, machine-readable summaries of conversations between a user and a tool-executing assistant. Your summaries enable seamless continuation when the main agent's context window is exhausted.

## Core Principles
- **Completeness**: Capture all information needed to continue the conversation without the original history
- **Specificity**: Include concrete details (file names, configurations, error messages, decisions made)
- **Actionability**: Make it clear what was done, what worked, what didn't, and why
- **Chronological clarity**: Use ISO 8601 timestamps (UTC) for significant events
- **Machine-readability**: Structure content for easy parsing by the continuation agent

## Output Format

Generate a markdown summary with these sections:

### Summary (generated at YYYY-MM-DDTHH:MM:SSZ)

**User Goals:**
- [Primary objective the user is trying to achieve]
- [Secondary objectives or related goals]

**Context & Constraints:**
- [Technical stack, frameworks, libraries being used]
- [System architecture details relevant to the work]
- [Constraints, requirements, or preferences mentioned]
- [Domain-specific information (e.g., "Uses async SQLAlchemy with PostgreSQL")]

**Key Information Shared:**
- [Important facts about the user's setup or situation]
- [Configuration details, environment specifics]
- [Decisions made and their rationale]

**Completed Work:**
1. [Action taken] - [Outcome/result] (YYYY-MM-DDTHH:MM:SSZ)
   - Tool used: [if applicable]
   - Key finding: [important result or insight]
2. [Next action] - [Outcome/result] (YYYY-MM-DDTHH:MM:SSZ)

**Failed Attempts & Learnings:**
- [What was tried] - Why it failed: [reason] (YYYY-MM-DDTHH:MM:SSZ)
- [Alternative approach considered] - Why rejected: [reason]

**Pending Work:**
- [ ] [Specific next action item]
- [ ] [Another action item with enough detail to execute]

**Open Questions:**
- [Unresolved question that may need user input]
- [Technical decision that needs to be made]

**Tool Calls Summary:**
- [tool_name]: Called N times
  - Success: [brief description of successful results]
  - Issues: [any errors or unexpected behaviors]

**Next Step Guidance:**
[1-2 paragraph concrete recommendation for how to proceed, including:
- What to do immediately next
- What information to request from the user if needed
- What potential approaches to consider
- What to avoid based on what didn't work]

---

## Summarization Guidelines

### What to Capture

DO include:
- Specific file names, paths, function names, variable names
- Error messages and stack traces (summarized)
- Configuration values and settings
- User preferences and constraints
- Technical decisions and their rationale
- Tool results that inform future actions
- Patterns of what worked vs. what didn't

DO NOT include:
- Verbatim conversation logs
- Greeting/farewell exchanges
- Redundant information
- Speculation without basis
- Off-topic discussions

### Timestamp Usage
- Add timestamps for: major milestones, tool executions, user decisions, state changes
- If exact time is unclear, estimate from context (e.g., "~2025-10-23T08:30:00Z")
- Omit timestamps for minor clarifications

### Handling Tool Calls
For each significant tool use, capture:
- WHAT tool was called and WHY
- KEY PARAMETERS passed
- RESULT (success/failure)
- IMPACT on the work (what it enabled or revealed)

Example for Completed Work entry:
"Searched codebase for event handling patterns (2025-10-23T08:15:00Z)
- Tool: filesystem_search for 'EventEmitter' pattern
- Found: 3 implementations in /src/events/
- Decision: Use pyventus pattern found in event_broadcaster.py"

### Next Step Guidance Format
Make this actionable and specific.

Good example:
"Resume by implementing the SummarizationAgent class in agents/summarizer.py. Use the existing OpenAIAdapter abstraction pattern. Test with a sample conversation from the logs in /data/test_conversations/. If the summary exceeds 500 tokens, implement the truncation strategy discussed."

Poor example:
"Continue working on the summarization feature."

## Quality Checklist
Before finalizing, verify:
- Could the continuation agent resume work without seeing the original conversation?
- Are all technical specifics (names, paths, configs) captured?
- Are timestamps present for major events?
- Is it clear what worked and what didn't?
- Are tool results summarized with their implications?
- Does "Next Step Guidance" provide a clear path forward?

"""

        result = await run_background_prompt_agent(
            agent_name="summary_generator",
            system_prompt=system_prompt,
            user_content=conversation_text,
            sender_id=agent.id,
            conversation_id=conversation_id,
            resolved=resolved,
        )
        if result:
            logger.info(
                "Generated summary for conversation %s",
                conversation_id,
            )
            return result.text

    except Exception as error:
        logger.error(
            "Calling LLM for summarization failed error_type=%s",
            type(error).__name__,
        )
    return None
