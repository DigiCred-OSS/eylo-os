"""Contracts shared across layers.

Types here are consumed by both `sockets/` and `modules/`, so they cannot live
in either without creating a dependency cycle. They are plain data with no
dependency on eylo code.

A type belongs here only when both layers genuinely need it. Behaviour does
not: if a module needs something a socket *does*, that call belongs in
`pipelines/`.
"""

from eylo.common.contracts.llm_response import (
    LLMContentBlock,
    LLMContentType,
    LLMResponse,
    LLMTextBlock,
    LLMToolUseBlock,
    LLMUsageInfo,
)
from eylo.common.contracts.provider_config import (
    Capability,
    NotConfiguredError,
    ProviderConfigError,
)
from eylo.common.contracts.storage import StorageAuthority, StorageLocator
from eylo.common.contracts.voice import InterruptionType

__all__ = [
    "Capability",
    "InterruptionType",
    "LLMContentBlock",
    "LLMContentType",
    "LLMResponse",
    "LLMTextBlock",
    "LLMToolUseBlock",
    "LLMUsageInfo",
    "NotConfiguredError",
    "ProviderConfigError",
    "StorageAuthority",
    "StorageLocator",
]
