"""Resolved-provider prompt runner for lightweight background agents."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from uuid import UUID

from eylo.modules.agent_runs.budgets import meter_current_agent_run_usage
from eylo.modules.agents.models import AgentStatus
from eylo.modules.agents.schemas.indb import AgentInDb
from eylo.modules.conversations.schemas.messages import MessageKind
from eylo.modules.llm_configs.domain import ResolvedLLM
from eylo.modules.llm_configs.resolver import LLMConfigResolver
from eylo.modules.llm_configs.wiring import build_llm_config_resolver
from eylo.modules.provider_configs.constants import Capability
from eylo.modules.provider_configs.errors import NotConfiguredError
from eylo.sockets.llm import LLMContentType, LLMFactory, LLMResponse, LLMTextBlock
from eylo.sockets.llm.transient import text_message

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BackgroundPromptResult:
    """Sanitized output metadata from one background LLM request."""

    text: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


async def resolve_background_agent(
    agent: AgentInDb,
    *,
    generation_overrides: Mapping[str, object] | None = None,
    resolver: LLMConfigResolver | None = None,
) -> ResolvedLLM:
    """Resolve one agent config with optional job-specific generation limits."""
    if agent.status is not AgentStatus.ACTIVE:
        raise NotConfiguredError(
            capability=Capability.LLM,
            missing=["published_agent"],
            configure_via=f"/api/agents/{agent.id}",
        )
    if (
        agent.llm_provider_config_id is None
        or agent.llm_provider_config_revision is None
    ):
        raise NotConfiguredError(
            capability=Capability.LLM,
            missing=["provider_config", "provider_config_revision"],
            configure_via=f"/api/agents/{agent.id}",
        )
    effective_overrides = agent.llm_overrides.model_dump(exclude_none=True)
    if generation_overrides:
        effective_overrides.update(generation_overrides)
    if resolver is None:
        resolver = build_llm_config_resolver()
    return await resolver.resolve_llm_pinned(
        agent.organization_id,
        provider_config_id=agent.llm_provider_config_id,
        revision=agent.llm_provider_config_revision,
        overrides=effective_overrides,
    )


async def run_background_prompt_agent(
    *,
    agent_name: str,
    system_prompt: str,
    user_content: str,
    sender_id: UUID,
    conversation_id: UUID,
    resolved: ResolvedLLM,
) -> BackgroundPromptResult | None:
    """Run a one-shot prompt through the agent's resolved native adapter."""
    adapter = LLMFactory.from_resolved(resolved).adapter
    response = await adapter.run_inference(
        messages=[
            text_message(
                sender_id,
                conversation_id,
                MessageKind.USER,
                user_content,
            )
        ],
        system_prompt=system_prompt,
        tools=[],
        llm_config=resolved.generation.to_storage(),
    )
    usage = response.usage
    await meter_current_agent_run_usage(
        input_tokens=None if usage is None else usage.input_tokens,
        output_tokens=None if usage is None else usage.output_tokens,
    )
    result = _result_from_response(response)
    if result is None:
        logger.warning("Background agent %s returned no text", agent_name)
    return result


def _result_from_response(response: LLMResponse) -> BackgroundPromptResult | None:
    text = next(
        (
            _text_from_content(block.content)
            for block in response.content
            if block.type == LLMContentType.TEXT
        ),
        None,
    )
    if not text or not text.strip():
        return None
    usage = response.usage
    return BackgroundPromptResult(
        text=text.strip(),
        model=response.model,
        input_tokens=usage.input_tokens if usage else 0,
        output_tokens=usage.output_tokens if usage else 0,
    )


def _text_from_content(content: object) -> str | None:
    if isinstance(content, LLMTextBlock):
        return content.text
    if isinstance(content, str):
        return content
    if isinstance(content, dict):
        text = content.get("text")
        return text if isinstance(text, str) else None
    text = getattr(content, "text", None)
    return text if isinstance(text, str) else None
