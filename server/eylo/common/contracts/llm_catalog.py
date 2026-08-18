"""Vendor-neutral LLM provider and model catalog contracts."""

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator

__all__ = [
    "LLMConfigSchema",
    "LLMModels",
    "LLMProviders",
    "is_model_supported",
    "models_for_provider",
]

_CLAUDE_MODELS = [
    # Latest Models (Claude 4.5)
    "claude-sonnet-4-5-20250929",
    "claude-haiku-4-5-20251001",
    "claude-opus-4-5-20251101",
    # Legacy Models (deprecated - migrate to Claude 4.5)
    "claude-opus-4-1-20250805",
    "claude-sonnet-4-20250514",
    "claude-3-7-sonnet-20250219",
    "claude-opus-4-20250514",
    "claude-3-haiku-20240307",
    # deprecated - no longer in official documentation
    "claude-3-5-sonnet-20241022",
]

_AWS_CLAUDE_MODELS = [
    # deprecated - use apac or global regional variants
    "anthropic.claude-3-7-sonnet-20250219-v1:0",
    # deprecated - use apac or global regional variants
    "us.anthropic.claude-3-7-sonnet-20250219-v1:0",
    # deprecated - use apac or global regional variants
    "eu.anthropic.claude-3-7-sonnet-20250219-v1:0",
    # deprecated - use apac or global regional variants
    "anthropic.claude-3-5-sonnet-20241022-v2:0",
    # deprecated - use apac or global regional variants
    "us.anthropic.claude-3-5-sonnet-20241022-v2:0",
    # deprecated - use apac or global regional variants
    "anthropic.claude-3-5-sonnet-20240620-v1:0",
    # deprecated - use apac or global regional variants
    "us.anthropic.claude-3-5-sonnet-20240620-v1:0",
    # deprecated - use apac or global regional variants
    "eu.anthropic.claude-3-5-sonnet-20240620-v1:0",
    # deprecated - use apac or global regional variants
    "us.anthropic.claude-3-5-haiku-20241022-v1:0",
    # deprecated - use apac or global regional variants
    "us.anthropic.claude-3-sonnet-20240229-v1:0",
    # deprecated - use apac or global regional variants
    "eu.anthropic.claude-3-sonnet-20240229-v1:0",
    # deprecated - use apac or global regional variants
    "anthropic.claude-3-haiku-20240307-v1:0",
    # deprecated - use apac or global regional variants
    "us.anthropic.claude-3-haiku-20240307-v1:0",
    # deprecated - use apac or global regional variants
    "eu.anthropic.claude-3-haiku-20240307-v1:0",
    # deprecated - use apac or global regional variants
    "us.anthropic.claude-3-opus-20240229-v1:0",
    # deprecated - use apac or global regional variants
    "anthropic.claude-sonnet-4-20250514-v1:0",
    # deprecated - use apac or global regional variants
    "us.anthropic.claude-sonnet-4-20250514-v1:0",
    # deprecated - use apac or global regional variants
    "eu.anthropic.claude-sonnet-4-20250514-v1:0",
    # deprecated - use apac or global regional variants
    "anthropic.claude-sonnet-4-5-20250929-v1:0",
    # deprecated - use apac or global regional variants
    "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
    # deprecated - use apac or global regional variants
    "au.anthropic.claude-sonnet-4-5-20250929-v1:0",
    # deprecated - use apac or global regional variants
    "eu.anthropic.claude-sonnet-4-5-20250929-v1:0",
    # deprecated - use apac or global regional variants
    "jp.anthropic.claude-sonnet-4-5-20250929-v1:0",
    # deprecated - use apac or global regional variants
    "us.anthropic.claude-opus-4-20250514-v1:0",
    # deprecated - use apac or global regional variants
    "anthropic.claude-opus-4-1-20250805-v1:0",
    # deprecated - use apac or global regional variants
    "us.anthropic.claude-opus-4-1-20250805-v1:0",
    # deprecated - use apac or global regional variants
    "us.anthropic.claude-opus-4-5-20251101-v1:0",
    # deprecated - use apac or global regional variants
    "eu.anthropic.claude-opus-4-5-20251101-v1:0",
    # deprecated - use apac or global regional variants
    "us.anthropic.claude-haiku-4-5-20251001-v1:0",
    # deprecated - use apac or global regional variants
    "au.anthropic.claude-haiku-4-5-20251001-v1:0",
    # deprecated - use apac or global regional variants
    "eu.anthropic.claude-haiku-4-5-20251001-v1:0",
    # deprecated - use apac or global regional variants
    "jp.anthropic.claude-haiku-4-5-20251001-v1:0",
    # Active Models - Claude 3.7 Sonnet
    "apac.anthropic.claude-3-7-sonnet-20250219-v1:0",
    # Active Models - Claude 3.5 Sonnet
    "apac.anthropic.claude-3-5-sonnet-20241022-v2:0",
    "apac.anthropic.claude-3-5-sonnet-20240620-v1:0",
    # Active Models - Claude 3 Sonnet
    "apac.anthropic.claude-3-sonnet-20240229-v1:0",
    # Active Models - Claude 3 Haiku
    "apac.anthropic.claude-3-haiku-20240307-v1:0",
    # Active Models - Claude Sonnet 4
    "global.anthropic.claude-sonnet-4-20250514-v1:0",
    "apac.anthropic.claude-sonnet-4-20250514-v1:0",
    # Active Models - Claude Sonnet 4.5
    "global.anthropic.claude-sonnet-4-5-20250929-v1:0",
    # Active Models - Claude Opus 4.5
    "global.anthropic.claude-opus-4-5-20251101-v1:0",
    # Active Models - Claude Haiku 4.5
    "global.anthropic.claude-haiku-4-5-20251001-v1:0",
]

