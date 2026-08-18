"""Organization-owned product projections for durable agent execution."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ENUM, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from eylo.common.models import EyloOrganizationModel
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


def _enum(enum_type: type, name: str) -> ENUM:
    return ENUM(
        enum_type,
        name=name,
        values_callable=lambda enum: [member.value for member in enum],
        create_type=False,
    )


class AgentRunModel(EyloOrganizationModel):
    """One product agent execution, independent of worker/process lifetime."""

    __tablename__ = "agent_runs"

    __table_args__ = (
        UniqueConstraint(
            "id",
            "organization_id",
            name="uq_agent_runs_id_organization_id",
        ),
        UniqueConstraint("idempotency_key", name="uq_agent_runs_idempotency_key"),
        UniqueConstraint("absurd_task_id", name="uq_agent_runs_absurd_task_id"),
        UniqueConstraint(
            "origin_message_id",
            name="uq_agent_runs_origin_message_id",
        ),
        UniqueConstraint(
            "origin_schedule_run_id",
            name="uq_agent_runs_origin_schedule_run_id",
        ),
        ForeignKeyConstraint(
            ["agent_id", "agent_revision", "organization_id"],
            [
                "agent_definition_revisions.agent_id",
                "agent_definition_revisions.revision",
                "agent_definition_revisions.organization_id",
            ],
            name="fk_agent_runs_agent_revision",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["origin_schedule_run_id", "organization_id"],
            ["scheduler_runs.id", "scheduler_runs.organization_id"],
            name="fk_agent_runs_schedule_occurrence",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["user_session_id", "organization_id"],
            ["user_sessions.id", "user_sessions.organization_id"],
            name="fk_agent_runs_user_session_organization",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "agent_revision > 0",
            name="ck_agent_runs_agent_revision_positive",
        ),
        CheckConstraint(
            "state_revision > 0",
            name="ck_agent_runs_state_revision_positive",
        ),
        CheckConstraint(
            "session_context_digest ~ '^[0-9a-f]{64}$'",
            name="ck_agent_runs_context_digest",
        ),
        CheckConstraint(
            "octet_length(context_manifest::text) <= 16384",
            name="ck_agent_runs_context_manifest_size",
        ),
        CheckConstraint(
            "jsonb_typeof(context_manifest) = 'object'",
            name="ck_agent_runs_context_manifest_object",
        ),
        CheckConstraint(
            "length(idempotency_key) BETWEEN 1 AND 320",
            name="ck_agent_runs_idempotency_key_size",
        ),
        CheckConstraint(
            "length(goal) BETWEEN 1 AND 16384",
            name="ck_agent_runs_goal_size",
        ),
        CheckConstraint(
            "result IS NULL OR octet_length(result::text) <= 65536",
            name="ck_agent_runs_result_size",
        ),
        CheckConstraint(
            "(origin_kind = 'message' AND origin_message_id IS NOT NULL "
            "AND origin_schedule_run_id IS NULL) OR "
            "(origin_kind = 'schedule_occurrence' "
            "AND origin_schedule_run_id IS NOT NULL "
            "AND origin_message_id IS NULL) OR "
            "(origin_kind = 'objective' AND origin_message_id IS NULL "
            "AND origin_schedule_run_id IS NULL)",
            name="ck_agent_runs_exactly_one_origin",
        ),
        CheckConstraint(
            "(lifecycle NOT IN ('completed', 'failed', 'cancelled') "
            "AND outcome IS NULL AND result IS NULL AND finished_at IS NULL "
            "AND cancelled_at IS NULL) OR "
            "(lifecycle = 'completed' "
            "AND outcome IN ('achieved', 'unachievable', 'exhausted') "
            "AND result IS NOT NULL AND failure_summary IS NULL "
            "AND finished_at IS NOT NULL AND cancelled_at IS NULL) OR "
            "(lifecycle = 'failed' AND outcome = 'failed' AND result IS NULL "
            "AND failure_summary IS NOT NULL "
            "AND length(btrim(failure_summary)) BETWEEN 1 AND 2000 "
            "AND finished_at IS NOT NULL AND cancelled_at IS NULL) OR "
            "(lifecycle = 'cancelled' AND outcome = 'cancelled' "
            "AND result IS NULL AND finished_at IS NOT NULL "
            "AND cancellation_requested_at IS NOT NULL "
            "AND cancelled_at IS NOT NULL)",
            name="ck_agent_runs_lifecycle_outcome",
        ),
        CheckConstraint(
            "outcome IS NULL OR outcome NOT IN ('unachievable', 'exhausted') "
            "OR (outcome_reason IS NOT NULL "
            "AND length(btrim(outcome_reason)) BETWEEN 1 AND 4000)",
            name="ck_agent_runs_conclusion_reason",
        ),
        CheckConstraint(
            "lifecycle NOT IN ('waiting_for_input', 'waiting_for_approval') "
            "OR waiting_at IS NOT NULL",
            name="ck_agent_runs_waiting_time",
        ),
        CheckConstraint(
            "lifecycle = 'queued' OR absurd_task_id IS NOT NULL OR "
            "(lifecycle = 'cancelled' AND started_at IS NULL "
            "AND cancellation_requested_at IS NOT NULL)",
            name="ck_agent_runs_task_bound_before_execution",
        ),
        *EyloOrganizationModel.get_organization_constraints(__tablename__),
    )

    initiating_principal_kind: Mapped[InitiatingPrincipalKind] = mapped_column(
        _enum(InitiatingPrincipalKind, "agent_run_principal_kind_enum"),
        nullable=False,
    )
    initiating_principal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    agent_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    origin_kind: Mapped[AgentRunOriginKind] = mapped_column(
        _enum(AgentRunOriginKind, "agent_run_origin_kind_enum"),
        nullable=False,
    )
    origin_message_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversation_messages.id", ondelete="RESTRICT"),
        nullable=True,
    )
    origin_schedule_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    user_session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    session_context_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    context_manifest: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    idempotency_key: Mapped[str] = mapped_column(String(320), nullable=False)
    absurd_task_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    lifecycle: Mapped[AgentRunLifecycle] = mapped_column(
        _enum(AgentRunLifecycle, "agent_run_lifecycle_enum"),
        nullable=False,
        default=AgentRunLifecycle.QUEUED,
        server_default=AgentRunLifecycle.QUEUED.value,
        index=True,
    )
    outcome: Mapped[AgentRunOutcome | None] = mapped_column(
        _enum(AgentRunOutcome, "agent_run_outcome_enum"), nullable=True
    )
    goal: Mapped[str] = mapped_column(Text, nullable=False)
    result: Mapped[dict | None] = mapped_column(
        JSONB(none_as_null=True), nullable=True
    )
    outcome_reason: Mapped[str | None] = mapped_column(String(4000), nullable=True)
    failure_summary: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    state_revision: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default=text("1")
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    waiting_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cancellation_requested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class OrganizationExecutionBudgetModel(EyloOrganizationModel):
    """One explicit execution-capacity policy for an organization."""

    __tablename__ = "organization_execution_budgets"

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            name="uq_organization_execution_budgets_organization_id",
        ),
        UniqueConstraint(
            "id",
            "organization_id",
            name="uq_organization_execution_budgets_id_organization_id",
        ),
        CheckConstraint(
            "max_concurrent_runs > 0 AND max_active_tokens > 0 AND "
            "max_active_milliseconds > 0 AND max_active_cost_microunits > 0",
            name="ck_organization_execution_budgets_capacity_positive",
        ),
        CheckConstraint(
            "run_token_limit > 0 AND run_time_limit_milliseconds > 0 AND "
            "run_cost_limit_microunits > 0 AND "
            "cost_microunits_per_million_tokens > 0",
            name="ck_organization_execution_budgets_run_limits_positive",
        ),
        CheckConstraint(
            "run_token_limit <= max_active_tokens AND "
            "run_time_limit_milliseconds <= max_active_milliseconds AND "
            "run_cost_limit_microunits <= max_active_cost_microunits",
            name="ck_organization_execution_budgets_run_limits_fit",
        ),
        CheckConstraint(
            "state_revision > 0",
            name="ck_organization_execution_budgets_revision_positive",
        ),
        *EyloOrganizationModel.get_organization_constraints(__tablename__),
    )

    max_concurrent_runs: Mapped[int] = mapped_column(Integer, nullable=False)
    max_active_tokens: Mapped[int] = mapped_column(BigInteger, nullable=False)
    max_active_milliseconds: Mapped[int] = mapped_column(BigInteger, nullable=False)
    max_active_cost_microunits: Mapped[int] = mapped_column(BigInteger, nullable=False)
    run_token_limit: Mapped[int] = mapped_column(BigInteger, nullable=False)
    run_time_limit_milliseconds: Mapped[int] = mapped_column(BigInteger, nullable=False)
    run_cost_limit_microunits: Mapped[int] = mapped_column(BigInteger, nullable=False)
    cost_microunits_per_million_tokens: Mapped[int] = mapped_column(
        BigInteger, nullable=False
    )
    state_revision: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default=text("1")
    )


class OrganizationExecutionReservationModel(EyloOrganizationModel):
    """Pinned capacity held by one organization-owned durable execution."""

    __tablename__ = "organization_execution_reservations"

    __table_args__ = (
        UniqueConstraint(
            "run_id",
            name="uq_execution_reservations_run_id",
        ),
        UniqueConstraint(
            "memory_formation_job_id",
            name="uq_execution_reservations_memory_job_id",
        ),
        UniqueConstraint(
            "memory_reconciliation_job_id",
            name="uq_execution_reservations_reconciliation_job_id",
        ),
        ForeignKeyConstraint(
            ["run_id", "organization_id"],
            ["agent_runs.id", "agent_runs.organization_id"],
            name="fk_execution_reservations_run",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["memory_formation_job_id", "organization_id"],
            ["memory_formation_jobs.id", "memory_formation_jobs.organization_id"],
            name="fk_execution_reservations_memory_job",
            ondelete="CASCADE",
            use_alter=True,
        ),
        ForeignKeyConstraint(
            ["memory_reconciliation_job_id", "organization_id"],
            [
                "memory_reconciliation_jobs.id",
                "memory_reconciliation_jobs.organization_id",
            ],
            name="fk_execution_reservations_reconciliation_job",
            ondelete="CASCADE",
            use_alter=True,
        ),
        ForeignKeyConstraint(
            ["budget_id", "organization_id"],
            [
                "organization_execution_budgets.id",
                "organization_execution_budgets.organization_id",
            ],
            name="fk_execution_reservations_budget",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "num_nonnulls(run_id, memory_formation_job_id, "
            "memory_reconciliation_job_id) = 1",
            name="ck_execution_reservations_one_owner",
        ),
        CheckConstraint(
            "budget_state_revision > 0 AND token_limit > 0 AND "
            "time_limit_milliseconds > 0 AND cost_limit_microunits > 0 AND "
            "cost_microunits_per_million_tokens > 0",
            name="ck_execution_reservations_limits_positive",
        ),
        CheckConstraint(
            "used_tokens >= 0 AND used_cost_microunits >= 0 AND "
            "active_milliseconds >= 0",
            name="ck_execution_reservations_usage_nonnegative",
        ),
        CheckConstraint(
            "(active IS TRUE AND released_at IS NULL) OR "
            "(active IS FALSE AND active_since IS NULL AND released_at IS NOT NULL)",
            name="ck_execution_reservations_active_state",
        ),
        *EyloOrganizationModel.get_organization_constraints(__tablename__),
    )

    run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    memory_formation_job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    memory_reconciliation_job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    budget_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    budget_state_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    token_limit: Mapped[int] = mapped_column(BigInteger, nullable=False)
    time_limit_milliseconds: Mapped[int] = mapped_column(BigInteger, nullable=False)
    cost_limit_microunits: Mapped[int] = mapped_column(BigInteger, nullable=False)
    cost_microunits_per_million_tokens: Mapped[int] = mapped_column(
        BigInteger, nullable=False
    )
    used_tokens: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default=text("0")
    )
    used_cost_microunits: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default=text("0")
    )
    usage_reported: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    active_milliseconds: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default=text("0")
    )
    active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    active_since: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    released_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    exceeded_dimension: Mapped[ExecutionBudgetDimension | None] = mapped_column(
        _enum(ExecutionBudgetDimension, "execution_budget_dimension_enum"),
        nullable=True,
    )


class AgentRunStepModel(EyloOrganizationModel):
    """Bounded append-only product/audit projection of one durable step."""

    __tablename__ = "agent_run_steps"

    __table_args__ = (
        UniqueConstraint("run_id", "step_key", name="uq_agent_run_steps_run_step_key"),
        UniqueConstraint(
            "provider_idempotency_key",
            name="uq_agent_run_steps_provider_idempotency_key",
        ),
        ForeignKeyConstraint(
            ["run_id", "organization_id"],
            ["agent_runs.id", "agent_runs.organization_id"],
            name="fk_agent_run_steps_run",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "length(step_key) BETWEEN 1 AND 256",
            name="ck_agent_run_steps_key_size",
        ),
        CheckConstraint(
            "octet_length(intent::text) <= 32768",
            name="ck_agent_run_steps_intent_size",
        ),
        CheckConstraint(
            "evidence IS NULL OR octet_length(evidence::text) <= 32768",
            name="ck_agent_run_steps_evidence_size",
        ),
        CheckConstraint(
            "octet_length(artifact_refs::text) <= 16384",
            name="ck_agent_run_steps_artifact_refs_size",
        ),
        CheckConstraint(
            "(status IN ('pending', 'running') AND completed_at IS NULL) OR "
            "(status IN ('completed', 'failed', 'cancelled') "
            "AND completed_at IS NOT NULL)",
            name="ck_agent_run_steps_terminal_time",
        ),
        *EyloOrganizationModel.get_organization_constraints(__tablename__),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    step_key: Mapped[str] = mapped_column(String(256), nullable=False)
    kind: Mapped[AgentRunStepKind] = mapped_column(
        _enum(AgentRunStepKind, "agent_run_step_kind_enum"), nullable=False
    )
    status: Mapped[AgentRunStepStatus] = mapped_column(
        _enum(AgentRunStepStatus, "agent_run_step_status_enum"),
        nullable=False,
        default=AgentRunStepStatus.PENDING,
        server_default=AgentRunStepStatus.PENDING.value,
    )
    intent: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    safe_summary: Mapped[str | None] = mapped_column(String(4000), nullable=True)
    evidence: Mapped[dict | None] = mapped_column(
        JSONB(none_as_null=True), nullable=True
    )
    artifact_refs: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    provider_idempotency_key: Mapped[str | None] = mapped_column(
        String(512), nullable=True
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class AgentRunTranscriptItemModel(EyloOrganizationModel):
    """Private canonical replay item for a non-conversation AgentRun.

    Conversation runs use canonical messages. Objective, schedule and
    background runs have no synthetic conversation, so their raw model/tool
    exchange lives here instead of leaking into public AgentRun step evidence
    or Absurd checkpoints.
    """

    __tablename__ = "agent_run_transcript_items"

    __table_args__ = (
        UniqueConstraint(
            "run_id",
            "sequence",
            name="uq_agent_run_transcript_items_run_sequence",
        ),
        UniqueConstraint(
            "run_id",
            "kind",
            "correlation_id",
            name="uq_agent_run_transcript_items_run_kind_correlation",
        ),
        ForeignKeyConstraint(
            ["run_id", "organization_id"],
            ["agent_runs.id", "agent_runs.organization_id"],
            name="fk_agent_run_transcript_items_run",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "sequence > 0",
            name="ck_agent_run_transcript_items_sequence_positive",
        ),
        CheckConstraint(
            "kind IN ('assistant_text', 'tool_call', 'tool_result')",
            name="ck_agent_run_transcript_items_kind",
        ),
        CheckConstraint(
            "correlation_id IS NULL OR length(correlation_id) BETWEEN 1 AND 256",
            name="ck_agent_run_transcript_items_correlation_size",
        ),
        CheckConstraint(
            "octet_length(payload::text) <= 65536",
            name="ck_agent_run_transcript_items_payload_size",
        ),
        *EyloOrganizationModel.get_organization_constraints(__tablename__),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    correlation_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)


class AgentInputRequestModel(EyloOrganizationModel):
    """Identified request that waits until explicit answer or cancellation."""

    __tablename__ = "agent_input_requests"

    __table_args__ = (
        UniqueConstraint("event_name", name="uq_agent_input_requests_event_name"),
        ForeignKeyConstraint(
            ["run_id", "organization_id"],
            ["agent_runs.id", "agent_runs.organization_id"],
            name="fk_agent_input_requests_run",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "state_revision > 0",
            name="ck_agent_input_requests_state_revision_positive",
        ),
        CheckConstraint(
            "length(prompt) BETWEEN 1 AND 8192",
            name="ck_agent_input_requests_prompt_size",
        ),
        CheckConstraint(
            "length(event_name) BETWEEN 1 AND 512",
            name="ck_agent_input_requests_event_name_size",
        ),
        CheckConstraint(
            "length(resume_step_key) BETWEEN 1 AND 256",
            name="ck_agent_input_requests_resume_step_key_size",
        ),
        CheckConstraint(
            "octet_length(expected_response_schema::text) <= 16384",
            name="ck_agent_input_requests_schema_size",
        ),
        CheckConstraint(
            "octet_length(continuation::text) <= 16384",
            name="ck_agent_input_requests_continuation_size",
        ),
        CheckConstraint(
            "response IS NULL OR octet_length(response::text) <= 65536",
            name="ck_agent_input_requests_response_size",
        ),
        CheckConstraint(
            "(answered_by_principal_kind IS NULL "
            "AND answered_by_principal_id IS NULL) OR "
            "(answered_by_principal_kind IS NOT NULL "
            "AND answered_by_principal_id IS NOT NULL)",
            name="ck_agent_input_requests_answer_principal_pair",
        ),
        CheckConstraint(
            "(status = 'pending' AND response IS NULL "
            "AND answered_at IS NULL AND cancelled_at IS NULL) OR "
            "(status = 'answered' AND response IS NOT NULL "
            "AND answered_at IS NOT NULL AND cancelled_at IS NULL "
            "AND answered_by_principal_id IS NOT NULL) OR "
            "(status = 'cancelled' AND response IS NULL "
            "AND answered_at IS NULL AND cancelled_at IS NOT NULL)",
            name="ck_agent_input_requests_lifecycle",
        ),
        *EyloOrganizationModel.get_organization_constraints(__tablename__),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    kind: Mapped[AgentInputRequestKind] = mapped_column(
        _enum(AgentInputRequestKind, "agent_input_request_kind_enum"),
        nullable=False,
    )
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    expected_response_schema: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    continuation: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    event_name: Mapped[str] = mapped_column(String(512), nullable=False)
    resume_step_key: Mapped[str] = mapped_column(String(256), nullable=False)
    status: Mapped[AgentInputRequestStatus] = mapped_column(
        _enum(AgentInputRequestStatus, "agent_input_request_status_enum"),
        nullable=False,
        default=AgentInputRequestStatus.PENDING,
        server_default=AgentInputRequestStatus.PENDING.value,
    )
    response: Mapped[dict | list | str | int | float | bool | None] = mapped_column(
        JSONB, nullable=True
    )
    answered_by_principal_kind: Mapped[InitiatingPrincipalKind | None] = mapped_column(
        _enum(InitiatingPrincipalKind, "agent_run_principal_kind_enum"),
        nullable=True,
    )
    answered_by_principal_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    state_revision: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default=text("1")
    )
    answered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
