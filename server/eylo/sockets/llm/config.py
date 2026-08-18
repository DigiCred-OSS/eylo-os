"""Validation shared by LLM vendor adapters at their public boundary."""

from collections.abc import Mapping
from typing import Any

from eylo.common.contracts.llm_runtime import InvalidLLMConfig


def require_model(config: Mapping[str, Any]) -> str:
    """Return one explicit model name; vendor adapters never select a model."""
    model = config.get("model")
    if not isinstance(model, str) or not model.strip():
        raise InvalidLLMConfig("LLM model must be configured explicitly.")
    return model.strip()


def require_max_tokens(config: Mapping[str, Any]) -> int:
    """Return an explicit output-token limit for providers that require one."""
    value = config.get("max_tokens")
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise InvalidLLMConfig(
            "LLM max_tokens must be configured explicitly for this provider."
        )
    return value


def configured_generation_params(
    config: Mapping[str, Any],
    *,
    max_tokens_parameter: str,
    stop_sequences_parameter: str | None,
    top_k_parameter: str | None = None,
) -> dict[str, Any]:
    """Translate only operator-supplied generation settings for one vendor."""
    parameter_names = (
        ("max_tokens", max_tokens_parameter),
        ("temperature", "temperature"),
        ("top_p", "top_p"),
        ("top_k", top_k_parameter),
        ("stop_sequences", stop_sequences_parameter),
    )
    return {
        target: config[source]
        for source, target in parameter_names
        if target is not None and source in config and config[source] is not None
    }


__all__ = [
    "configured_generation_params",
    "require_max_tokens",
    "require_model",
]
