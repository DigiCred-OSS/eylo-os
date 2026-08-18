"""Immutable run configuration for the framework path."""

from __future__ import annotations

from pydantic import Field

from .common import FrozenFrameworkModel, JsonObject


class RunConfig(FrozenFrameworkModel):
    """Per-run settings for ``FrameworkRunner``."""

    max_turns: int = Field(default=15, gt=0)
    request_timeout_seconds: float = Field(default=120.0, gt=0)
    stream: bool = False
    prompt_caching: bool = False
    max_handoffs: int = Field(default=3, ge=0)
    handoff_lookback_window: int = Field(default=10, gt=0)
    tracing_enabled: bool = True
    metadata: JsonObject = Field(default_factory=dict)
