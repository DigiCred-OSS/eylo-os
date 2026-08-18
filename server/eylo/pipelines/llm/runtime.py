"""Composition seam between platform modules and the concrete LLM runtime."""

from eylo.modules.llm_configs.domain import ResolvedLLM
from eylo.pipelines.llm.background_agents.framework_prompt import (
    BackgroundPromptResult,
    resolve_background_agent,
    run_background_prompt_agent,
)
from eylo.sockets.llm import LLMFactory
from eylo.sockets.llm.transient import (
    response_messages,
    text_message,
    text_parts,
    tool_result_messages,
    tool_uses,
)


def build_llm_adapter(resolved: ResolvedLLM):
    """Construct the concrete adapter for one fully resolved org config."""
    return LLMFactory.from_resolved(resolved).adapter


__all__ = [
    "BackgroundPromptResult",
    "build_llm_adapter",
    "resolve_background_agent",
    "response_messages",
    "run_background_prompt_agent",
    "text_message",
    "text_parts",
    "tool_result_messages",
    "tool_uses",
]
