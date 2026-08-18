"""Run one-shot parallel LLM tasks through pipeline composition."""

from __future__ import annotations

import logging
from uuid import UUID

from eylo.common.database import start_transaction
from eylo.modules.llm_configs.resolver import LLMConfigResolver
from eylo.modules.llm_configs.wiring import build_llm_config_resolver
from eylo.modules.parallel_agents.schemas import TaskContent, WorkerResult
from eylo.pipelines.llm.runtime import (
    run_background_prompt_agent,
)

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are a task worker. Complete the given task thoroughly and concisely. "
    "Return only the result — no preamble, no commentary."
)


class LLMTaskWorker:
    """Execute one task using the organization's default LLM config."""

    def __init__(
        self,
        task_content: TaskContent,
        organization_id: UUID,
        conversation_id: UUID,
        sender_id: UUID,
        *,
        resolver: LLMConfigResolver | None = None,
    ) -> None:
        self.task_content = task_content
        self.organization_id = organization_id
        self.conversation_id = conversation_id
        self.sender_id = sender_id
        self._resolver = resolver

    async def run(self) -> WorkerResult:
        """Resolve credentials in-process, then execute a single LLM call."""
        config_id = self.task_content.llm_provider_config_id
        config_revision = self.task_content.llm_provider_config_revision
        if config_id is None or config_revision is None:
            raise ValueError("Bare LLM task has no pinned LLM authority.")
        resolver = self._resolver
        if resolver is None:
            async with start_transaction(ro=True):
                resolver = build_llm_config_resolver()
                resolved = await resolver.resolve_llm_pinned(
                    self.organization_id,
                    provider_config_id=config_id,
                    revision=config_revision,
                    overrides={"max_tokens": 1000, "temperature": 0.3},
                )
        else:
            resolved = await resolver.resolve_llm_pinned(
                self.organization_id,
                provider_config_id=config_id,
                revision=config_revision,
                overrides={"max_tokens": 1000, "temperature": 0.3},
            )

        result = await run_background_prompt_agent(
            agent_name="parallel_llm_task",
            system_prompt=SYSTEM_PROMPT,
            user_content=self.task_content.instruction,
            sender_id=self.sender_id,
            conversation_id=self.conversation_id,
            resolved=resolved,
        )
        if result is None:
            logger.warning(
                "LLM task worker got no text response for org=%s",
                self.organization_id,
            )
            return WorkerResult(
                text="Task completed but produced no text output.",
                model_used=resolved.generation.model.value,
                iterations_used=1,
            )
        return WorkerResult(
            text=result.text,
            model_used=result.model,
            iterations_used=1,
        )
