"""Sarvam chat adapter built on the official Sarvam SDK."""

from __future__ import annotations

from typing import Any

from sarvamai import AsyncSarvamAI

from eylo.sockets.llm.vendors.openai import OpenAIAdapter


class _SarvamChatCompletionsProxy:
    def __init__(self, client: AsyncSarvamAI):
        self._client = client

    async def create(self, **kwargs: Any) -> Any:
        return await self._client.chat.completions(**kwargs)


class _SarvamChatProxy:
    def __init__(self, client: AsyncSarvamAI):
        self.completions = _SarvamChatCompletionsProxy(client)


class _SarvamCompatClient:
    def __init__(self, client: AsyncSarvamAI):
        self.chat = _SarvamChatProxy(client)


class SarvamAdapter(OpenAIAdapter):
    """Sarvam adapter using the official Sarvam SDK."""

    vendor_name = "sarvam"
    max_tokens_parameter = "max_tokens"

    def get_client(self) -> _SarvamCompatClient:
        """Get an authenticated Sarvam SDK client wrapped in the OpenAI seam."""
        client = AsyncSarvamAI(
            api_subscription_key=self._api_key,
        )
        return _SarvamCompatClient(client)
