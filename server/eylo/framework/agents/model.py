"""Provider-agnostic model contracts for framework runs."""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Protocol
from uuid import UUID

from pydantic import Field

from .common import FrameworkMetadata, FrozenFrameworkModel, JsonObject

if TYPE_CHECKING:
    from .context import RunInput


class ModelSettings(FrozenFrameworkModel):
    """Typed model configuration for one agent or run."""

    provider_config_id: UUID | None = None
    provider_config_revision: int | None = Field(default=None, gt=0)
    model: str | None = None
    vendor: str | None = None
    max_tokens: int | None = Field(default=None, gt=0)
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    top_p: float | None = Field(default=None, ge=0.0, le=1.0)
    top_k: int | None = Field(default=None, gt=0)
    stop_sequences: tuple[str, ...] | None = None
    prompt_caching: bool = False
    reasoning: JsonObject | None = None


class ModelBlockKind(str, Enum):
    """Normalized model output block kind."""

    TEXT = "text"
    TOOL_CALL = "tool_call"
    REASONING = "reasoning"


class ModelOutputBlock(FrozenFrameworkModel):
    """One normalized output block returned by a model."""

    kind: ModelBlockKind
    content: str | JsonObject


class ModelUsage(FrozenFrameworkModel):
    """Token usage reported by a model response."""

    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0
    reasoning_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        """Return total billable-ish tokens known to the framework."""
        return self.input_tokens + self.output_tokens


class ModelResponse(FrozenFrameworkModel):
    """Provider-neutral model response consumed by the framework runner."""

    id: str
    model: str
    blocks: tuple[ModelOutputBlock, ...] = ()
    usage: ModelUsage = Field(default_factory=ModelUsage)
    stop_reason: str | None = None
    metadata: FrameworkMetadata = Field(default_factory=FrameworkMetadata)


class Model(Protocol):
    """Protocol implemented by model adapters used by ``FrameworkRunner``."""

    async def generate(
        self,
        run_input: RunInput,
        settings: ModelSettings,
    ) -> ModelResponse:
        """Generate one complete model response."""
