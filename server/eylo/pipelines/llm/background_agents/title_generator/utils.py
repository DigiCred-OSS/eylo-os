"""Utility helper functions for conversation title generation.

This module contains helper functions factored out from the main title generation
worker logic to improve modularity and reduce the main file's length.
"""

import logging
from typing import Dict, List, Optional
from uuid import UUID

from eylo.modules.agents.schemas.indb import AgentInDb
from eylo.modules.llm_configs.domain import ResolvedLLM

from ..framework_prompt import run_background_prompt_agent

logger = logging.getLogger(__name__)


def generate_fallback_title(
    content: str, conversation_id: str, max_len: int = 100
) -> str:
    """Generates a fallback title by truncating the given content."""
    fallback_title = content[:max_len]
    logger.info(
        "Using truncated fallback title for conversation %s",
        conversation_id,
    )
    return fallback_title


def ensure_title_max_length(
    title: str, conversation_id: str, max_db_len: int = 255
) -> str:
    """Ensures the title does not exceed the maximum database length."""
    if len(title) > max_db_len:
        title = title[:max_db_len]
        logger.warning(
            "Generated title for conversation %s exceeded %s characters and was truncated",
            conversation_id,
            max_db_len,
        )
    return title


async def call_llm_for_title_generation(
    system_prompt: str,
    llm_messages: List[Dict[str, str]],
    agent: AgentInDb,
    resolved: ResolvedLLM,
    conversation_id: UUID,
) -> Optional[str]:
    """Calls the LLM to generate a title and parses the response."""
    try:
        title_result = await run_background_prompt_agent(
            agent_name="title_generator",
            system_prompt=system_prompt,
            user_content=_single_user_content(llm_messages),
            sender_id=agent.id,
            conversation_id=conversation_id,
            resolved=resolved,
        )
        if title_result:
            title_candidate = title_result.text.strip("\"'")
            logger.info("LLM generated title for conversation %s", conversation_id)
            return title_candidate
        else:
            logger.warning(f"LLM generated an empty title for conv {conversation_id}.")
    except Exception as error:
        logger.error(
            "LLM title generation failed conversation=%s error_type=%s",
            conversation_id,
            type(error).__name__,
        )

    return None


def _single_user_content(llm_messages: List[Dict[str, str]]) -> str:
    """Return the user prompt content expected by the background agent helper."""
    return "\n".join(
        message["content"]
        for message in llm_messages
        if message.get("role") == "user" and message.get("content")
    )
