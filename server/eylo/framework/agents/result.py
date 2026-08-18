"""Run result contracts."""

from __future__ import annotations

from enum import Enum
from uuid import UUID

from pydantic import Field

from .agent import AgentSpec
from .common import FrameworkMetadata, FrozenFrameworkModel
from .items import RunItem
from .model import ModelResponse, ModelUsage


class RunStatus(str, Enum):
    """Terminal or interrupted state of a framework run."""

    COMPLETED = "completed"
    FAILED = "failed"
    GUARDRAIL_TRIPPED = "guardrail_tripped"
    TIMED_OUT = "timed_out"
    MAX_TURNS_EXCEEDED = "max_turns_exceeded"
    WAITING_FOR_INPUT = "waiting_for_input"
    WAITING_FOR_APPROVAL = "waiting_for_approval"
    CANCELLED = "cancelled"


class RunResult(FrozenFrameworkModel):
    """Immutable outcome of a framework run."""

    run_id: UUID
    status: RunStatus
    final_output: str | None = None
    final_message_id: UUID | None = None
    items: tuple[RunItem, ...] = ()
    model_responses: tuple[ModelResponse, ...] = ()
    usage: ModelUsage = Field(default_factory=ModelUsage)
    starting_agent: AgentSpec | None = None
    final_agent: AgentSpec | None = None
    error_message: str | None = None
    metadata: FrameworkMetadata = Field(default_factory=FrameworkMetadata)

    @property
    def is_success(self) -> bool:
        """Return whether the run completed successfully."""
        return self.status == RunStatus.COMPLETED