_OPENAI_ACTIVE_MODELS = [
    # Frontier models - https://developers.openai.com/api/docs/models/all
    "gpt-5.4",
    "gpt-5.4-pro",
    "gpt-5.4-mini",
    "gpt-5.4-nano",
    "gpt-5-mini",
    "gpt-5-nano",
    "gpt-5",
    "gpt-4.1",
]

_OPENAI_DEPRECATED_MODELS = [
    "gpt-4o",
    "gpt-4o-mini",
    "gpt-4-turbo",
    "gpt-4",
    "gpt-3.5-turbo",
    "gpt-5.2",
    "gpt-5.1",
    "gpt-5.2-pro",
    "gpt-5-pro",
]

_OPENAI_MODELS = _OPENAI_ACTIVE_MODELS + _OPENAI_DEPRECATED_MODELS

_GEMINI_MODELS = [
    # deprecated - experimental/unstable
    "gemini-2.0-flash-exp",
    # deprecated - shutdown earliest February 2026
    "gemini-2.0-flash-001",
    "gemini-1.5-pro",
    "gemini-1.5-flash",
    # Gemini 3 Models (Latest)
    "gemini-3-flash-preview",
    "gemini-3-pro-preview",
    # Gemini 2.5 Models
    "gemini-2.5-flash",
    "gemini-2.5-pro",
    "gemini-2.5-flash-lite",
]

_CEREBRAS_MODELS = [
    "gpt-oss-120b",
    "zai-glm-4.7",
]
# Retain these only for reading existing configs. Cerebras removed both after
# May 27, 2026, so new configs must not offer them in the model selector.
# Source: https://inference-docs.cerebras.ai/support/deprecation
_CEREBRAS_LEGACY_MODELS = [
    "llama3.1-8b",
    "qwen-3-235b-a22b-instruct-2507",
]

_GROQ_MODELS = [
    "llama-3.1-8b-instant",
    "llama-3.3-70b-versatile",
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "moonshotai/kimi-k2-instruct-0905",
    "qwen/qwen3-32b",
]

