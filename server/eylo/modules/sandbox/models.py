"""Ephemeral sandbox compute and immutable AgentRun workspace checkpoints."""

from __future__ import annotations

import uuid

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    LargeBinary,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ENUM, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from eylo.common.contracts.sandbox import SandboxAccess, SandboxState
from eylo.common.models import EyloOrganizationModel


class SandboxSessionModel(EyloOrganizationModel):
    """One workspace, tracked so it can be resumed and so it cannot be leaked.

    **The row exists mainly so the container cannot outlive it.** A sandbox
    that only lived in Docker would be a bill nobody notices: a worker dies
    mid-task and the container idles until someone goes looking. Every session
    has an expiry here, and a reaper reads this table rather than the daemon.
    """

    __tablename__ = "sandbox_sessions"

    __table_args__ = (
        *EyloOrganizationModel.get_organization_constraints(__tablename__),
        ForeignKeyConstraint(
            ["agent_run_id", "organization_id"],
            ["agent_runs.id", "agent_runs.organization_id"],
            name="fk_sandbox_sessions_agent_run",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["sandbox_provider_config_id", "organization_id"],
            ["provider_configs.id", "provider_configs.organization_id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["sandbox_provider_config_id", "sandbox_provider_config_revision"],
            [
                "provider_config_revisions.provider_config_id",
                "provider_config_revisions.revision",
            ],
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "sandbox_provider_config_revision > 0",
            name="ck_sandbox_sessions_config_revision_positive",
        ),
        Index(
            "uq_sandbox_sessions_live_agent_run",
            "agent_run_id",
            unique=True,
            postgresql_where=text(
                "agent_run_id IS NOT NULL AND state IN "
                "('starting', 'running', 'paused') AND deleted IS FALSE"
            ),
        ),
    )

    # The vendor's own handle — a container id for Docker. Opaque here.
    vendor_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True, index=True
    )
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    image: Mapped[str] = mapped_column(String(512), nullable=False)
    sandbox_provider_config_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    sandbox_provider_config_revision: Mapped[int] = mapped_column(
        Integer, nullable=False
    )
    grant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sandbox_grants.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    grant_revision: Mapped[int | None] = mapped_column(Integer, nullable=True)
    effective_policy: Mapped[dict] = mapped_column(JSONB, nullable=False)

    state: Mapped[SandboxState] = mapped_column(
        ENUM(
            SandboxState,
            name="sandbox_state_enum",
            values_callable=lambda enum: [member.value for member in enum],
            create_type=False,
        ),
        nullable=False,
        index=True,
    )

    # Which agent this belongs to, when an agent's work created it. An agent
    # reaches its own sessions and no others — the same rule the scheduler uses
    # for schedules, for the same reason.
    agent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agent_agents.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    agent_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )

    workspace: Mapped[str] = mapped_column(String(256), nullable=False)
    expires_at = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    last_used_at = mapped_column(DateTime(timezone=True), nullable=True)


class SandboxWorkspaceCheckpointModel(EyloOrganizationModel):
    """One immutable, content-verified logical workspace revision."""

    __tablename__ = "sandbox_workspace_checkpoints"

    __table_args__ = (
        *EyloOrganizationModel.get_organization_constraints(__tablename__),
        UniqueConstraint(
            "agent_run_id",
            "revision",
            name="uq_sandbox_workspace_checkpoints_run_revision",
        ),
        UniqueConstraint(
            "agent_run_id",
            "source_step_key",
            name="uq_sandbox_workspace_checkpoints_run_step",
        ),
        ForeignKeyConstraint(
            ["agent_run_id", "organization_id"],
            ["agent_runs.id", "agent_runs.organization_id"],
            name="fk_sandbox_workspace_checkpoints_agent_run",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["sandbox_provider_config_id", "organization_id"],
            ["provider_configs.id", "provider_configs.organization_id"],
            name="fk_sandbox_workspace_checkpoints_config_organization",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["sandbox_provider_config_id", "sandbox_provider_config_revision"],
            [
                "provider_config_revisions.provider_config_id",
                "provider_config_revisions.revision",
            ],
            name="fk_sandbox_workspace_checkpoints_config_revision",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "revision > 0 AND sandbox_provider_config_revision > 0",
            name="ck_sandbox_workspace_checkpoints_revisions_positive",
        ),
        CheckConstraint(
            "grant_revision IS NULL OR grant_revision > 0",
            name="ck_sandbox_workspace_checkpoints_grant_revision_positive",
        ),
        CheckConstraint(
            "workspace_digest ~ '^[0-9a-f]{64}$'",
            name="ck_sandbox_workspace_checkpoints_digest",
        ),
        CheckConstraint(
            "byte_size > 0 AND octet_length(workspace_archive) = byte_size",
            name="ck_sandbox_workspace_checkpoints_size",
        ),
        CheckConstraint(
            "length(source_step_key) BETWEEN 1 AND 256",
            name="ck_sandbox_workspace_checkpoints_step_key_size",
        ),
    )

    agent_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    source_step_key: Mapped[str] = mapped_column(String(256), nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    image: Mapped[str] = mapped_column(String(512), nullable=False)
    sandbox_provider_config_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    sandbox_provider_config_revision: Mapped[int] = mapped_column(
        Integer, nullable=False
    )
    grant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sandbox_grants.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    grant_revision: Mapped[int | None] = mapped_column(Integer, nullable=True)
    effective_policy: Mapped[dict] = mapped_column(JSONB, nullable=False)
    workspace_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    byte_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    workspace_archive: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    # Canonical model-facing output for this action. Raw output stays beside the
    # private workspace checkpoint; it is never copied into AgentRun step/API
    # projections or Absurd checkpoints.
    tool_result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class SandboxGrantModel(EyloOrganizationModel):
    """An agent's permission to run code."""

    __tablename__ = "sandbox_grants"

    __table_args__ = (
        *EyloOrganizationModel.get_organization_constraints(__tablename__),
        UniqueConstraint("agent_id"),
        ForeignKeyConstraint(
            ["agent_id", "organization_id"],
            ["agent_agents.id", "agent_agents.organization_id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["sandbox_provider_config_id", "organization_id"],
            ["provider_configs.id", "provider_configs.organization_id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["sandbox_provider_config_id", "sandbox_provider_config_revision"],
            [
                "provider_config_revisions.provider_config_id",
                "provider_config_revisions.revision",
            ],
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "revision > 0",
            name="ck_sandbox_grants_revision_positive",
        ),
        CheckConstraint(
            "sandbox_provider_config_revision > 0",
            name="ck_sandbox_grants_config_revision_positive",
        ),
    )

    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    sandbox_provider_config_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    sandbox_provider_config_revision: Mapped[int] = mapped_column(
        Integer, nullable=False
    )
    revision: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default=text("1"),
    )
    access: Mapped[SandboxAccess] = mapped_column(
        ENUM(
            SandboxAccess,
            name="sandbox_access_enum",
            values_callable=lambda enum: [member.value for member in enum],
            create_type=False,
        ),
        nullable=False,
        doc="Explicit RUN permission for bounded no-egress compute.",
    )

    # How many workspaces this agent may hold at once, within whatever the
    # organization allows. None means the organization's limit.
    max_sessions: Mapped[int | None] = mapped_column(Integer, nullable=True)
