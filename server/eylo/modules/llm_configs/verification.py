"""Live credential verification through official async provider SDKs.

API patterns follow current official SDK references:
- Anthropic and Bedrock: https://github.com/anthropics/anthropic-sdk-python
- Bedrock example: https://github.com/anthropics/anthropic-sdk-python/blob/main/examples/bedrock.py
- Cerebras: https://github.com/Cerebras/cerebras-cloud-sdk-python#async-usage
- Gemini: https://github.com/googleapis/python-genai#client-context-managers
- Groq: https://github.com/groq/groq-python#async-usage
- OpenAI: https://github.com/openai/openai-python#async-usage
- Sarvam: https://pypi.org/project/sarvamai/0.1.28/
"""

import asyncio
from collections.abc import Awaitable
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

import httpx
from anthropic import AsyncAnthropic, AsyncAnthropicBedrock
from cerebras.cloud.sdk import AsyncCerebras
from google import genai
from google.genai import types
from groq import AsyncGroq
from openai import AsyncOpenAI
from sarvamai import AsyncSarvamAI

from eylo.modules.llm_configs.catalog import LLMProviders
from eylo.modules.llm_configs.domain import (
    LLMProviderConfig,
)
from eylo.modules.llm_configs.service import (
    LLMConfigService,
    to_llm_provider_config,
)

_VERIFICATION_PROMPT = "Reply OK."
_VERIFICATION_TIMEOUT_SECONDS = 20.0


class LLMVerificationError(Exception):
    """Raised when a provider rejects or cannot complete verification."""


@dataclass(frozen=True)
class LLMProviderVerification:
    provider: str
    model: str


@dataclass(frozen=True)
class LLMVerificationResult:
    provider: str
    model: str
    revision: int
    verified_at: datetime