# OpenAI Responses API supports the same models as Chat Completions.
# Kept as a separate list so model availability can diverge independently.
_OPENAI_RESPONSES_MODELS = list(_OPENAI_MODELS)

_SARVAM_MODELS = [
    "sarvam-30b",
    "sarvam-105b",
    # Legacy model retained for compatibility.
    "sarvam-m",
]


class LLMProviders(str, Enum):
    ANTHROPIC = "ANTHROPIC"
    BEDROCK = "BEDROCK"
    CEREBRAS = "CEREBRAS"
    GEMINI = "GEMINI"
    GROQ = "GROQ"
    OPENAI = "OPENAI"
    OPENAI_RESPONSES = "OPENAI_RESPONSES"
    SARVAM = "SARVAM"


class LLMModels(str, Enum):
    # Anthropic Direct API Models - Latest (Claude 4.5)
    ANTHROPIC_CLAUDE_SONNET_4_5 = "claude-sonnet-4-5-20250929"
    ANTHROPIC_CLAUDE_HAIKU_4_5 = "claude-haiku-4-5-20251001"
    ANTHROPIC_CLAUDE_OPUS_4_5 = "claude-opus-4-5-20251101"

    # Anthropic Direct API Models - Legacy (deprecated - migrate to Claude 4.5)
    ANTHROPIC_CLAUDE_OPUS_4_1 = "claude-opus-4-1-20250805"
    ANTHROPIC_CLAUDE_SONNET_4 = "claude-sonnet-4-20250514"
    ANTHROPIC_CLAUDE_3_7_SONNET = "claude-3-7-sonnet-20250219"
    ANTHROPIC_CLAUDE_OPUS_4 = "claude-opus-4-20250514"
    ANTHROPIC_CLAUDE_3_HAIKU = "claude-3-haiku-20240307"
    # deprecated - no longer in official documentation
    ANTHROPIC_CLAUDE_3_5_SONNET = "claude-3-5-sonnet-20241022"

    # AWS Bedrock Models - Latest (Claude 4.5) - Active APAC/Global only
    BEDROCK_GLOBAL_CLAUDE_SONNET_4_5 = (
        "global.anthropic.claude-sonnet-4-5-20250929-v1:0"
    )
    BEDROCK_GLOBAL_CLAUDE_OPUS_4_5 = "global.anthropic.claude-opus-4-5-20251101-v1:0"
    BEDROCK_GLOBAL_CLAUDE_HAIKU_4_5 = "global.anthropic.claude-haiku-4-5-20251001-v1:0"

    # AWS Bedrock Models - Claude Sonnet 4 - Active APAC/Global only
    BEDROCK_GLOBAL_CLAUDE_SONNET_4 = "global.anthropic.claude-sonnet-4-20250514-v1:0"
    BEDROCK_APAC_CLAUDE_SONNET_4 = "apac.anthropic.claude-sonnet-4-20250514-v1:0"

    # AWS Bedrock Models - Claude 3.7 Sonnet - Active APAC only
    BEDROCK_APAC_CLAUDE_3_7_SONNET = "apac.anthropic.claude-3-7-sonnet-20250219-v1:0"

    # AWS Bedrock Models - Claude 3.5 Sonnet - Active APAC only
    BEDROCK_APAC_CLAUDE_3_5_SONNET_V2 = "apac.anthropic.claude-3-5-sonnet-20241022-v2:0"
    BEDROCK_APAC_CLAUDE_3_5_SONNET = "apac.anthropic.claude-3-5-sonnet-20240620-v1:0"

    # AWS Bedrock Models - Claude 3 Sonnet - Active APAC only
    BEDROCK_APAC_CLAUDE_3_SONNET = "apac.anthropic.claude-3-sonnet-20240229-v1:0"

    # AWS Bedrock Models - Claude 3 Haiku - Active APAC only
    BEDROCK_APAC_CLAUDE_3_HAIKU = "apac.anthropic.claude-3-haiku-20240307-v1:0"

    # deprecated - use apac or global regional variants
    BEDROCK_CLAUDE_3_7_SONNET = "anthropic.claude-3-7-sonnet-20250219-v1:0"
    # deprecated - use apac or global regional variants
    BEDROCK_US_CLAUDE_3_7_SONNET = "us.anthropic.claude-3-7-sonnet-20250219-v1:0"
    # deprecated - use apac or global regional variants
    BEDROCK_EU_CLAUDE_3_7_SONNET = "eu.anthropic.claude-3-7-sonnet-20250219-v1:0"
    # deprecated - use apac or global regional variants
    BEDROCK_CLAUDE_3_5_SONNET = "anthropic.claude-3-5-sonnet-20241022-v2:0"
    # deprecated - use apac or global regional variants
    BEDROCK_US_CLAUDE_3_5_SONNET = "us.anthropic.claude-3-5-sonnet-20241022-v2:0"
    # deprecated - use apac or global regional variants
    BEDROCK_CLAUDE_3_5_SONNET_20240620 = "anthropic.claude-3-5-sonnet-20240620-v1:0"
    # deprecated - use apac or global regional variants
    BEDROCK_US_CLAUDE_3_5_SONNET_20240620 = (
        "us.anthropic.claude-3-5-sonnet-20240620-v1:0"
    )
    # deprecated - use apac or global regional variants
    BEDROCK_EU_CLAUDE_3_5_SONNET = "eu.anthropic.claude-3-5-sonnet-20240620-v1:0"
    # deprecated - use apac or global regional variants
    BEDROCK_US_CLAUDE_3_5_HAIKU = "us.anthropic.claude-3-5-haiku-20241022-v1:0"
    # deprecated - use apac or global regional variants
    BEDROCK_US_CLAUDE_3_SONNET = "us.anthropic.claude-3-sonnet-20240229-v1:0"
    # deprecated - use apac or global regional variants
    BEDROCK_EU_CLAUDE_3_SONNET = "eu.anthropic.claude-3-sonnet-20240229-v1:0"
    # deprecated - use apac or global regional variants
    BEDROCK_CLAUDE_3_HAIKU = "anthropic.claude-3-haiku-20240307-v1:0"
    # deprecated - use apac or global regional variants
    BEDROCK_US_CLAUDE_3_HAIKU = "us.anthropic.claude-3-haiku-20240307-v1:0"
    # deprecated - use apac or global regional variants
    BEDROCK_EU_CLAUDE_3_HAIKU = "eu.anthropic.claude-3-haiku-20240307-v1:0"
    # deprecated - use apac or global regional variants
    BEDROCK_US_CLAUDE_3_OPUS = "us.anthropic.claude-3-opus-20240229-v1:0"
    # deprecated - use apac or global regional variants
    BEDROCK_CLAUDE_SONNET_4 = "anthropic.claude-sonnet-4-20250514-v1:0"
    # deprecated - use apac or global regional variants
    BEDROCK_US_CLAUDE_SONNET_4 = "us.anthropic.claude-sonnet-4-20250514-v1:0"
    # deprecated - use apac or global regional variants
    BEDROCK_EU_CLAUDE_SONNET_4 = "eu.anthropic.claude-sonnet-4-20250514-v1:0"
    # deprecated - use apac or global regional variants
    BEDROCK_CLAUDE_SONNET_4_5 = "anthropic.claude-sonnet-4-5-20250929-v1:0"
    # deprecated - use apac or global regional variants
    BEDROCK_US_CLAUDE_SONNET_4_5 = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
    # deprecated - use apac or global regional variants
    BEDROCK_AU_CLAUDE_SONNET_4_5 = "au.anthropic.claude-sonnet-4-5-20250929-v1:0"
    # deprecated - use apac or global regional variants
    BEDROCK_EU_CLAUDE_SONNET_4_5 = "eu.anthropic.claude-sonnet-4-5-20250929-v1:0"
    # deprecated - use apac or global regional variants
    BEDROCK_JP_CLAUDE_SONNET_4_5 = "jp.anthropic.claude-sonnet-4-5-20250929-v1:0"
    # deprecated - use apac or global regional variants
    BEDROCK_US_CLAUDE_OPUS_4 = "us.anthropic.claude-opus-4-20250514-v1:0"
    # deprecated - use apac or global regional variants
    BEDROCK_CLAUDE_OPUS_4_1 = "anthropic.claude-opus-4-1-20250805-v1:0"
    # deprecated - use apac or global regional variants
    BEDROCK_US_CLAUDE_OPUS_4_1 = "us.anthropic.claude-opus-4-1-20250805-v1:0"
    # deprecated - use apac or global regional variants
    BEDROCK_US_CLAUDE_OPUS_4_5 = "us.anthropic.claude-opus-4-5-20251101-v1:0"
    # deprecated - use apac or global regional variants
    BEDROCK_EU_CLAUDE_OPUS_4_5 = "eu.anthropic.claude-opus-4-5-20251101-v1:0"
    # deprecated - use apac or global regional variants
    BEDROCK_US_CLAUDE_HAIKU_4_5 = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
    # deprecated - use apac or global regional variants
    BEDROCK_AU_CLAUDE_HAIKU_4_5 = "au.anthropic.claude-haiku-4-5-20251001-v1:0"
    # deprecated - use apac or global regional variants
    BEDROCK_EU_CLAUDE_HAIKU_4_5 = "eu.anthropic.claude-haiku-4-5-20251001-v1:0"
    # deprecated - use apac or global regional variants
    BEDROCK_JP_CLAUDE_HAIKU_4_5 = "jp.anthropic.claude-haiku-4-5-20251001-v1:0"

    # Google Gemini Models
    # deprecated - experimental/unstable
    GEMINI_2_0_FLASH_EXP = "gemini-2.0-flash-exp"
    # deprecated - shutdown earliest February 2026
    GEMINI_2_0_FLASH = "gemini-2.0-flash-001"
    GEMINI_1_5_PRO = "gemini-1.5-pro"
    GEMINI_1_5_FLASH = "gemini-1.5-flash"
    # Gemini 3 Models (Latest)
    GEMINI_3_FLASH = "gemini-3-flash-preview"
    GEMINI_3_PRO = "gemini-3-pro-preview"
    # Gemini 2.5 Models
    GEMINI_2_5_FLASH = "gemini-2.5-flash"
    GEMINI_2_5_PRO = "gemini-2.5-pro"
    GEMINI_2_5_FLASH_LITE = "gemini-2.5-flash-lite"

    # OpenAI Models - Frontier (active)
    OPENAI_GPT_5_4 = "gpt-5.4"
    OPENAI_GPT_5_4_PRO = "gpt-5.4-pro"
    OPENAI_GPT_5_4_MINI = "gpt-5.4-mini"
    OPENAI_GPT_5_4_NANO = "gpt-5.4-nano"
    OPENAI_GPT_5_MINI = "gpt-5-mini"
    OPENAI_GPT_5_NANO = "gpt-5-nano"
    OPENAI_GPT_5 = "gpt-5"
    OPENAI_GPT_4_1 = "gpt-4.1"

    # OpenAI Models - Deprecated
    OPENAI_GPT_4O = "gpt-4o"
    OPENAI_GPT_4O_MINI = "gpt-4o-mini"
    OPENAI_GPT_4_TURBO = "gpt-4-turbo"
    OPENAI_GPT_4 = "gpt-4"
    OPENAI_GPT_3_5_TURBO = "gpt-3.5-turbo"
    OPENAI_GPT_5_2 = "gpt-5.2"
    OPENAI_GPT_5_1 = "gpt-5.1"
    OPENAI_GPT_5_2_PRO = "gpt-5.2-pro"
    OPENAI_GPT_5_PRO = "gpt-5-pro"

    # Sarvam Models
    SARVAM_30B = "sarvam-30b"
    SARVAM_105B = "sarvam-105b"
    # Legacy model - prefer Sarvam-30B or Sarvam-105B.
    SARVAM_M = "sarvam-m"

    # Cerebras Models
    CEREBRAS_LLAMA_3_1_8B = "llama3.1-8b"
    CEREBRAS_GPT_OSS_120B = "gpt-oss-120b"
    CEREBRAS_QWEN_3_235B = "qwen-3-235b-a22b-instruct-2507"
    CEREBRAS_ZAI_GLM_4_7 = "zai-glm-4.7"

    # Groq Models
    GROQ_LLAMA_3_1_8B = "llama-3.1-8b-instant"
    GROQ_LLAMA_3_3_70B = "llama-3.3-70b-versatile"
    GROQ_GPT_OSS_120B = "openai/gpt-oss-120b"
    GROQ_GPT_OSS_20B = "openai/gpt-oss-20b"
    GROQ_KIMI_K2 = "moonshotai/kimi-k2-instruct-0905"
    GROQ_QWEN3_32B = "qwen/qwen3-32b"


