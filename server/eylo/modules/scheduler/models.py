"""Schedules, and the immutable occurrences they produce.

Two tables, and the split is the design. A **schedule** is a standing intention
— a rule, a timezone, an action. A **run** is one occurrence of it and the
immutable origin of one durable ``AgentRun``. Absurd owns execution durability;
the occurrence never carries a second claim/lease/retry state machine.

Separating them is what makes "fires once" provable. The uniqueness of an
occurrence lives on the run table as a constraint the database enforces, rather
than on a worker remembering what it already did.
"""

from __future__ import annotations

import uuid

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ENUM, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from eylo.common.contracts.scheduler import MisfirePolicy
from eylo.common.models import EyloOrganizationModel
from eylo.common.revisions import DefinitionLifecycle, RevisionAvailability


class ScheduleModel(EyloOrganizationModel):
    """Stable schedule identity, current published projection, and clock state."""

    __tablename__ = "scheduler_schedules"

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "key",
            name="uq_scheduler_schedules_organization_key",
        ),
        UniqueConstraint(
            "id",
            "organization_id",
            name="uq_scheduler_schedules_id_organization_id",
        ),
        CheckConstraint(
            "published_revision > 0",
            name="ck_scheduler_schedules_published_revision_positive",
        ),
        CheckConstraint(
            "lifecycle IN ('published', 'withdrawn', 'archived')",
            name="ck_scheduler_schedules_lifecycle",
        ),
        CheckConstraint(
            "agent_revision > 0",
            name="ck_scheduler_schedules_agent_revision_positive",
        ),
        ForeignKeyConstraint(
            ["id", "published_revision", "organization_id"],
            [
                "scheduler_schedule_revisions.schedule_id",
                "scheduler_schedule_revisions.revision",
                "scheduler_schedule_revisions.organization_id",
            ],
            name="fk_scheduler_schedules_published_revision",
            ondelete="RESTRICT",
            use_alter=True,
            deferrable=True,
            initially="DEFERRED",
        ),
        ForeignKeyConstraint(
            ["agent_id", "agent_revision", "organization_id"],
            [
                "agent_definition_revisions.agent_id",
                "agent_definition_revisions.revision",
                "agent_definition_revisions.organization_id",
            ],
            name="fk_scheduler_schedules_agent_revision",
            ondelete="RESTRICT",
        ),
        *EyloOrganizationModel.get_organization_constraints(__tablename__),
    )

    key: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(256), nullable=False)

    published_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    lifecycle: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=DefinitionLifecycle.PUBLISHED.value,
        server_default=DefinitionLifecycle.PUBLISHED.value,
    )

    # Exact execution authority. Schedules trigger agents; they never select a
    # platform/default executor or dispatch module code directly.
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    agent_revision: Mapped[int] = mapped_column(Integer, nullable=False)

    # The recurrence. `rule` is None for a one-shot; `timezone` has no default
    # because "every morning at 9" is not a UTC statement — see
    # sockets/scheduler/recurrence.py.
    rule: Mapped[str | None] = mapped_column(Text, nullable=True)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    starts_at = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at = mapped_column(DateTime(timezone=True), nullable=True)

    # What to do. The scheduler never interprets either — that is what lets a
    # module add a schedulable capability without the scheduler learning it.
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    payload: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )

    misfire_policy: Mapped[MisfirePolicy] = mapped_column(
        ENUM(
            MisfirePolicy,
            name="scheduler_misfire_policy_enum",
            values_callable=lambda enum: [member.value for member in enum],
            create_type=False,
        ),
        nullable=False,
        default=MisfirePolicy.COALESCE,
        server_default=MisfirePolicy.COALESCE.value,
    )

    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )

    # The next occurrence, in UTC. Computed by the platform's recurrence engine
    # and stored here so the due query is an index scan rather than a rule
    # evaluation per row. NULL means retired: exhausted by COUNT, past UNTIL,
    # past `ends_at`, or a one-shot that has fired.
    next_at = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    last_fired_at = mapped_column(DateTime(timezone=True), nullable=True)

    # Set when a schedule runs out of future — exhausted by COUNT, past UNTIL,
    # past `ends_at`, or a one-shot that has fired.
    #
    # It exists to make a distinction the recovery sweep depends on. A worker
    # that claims a schedule and dies before creating its run leaves `next_at`
    # NULL, which is *also* what a finished schedule looks like. Without this
    # column the sweeper cannot tell "this recurring job stopped forever with no
    # error anywhere" from "this one is legitimately over", and would either
    # resurrect finished schedules or abandon stranded ones.
    retired_at = mapped_column(DateTime(timezone=True), nullable=True)

    # Why a schedule stopped producing runs, when it stopped for a reason. A
    # schedule whose action was removed in a deploy keeps this and stays
    # enabled — see the contract: a deploy must not silently delete an
    # operator's recurring job.
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)


