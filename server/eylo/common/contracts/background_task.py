"""Shared persisted background-task envelopes and runtime policy."""

from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class TaskExecutionAuthorityMismatch(ValueError):
    """The persisted task target differs from its immutable AgentRun target."""


class TaskContent(BaseModel):
    """Immutable content stored inside a SYSTEM/TASK message."""

    instruction: str = Field(..., description="Self-contained task description")
    source_agent_id: UUID
    source_agent_revision: int = Field(gt=0)
    swarm_id: Optional[str] = Field(
        None, description="Swarm agent slug, or null for bare LLM task"
    )
    swarm_agent_id: UUID | None = None
    swarm_agent_revision: int | None = Field(default=None, gt=0)
    swarm_topology_id: UUID | None = None
    swarm_topology_revision: int | None = Field(default=None, gt=0)
    background_agent_id: UUID | None = Field(
        None,
        description=(
            "Background agent id. Set when the platform dispatched this on "
            "attachment rather than the model calling spawn_task_fnf, and it "
            "is what routes the worker to the background arm."
        ),
    )
    background_agent_revision: int | None = Field(default=None, gt=0)
    llm_provider_config_id: UUID | None = None
    llm_provider_config_revision: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def require_bare_task_llm_authority(self) -> "TaskContent":
        swarm_ref_values = (
            self.swarm_agent_id,
            self.swarm_agent_revision,
            self.swarm_topology_id,
            self.swarm_topology_revision,
        )
        swarm_ref_present = all(value is not None for value in swarm_ref_values)
        if any(value is not None for value in swarm_ref_values) != swarm_ref_present:
            raise ValueError(
                "Swarm topology and agent revision refs must be complete."
            )
        if (self.swarm_id is not None) != swarm_ref_present:
            raise ValueError(
                "Swarm tasks require exact topology and agent revisions."
            )
        if (self.background_agent_id is None) != (
            self.background_agent_revision is None
        ):
            raise ValueError(
                "Background tasks require an exact agent id and revision."
            )
        if self.swarm_id is not None and self.background_agent_id is not None:
            raise ValueError("A task cannot target both swarm and background agents.")
        if self.swarm_id is None and self.background_agent_id is None and (
            self.llm_provider_config_id is None
            or self.llm_provider_config_revision is None
        ):
            raise ValueError("Bare LLM tasks require pinned LLM authority.")
        return self

    def execution_agent_ref(self) -> tuple[UUID, int]:
        """Return the exact agent revision this task asks a worker to execute."""
        if self.background_agent_id is not None:
            assert self.background_agent_revision is not None
            return self.background_agent_id, self.background_agent_revision
        if self.swarm_agent_id is not None:
            assert self.swarm_agent_revision is not None
            return self.swarm_agent_id, self.swarm_agent_revision
        return self.source_agent_id, self.source_agent_revision

    def require_execution_agent_ref(
        self,
        *,
        agent_id: UUID,
        agent_revision: int,
    ) -> None:
        """Refuse a task envelope that could redirect a claimed durable run."""
        if self.execution_agent_ref() != (agent_id, agent_revision):
            raise TaskExecutionAuthorityMismatch(
                "Task execution agent does not match the claimed durable run."
            )

    def to_json(self) -> str:
        return self.model_dump_json()

    @classmethod
    def from_json(cls, raw: str) -> "TaskContent":
        return cls.model_validate_json(raw)


class TaskResultContent(BaseModel):
    """Content stored inside a SYSTEM/TASK_RESULT message."""

    result: str = Field(..., description="Worker output text")
    meta: Optional[dict] = Field(
        None,
        description="Worker metadata (iterations_used, model_used)",
    )

    def to_json(self) -> str:
        return self.model_dump_json()

    @classmethod
    def from_json(cls, raw: str) -> "TaskResultContent":
        return cls.model_validate_json(raw)
