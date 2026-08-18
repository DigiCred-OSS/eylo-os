"""Run input and mutable run context contracts."""

from __future__ import annotations

import time
from uuid import UUID, uuid4

from pydantic import Field

from .agent import AgentSpec
from .common import FrameworkMetadata, FrameworkModel, FrozenFrameworkModel
from .config import RunConfig
from .model import ModelUsage
from .tool import ToolSpec


class RunMessage(FrozenFrameworkModel):
    """LLM-visible message passed to a model."""

    role: str
    content: str
    id: UUID | None = None
    metadata: FrameworkMetadata = Field(default_factory=FrameworkMetadata)


class RunInput(FrozenFrameworkModel):
    """All LLM-visible input for one model call."""

    instructions: str
    messages: tuple[RunMessage, ...] = ()
    tools: tuple[ToolSpec, ...] = ()
    metadata: FrameworkMetadata = Field(default_factory=FrameworkMetadata)


class RunContext(FrameworkModel):
    """Mutable local state for one framework run.

    ``local_context`` is for application dependencies and must never be copied
    into ``RunInput``.
    """

    run_id: UUID = Field(default_factory=uuid4)
    request_id: UUID | None = None
    conversation_id: UUID | None = None
    organization_id: UUID | None = None
    config: RunConfig = Field(default_factory=RunConfig)
    current_agent: AgentSpec
    handoff_chain: list[AgentSpec] = Field(default_factory=list)
    turn: int = 0
    usage: ModelUsage = Field(default_factory=ModelUsage)
    start_time: float = Field(default_factory=time.monotonic)
    local_context: object | None = None
    metadata: FrameworkMetadata = Field(default_factory=FrameworkMetadata)

    @property
    def elapsed_seconds(self) -> float:
        """Return wall-clock runtime for this run."""
        return time.monotonic() - self.start_time

    @property
    def is_timed_out(self) -> bool:
        """Return whether the run exceeded its timeout."""
        return self.elapsed_seconds >= self.config.request_timeout_seconds

    @property
    def remaining_timeout_seconds(self) -> float:
        """Return wall-clock seconds left before the run times out."""
        return max(self.config.request_timeout_seconds - self.elapsed_seconds, 0.0)

    def record_handoff(self, agent: AgentSpec) -> None:
        """Record an active-agent switch."""
        self.current_agent = agent
        self.handoff_chain.append(agent)