class LLMCredentialVerifier:
    """Make one bounded, minimal generation call for a validated config."""

    async def verify(self, config: LLMProviderConfig) -> LLMProviderVerification:
        handlers = {
            LLMProviders.ANTHROPIC: self._verify_anthropic,
            LLMProviders.BEDROCK: self._verify_bedrock,
            LLMProviders.CEREBRAS: self._verify_cerebras,
            LLMProviders.GEMINI: self._verify_gemini,
            LLMProviders.GROQ: self._verify_groq,
            LLMProviders.OPENAI: self._verify_openai,
            LLMProviders.OPENAI_RESPONSES: self._verify_openai_responses,
            LLMProviders.SARVAM: self._verify_sarvam,
        }
        try:
            await handlers[config.provider](config)
        except Exception:
            raise LLMVerificationError(
                "LLM provider verification failed."
            ) from None
        return LLMProviderVerification(
            provider=config.storage_provider,
            model=config.generation.model.value,
        )

    async def _verify_anthropic(self, config: LLMProviderConfig) -> None:
        async with AsyncAnthropic(
            api_key=_api_key(config),
            timeout=_VERIFICATION_TIMEOUT_SECONDS,
            max_retries=0,
        ) as client:
            await _with_timeout(
                client.messages.create(
                    model=config.generation.model.value,
                    max_tokens=1,
                    messages=[{"role": "user", "content": _VERIFICATION_PROMPT}],
                )
            )

    async def _verify_bedrock(self, config: LLMProviderConfig) -> None:
        client = AsyncAnthropicBedrock(
            aws_access_key=_required_secret(config, "access_key_id"),
            aws_secret_key=_required_secret(config, "secret_access_key"),
            aws_session_token=config.secrets.get("session_token"),
            aws_region=config.region,
            timeout=_VERIFICATION_TIMEOUT_SECONDS,
            max_retries=0,
        )
        async with client:
            await _with_timeout(
                client.messages.create(
                    model=config.generation.model.value,
                    max_tokens=1,
                    messages=[{"role": "user", "content": _VERIFICATION_PROMPT}],
                )
            )

    async def _verify_cerebras(self, config: LLMProviderConfig) -> None:
        async with AsyncCerebras(
            api_key=_api_key(config),
            timeout=_VERIFICATION_TIMEOUT_SECONDS,
            max_retries=0,
        ) as client:
            await _with_timeout(
                client.chat.completions.create(
                    model=config.generation.model.value,
                    messages=[{"role": "user", "content": _VERIFICATION_PROMPT}],
                    max_completion_tokens=1,
                )
            )

    async def _verify_gemini(self, config: LLMProviderConfig) -> None:
        client = genai.Client(api_key=_api_key(config))
        async with client.aio as async_client:
            await _with_timeout(
                async_client.models.generate_content(
                    model=config.generation.model.value,
                    contents=_VERIFICATION_PROMPT,
                    config=types.GenerateContentConfig(max_output_tokens=1),
                )
            )

    async def _verify_groq(self, config: LLMProviderConfig) -> None:
        async with AsyncGroq(
            api_key=_api_key(config),
            timeout=_VERIFICATION_TIMEOUT_SECONDS,
            max_retries=0,
        ) as client:
            await _with_timeout(
                client.chat.completions.create(
                    model=config.generation.model.value,
                    messages=[{"role": "user", "content": _VERIFICATION_PROMPT}],
                    max_completion_tokens=1,
                )
            )

    async def _verify_openai(self, config: LLMProviderConfig) -> None:
        async with AsyncOpenAI(
            api_key=_api_key(config),
            timeout=_VERIFICATION_TIMEOUT_SECONDS,
            max_retries=0,
        ) as client:
            await _with_timeout(
                client.chat.completions.create(
                    model=config.generation.model.value,
                    messages=[{"role": "user", "content": _VERIFICATION_PROMPT}],
                    max_completion_tokens=1,
                )
            )

    async def _verify_openai_responses(self, config: LLMProviderConfig) -> None:
        async with AsyncOpenAI(
            api_key=_api_key(config),
            timeout=_VERIFICATION_TIMEOUT_SECONDS,
            max_retries=0,
        ) as client:
            await _with_timeout(
                client.responses.create(
                    model=config.generation.model.value,
                    input=_VERIFICATION_PROMPT,
                    max_output_tokens=16,
                )
            )

    async def _verify_sarvam(self, config: LLMProviderConfig) -> None:
        async with httpx.AsyncClient(
            timeout=_VERIFICATION_TIMEOUT_SECONDS
        ) as http_client:
            client = AsyncSarvamAI(
                api_subscription_key=_api_key(config),
                timeout=_VERIFICATION_TIMEOUT_SECONDS,
                httpx_client=http_client,
            )
            await _with_timeout(
                client.chat.completions(
                    model=config.generation.model.value,
                    messages=[{"role": "user", "content": _VERIFICATION_PROMPT}],
                    max_tokens=1,
                )
            )


class LLMConfigVerificationService:
    """Load an org-owned config, then invoke the external verification gateway."""

    def __init__(
        self,
        configs: LLMConfigService,
        verifier: LLMCredentialVerifier,
    ):
        self._configs = configs
        self._verifier = verifier

    async def verify(
        self,
        *,
        organization_id: UUID,
        config_id: UUID,
    ) -> LLMVerificationResult:
        stored = await self._configs.get(
            organization_id=organization_id,
            config_id=config_id,
        )
        result = await self._verifier.verify(to_llm_provider_config(stored))
        verified = await self._configs.mark_verified(
            organization_id=organization_id,
            config_id=config_id,
            expected_revision=stored.revision,
        )
        assert verified.verified_at is not None
        return LLMVerificationResult(
            provider=result.provider,
            model=result.model,
            revision=verified.revision,
            verified_at=verified.verified_at,
        )


async def _with_timeout(request: Awaitable[object]) -> None:
    await asyncio.wait_for(request, timeout=_VERIFICATION_TIMEOUT_SECONDS)


def _api_key(config: LLMProviderConfig) -> str:
    return _required_secret(config, "api_key")


def _required_secret(config: LLMProviderConfig, name: str) -> str:
    value = config.secrets.get(name)
    if value is None:
        raise LLMVerificationError("LLM provider verification failed.")
    return value