_MODELS_BY_PROVIDER = {
    LLMProviders.ANTHROPIC: tuple(_CLAUDE_MODELS),
    LLMProviders.BEDROCK: tuple(_AWS_CLAUDE_MODELS),
    LLMProviders.CEREBRAS: tuple(_CEREBRAS_MODELS + _CEREBRAS_LEGACY_MODELS),
    LLMProviders.GEMINI: tuple(_GEMINI_MODELS),
    LLMProviders.GROQ: tuple(_GROQ_MODELS),
    LLMProviders.OPENAI: tuple(_OPENAI_MODELS),
    LLMProviders.OPENAI_RESPONSES: tuple(_OPENAI_RESPONSES_MODELS),
    LLMProviders.SARVAM: tuple(_SARVAM_MODELS),
}
_SELECTABLE_MODELS_BY_PROVIDER = {
    **_MODELS_BY_PROVIDER,
    LLMProviders.CEREBRAS: tuple(_CEREBRAS_MODELS),
}


def is_model_supported(vendor: LLMProviders, model: LLMModels | str) -> bool:
    """Return whether a model belongs to a native provider's catalog."""
    model_value = model.value if isinstance(model, LLMModels) else model
    return model_value in _MODELS_BY_PROVIDER.get(vendor, ())


def models_for_provider(provider: LLMProviders) -> tuple[str, ...]:
    """Return one provider's supported models in deterministic catalog order."""
    return _SELECTABLE_MODELS_BY_PROVIDER[provider]


class LLMConfigSchema(BaseModel):
    vendor: LLMProviders = Field(
        ..., description="The LLM vendor (e.g., Anthropic, AWS Bedrock)."
    )
    model: LLMModels = Field(
        ..., description="The model name (e.g., claude-3-7-sonnet-20250219)."
    )
    max_tokens: Optional[int] = Field(
        None, description="Maximum number of tokens to generate."
    )
    # read about NOT_GIVEN
    top_k: Optional[int] = Field(None, description="Top K sampling.")
    top_p: Optional[float] = Field(None, description="Top P sampling.")
    temperature: Optional[float] = Field(None, description="Sampling temperature.")
    stop_sequences: Optional[List[str]] = Field(
        None, description="List of stop sequences to use for generation."
    )

    @model_validator(mode="after")
    def validate_model_vendor(self):
        if not is_model_supported(self.vendor, self.model):
            raise ValueError(
                f"Model {self.model} is not valid for vendor {self.vendor}."
            )
        return self

    class Config:
        from_attributes = True
