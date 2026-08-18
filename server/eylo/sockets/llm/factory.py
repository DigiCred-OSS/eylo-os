"""Construct native LLM adapters from organization-scoped resolved config."""

from eylo.common.contracts.llm_catalog import LLMProviders
from eylo.common.contracts.llm_runtime import (
    InvalidLLMConfig,
    ResolvedLLMConfig,
)
from eylo.sockets.llm.base import LLMVendorAdapter
from eylo.sockets.llm.vendors.anthropic import AnthropicAdapter
from eylo.sockets.llm.vendors.bedrock import AWSBedrockAdapter
from eylo.sockets.llm.vendors.cerebras import CerebrasAdapter
from eylo.sockets.llm.vendors.gemini import GeminiAdapter
from eylo.sockets.llm.vendors.groq import GroqAdapter
from eylo.sockets.llm.vendors.openai import OpenAIAdapter
from eylo.sockets.llm.vendors.openai_responses import OpenAIResponsesAdapter
from eylo.sockets.llm.vendors.sarvam import SarvamAdapter

LLMService = LLMVendorAdapter


class LLMFactory:
    """Create one cached native adapter from an immutable resolved config."""

    def __init__(self, resolved_llm: ResolvedLLMConfig) -> None:
        self._resolved_llm = resolved_llm
        self._llm_service: LLMService | None = None

    @classmethod
    def from_resolved(cls, resolved_llm: ResolvedLLMConfig) -> "LLMFactory":
        return cls(resolved_llm)

    def get_adapter(self) -> LLMService:
        if self._llm_service is None:
            self._llm_service = self._create_adapter(self._resolved_llm)
        return self._llm_service

    @staticmethod
    def _create_adapter(resolved: ResolvedLLMConfig) -> LLMService:
        if resolved.provider is LLMProviders.ANTHROPIC:
            return AnthropicAdapter(api_key=_required_secret(resolved, "api_key"))
        if resolved.provider is LLMProviders.BEDROCK:
            return AWSBedrockAdapter(
                aws_access_key=_required_secret(resolved, "access_key_id"),
                aws_secret_key=_required_secret(resolved, "secret_access_key"),
                aws_session_token=resolved.secret("session_token"),
                aws_region=_required_region(resolved),
            )
        if resolved.provider is LLMProviders.CEREBRAS:
            return CerebrasAdapter(api_key=_required_secret(resolved, "api_key"))
        if resolved.provider is LLMProviders.GEMINI:
            return GeminiAdapter(api_key=_required_secret(resolved, "api_key"))
        if resolved.provider is LLMProviders.GROQ:
            return GroqAdapter(api_key=_required_secret(resolved, "api_key"))
        if resolved.provider is LLMProviders.OPENAI:
            return OpenAIAdapter(api_key=_required_secret(resolved, "api_key"))
        if resolved.provider is LLMProviders.OPENAI_RESPONSES:
            return OpenAIResponsesAdapter(
                api_key=_required_secret(resolved, "api_key")
            )
        if resolved.provider is LLMProviders.SARVAM:
            return SarvamAdapter(api_key=_required_secret(resolved, "api_key"))
        raise InvalidLLMConfig("Resolved LLM provider is not supported.")

    @property
    def adapter(self) -> LLMVendorAdapter:
        return self.get_adapter()


def _required_secret(resolved: ResolvedLLMConfig, name: str) -> str:
    value = resolved.secret(name)
    if value is None:
        raise InvalidLLMConfig("Resolved LLM credentials are incomplete.")
    return value


def _required_region(resolved: ResolvedLLMConfig) -> str:
    if resolved.region is None:
        raise InvalidLLMConfig("Resolved LLM region is missing.")
    return resolved.region