class ScheduleRevisionModel(EyloOrganizationModel):
    """One immutable published schedule definition."""

    __tablename__ = "scheduler_schedule_revisions"

    __table_args__ = (
        ForeignKeyConstraint(
            ["schedule_id", "organization_id"],
            ["scheduler_schedules.id", "scheduler_schedules.organization_id"],
            name="fk_scheduler_schedule_revisions_header_organization",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["agent_id", "agent_revision", "organization_id"],
            [
                "agent_definition_revisions.agent_id",
                "agent_definition_revisions.revision",
                "agent_definition_revisions.organization_id",
            ],
            name="fk_scheduler_schedule_revisions_agent_revision",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "schedule_id",
            "revision",
            name="uq_scheduler_schedule_revisions_ref",
        ),
        UniqueConstraint(
            "schedule_id",
            "revision",
            "organization_id",
            name="uq_scheduler_schedule_revisions_ref_organization",
        ),
        CheckConstraint(
            "revision > 0",
            name="ck_scheduler_schedule_revisions_revision_positive",
        ),
        CheckConstraint(
            "agent_revision > 0",
            name="ck_scheduler_schedule_revisions_agent_revision_positive",
        ),
        CheckConstraint(
            "availability IN ('published', 'revoked')",
            name="ck_scheduler_schedule_revisions_availability",
        ),
        CheckConstraint(
            "(availability = 'published' AND revoked_at IS NULL "
            "AND revoked_by IS NULL AND revocation_reason IS NULL "
            "AND cancellation_requested_at IS NULL) OR "
            "(availability = 'revoked' AND revoked_at IS NOT NULL "
            "AND revoked_by IS NOT NULL AND revocation_reason IS NOT NULL "
            "AND length(btrim(revocation_reason)) BETWEEN 1 AND 2000 "
            "AND cancellation_requested_at IS NOT NULL)",
            name="ck_scheduler_schedule_revisions_revocation_metadata",
        ),
        *EyloOrganizationModel.get_organization_constraints(__tablename__),
    )

    schedule_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    rule: Mapped[str | None] = mapped_column(Text, nullable=True)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    starts_at = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at = mapped_column(DateTime(timezone=True), nullable=True)
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    payload: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    misfire_policy: Mapped[MisfirePolicy] = mapped_column(
        ENUM(
            MisfirePolicy,
            name="scheduler_misfire_policy_enum",
            values_callable=lambda enum: [member.value for member in enum],
            create_type=False,
        ),
        nullable=False,
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False)
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    agent_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    availability: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=RevisionAvailability.PUBLISHED.value,
        server_default=RevisionAvailability.PUBLISHED.value,
    )
    published_at = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    published_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    revoked_at = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    revocation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancellation_requested_at = mapped_column(DateTime(timezone=True), nullable=True)


class ScheduleRunModel(EyloOrganizationModel):
    """One immutable schedule occurrence and AgentRun origin."""

    __tablename__ = "scheduler_runs"

    __table_args__ = (
        # **This is the "fires once" guarantee**, and it is a database
        # constraint rather than worker discipline on purpose. Two workers
        # racing to advance the same schedule can both decide an occurrence is
        # due; only one of them can insert it. The loser gets an
        # IntegrityError, which is a correct outcome rather than an error.
        UniqueConstraint(
            "schedule_id",
            "scheduled_for",
            name="uq_scheduler_runs_schedule_occurrence",
        ),
        UniqueConstraint(
            "id",
            "organization_id",
            name="uq_scheduler_runs_id_organization_id",
        ),
        ForeignKeyConstraint(
            ["schedule_id", "schedule_revision", "organization_id"],
            [
                "scheduler_schedule_revisions.schedule_id",
                "scheduler_schedule_revisions.revision",
                "scheduler_schedule_revisions.organization_id",
            ],
            name="fk_scheduler_runs_schedule_revision",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["agent_id", "agent_revision", "organization_id"],
            [
                "agent_definition_revisions.agent_id",
                "agent_definition_revisions.revision",
                "agent_definition_revisions.organization_id",
            ],
            name="fk_scheduler_runs_agent_revision",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "schedule_revision > 0",
            name="ck_scheduler_runs_schedule_revision_positive",
        ),
        CheckConstraint(
            "agent_revision > 0",
            name="ck_scheduler_runs_agent_revision_positive",
        ),
        *EyloOrganizationModel.get_organization_constraints(__tablename__),
    )

    schedule_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    schedule_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    agent_revision: Mapped[int] = mapped_column(Integer, nullable=False)

    # The occurrence this run is for, in UTC. Part of the uniqueness key, so it
    # is the occurrence's identity rather than a timestamp for display.
    scheduled_for = mapped_column(DateTime(timezone=True), nullable=False)

    # Snapshotted from the schedule at creation, not read through the foreign
    # key at execution. A schedule edited between a run being created and
    # running must not retroactively change what that run does — an operator
    # who fixes a payload expects the fix to apply to the *next* run, and a run
    # that did something other than what it recorded is unauditable.
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    payload: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )

    # How many occurrences were coalesced into this one. Non-zero means the
    # scheduler was not running when they came due; recorded rather than
    # dropped so an operator can see what an outage cost.
    misfired_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
