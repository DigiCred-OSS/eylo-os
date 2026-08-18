"""Private API projections and commands for durable agent runs."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

from eylo.modules.agent_runs.domain import (
    AgentInputRequestKind,
    AgentInputRequestStatus,
    AgentRunLifecycle,
    AgentRunOriginKind,
    AgentRunOutcome,
    AgentRunStepKind,
    AgentRunStepStatus,
    ExecutionBudgetDimension,
    InitiatingPrincipalKind,
)

_BIGINT_MAX = 9_223_372_036_854_775_807


class OrganizationExecutionBudgetLimits(BaseModel):
    """All boundaries are explicit; the platform supplies no budget defaults."""

    model_config = ConfigDict(extra="forbid")

    max_concurrent_runs: int = Field(gt=0, le=2_147_483_647)
    max_active_tokens: int = Field(gt=0, le=_BIGINT_MAX)
    max_active_milliseconds: int = Field(gt=0, le=_BIGINT_MAX)
    max_active_cost_microunits: int = Field(gt=0, le=_BIGINT_MAX)
    run_token_limit: int = Field(gt=0, le=_BIGINT_MAX)
    run_time_limit_milliseconds: int = Field(gt=0, le=_BIGINT_MAX)
    run_cost_limit_microunits: int = Field(gt=0, le=_BIGINT_MAX)
    cost_microunits_per_million_tokens: int = Field(
        gt=0,
        le=_BIGINT_MAX,
        description=(
            "Organization-defined accounting rate used to convert metered tokens "
            "into budget microunits; it is not a provider invoice price."
        ),
    )

    @model_validator(mode="after")
    def validate_run_limits_fit(self) -> OrganizationExecutionBudgetLimits:
        pairs = (
            ("tokens", self.run_token_limit, self.max_active_tokens),
            (
                "active time",
                self.run_time_limit_milliseconds,
                self.max_active_milliseconds,
            ),
            (
                "cost",
                self.run_cost_limit_microunits,
                self.max_active_cost_microunits,
            ),
        )
        for label, run_limit, active_limit in pairs:
            if run_limit > active_limit:
                raise ValueError(
                    f"Per-run {label} limit cannot exceed organization capacity."
                )
        return self


class OrganizationExecutionBudgetUpsert(OrganizationExecutionBudgetLimits):
    """Create a first policy or replace the observed policy revision."""

    expected_state_revision: int | None = Field(default=None, ge=1)


class OrganizationExecutionBudgetRead(OrganizationExecutionBudgetLimits):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    organization_id: UUID
    state_revision: int
    created_at: datetime
    updated_at: datetime


class AgentRunReservationRead(BaseModel):
    """Current pinned usage envelope shown with its organization-owned run."""

    model_config = ConfigDict(from_attributes=True, extra="forbid")

    token_limit: int
    time_limit_milliseconds: int
    cost_limit_microunits: int
    used_tokens: int
    used_cost_microunits: int
    active_milliseconds: int
    active: bool
    active_since: datetime | None
    released_at: datetime | None
    exceeded_dimension: ExecutionBudgetDimension | None


class AgentRunCancelRequest(BaseModel):
    """Optimistic cancellation command for one visible run revision."""

    model_config = ConfigDict(extra="forbid")

    expected_state_revision: int = Field(ge=1)


class AgentInputResponseRequest(BaseModel):
    """One explicit response to one still-pending input request."""

    model_config = ConfigDict(extra="forbid")

    expected_state_revision: int = Field(ge=1)
    response: JsonValue


class AgentRunCancellationDisposition(str, Enum):
    """Whether cancellation completed locally or awaits the durable worker."""

    REQUESTED = "requested"
    CANCELLED = "cancelled"


class AgentRunStepRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    step_key: str
    kind: AgentRunStepKind
    status: AgentRunStepStatus
    intent: dict
    safe_summary: str | None
    evidence: dict | None
    artifact_refs: list
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class AgentInputRequestRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    kind: AgentInputRequestKind
    prompt: str
    expected_response_schema: dict
    status: AgentInputRequestStatus
    response: JsonValue | None
    answered_by_principal_kind: InitiatingPrincipalKind | None
    answered_by_principal_id: UUID | None
    state_revision: int
    answered_at: datetime | None
    cancelled_at: datetime | None
    created_at: datetime
    updated_at: datetime


class AgentRunRead(BaseModel):
    """Organization-owned run state without internal engine identifiers."""

    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    organization_id: UUID
    initiating_principal_kind: InitiatingPrincipalKind
    initiating_principal_id: UUID
    agent_id: UUID
    agent_revision: int
    origin_kind: AgentRunOriginKind
    origin_message_id: UUID | None
    origin_schedule_run_id: UUID | None
    lifecycle: AgentRunLifecycle
    outcome: AgentRunOutcome | None
    goal: str
    result: dict | None
    outcome_reason: str | None
    failure_summary: str | None
    state_revision: int
    started_at: datetime | None
    waiting_at: datetime | None
    cancellation_requested_at: datetime | None
    cancelled_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
    updated_at: datetime
    reservation: AgentRunReservationRead | None
    steps: list[AgentRunStepRead]
    input_requests: list[AgentInputRequestRead]


class AgentRunCancellationRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    disposition: AgentRunCancellationDisposition
    run: AgentRunRead
