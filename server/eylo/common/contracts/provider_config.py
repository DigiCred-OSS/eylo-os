"""Neutral provider-capability names and configuration failure contracts."""

import re
from collections.abc import Iterable
from enum import Enum

_MISSING_IDENTIFIER_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


class Capability(str, Enum):
    LLM = "llm"
    STT = "stt"
    TTS = "tts"
    REALTIME = "realtime"
    WEBRTC = "webrtc"
    TELEPHONY = "telephony"
    EMAIL = "email"
    STORAGE = "storage"
    MEMORY = "memory"
    EMBEDDING = "embedding"
    RERANKING = "reranking"
    SANDBOX = "sandbox"


class ProviderConfigError(Exception):
    """Base error for provider-config lifecycle operations."""


class NotConfiguredError(ProviderConfigError):
    """Structured error for an unavailable external capability."""

    def __init__(
        self,
        *,
        capability: Capability | str,
        missing: Iterable[str],
        configure_via: str,
    ):
        self.capability = _validate_capability(capability)
        self.missing = _validate_missing(missing)
        self.configure_via = _validate_configure_path(configure_via)
        super().__init__(f"{self.capability.value} capability is not configured.")


def _validate_capability(value: Capability | str) -> Capability:
    try:
        return Capability(value)
    except ValueError as error:
        raise ValueError("Capability is not supported.") from error


def _validate_missing(values: Iterable[str]) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)):
        raise ValueError("Missing identifiers must be a collection of names.")
    missing = tuple(values)
    if not missing or not all(
        isinstance(value, str) and _MISSING_IDENTIFIER_PATTERN.fullmatch(value)
        for value in missing
    ):
        raise ValueError("Missing identifiers must be stable machine-readable names.")
    return missing


def _validate_configure_path(value: str) -> str:
    if not isinstance(value, str) or not value.startswith("/api/"):
        raise ValueError("Configuration path must be an API path.")
    return value


__all__ = ["Capability", "NotConfiguredError", "ProviderConfigError"]
