"""Neutral values required to select and construct an LLM adapter."""

from collections.abc import Mapping
from typing import Protocol, runtime_checkable

from eylo.common.contracts.llm_catalog import LLMProviders


class LLMConfigError(Exception):
    """Base error for invalid LLM provider configuration."""


class InvalidLLMConfig(LLMConfigError):
    """Raised when LLM config, overrides or secrets violate policy."""


@runtime_checkable
class ResolvedLLMConfig(Protocol):
    """Structural resolved-config view required by adapter factories."""

    @property
    def provider(self) -> LLMProviders: ...

    @property
    def secrets(self) -> Mapping[str, str]: ...

    @property
    def region(self) -> str | None: ...

    def secret(self, name: str) -> str | None: ...
