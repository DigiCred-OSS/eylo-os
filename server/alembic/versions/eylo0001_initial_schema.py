"""Create the complete Eylo schema from an empty PostgreSQL DB.

Revision ID: eylo0001
Revises: none
Create Date: 2026-08-17

This repository carries no historical platform data. Integrations V1 is not
represented in this baseline: curated integrations, platform tools, and MCP
servers are the only integration/tool authorities. Foreign keys are created
after all tables because the schema contains deliberate aggregate cycles.
Absurd's exact pinned 0.4.0 SQL remains the durable-execution authority.
"""

from collections.abc import Sequence
from pathlib import Path
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "eylo0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ABSURD_SCHEMA_PATH = (
    Path(__file__).resolve().parents[1] / "vendor" / "absurd-0.4.0.sql"
)
_DEFERRED_FOREIGN_KEYS: list[tuple[str, str | None, sa.ForeignKeyConstraint]] = []


class _VectorType(sa.types.UserDefinedType):
    """Migration-local pgvector type; the baseline stays self-contained."""

    cache_ok = True

    def get_col_spec(self, **_kwargs: object) -> str:
        return "vector"


def _create_table(table_name: str, *elements: Any, **kwargs: Any) -> Any:
    """Create one frozen table and defer its FKs until every target exists."""
    foreign_keys = tuple(
        element for element in elements if isinstance(element, sa.ForeignKeyConstraint)
    )
    _DEFERRED_FOREIGN_KEYS.extend(
        (table_name, kwargs.get("schema"), constraint) for constraint in foreign_keys
    )
    table_elements = tuple(
        element
        for element in elements
        if not isinstance(element, sa.ForeignKeyConstraint)
    )
    return op.create_table(table_name, *table_elements, **kwargs)


def _create_deferred_foreign_keys() -> None:
    for source_table, source_schema, constraint in _DEFERRED_FOREIGN_KEYS:
        target_specs = [str(element._get_colspec()) for element in constraint.elements]
        targets = [target_spec.rsplit(".", 1) for target_spec in target_specs]
        target_tables = {target[0] for target in targets}
        if len(target_tables) != 1:
            raise RuntimeError(
                f"Foreign key {constraint.name!r} spans multiple target tables."
            )

        qualified_target = target_tables.pop()
        if "." in qualified_target:
            target_schema, target_table = qualified_target.rsplit(".", 1)
        else:
            target_schema, target_table = None, qualified_target

        options = {
            key: value
            for key, value in {
                "onupdate": constraint.onupdate,
                "ondelete": constraint.ondelete,
                "deferrable": constraint.deferrable,
                "initially": constraint.initially,
                "match": constraint.match,
                "source_schema": source_schema,
                "referent_schema": target_schema,
            }.items()
            if value is not None
        }
        op.create_foreign_key(
            constraint.name,
            source_table,
            target_table,
            list(constraint.column_keys),
            [target[1] for target in targets],
            **options,
        )


def _install_absurd_schema() -> None:
    schema_sql = _ABSURD_SCHEMA_PATH.read_text(encoding="utf-8")
    schema_sql += (
        "\nSELECT absurd.create_queue('eylo-agent-runs-v1', 'unpartitioned');\n"
    )
    adapted_connection = op.get_bind().connection.dbapi_connection
    adapted_connection.run_async(lambda connection: connection.execute(schema_sql))


def _drop_public_foreign_keys() -> None:
    op.execute(
        """
        DO $$
        DECLARE constraint_row record;
        BEGIN
          FOR constraint_row IN
            SELECT constraint_record.conrelid::regclass AS table_name,
                   constraint_record.conname AS constraint_name
            FROM pg_constraint AS constraint_record
            JOIN pg_namespace AS namespace
              ON namespace.oid = constraint_record.connamespace
            WHERE constraint_record.contype = 'f'
              AND namespace.nspname = 'public'
          LOOP
            EXECUTE format(
              'ALTER TABLE %s DROP CONSTRAINT %I',
              constraint_row.table_name,
              constraint_row.constraint_name
            );
          END LOOP;
        END
        $$;
        """
    )


def _drop_public_enum_types() -> None:
    op.execute(
        """
        DO $$
        DECLARE enum_row record;
        BEGIN
          FOR enum_row IN
            SELECT namespace.nspname AS schema_name, type_record.typname AS type_name
            FROM pg_type AS type_record
            JOIN pg_namespace AS namespace ON namespace.oid = type_record.typnamespace
            WHERE type_record.typtype = 'e'
              AND namespace.nspname = 'public'
          LOOP
            EXECUTE format(
              'DROP TYPE IF EXISTS %I.%I',
              enum_row.schema_name,
              enum_row.type_name
            );
          END LOOP;
        END
        $$;
        """
    )


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    # ### commands auto generated by Alembic - please adjust! ###
    _create_table(
        "agent_runs",
        sa.Column(
            "initiating_principal_kind",
            postgresql.ENUM(
                "member",
                "contact",
                "api_key",
                "widget",
                "worker",
                name="agent_run_principal_kind_enum",
            ),
            nullable=False,
        ),
        sa.Column("initiating_principal_id", sa.UUID(), nullable=False),
        sa.Column("agent_id", sa.UUID(), nullable=False),
        sa.Column("agent_revision", sa.Integer(), nullable=False),
        sa.Column(
            "origin_kind",
            postgresql.ENUM(
                "message",
                "schedule_occurrence",
                "objective",
                name="agent_run_origin_kind_enum",
            ),
            nullable=False,
        ),
        sa.Column("origin_message_id", sa.UUID(), nullable=True),
        sa.Column("origin_schedule_run_id", sa.UUID(), nullable=True),
        sa.Column("user_session_id", sa.UUID(), nullable=True),
        sa.Column("session_context_digest", sa.String(length=64), nullable=False),
        sa.Column(
            "context_manifest",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("idempotency_key", sa.String(length=320), nullable=False),
        sa.Column("absurd_task_id", sa.UUID(), nullable=True),
        sa.Column(
            "lifecycle",
            postgresql.ENUM(
                "queued",
                "running",
                "waiting_for_input",
                "waiting_for_approval",
                "completed",
                "failed",
                "cancelled",
                name="agent_run_lifecycle_enum",
            ),
            server_default="queued",
            nullable=False,
        ),
        sa.Column(
            "outcome",
            postgresql.ENUM(
                "achieved",
                "unachievable",
                "failed",
                "cancelled",
                "exhausted",
                name="agent_run_outcome_enum",
            ),
            nullable=True,
        ),
        sa.Column("goal", sa.Text(), nullable=False),
        sa.Column(
            "result",
            postgresql.JSONB(astext_type=sa.Text(), none_as_null=True),
            nullable=True,
        ),
        sa.Column("outcome_reason", sa.String(length=4000), nullable=True),
        sa.Column("failure_summary", sa.String(length=2000), nullable=True),
        sa.Column(
            "state_revision", sa.Integer(), server_default=sa.text("1"), nullable=False
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("waiting_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "cancellation_requested_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("external_id", sa.String(length=320), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(lifecycle NOT IN ('completed', 'failed', 'cancelled') AND outcome IS NULL AND result IS NULL AND finished_at IS NULL AND cancelled_at IS NULL) OR (lifecycle = 'completed' AND outcome IN ('achieved', 'unachievable', 'exhausted') AND result IS NOT NULL AND failure_summary IS NULL AND finished_at IS NOT NULL AND cancelled_at IS NULL) OR (lifecycle = 'failed' AND outcome = 'failed' AND result IS NULL AND failure_summary IS NOT NULL AND length(btrim(failure_summary)) BETWEEN 1 AND 2000 AND finished_at IS NOT NULL AND cancelled_at IS NULL) OR (lifecycle = 'cancelled' AND outcome = 'cancelled' AND result IS NULL AND finished_at IS NOT NULL AND cancellation_requested_at IS NOT NULL AND cancelled_at IS NOT NULL)",
            name="ck_agent_runs_lifecycle_outcome",
        ),
        sa.CheckConstraint(
            "(origin_kind = 'message' AND origin_message_id IS NOT NULL AND origin_schedule_run_id IS NULL) OR (origin_kind = 'schedule_occurrence' AND origin_schedule_run_id IS NOT NULL AND origin_message_id IS NULL) OR (origin_kind = 'objective' AND origin_message_id IS NULL AND origin_schedule_run_id IS NULL)",
            name="ck_agent_runs_exactly_one_origin",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(context_manifest) = 'object'",
            name="ck_agent_runs_context_manifest_object",
        ),
        sa.CheckConstraint(
            "lifecycle = 'queued' OR absurd_task_id IS NOT NULL OR (lifecycle = 'cancelled' AND started_at IS NULL AND cancellation_requested_at IS NOT NULL)",
            name="ck_agent_runs_task_bound_before_execution",
        ),
        sa.CheckConstraint(
            "lifecycle NOT IN ('waiting_for_input', 'waiting_for_approval') OR waiting_at IS NOT NULL",
            name="ck_agent_runs_waiting_time",
        ),
        sa.CheckConstraint(
            "outcome IS NULL OR outcome NOT IN ('unachievable', 'exhausted') OR (outcome_reason IS NOT NULL AND length(btrim(outcome_reason)) BETWEEN 1 AND 4000)",
            name="ck_agent_runs_conclusion_reason",
        ),
        sa.CheckConstraint(
            "session_context_digest ~ '^[0-9a-f]{64}$'",
            name="ck_agent_runs_context_digest",
        ),
        sa.CheckConstraint(
            "agent_revision > 0", name="ck_agent_runs_agent_revision_positive"
        ),
        sa.CheckConstraint(
            "length(goal) BETWEEN 1 AND 16384", name="ck_agent_runs_goal_size"
        ),
        sa.CheckConstraint(
            "length(idempotency_key) BETWEEN 1 AND 320",
            name="ck_agent_runs_idempotency_key_size",
        ),
        sa.CheckConstraint(
            "octet_length(context_manifest::text) <= 16384",
            name="ck_agent_runs_context_manifest_size",
        ),
        sa.CheckConstraint(
            "result IS NULL OR octet_length(result::text) <= 65536",
            name="ck_agent_runs_result_size",
        ),
        sa.CheckConstraint(
            "state_revision > 0", name="ck_agent_runs_state_revision_positive"
        ),
        sa.ForeignKeyConstraint(
            ["agent_id", "agent_revision", "organization_id"],
            [
                "agent_definition_revisions.agent_id",
                "agent_definition_revisions.revision",
                "agent_definition_revisions.organization_id",
            ],
            name="fk_agent_runs_agent_revision",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organization_organizations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["origin_message_id"], ["conversation_messages.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["origin_schedule_run_id", "organization_id"],
            ["scheduler_runs.id", "scheduler_runs.organization_id"],
            name="fk_agent_runs_schedule_occurrence",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["user_session_id", "organization_id"],
            ["user_sessions.id", "user_sessions.organization_id"],
            name="fk_agent_runs_user_session_organization",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("absurd_task_id", name="uq_agent_runs_absurd_task_id"),
        sa.UniqueConstraint(
            "id", "organization_id", name="uq_agent_runs_id_organization_id"
        ),
        sa.UniqueConstraint("idempotency_key", name="uq_agent_runs_idempotency_key"),
        sa.UniqueConstraint(
            "origin_message_id", name="uq_agent_runs_origin_message_id"
        ),
        sa.UniqueConstraint(
            "origin_schedule_run_id", name="uq_agent_runs_origin_schedule_run_id"
        ),
    )
    op.create_index(
        op.f("ix_agent_runs_agent_id"), "agent_runs", ["agent_id"], unique=False
    )
    op.create_index(
        op.f("ix_agent_runs_created_at"), "agent_runs", ["created_at"], unique=False
    )
    op.create_index(
        op.f("ix_agent_runs_initiating_principal_id"),
        "agent_runs",
        ["initiating_principal_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_agent_runs_lifecycle"), "agent_runs", ["lifecycle"], unique=False
    )
    op.create_index(
        op.f("ix_agent_runs_organization_id"),
        "agent_runs",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_agent_runs_user_session_id"),
        "agent_runs",
        ["user_session_id"],
        unique=False,
    )
    op.create_index(
        "ix_unq_agent_runs_ext_id_org_id",
        "agent_runs",
        ["external_id", "organization_id"],
        unique=True,
    )
    _create_table(
        "agent_swarm_revisions",
        sa.Column("swarm_id", sa.UUID(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("slug", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "availability",
            sa.String(length=16),
            server_default="published",
            nullable=False,
        ),
        sa.Column(
            "published_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("published_by", sa.UUID(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by", sa.UUID(), nullable=True),
        sa.Column("revocation_reason", sa.Text(), nullable=True),
        sa.Column(
            "cancellation_requested_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("external_id", sa.String(length=320), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(availability = 'published' AND revoked_at IS NULL AND revoked_by IS NULL AND revocation_reason IS NULL AND cancellation_requested_at IS NULL) OR (availability = 'revoked' AND revoked_at IS NOT NULL AND revoked_by IS NOT NULL AND revocation_reason IS NOT NULL AND length(btrim(revocation_reason)) BETWEEN 1 AND 2000 AND cancellation_requested_at IS NOT NULL)",
            name="ck_agent_swarm_revisions_revocation_metadata",
        ),
        sa.CheckConstraint(
            "availability IN ('published', 'revoked')",
            name="ck_agent_swarm_revisions_availability",
        ),
        sa.CheckConstraint(
            "revision > 0", name="ck_agent_swarm_revisions_revision_positive"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organization_organizations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["swarm_id", "organization_id"],
            ["agent_swarms.id", "agent_swarms.organization_id"],
            name="fk_agent_swarm_revisions_header_organization",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "swarm_id",
            "revision",
            "organization_id",
            name="uq_agent_swarm_revisions_ref_organization",
        ),
        sa.UniqueConstraint(
            "swarm_id", "revision", name="uq_agent_swarm_revisions_ref"
        ),
    )
    op.create_index(
        op.f("ix_agent_swarm_revisions_created_at"),
        "agent_swarm_revisions",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_agent_swarm_revisions_organization_id"),
        "agent_swarm_revisions",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_agent_swarm_revisions_swarm_id"),
        "agent_swarm_revisions",
        ["swarm_id"],
        unique=False,
    )
    op.create_index(
        "ix_unq_agent_swarm_revisions_ext_id_org_id",
        "agent_swarm_revisions",
        ["external_id", "organization_id"],
        unique=True,
    )
    _create_table(
        "agent_swarms",
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("slug", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "lifecycle", sa.String(length=16), server_default="draft", nullable=False
        ),
        sa.Column("published_revision", sa.Integer(), nullable=True),
        sa.Column(
            "draft_version", sa.Integer(), server_default=sa.text("1"), nullable=False
        ),
        sa.Column(
            "draft_dirty", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("external_id", sa.String(length=320), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(lifecycle = 'draft' AND published_revision IS NULL AND draft_dirty = true) OR (lifecycle <> 'draft' AND published_revision IS NOT NULL)",
            name="ck_agent_swarms_lifecycle_revision",
        ),
        sa.CheckConstraint(
            "lifecycle IN ('draft', 'published', 'withdrawn', 'archived')",
            name="ck_agent_swarms_lifecycle",
        ),
        sa.CheckConstraint(
            "draft_version > 0", name="ck_agent_swarms_draft_version_positive"
        ),
        sa.CheckConstraint(
            "published_revision IS NULL OR published_revision > 0",
            name="ck_agent_swarms_published_revision_positive",
        ),
        sa.ForeignKeyConstraint(
            ["id", "published_revision", "organization_id"],
            [
                "agent_swarm_revisions.swarm_id",
                "agent_swarm_revisions.revision",
                "agent_swarm_revisions.organization_id",
            ],
            name="fk_agent_swarms_published_revision",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organization_organizations.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "id", "organization_id", name="uq_agent_swarms_id_organization_id"
        ),
    )
    op.create_index(
        op.f("ix_agent_swarms_created_at"), "agent_swarms", ["created_at"], unique=False
    )
    op.create_index(
        op.f("ix_agent_swarms_organization_id"),
        "agent_swarms",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "ix_unq_agent_swarms_ext_id_org_id",
        "agent_swarms",
        ["external_id", "organization_id"],
        unique=True,
    )
    op.create_index(
        "uq_agent_swarms_org_slug_active",
        "agent_swarms",
        ["organization_id", "slug"],
        unique=True,
        postgresql_where=sa.text("deleted = false"),
    )
    _create_table(
        "conversation_messages",
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("content_kind", sa.Text(), nullable=False),
        sa.Column("content", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("parent_message_id", sa.UUID(), nullable=True),
        sa.Column("request_id", sa.UUID(), nullable=True),
        sa.Column("request_status", sa.Text(), nullable=True),
        sa.Column("request_feedback", sa.Text(), nullable=True),
        sa.Column("meta", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("external_id", sa.String(length=320), nullable=True),
        sa.Column("conversation_id", sa.UUID(), nullable=False),
        sa.Column("user_session_id", sa.UUID(), nullable=True),
        sa.Column("sender_participant_id", sa.UUID(), nullable=False),
        sa.Column("agent_run_id", sa.UUID(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "agent_run_id IS NULL OR kind IN ('ASSISTANT', 'TOOL_USE', 'TOOL_RESULT') OR (kind = 'SYSTEM' AND content_kind = 'TASK_RESULT')",
            name="ck_conversation_messages_agent_run_output_kind",
        ),
        sa.ForeignKeyConstraint(
            ["agent_run_id"], ["agent_runs.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["user_session_id", "conversation_id"],
            [
                "user_session_conversations.user_session_id",
                "user_session_conversations.conversation_id",
            ],
            name="fk_conversation_messages_user_session_conversation",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversation_conversations.id"],
        ),
        sa.ForeignKeyConstraint(
            ["parent_message_id"],
            ["conversation_messages.id"],
        ),
        sa.ForeignKeyConstraint(
            ["sender_participant_id"],
            ["conversation_participants.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_conversation_messages_agent_run_id"),
        "conversation_messages",
        ["agent_run_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_conversation_messages_conversation_id"),
        "conversation_messages",
        ["conversation_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_conversation_messages_created_at"),
        "conversation_messages",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_conversation_messages_external_id"),
        "conversation_messages",
        ["external_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_conversation_messages_request_id"),
        "conversation_messages",
        ["request_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_conversation_messages_sender_participant_id"),
        "conversation_messages",
        ["sender_participant_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_conversation_messages_user_session_id"),
        "conversation_messages",
        ["user_session_id"],
        unique=False,
    )
    op.create_index(
        "uq_conversation_messages_task_result_agent_run",
        "conversation_messages",
        ["agent_run_id"],
        unique=True,
        postgresql_where=sa.text(
            "kind = 'SYSTEM' AND content_kind = 'TASK_RESULT' AND deleted IS FALSE"
        ),
    )
    _create_table(
        "organization_organizations",
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_organization_organizations_created_at"),
        "organization_organizations",
        ["created_at"],
        unique=False,
    )
    _create_table(
        "agent_input_requests",
        sa.Column("run_id", sa.UUID(), nullable=False),
        sa.Column(
            "kind",
            postgresql.ENUM("input", "approval", name="agent_input_request_kind_enum"),
            nullable=False,
        ),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column(
            "expected_response_schema",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "continuation",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("event_name", sa.String(length=512), nullable=False),
        sa.Column("resume_step_key", sa.String(length=256), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "pending",
                "answered",
                "cancelled",
                name="agent_input_request_status_enum",
            ),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("response", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "answered_by_principal_kind",
            postgresql.ENUM(
                "member",
                "contact",
                "api_key",
                "widget",
                "worker",
                name="agent_run_principal_kind_enum",
            ),
            nullable=True,
        ),
        sa.Column("answered_by_principal_id", sa.UUID(), nullable=True),
        sa.Column(
            "state_revision", sa.Integer(), server_default=sa.text("1"), nullable=False
        ),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("external_id", sa.String(length=320), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(status = 'pending' AND response IS NULL AND answered_at IS NULL AND cancelled_at IS NULL) OR (status = 'answered' AND response IS NOT NULL AND answered_at IS NOT NULL AND cancelled_at IS NULL AND answered_by_principal_id IS NOT NULL) OR (status = 'cancelled' AND response IS NULL AND answered_at IS NULL AND cancelled_at IS NOT NULL)",
            name="ck_agent_input_requests_lifecycle",
        ),
        sa.CheckConstraint(
            "(answered_by_principal_kind IS NULL AND answered_by_principal_id IS NULL) OR (answered_by_principal_kind IS NOT NULL AND answered_by_principal_id IS NOT NULL)",
            name="ck_agent_input_requests_answer_principal_pair",
        ),
        sa.CheckConstraint(
            "length(event_name) BETWEEN 1 AND 512",
            name="ck_agent_input_requests_event_name_size",
        ),
        sa.CheckConstraint(
            "length(prompt) BETWEEN 1 AND 8192",
            name="ck_agent_input_requests_prompt_size",
        ),
        sa.CheckConstraint(
            "length(resume_step_key) BETWEEN 1 AND 256",
            name="ck_agent_input_requests_resume_step_key_size",
        ),
        sa.CheckConstraint(
            "octet_length(continuation::text) <= 16384",
            name="ck_agent_input_requests_continuation_size",
        ),
        sa.CheckConstraint(
            "octet_length(expected_response_schema::text) <= 16384",
            name="ck_agent_input_requests_schema_size",
        ),
        sa.CheckConstraint(
            "response IS NULL OR octet_length(response::text) <= 65536",
            name="ck_agent_input_requests_response_size",
        ),
        sa.CheckConstraint(
            "state_revision > 0", name="ck_agent_input_requests_state_revision_positive"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organization_organizations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["run_id", "organization_id"],
            ["agent_runs.id", "agent_runs.organization_id"],
            name="fk_agent_input_requests_run",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_name", name="uq_agent_input_requests_event_name"),
    )
    op.create_index(
        op.f("ix_agent_input_requests_created_at"),
        "agent_input_requests",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_agent_input_requests_organization_id"),
        "agent_input_requests",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_agent_input_requests_run_id"),
        "agent_input_requests",
        ["run_id"],
        unique=False,
    )
    op.create_index(
        "ix_unq_agent_input_requests_ext_id_org_id",
        "agent_input_requests",
        ["external_id", "organization_id"],
        unique=True,
    )
    _create_table(
        "agent_run_steps",
        sa.Column("run_id", sa.UUID(), nullable=False),
        sa.Column("step_key", sa.String(length=256), nullable=False),
        sa.Column(
            "kind",
            postgresql.ENUM(
                "agent_turn",
                "model_inference",
                "tool",
                "sandbox",
                "artifact_export",
                name="agent_run_step_kind_enum",
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            postgresql.ENUM(
                "pending",
                "running",
                "completed",
                "failed",
                "cancelled",
                name="agent_run_step_status_enum",
            ),
            server_default="pending",
            nullable=False,
        ),
        sa.Column(
            "intent",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("safe_summary", sa.String(length=4000), nullable=True),
        sa.Column(
            "evidence",
            postgresql.JSONB(astext_type=sa.Text(), none_as_null=True),
            nullable=True,
        ),
        sa.Column(
            "artifact_refs",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("provider_idempotency_key", sa.String(length=512), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("external_id", sa.String(length=320), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(status IN ('pending', 'running') AND completed_at IS NULL) OR (status IN ('completed', 'failed', 'cancelled') AND completed_at IS NOT NULL)",
            name="ck_agent_run_steps_terminal_time",
        ),
        sa.CheckConstraint(
            "evidence IS NULL OR octet_length(evidence::text) <= 32768",
            name="ck_agent_run_steps_evidence_size",
        ),
        sa.CheckConstraint(
            "length(step_key) BETWEEN 1 AND 256", name="ck_agent_run_steps_key_size"
        ),
        sa.CheckConstraint(
            "octet_length(artifact_refs::text) <= 16384",
            name="ck_agent_run_steps_artifact_refs_size",
        ),
        sa.CheckConstraint(
            "octet_length(intent::text) <= 32768", name="ck_agent_run_steps_intent_size"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organization_organizations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["run_id", "organization_id"],
            ["agent_runs.id", "agent_runs.organization_id"],
            name="fk_agent_run_steps_run",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider_idempotency_key",
            name="uq_agent_run_steps_provider_idempotency_key",
        ),
        sa.UniqueConstraint(
            "run_id", "step_key", name="uq_agent_run_steps_run_step_key"
        ),
    )
    op.create_index(
        op.f("ix_agent_run_steps_created_at"),
        "agent_run_steps",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_agent_run_steps_organization_id"),
        "agent_run_steps",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_agent_run_steps_run_id"), "agent_run_steps", ["run_id"], unique=False
    )
    op.create_index(
        "ix_unq_agent_run_steps_ext_id_org_id",
        "agent_run_steps",
        ["external_id", "organization_id"],
        unique=True,
    )
    _create_table(
        "agent_run_transcript_items",
        sa.Column("run_id", sa.UUID(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("correlation_id", sa.String(length=256), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("external_id", sa.String(length=320), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "kind IN ('assistant_text', 'tool_call', 'tool_result')",
            name="ck_agent_run_transcript_items_kind",
        ),
        sa.CheckConstraint(
            "correlation_id IS NULL OR length(correlation_id) BETWEEN 1 AND 256",
            name="ck_agent_run_transcript_items_correlation_size",
        ),
        sa.CheckConstraint(
            "octet_length(payload::text) <= 65536",
            name="ck_agent_run_transcript_items_payload_size",
        ),
        sa.CheckConstraint(
            "sequence > 0", name="ck_agent_run_transcript_items_sequence_positive"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organization_organizations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["run_id", "organization_id"],
            ["agent_runs.id", "agent_runs.organization_id"],
            name="fk_agent_run_transcript_items_run",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "run_id",
            "kind",
            "correlation_id",
            name="uq_agent_run_transcript_items_run_kind_correlation",
        ),
        sa.UniqueConstraint(
            "run_id", "sequence", name="uq_agent_run_transcript_items_run_sequence"
        ),
    )
    op.create_index(
        op.f("ix_agent_run_transcript_items_created_at"),
        "agent_run_transcript_items",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_agent_run_transcript_items_organization_id"),
        "agent_run_transcript_items",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_agent_run_transcript_items_run_id"),
        "agent_run_transcript_items",
        ["run_id"],
        unique=False,
    )
    op.create_index(
        "ix_unq_agent_run_transcript_items_ext_id_org_id",
        "agent_run_transcript_items",
        ["external_id", "organization_id"],
        unique=True,
    )
    _create_table(
        "auth_api_keys",
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("key_prefix", sa.String(), nullable=False),
        sa.Column("hashed_key", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("usage_count", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("external_id", sa.String(length=320), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organization_organizations.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_auth_api_keys_created_at"),
        "auth_api_keys",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_auth_api_keys_hashed_key"),
        "auth_api_keys",
        ["hashed_key"],
        unique=True,
    )
    op.create_index(
        op.f("ix_auth_api_keys_key_prefix"),
        "auth_api_keys",
        ["key_prefix"],
        unique=False,
    )
    op.create_index(
        "ix_auth_api_keys_org_id", "auth_api_keys", ["organization_id"], unique=False
    )
    op.create_index(
        op.f("ix_auth_api_keys_organization_id"),
        "auth_api_keys",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "ix_unq_auth_api_keys_ext_id_org_id",
        "auth_api_keys",
        ["external_id", "organization_id"],
        unique=True,
    )
    _create_table(
        "contact_contacts",
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("primary_email", sa.String(length=320), nullable=True),
        sa.Column("primary_phone", sa.String(length=16), nullable=True),
        sa.Column(
            "preferences", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column(
            "lifecycle", sa.String(length=32), server_default="active", nullable=False
        ),
        sa.Column("deletion_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("external_id", sa.String(length=320), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(lifecycle = 'active' AND deletion_requested_at IS NULL) OR (lifecycle = 'deletion_pending' AND deletion_requested_at IS NOT NULL)",
            name="ck_contact_contacts_lifecycle",
        ),
        sa.CheckConstraint(
            "primary_phone IS NULL OR primary_phone ~ '^\\+[1-9][0-9]{1,14}$'",
            name="ck_contact_contacts_primary_phone_e164",
        ),
        sa.CheckConstraint(
            "primary_email IS NULL OR primary_email = lower(btrim(primary_email))",
            name="ck_contact_contacts_primary_email_canonical",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organization_organizations.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "id", "organization_id", name="uq_contact_contacts_id_organization_id"
        ),
    )
    op.create_index(
        op.f("ix_contact_contacts_created_at"),
        "contact_contacts",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_contact_contacts_lifecycle"),
        "contact_contacts",
        ["lifecycle"],
        unique=False,
    )
    op.create_index(
        op.f("ix_contact_contacts_organization_id"),
        "contact_contacts",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "ix_unq_contact_contacts_ext_id_org_id",
        "contact_contacts",
        ["external_id", "organization_id"],
        unique=True,
    )
    op.create_index(
        "ix_unqc_contact_email_org_id",
        "contact_contacts",
        ["primary_email", "organization_id"],
        unique=True,
    )
    op.create_index(
        "ix_unqc_contact_phone_org_id",
        "contact_contacts",
        ["primary_phone", "organization_id"],
        unique=True,
    )
    _create_table(
        "conversation_conversations",
        sa.Column(
            "channel",
            postgresql.ENUM(
                "PHONE",
                "CHAT",
                "WEB",
                "WIDGET",
                "SMS",
                "API",
                name="conversation_channel_enum",
            ),
            server_default="CHAT",
            nullable=False,
        ),
        sa.Column(
            "status",
            postgresql.ENUM(
                "ACTIVE", "COMPLETED", "ABANDONED", name="conversation_status_enum"
            ),
            server_default="ACTIVE",
            nullable=False,
        ),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("has_triggered_title_generation", sa.Boolean(), nullable=True),
        sa.Column("meta", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("swarm_id", sa.UUID(), nullable=True),
        sa.Column("swarm_revision", sa.Integer(), nullable=True),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("external_id", sa.String(length=320), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(swarm_id IS NULL AND swarm_revision IS NULL) OR (swarm_id IS NOT NULL AND swarm_revision > 0)",
            name="ck_conversation_conversations_swarm_ref",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organization_organizations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["swarm_id", "swarm_revision", "organization_id"],
            [
                "agent_swarm_revisions.swarm_id",
                "agent_swarm_revisions.revision",
                "agent_swarm_revisions.organization_id",
            ],
            name="fk_conversation_conversations_swarm_revision",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "id",
            "organization_id",
            name="uq_conversation_conversations_id_organization",
        ),
    )
    op.create_index(
        op.f("ix_conversation_conversations_created_at"),
        "conversation_conversations",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_conversation_conversations_organization_id"),
        "conversation_conversations",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "ix_unq_conversation_conversations_ext_id_org_id",
        "conversation_conversations",
        ["external_id", "organization_id"],
        unique=True,
    )
    _create_table(
        "definition_templates",
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("slug", sa.String(length=128), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("draft_body", sa.Text(), nullable=False),
        sa.Column(
            "draft_variable_schema",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "lifecycle", sa.String(length=16), server_default="draft", nullable=False
        ),
        sa.Column("published_revision", sa.Integer(), nullable=True),
        sa.Column(
            "draft_version", sa.Integer(), server_default=sa.text("1"), nullable=False
        ),
        sa.Column(
            "draft_dirty", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("external_id", sa.String(length=320), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(lifecycle = 'draft' AND published_revision IS NULL AND draft_dirty = true) OR (lifecycle <> 'draft' AND published_revision IS NOT NULL)",
            name="ck_definition_templates_lifecycle_revision",
        ),
        sa.CheckConstraint(
            "lifecycle IN ('draft', 'published', 'withdrawn', 'archived')",
            name="ck_definition_templates_lifecycle",
        ),
        sa.CheckConstraint(
            "draft_version > 0", name="ck_definition_templates_draft_version_positive"
        ),
        sa.CheckConstraint(
            "published_revision IS NULL OR published_revision > 0",
            name="ck_definition_templates_published_revision_positive",
        ),
        sa.ForeignKeyConstraint(
            ["id", "published_revision", "organization_id"],
            [
                "definition_template_revisions.template_id",
                "definition_template_revisions.revision",
                "definition_template_revisions.organization_id",
            ],
            name="fk_definition_templates_published_revision",
            ondelete="RESTRICT",
            use_alter=True,
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organization_organizations.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "id", "organization_id", name="uq_definition_templates_id_organization_id"
        ),
    )
    op.create_index(
        op.f("ix_definition_templates_created_at"),
        "definition_templates",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_definition_templates_organization_id"),
        "definition_templates",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "ix_unq_definition_templates_ext_id_org_id",
        "definition_templates",
        ["external_id", "organization_id"],
        unique=True,
    )
    op.create_index(
        "uq_definition_templates_org_slug_active",
        "definition_templates",
        ["organization_id", "slug"],
        unique=True,
        postgresql_where=sa.text("deleted = false"),
    )
    _create_table(
        "event_outbox",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("subject_type", sa.String(length=128), nullable=False),
        sa.Column("subject_id", sa.UUID(), nullable=False),
        sa.Column("event_type", sa.String(length=192), nullable=False),
        sa.Column("event_version", sa.SmallInteger(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("correlation_id", sa.UUID(), nullable=True),
        sa.Column("causation_id", sa.UUID(), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.CheckConstraint(
            "event_type ~ '^[a-z][a-z0-9_.-]*$'", name="ck_event_outbox_event_type"
        ),
        sa.CheckConstraint(
            "jsonb_typeof(payload) = 'object'", name="ck_event_outbox_payload_object"
        ),
        sa.CheckConstraint(
            "subject_type ~ '^[a-z][a-z0-9_.-]*$'", name="ck_event_outbox_subject_type"
        ),
        sa.CheckConstraint(
            "causation_id IS NULL OR causation_id <> id",
            name="ck_event_outbox_not_self_caused",
        ),
        sa.CheckConstraint(
            "event_version BETWEEN 1 AND 32767", name="ck_event_outbox_version"
        ),
        sa.CheckConstraint(
            "octet_length(payload::text) <= 65536", name="ck_event_outbox_payload_size"
        ),
        sa.CheckConstraint(
            "recorded_at >= occurred_at",
            name="ck_event_outbox_recorded_after_occurrence",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organization_organizations.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "id", "organization_id", name="uq_event_outbox_id_organization_id"
        ),
    )
    op.create_index(
        op.f("ix_event_outbox_event_type"), "event_outbox", ["event_type"], unique=False
    )
    op.create_index(
        op.f("ix_event_outbox_organization_id"),
        "event_outbox",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "ix_event_outbox_org_correlation_occurred",
        "event_outbox",
        ["organization_id", "correlation_id", "occurred_at", "id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_event_outbox_recorded_at"),
        "event_outbox",
        ["recorded_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_event_outbox_subject_id"), "event_outbox", ["subject_id"], unique=False
    )
    _create_table(
        "integration_v2_installations",
        sa.Column("vendor", sa.String(length=64), nullable=False),
        sa.Column("auth_kind", sa.String(length=32), nullable=False),
        sa.Column("instance_url", sa.String(length=512), nullable=True),
        sa.Column("oauth_client_id", sa.String(length=512), nullable=True),
        sa.Column("oauth_client_secret", sa.Text(), nullable=True),
        sa.Column("oauth_tenant", sa.String(length=128), nullable=True),
        sa.Column("installed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("installed_by", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("external_id", sa.String(length=320), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "auth_kind IN ('no_auth', 'api_key', 'basic', 'oauth2')",
            name="ck_integration_v2_installations_auth_kind",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organization_organizations.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "id",
            "organization_id",
            name="uq_integration_v2_installations_id_organization_id",
        ),
    )
    op.create_index(
        op.f("ix_integration_v2_installations_created_at"),
        "integration_v2_installations",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_integration_v2_installations_organization_id"),
        "integration_v2_installations",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "ix_unq_integration_v2_installations_ext_id_org_id",
        "integration_v2_installations",
        ["external_id", "organization_id"],
        unique=True,
    )
    op.create_index(
        "uq_integration_v2_installations_org_vendor_active",
        "integration_v2_installations",
        ["organization_id", "vendor"],
        unique=True,
        postgresql_where="deleted = false",
    )
    _create_table(
        "mcp_servers",
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("slug", sa.String(length=128), nullable=False),
        sa.Column("config", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("discovered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("discovered_tool_count", sa.Integer(), nullable=True),
        sa.Column(
            "lifecycle", sa.String(length=16), server_default="draft", nullable=False
        ),
        sa.Column("published_revision", sa.Integer(), nullable=True),
        sa.Column(
            "draft_version", sa.Integer(), server_default=sa.text("1"), nullable=False
        ),
        sa.Column(
            "draft_dirty", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("external_id", sa.String(length=320), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(lifecycle = 'draft' AND published_revision IS NULL AND draft_dirty = true) OR (lifecycle <> 'draft' AND published_revision IS NOT NULL)",
            name="ck_mcp_servers_lifecycle_revision",
        ),
        sa.CheckConstraint(
            "lifecycle IN ('draft', 'published', 'withdrawn', 'archived')",
            name="ck_mcp_servers_lifecycle",
        ),
        sa.CheckConstraint(
            "draft_version > 0", name="ck_mcp_servers_draft_version_positive"
        ),
        sa.CheckConstraint(
            "published_revision IS NULL OR published_revision > 0",
            name="ck_mcp_servers_published_revision_positive",
        ),
        sa.ForeignKeyConstraint(
            ["id", "published_revision", "organization_id"],
            [
                "mcp_server_definition_revisions.server_id",
                "mcp_server_definition_revisions.revision",
                "mcp_server_definition_revisions.organization_id",
            ],
            name="fk_mcp_servers_published_definition_revision",
            ondelete="RESTRICT",
            use_alter=True,
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organization_organizations.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "id", "organization_id", name="uq_mcp_servers_id_organization_id"
        ),
    )
    op.create_index(
        op.f("ix_mcp_servers_created_at"), "mcp_servers", ["created_at"], unique=False
    )
    op.create_index(
        op.f("ix_mcp_servers_organization_id"),
        "mcp_servers",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "ix_unq_mcp_servers_ext_id_org_id",
        "mcp_servers",
        ["external_id", "organization_id"],
        unique=True,
    )
    op.create_index(
        "uq_mcp_servers_org_slug_active",
        "mcp_servers",
        ["organization_id", "slug"],
        unique=True,
        postgresql_where=sa.text("deleted = false"),
    )
    _create_table(
        "member_members",
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("last_login", sa.DateTime(timezone=True), nullable=True),
        sa.Column("password", sa.Text(), nullable=True),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("external_id", sa.String(length=320), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organization_organizations.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index(
        op.f("ix_member_members_created_at"),
        "member_members",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_member_members_organization_id"),
        "member_members",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "ix_unq_member_members_ext_id_org_id",
        "member_members",
        ["external_id", "organization_id"],
        unique=True,
    )
    _create_table(
        "organization_execution_budgets",
        sa.Column("max_concurrent_runs", sa.Integer(), nullable=False),
        sa.Column("max_active_tokens", sa.BigInteger(), nullable=False),
        sa.Column("max_active_milliseconds", sa.BigInteger(), nullable=False),
        sa.Column("max_active_cost_microunits", sa.BigInteger(), nullable=False),
        sa.Column("run_token_limit", sa.BigInteger(), nullable=False),
        sa.Column("run_time_limit_milliseconds", sa.BigInteger(), nullable=False),
        sa.Column("run_cost_limit_microunits", sa.BigInteger(), nullable=False),
        sa.Column(
            "cost_microunits_per_million_tokens", sa.BigInteger(), nullable=False
        ),
        sa.Column(
            "state_revision", sa.Integer(), server_default=sa.text("1"), nullable=False
        ),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("external_id", sa.String(length=320), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "max_concurrent_runs > 0 AND max_active_tokens > 0 AND max_active_milliseconds > 0 AND max_active_cost_microunits > 0",
            name="ck_organization_execution_budgets_capacity_positive",
        ),
        sa.CheckConstraint(
            "run_token_limit <= max_active_tokens AND run_time_limit_milliseconds <= max_active_milliseconds AND run_cost_limit_microunits <= max_active_cost_microunits",
            name="ck_organization_execution_budgets_run_limits_fit",
        ),
        sa.CheckConstraint(
            "run_token_limit > 0 AND run_time_limit_milliseconds > 0 AND run_cost_limit_microunits > 0 AND cost_microunits_per_million_tokens > 0",
            name="ck_organization_execution_budgets_run_limits_positive",
        ),
        sa.CheckConstraint(
            "state_revision > 0",
            name="ck_organization_execution_budgets_revision_positive",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organization_organizations.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "id",
            "organization_id",
            name="uq_organization_execution_budgets_id_organization_id",
        ),
        sa.UniqueConstraint(
            "organization_id", name="uq_organization_execution_budgets_organization_id"
        ),
    )
    op.create_index(
        op.f("ix_organization_execution_budgets_created_at"),
        "organization_execution_budgets",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_organization_execution_budgets_organization_id"),
        "organization_execution_budgets",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "ix_unq_organization_execution_budgets_ext_id_org_id",
        "organization_execution_budgets",
        ["external_id", "organization_id"],
        unique=True,
    )
    _create_table(
        "outbound_attempts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("owner_kind", sa.String(length=64), nullable=False),
        sa.Column("owner_id", sa.UUID(), nullable=False),
        sa.Column("operation_key", sa.String(length=192), nullable=False),
        sa.Column("provider_operation", sa.String(length=192), nullable=False),
        sa.Column("transport_kind", sa.String(length=32), nullable=False),
        sa.Column("destination_origin", sa.String(length=512), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("provider_idempotency_key", sa.String(length=64), nullable=False),
        sa.Column(
            "state",
            postgresql.ENUM(
                "prepared",
                "in_flight",
                "succeeded",
                "retryable",
                "terminal",
                "unknown",
                "cancelled",
                name="outbound_attempt_state_enum",
            ),
            server_default="prepared",
            nullable=False,
        ),
        sa.Column(
            "send_count", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column("provider_reference", sa.String(length=320), nullable=True),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("failure_code", sa.String(length=128), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("outcome_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reconciled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(state = 'prepared' AND send_count = 0 AND outcome_at IS NULL AND failure_code IS NULL) OR (state = 'in_flight' AND send_count > 0 AND outcome_at IS NULL AND failure_code IS NULL) OR (state = 'succeeded' AND send_count > 0 AND outcome_at IS NOT NULL AND failure_code IS NULL) OR (state = 'retryable' AND send_count > 0 AND outcome_at IS NOT NULL AND failure_code IS NOT NULL) OR (state = 'terminal' AND outcome_at IS NOT NULL AND failure_code IS NOT NULL) OR (state = 'unknown' AND send_count > 0 AND outcome_at IS NOT NULL AND failure_code IS NOT NULL) OR (state = 'cancelled' AND cancel_requested_at IS NOT NULL AND outcome_at IS NOT NULL)",
            name="ck_outbound_attempts_lifecycle",
        ),
        sa.CheckConstraint(
            "failure_code IS NULL OR failure_code ~ '^[a-z][a-z0-9_.-]*$'",
            name="ck_outbound_attempts_failure_code",
        ),
        sa.CheckConstraint(
            "operation_key ~ '^[a-z][a-z0-9_.-]*$'",
            name="ck_outbound_attempts_operation_key",
        ),
        sa.CheckConstraint(
            "owner_kind ~ '^[a-z][a-z0-9_.-]*$'", name="ck_outbound_attempts_owner_kind"
        ),
        sa.CheckConstraint(
            "provider_operation ~ '^[a-z][a-z0-9_.-]*$'",
            name="ck_outbound_attempts_provider_operation",
        ),
        sa.CheckConstraint(
            "request_fingerprint ~ '^[0-9a-f]{64}$'",
            name="ck_outbound_attempts_request_fingerprint",
        ),
        sa.CheckConstraint(
            "transport_kind ~ '^[a-z][a-z0-9_.-]*$'",
            name="ck_outbound_attempts_transport_kind",
        ),
        sa.CheckConstraint(
            "(send_count = 0 AND started_at IS NULL) OR (send_count > 0 AND started_at IS NOT NULL)",
            name="ck_outbound_attempts_send_start_pair",
        ),
        sa.CheckConstraint(
            "outcome_at IS NULL OR started_at IS NULL OR outcome_at >= started_at",
            name="ck_outbound_attempts_outcome_order",
        ),
        sa.CheckConstraint(
            "reconciled_at IS NULL OR (started_at IS NOT NULL AND outcome_at IS NOT NULL AND reconciled_at >= outcome_at)",
            name="ck_outbound_attempts_reconciliation_order",
        ),
        sa.CheckConstraint(
            "send_count BETWEEN 0 AND 100", name="ck_outbound_attempts_send_count"
        ),
        sa.CheckConstraint(
            "status_code IS NULL OR status_code BETWEEN 100 AND 599",
            name="ck_outbound_attempts_status_code",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organization_organizations.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "id", "organization_id", name="uq_outbound_attempts_id_organization"
        ),
        sa.UniqueConstraint(
            "organization_id",
            "owner_kind",
            "owner_id",
            "operation_key",
            name="uq_outbound_attempts_owner_operation",
        ),
        sa.UniqueConstraint(
            "provider_idempotency_key", name="uq_outbound_attempts_provider_idempotency"
        ),
    )
    op.create_index(
        op.f("ix_outbound_attempts_organization_id"),
        "outbound_attempts",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_outbound_attempts_owner_id"),
        "outbound_attempts",
        ["owner_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_outbound_attempts_state"), "outbound_attempts", ["state"], unique=False
    )
    _create_table(
        "provider_configs",
        sa.Column(
            "capability",
            postgresql.ENUM(
                "llm",
                "stt",
                "tts",
                "realtime",
                "webrtc",
                "telephony",
                "email",
                "storage",
                "memory",
                "embedding",
                "reranking",
                "sandbox",
                name="provider_capability_enum",
            ),
            nullable=False,
        ),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "config",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("encrypted_secrets", sa.Text(), nullable=False),
        sa.Column("revision", sa.Integer(), server_default="1", nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("external_id", sa.String(length=320), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organization_organizations.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "id", "organization_id", name="uq_provider_configs_id_organization_id"
        ),
    )
    op.create_index(
        op.f("ix_provider_configs_created_at"),
        "provider_configs",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_provider_configs_organization_id"),
        "provider_configs",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "ix_unq_provider_configs_ext_id_org_id",
        "provider_configs",
        ["external_id", "organization_id"],
        unique=True,
    )
    op.create_index(
        "uq_provider_configs_org_capability_name_active",
        "provider_configs",
        ["organization_id", "capability", "name"],
        unique=True,
        postgresql_where=sa.text("deleted = false"),
    )
    _create_table(
        "auth_sessions",
        sa.Column("session_token", sa.String(), nullable=False),
        sa.Column("contact_id", sa.UUID(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_active_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("user_agent", sa.String(), nullable=True),
        sa.Column("ip_address", sa.String(), nullable=True),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("external_id", sa.String(length=320), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["contact_id", "organization_id"],
            ["contact_contacts.id", "contact_contacts.organization_id"],
            name="fk_auth_sessions_contact_organization",
        ),
        sa.ForeignKeyConstraint(
            ["contact_id"],
            ["contact_contacts.id"],
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organization_organizations.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "id", "organization_id", name="uq_auth_sessions_id_organization"
        ),
    )
    op.create_index(
        "ix_auth_sessions_contact_id", "auth_sessions", ["contact_id"], unique=False
    )
    op.create_index(
        op.f("ix_auth_sessions_created_at"),
        "auth_sessions",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_auth_sessions_organization_id"),
        "auth_sessions",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_auth_sessions_session_token"),
        "auth_sessions",
        ["session_token"],
        unique=True,
    )
    op.create_index(
        "ix_unq_auth_sessions_ext_id_org_id",
        "auth_sessions",
        ["external_id", "organization_id"],
        unique=True,
    )
    _create_table(
        "connection_connections",
        sa.Column("integration_id", sa.UUID(), nullable=False),
        sa.Column("contact_id", sa.UUID(), nullable=True),
        sa.Column(
            "connection_kind",
            postgresql.ENUM("ORGANIZATION", "CONTACT", name="connection_kind_enum"),
            nullable=False,
        ),
        sa.Column(
            "status",
            postgresql.ENUM(
                "INITIATED",
                "ACTIVE",
                "INACTIVE",
                "FAILED",
                "REVOKED",
                name="connection_status_enum",
            ),
            server_default="INITIATED",
            nullable=False,
        ),
        sa.Column(
            "credentials", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column("credentials_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_refresh_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_refresh_failure_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "refresh_attempts", sa.SmallInteger(), server_default="0", nullable=False
        ),
        sa.Column(
            "is_refresh_exhausted", sa.Boolean(), server_default="false", nullable=False
        ),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("external_id", sa.String(length=320), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(connection_kind = 'CONTACT' AND contact_id IS NOT NULL) OR (connection_kind = 'ORGANIZATION' AND contact_id IS NULL)",
            name="ck_connection_connections_exact_owner",
        ),
        sa.ForeignKeyConstraint(
            ["contact_id", "organization_id"],
            ["contact_contacts.id", "contact_contacts.organization_id"],
            name="fk_connection_connections_contact_organization",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["integration_id", "organization_id"],
            [
                "integration_v2_installations.id",
                "integration_v2_installations.organization_id",
            ],
            name="fk_connection_connections_installation_organization",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organization_organizations.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_connection_connections_contact_id"),
        "connection_connections",
        ["contact_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_connection_connections_created_at"),
        "connection_connections",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_connection_connections_credentials_expires_at"),
        "connection_connections",
        ["credentials_expires_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_connection_connections_integration_id"),
        "connection_connections",
        ["integration_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_connection_connections_last_refresh_failure_at"),
        "connection_connections",
        ["last_refresh_failure_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_connection_connections_last_refresh_success_at"),
        "connection_connections",
        ["last_refresh_success_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_connection_connections_organization_id"),
        "connection_connections",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "ix_unq_connection_connections_ext_id_org_id",
        "connection_connections",
        ["external_id", "organization_id"],
        unique=True,
    )
    _create_table(
        "connection_oauth_states",
        sa.Column(
            "state",
            sa.String(length=64),
            nullable=False,
            comment="Unique state token for OAuth flow",
        ),
        sa.Column(
            "integration_id",
            sa.UUID(),
            nullable=False,
            comment="Curated vendor installation this flow authorizes.",
        ),
        sa.Column(
            "code_verifier",
            sa.String(length=128),
            nullable=True,
            comment="PKCE code verifier held for the token exchange. Null for providers that do not use PKCE. Never leaves the server: only its S256 challenge is sent to the authorization endpoint.",
        ),
        sa.Column(
            "organization_id",
            sa.UUID(),
            nullable=False,
            comment="Organization initiating the OAuth flow",
        ),
        sa.Column(
            "contact_id",
            sa.UUID(),
            nullable=True,
            comment="Optional contact to associate with resulting connection",
        ),
        sa.Column(
            "redirect_uri",
            sa.String(length=512),
            nullable=True,
            comment="Custom redirect URI for this flow",
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="When this state token expires",
        ),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["contact_id", "organization_id"],
            ["contact_contacts.id", "contact_contacts.organization_id"],
            name="fk_connection_oauth_states_contact_organization",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["integration_id", "organization_id"],
            [
                "integration_v2_installations.id",
                "integration_v2_installations.organization_id",
            ],
            name="fk_connection_oauth_states_installation_organization",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organization_organizations.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_connection_oauth_states_created_at"),
        "connection_oauth_states",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_connection_oauth_states_expires_at"),
        "connection_oauth_states",
        ["expires_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_connection_oauth_states_integration_id"),
        "connection_oauth_states",
        ["integration_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_connection_oauth_states_organization_id"),
        "connection_oauth_states",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "ix_oauth_states_expires_at",
        "connection_oauth_states",
        ["expires_at"],
        unique=False,
    )
    op.create_index(
        "ix_oauth_states_state", "connection_oauth_states", ["state"], unique=True
    )
    _create_table(
        "definition_template_revisions",
        sa.Column("template_id", sa.UUID(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "variable_schema",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("renderer_version", sa.String(length=32), nullable=False),
        sa.Column(
            "availability",
            sa.String(length=16),
            server_default="published",
            nullable=False,
        ),
        sa.Column(
            "published_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by", sa.UUID(), nullable=True),
        sa.Column("revocation_reason", sa.Text(), nullable=True),
        sa.Column(
            "cancellation_requested_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("external_id", sa.String(length=320), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(availability = 'published' AND revoked_at IS NULL AND revoked_by IS NULL AND revocation_reason IS NULL AND cancellation_requested_at IS NULL) OR (availability = 'revoked' AND revoked_at IS NOT NULL AND revoked_by IS NOT NULL AND revocation_reason IS NOT NULL AND length(btrim(revocation_reason)) BETWEEN 1 AND 2000 AND cancellation_requested_at IS NOT NULL)",
            name="ck_definition_template_revisions_revocation_metadata",
        ),
        sa.CheckConstraint(
            "availability IN ('published', 'revoked')",
            name="ck_definition_template_revisions_availability",
        ),
        sa.CheckConstraint(
            "revision > 0", name="ck_definition_template_revisions_revision_positive"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organization_organizations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["template_id", "organization_id"],
            ["definition_templates.id", "definition_templates.organization_id"],
            name="fk_definition_template_revisions_template_organization",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "template_id",
            "revision",
            "organization_id",
            name="uq_definition_template_revisions_ref_organization",
        ),
        sa.UniqueConstraint(
            "template_id",
            "revision",
            name="uq_definition_template_revisions_template_revision",
        ),
    )
    op.create_index(
        op.f("ix_definition_template_revisions_created_at"),
        "definition_template_revisions",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_definition_template_revisions_organization_id"),
        "definition_template_revisions",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_definition_template_revisions_template_id"),
        "definition_template_revisions",
        ["template_id"],
        unique=False,
    )
    op.create_index(
        "ix_unq_definition_template_revisions_ext_id_org_id",
        "definition_template_revisions",
        ["external_id", "organization_id"],
        unique=True,
    )
    _create_table(
        "deletion_jobs",
        sa.Column(
            "target_type",
            postgresql.ENUM("call", "contact", name="deletion_target_type_enum"),
            nullable=False,
        ),
        sa.Column("target_id", sa.UUID(), nullable=False),
        sa.Column("requested_by_member_id", sa.UUID(), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "pending",
                "running",
                "succeeded",
                "failed",
                name="deletion_job_status_enum",
            ),
            server_default="pending",
            nullable=False,
        ),
        sa.Column(
            "error_code",
            postgresql.ENUM(
                "call_active",
                "object_delete_failed",
                "erasure_failed",
                "dependency_unavailable",
                "internal_failure",
                name="deletion_error_code_enum",
            ),
            nullable=True,
        ),
        sa.Column("absurd_task_id", sa.UUID(), nullable=True),
        sa.Column(
            "attempts", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("external_id", sa.String(length=320), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(status IN ('pending', 'running') AND finished_at IS NULL) OR (status IN ('succeeded', 'failed') AND finished_at IS NOT NULL)",
            name="ck_deletion_jobs_terminal_time",
        ),
        sa.CheckConstraint(
            "status <> 'failed' OR error_code IS NOT NULL",
            name="ck_deletion_jobs_failure_has_error",
        ),
        sa.CheckConstraint(
            "status <> 'running' OR started_at IS NOT NULL",
            name="ck_deletion_jobs_running_started",
        ),
        sa.CheckConstraint(
            "status <> 'succeeded' OR error_code IS NULL",
            name="ck_deletion_jobs_success_has_no_error",
        ),
        sa.CheckConstraint(
            "status = 'pending' OR absurd_task_id IS NOT NULL",
            name="ck_deletion_jobs_bound_before_execution",
        ),
        sa.CheckConstraint(
            "attempts >= 0 AND max_attempts > 0", name="ck_deletion_jobs_attempts"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organization_organizations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["requested_by_member_id"], ["member_members.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("absurd_task_id"),
        sa.UniqueConstraint(
            "organization_id",
            "target_type",
            "target_id",
            name="uq_deletion_jobs_target",
        ),
    )
    op.create_index(
        op.f("ix_deletion_jobs_created_at"),
        "deletion_jobs",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_deletion_jobs_organization_id"),
        "deletion_jobs",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_deletion_jobs_requested_by_member_id"),
        "deletion_jobs",
        ["requested_by_member_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_deletion_jobs_status"), "deletion_jobs", ["status"], unique=False
    )
    op.create_index(
        op.f("ix_deletion_jobs_target_id"), "deletion_jobs", ["target_id"], unique=False
    )
    op.create_index(
        op.f("ix_deletion_jobs_target_type"),
        "deletion_jobs",
        ["target_type"],
        unique=False,
    )
    op.create_index(
        "ix_unq_deletion_jobs_ext_id_org_id",
        "deletion_jobs",
        ["external_id", "organization_id"],
        unique=True,
    )
    _create_table(
        "event_deliveries",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("event_id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("consumer_name", sa.String(length=192), nullable=False),
        sa.Column("absurd_task_id", sa.UUID(), nullable=True),
        sa.Column(
            "state",
            postgresql.ENUM(
                "pending",
                "running",
                "succeeded",
                "dead_letter",
                name="event_delivery_state_enum",
            ),
            server_default="pending",
            nullable=False,
        ),
        sa.Column(
            "attempts", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column(
            "max_attempts", sa.Integer(), server_default=sa.text("3"), nullable=False
        ),
        sa.Column("last_error", sa.String(length=2000), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(state = 'pending' AND attempts = 0 AND started_at IS NULL AND finished_at IS NULL AND last_error IS NULL) OR (state = 'running' AND absurd_task_id IS NOT NULL AND attempts BETWEEN 1 AND max_attempts AND started_at IS NOT NULL AND finished_at IS NULL) OR (state = 'succeeded' AND absurd_task_id IS NOT NULL AND attempts BETWEEN 1 AND max_attempts AND started_at IS NOT NULL AND finished_at IS NOT NULL AND last_error IS NULL) OR (state = 'dead_letter' AND absurd_task_id IS NOT NULL AND attempts BETWEEN 1 AND max_attempts AND started_at IS NOT NULL AND finished_at IS NOT NULL AND last_error IS NOT NULL AND length(btrim(last_error)) BETWEEN 1 AND 2000)",
            name="ck_event_deliveries_lifecycle",
        ),
        sa.CheckConstraint(
            "consumer_name ~ '^[a-z][a-z0-9_.-]*$'",
            name="ck_event_deliveries_consumer_name",
        ),
        sa.CheckConstraint(
            "finished_at IS NULL OR (started_at IS NOT NULL AND finished_at >= started_at)",
            name="ck_event_deliveries_time_order",
        ),
        sa.CheckConstraint(
            "max_attempts BETWEEN 1 AND 100 AND attempts BETWEEN 0 AND max_attempts",
            name="ck_event_deliveries_attempts",
        ),
        sa.ForeignKeyConstraint(
            ["event_id", "organization_id"],
            ["event_outbox.id", "event_outbox.organization_id"],
            name="fk_event_deliveries_event",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "absurd_task_id", name="uq_event_deliveries_absurd_task_id"
        ),
        sa.UniqueConstraint(
            "event_id", "consumer_name", name="uq_event_deliveries_event_consumer"
        ),
        sa.UniqueConstraint(
            "id",
            "event_id",
            "organization_id",
            "consumer_name",
            name="uq_event_deliveries_exact_authority",
        ),
    )
    op.create_index(
        op.f("ix_event_deliveries_event_id"),
        "event_deliveries",
        ["event_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_event_deliveries_organization_id"),
        "event_deliveries",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_event_deliveries_state"), "event_deliveries", ["state"], unique=False
    )
    _create_table(
        "integration_v2_tools",
        sa.Column("installation_id", sa.UUID(), nullable=False),
        sa.Column("wire_id", sa.String(length=512), nullable=False),
        sa.Column(
            "execution_mode",
            sa.String(length=32),
            server_default="auto",
            nullable=False,
        ),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("external_id", sa.String(length=320), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "execution_mode IN ('auto', 'requires_approval', 'disabled')",
            name="ck_integration_v2_tools_execution_mode",
        ),
        sa.ForeignKeyConstraint(
            ["installation_id", "organization_id"],
            [
                "integration_v2_installations.id",
                "integration_v2_installations.organization_id",
            ],
            name="fk_integration_v2_tools_installation_organization",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organization_organizations.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "id", "organization_id", name="uq_integration_v2_tools_id_organization_id"
        ),
    )
    op.create_index(
        op.f("ix_integration_v2_tools_created_at"),
        "integration_v2_tools",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_integration_v2_tools_installation_id"),
        "integration_v2_tools",
        ["installation_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_integration_v2_tools_organization_id"),
        "integration_v2_tools",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "ix_unq_integration_v2_tools_ext_id_org_id",
        "integration_v2_tools",
        ["external_id", "organization_id"],
        unique=True,
    )
    op.create_index(
        "uq_integration_v2_tools_org_wire_active",
        "integration_v2_tools",
        ["organization_id", "wire_id"],
        unique=True,
        postgresql_where="deleted = false",
    )
    _create_table(
        "mcp_server_definition_revisions",
        sa.Column("server_id", sa.UUID(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("slug", sa.String(length=128), nullable=False),
        sa.Column("config", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "availability",
            sa.String(length=16),
            server_default="published",
            nullable=False,
        ),
        sa.Column(
            "published_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("published_by", sa.UUID(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by", sa.UUID(), nullable=True),
        sa.Column("revocation_reason", sa.String(length=2000), nullable=True),
        sa.Column(
            "cancellation_requested_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("external_id", sa.String(length=320), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(availability = 'published' AND revoked_at IS NULL AND revoked_by IS NULL AND revocation_reason IS NULL AND cancellation_requested_at IS NULL) OR (availability = 'revoked' AND revoked_at IS NOT NULL AND revoked_by IS NOT NULL AND revocation_reason IS NOT NULL AND length(btrim(revocation_reason)) BETWEEN 1 AND 2000 AND cancellation_requested_at IS NOT NULL)",
            name="ck_mcp_server_definition_revisions_revocation_metadata",
        ),
        sa.CheckConstraint(
            "availability IN ('published', 'revoked')",
            name="ck_mcp_server_definition_revisions_availability",
        ),
        sa.CheckConstraint(
            "revision > 0", name="ck_mcp_server_definition_revisions_revision_positive"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organization_organizations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["server_id", "organization_id"],
            ["mcp_servers.id", "mcp_servers.organization_id"],
            name="fk_mcp_server_definition_revisions_header_organization",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "server_id",
            "revision",
            "organization_id",
            name="uq_mcp_server_definition_revisions_ref_organization",
        ),
        sa.UniqueConstraint(
            "server_id", "revision", name="uq_mcp_server_definition_revisions_ref"
        ),
    )
    op.create_index(
        op.f("ix_mcp_server_definition_revisions_created_at"),
        "mcp_server_definition_revisions",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_mcp_server_definition_revisions_organization_id"),
        "mcp_server_definition_revisions",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_mcp_server_definition_revisions_server_id"),
        "mcp_server_definition_revisions",
        ["server_id"],
        unique=False,
    )
    op.create_index(
        "ix_unq_mcp_server_definition_revisions_ext_id_org_id",
        "mcp_server_definition_revisions",
        ["external_id", "organization_id"],
        unique=True,
    )
    _create_table(
        "organization_execution_reservations",
        sa.Column("run_id", sa.UUID(), nullable=True),
        sa.Column("memory_formation_job_id", sa.UUID(), nullable=True),
        sa.Column("memory_reconciliation_job_id", sa.UUID(), nullable=True),
        sa.Column("budget_id", sa.UUID(), nullable=False),
        sa.Column("budget_state_revision", sa.Integer(), nullable=False),
        sa.Column("token_limit", sa.BigInteger(), nullable=False),
        sa.Column("time_limit_milliseconds", sa.BigInteger(), nullable=False),
        sa.Column("cost_limit_microunits", sa.BigInteger(), nullable=False),
        sa.Column(
            "cost_microunits_per_million_tokens", sa.BigInteger(), nullable=False
        ),
        sa.Column(
            "used_tokens", sa.BigInteger(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column(
            "used_cost_microunits",
            sa.BigInteger(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "usage_reported",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "active_milliseconds",
            sa.BigInteger(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "active", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
        sa.Column("active_since", sa.DateTime(timezone=True), nullable=True),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "exceeded_dimension",
            postgresql.ENUM(
                "concurrency",
                "tokens",
                "active_time",
                "cost",
                name="execution_budget_dimension_enum",
            ),
            nullable=True,
        ),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("external_id", sa.String(length=320), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(active IS TRUE AND released_at IS NULL) OR (active IS FALSE AND active_since IS NULL AND released_at IS NOT NULL)",
            name="ck_execution_reservations_active_state",
        ),
        sa.CheckConstraint(
            "budget_state_revision > 0 AND token_limit > 0 AND time_limit_milliseconds > 0 AND cost_limit_microunits > 0 AND cost_microunits_per_million_tokens > 0",
            name="ck_execution_reservations_limits_positive",
        ),
        sa.CheckConstraint(
            "num_nonnulls(run_id, memory_formation_job_id, memory_reconciliation_job_id) = 1",
            name="ck_execution_reservations_one_owner",
        ),
        sa.CheckConstraint(
            "used_tokens >= 0 AND used_cost_microunits >= 0 AND active_milliseconds >= 0",
            name="ck_execution_reservations_usage_nonnegative",
        ),
        sa.ForeignKeyConstraint(
            ["budget_id", "organization_id"],
            [
                "organization_execution_budgets.id",
                "organization_execution_budgets.organization_id",
            ],
            name="fk_execution_reservations_budget",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["memory_formation_job_id", "organization_id"],
            ["memory_formation_jobs.id", "memory_formation_jobs.organization_id"],
            name="fk_execution_reservations_memory_job",
            ondelete="CASCADE",
            use_alter=True,
        ),
        sa.ForeignKeyConstraint(
            ["memory_reconciliation_job_id", "organization_id"],
            [
                "memory_reconciliation_jobs.id",
                "memory_reconciliation_jobs.organization_id",
            ],
            name="fk_execution_reservations_reconciliation_job",
            ondelete="CASCADE",
            use_alter=True,
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organization_organizations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["run_id", "organization_id"],
            ["agent_runs.id", "agent_runs.organization_id"],
            name="fk_execution_reservations_run",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "memory_formation_job_id", name="uq_execution_reservations_memory_job_id"
        ),
        sa.UniqueConstraint(
            "memory_reconciliation_job_id",
            name="uq_execution_reservations_reconciliation_job_id",
        ),
        sa.UniqueConstraint("run_id", name="uq_execution_reservations_run_id"),
    )
    op.create_index(
        op.f("ix_organization_execution_reservations_created_at"),
        "organization_execution_reservations",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_organization_execution_reservations_memory_formation_job_id"),
        "organization_execution_reservations",
        ["memory_formation_job_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_organization_execution_reservations_memory_reconciliation_job_id"),
        "organization_execution_reservations",
        ["memory_reconciliation_job_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_organization_execution_reservations_organization_id"),
        "organization_execution_reservations",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_organization_execution_reservations_run_id"),
        "organization_execution_reservations",
        ["run_id"],
        unique=False,
    )
    op.create_index(
        "ix_unq_organization_execution_reservations_ext_id_org_id",
        "organization_execution_reservations",
        ["external_id", "organization_id"],
        unique=True,
    )
    _create_table(
        "platform_tools",
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("slug", sa.String(length=128), nullable=False),
        sa.Column(
            "kind",
            postgresql.ENUM("LOCAL", "SYSTEM", "MCP", "CURATED", name="tool_kind_enum"),
            nullable=False,
        ),
        sa.Column("display_name", sa.String(length=256), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("llm_config", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "executor_config", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column(
            "output_schema", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column(
            "execution_mode",
            sa.String(length=32),
            server_default="auto",
            nullable=False,
        ),
        sa.Column("wire_id", sa.String(length=512), nullable=True),
        sa.Column("mcp_server_id", sa.UUID(), nullable=True),
        sa.Column(
            "lifecycle", sa.String(length=16), server_default="draft", nullable=False
        ),
        sa.Column("published_revision", sa.Integer(), nullable=True),
        sa.Column(
            "draft_version", sa.Integer(), server_default=sa.text("1"), nullable=False
        ),
        sa.Column(
            "draft_dirty", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("external_id", sa.String(length=320), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(kind = 'MCP' AND mcp_server_id IS NOT NULL AND wire_id IS NOT NULL) OR (kind <> 'MCP' AND mcp_server_id IS NULL AND wire_id IS NULL)",
            name="ck_platform_tools_exact_mcp_owner",
        ),
        sa.CheckConstraint(
            "(lifecycle = 'draft' AND published_revision IS NULL AND draft_dirty = true) OR (lifecycle <> 'draft' AND published_revision IS NOT NULL)",
            name="ck_platform_tools_lifecycle_revision",
        ),
        sa.CheckConstraint(
            "execution_mode IN ('auto', 'requires_approval', 'disabled')",
            name="ck_platform_tools_execution_mode",
        ),
        sa.CheckConstraint(
            "kind IN ('LOCAL', 'SYSTEM', 'MCP')",
            name="ck_platform_tools_persisted_kind",
        ),
        sa.CheckConstraint(
            "lifecycle IN ('draft', 'published', 'withdrawn', 'archived')",
            name="ck_platform_tools_lifecycle",
        ),
        sa.CheckConstraint(
            "draft_version > 0", name="ck_platform_tools_draft_version_positive"
        ),
        sa.CheckConstraint(
            "published_revision IS NULL OR published_revision > 0",
            name="ck_platform_tools_published_revision_positive",
        ),
        sa.ForeignKeyConstraint(
            ["id", "published_revision", "organization_id"],
            [
                "tool_definition_revisions.tool_id",
                "tool_definition_revisions.revision",
                "tool_definition_revisions.organization_id",
            ],
            name="fk_platform_tools_published_definition_revision",
            ondelete="RESTRICT",
            use_alter=True,
        ),
        sa.ForeignKeyConstraint(
            ["mcp_server_id"], ["mcp_servers.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organization_organizations.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "id", "organization_id", name="uq_platform_tools_id_organization_id"
        ),
    )
    op.create_index(
        op.f("ix_platform_tools_created_at"),
        "platform_tools",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_platform_tools_mcp_server_id"),
        "platform_tools",
        ["mcp_server_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_platform_tools_organization_id"),
        "platform_tools",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "ix_unq_platform_tools_ext_id_org_id",
        "platform_tools",
        ["external_id", "organization_id"],
        unique=True,
    )
    op.create_index(
        "uq_platform_tools_mcp_wire_active",
        "platform_tools",
        ["mcp_server_id", "wire_id"],
        unique=True,
        postgresql_where=sa.text(
            "mcp_server_id IS NOT NULL AND wire_id IS NOT NULL AND deleted = false"
        ),
    )
    op.create_index(
        "uq_platform_tools_org_slug_unbound_active",
        "platform_tools",
        ["organization_id", "slug"],
        unique=True,
        postgresql_where=sa.text("mcp_server_id IS NULL AND deleted = false"),
    )
    _create_table(
        "provider_config_revisions",
        sa.Column("provider_config_id", sa.UUID(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column(
            "config",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("encrypted_secrets", sa.Text(), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "verification_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("external_id", sa.String(length=320), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organization_organizations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["provider_config_id", "organization_id"],
            ["provider_configs.id", "provider_configs.organization_id"],
            name="fk_provider_config_revisions_config_organization",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider_config_id",
            "revision",
            "organization_id",
            name="uq_provider_config_revisions_config_revision_organization",
        ),
        sa.UniqueConstraint(
            "provider_config_id",
            "revision",
            name="uq_provider_config_revisions_config_revision",
        ),
    )
    op.create_index(
        op.f("ix_provider_config_revisions_created_at"),
        "provider_config_revisions",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_provider_config_revisions_organization_id"),
        "provider_config_revisions",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_provider_config_revisions_provider_config_id"),
        "provider_config_revisions",
        ["provider_config_id"],
        unique=False,
    )
    op.create_index(
        "ix_unq_provider_config_revisions_ext_id_org_id",
        "provider_config_revisions",
        ["external_id", "organization_id"],
        unique=True,
    )
    _create_table(
        "agent_agents",
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("slug", sa.String(length=128), nullable=False),
        sa.Column("llm_provider_config_id", sa.UUID(), nullable=True),
        sa.Column("llm_provider_config_revision", sa.Integer(), nullable=True),
        sa.Column("email_provider_config_id", sa.UUID(), nullable=True),
        sa.Column("email_provider_config_revision", sa.Integer(), nullable=True),
        sa.Column("webrtc_provider_config_id", sa.UUID(), nullable=True),
        sa.Column("webrtc_provider_config_revision", sa.Integer(), nullable=True),
        sa.Column("voice_config_id", sa.UUID(), nullable=True),
        sa.Column("voice_config_revision", sa.Integer(), nullable=True),
        sa.Column(
            "llm_overrides",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("reranking_provider_config_id", sa.UUID(), nullable=True),
        sa.Column("reranking_provider_config_revision", sa.Integer(), nullable=True),
        sa.Column("memory_provider_config_id", sa.UUID(), nullable=True),
        sa.Column("memory_provider_config_revision", sa.Integer(), nullable=True),
        sa.Column(
            "allow_file_uploads",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("file_upload_embedding_provider_config_id", sa.UUID(), nullable=True),
        sa.Column(
            "file_upload_embedding_provider_config_revision",
            sa.Integer(),
            nullable=True,
        ),
        sa.Column("instruction_template_id", sa.UUID(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("webhook", sa.Text(), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(
                "DRAFT", "ACTIVE", "INACTIVE", "ARCHIVED", name="agent_status_enum"
            ),
            server_default="DRAFT",
            nullable=False,
        ),
        sa.Column(
            "kind",
            postgresql.ENUM("CONVERSATIONAL", "BACKGROUND", name="agent_kind_enum"),
            server_default="CONVERSATIONAL",
            nullable=False,
        ),
        sa.Column("implementation", sa.Text(), nullable=True),
        sa.Column("prompt", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "lifecycle", sa.String(length=16), server_default="draft", nullable=False
        ),
        sa.Column("published_revision", sa.Integer(), nullable=True),
        sa.Column(
            "draft_version", sa.Integer(), server_default=sa.text("1"), nullable=False
        ),
        sa.Column(
            "draft_dirty", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("external_id", sa.String(length=320), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(lifecycle = 'draft' AND published_revision IS NULL AND draft_dirty = true) OR (lifecycle <> 'draft' AND published_revision IS NOT NULL)",
            name="ck_agent_agents_lifecycle_revision",
        ),
        sa.CheckConstraint(
            "lifecycle IN ('draft', 'published', 'withdrawn', 'archived')",
            name="ck_agent_agents_lifecycle",
        ),
        sa.CheckConstraint(
            "(allow_file_uploads = false AND file_upload_embedding_provider_config_id IS NULL AND file_upload_embedding_provider_config_revision IS NULL) OR (allow_file_uploads = true AND file_upload_embedding_provider_config_id IS NOT NULL AND (file_upload_embedding_provider_config_revision IS NULL OR file_upload_embedding_provider_config_revision > 0))",
            name="ck_agent_agents_file_upload_configuration",
        ),
        sa.CheckConstraint(
            "draft_version > 0", name="ck_agent_agents_draft_version_positive"
        ),
        sa.CheckConstraint(
            "email_provider_config_revision IS NULL OR email_provider_config_id IS NOT NULL",
            name="ck_agent_agents_email_revision_has_config",
        ),
        sa.CheckConstraint(
            "email_provider_config_revision IS NULL OR email_provider_config_revision > 0",
            name="ck_agent_agents_email_revision_positive",
        ),
        sa.CheckConstraint(
            "llm_provider_config_revision IS NULL OR llm_provider_config_id IS NOT NULL",
            name="ck_agent_agents_llm_revision_has_config",
        ),
        sa.CheckConstraint(
            "llm_provider_config_revision IS NULL OR llm_provider_config_revision > 0",
            name="ck_agent_agents_llm_revision_positive",
        ),
        sa.CheckConstraint(
            "memory_provider_config_revision IS NULL OR memory_provider_config_id IS NOT NULL",
            name="ck_agent_agents_memory_revision_has_config",
        ),
        sa.CheckConstraint(
            "memory_provider_config_revision IS NULL OR memory_provider_config_revision > 0",
            name="ck_agent_agents_memory_revision_positive",
        ),
        sa.CheckConstraint(
            "published_revision IS NULL OR published_revision > 0",
            name="ck_agent_agents_published_revision_positive",
        ),
        sa.CheckConstraint(
            "reranking_provider_config_revision IS NULL OR reranking_provider_config_id IS NOT NULL",
            name="ck_agent_agents_reranking_revision_has_config",
        ),
        sa.CheckConstraint(
            "reranking_provider_config_revision IS NULL OR reranking_provider_config_revision > 0",
            name="ck_agent_agents_reranking_revision_positive",
        ),
        sa.CheckConstraint(
            "webrtc_provider_config_revision IS NULL OR webrtc_provider_config_id IS NOT NULL",
            name="ck_agent_agents_webrtc_revision_has_config",
        ),
        sa.CheckConstraint(
            "webrtc_provider_config_revision IS NULL OR webrtc_provider_config_revision > 0",
            name="ck_agent_agents_webrtc_revision_positive",
        ),
        sa.CheckConstraint(
            "(voice_config_id IS NULL AND voice_config_revision IS NULL) OR (voice_config_id IS NOT NULL AND voice_config_revision > 0)",
            name="ck_agent_agents_voice_config_ref",
        ),
        sa.CheckConstraint(
            "kind <> 'BACKGROUND' OR (voice_config_id IS NULL AND voice_config_revision IS NULL)",
            name="ck_agent_agents_background_without_voice_config",
        ),
        sa.ForeignKeyConstraint(
            ["email_provider_config_id", "email_provider_config_revision"],
            [
                "provider_config_revisions.provider_config_id",
                "provider_config_revisions.revision",
            ],
            name="fk_agent_agents_email_config_revision",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["email_provider_config_id", "organization_id"],
            ["provider_configs.id", "provider_configs.organization_id"],
            name="fk_agent_agents_email_config_organization",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            [
                "file_upload_embedding_provider_config_id",
                "file_upload_embedding_provider_config_revision",
            ],
            [
                "provider_config_revisions.provider_config_id",
                "provider_config_revisions.revision",
            ],
            name="fk_agent_agents_file_upload_embedding_config_revision",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["file_upload_embedding_provider_config_id", "organization_id"],
            ["provider_configs.id", "provider_configs.organization_id"],
            name="fk_agent_agents_file_upload_embedding_config_organization",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["id", "published_revision", "organization_id"],
            [
                "agent_definition_revisions.agent_id",
                "agent_definition_revisions.revision",
                "agent_definition_revisions.organization_id",
            ],
            name="fk_agent_agents_published_definition_revision",
            ondelete="RESTRICT",
            use_alter=True,
        ),
        sa.ForeignKeyConstraint(
            ["instruction_template_id", "organization_id"],
            ["definition_templates.id", "definition_templates.organization_id"],
            name="fk_agent_agents_instruction_template_organization",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["llm_provider_config_id", "llm_provider_config_revision"],
            [
                "provider_config_revisions.provider_config_id",
                "provider_config_revisions.revision",
            ],
            name="fk_agent_agents_llm_config_revision",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["llm_provider_config_id", "organization_id"],
            ["provider_configs.id", "provider_configs.organization_id"],
            name="fk_agent_agents_llm_config_organization",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["memory_provider_config_id", "memory_provider_config_revision"],
            [
                "provider_config_revisions.provider_config_id",
                "provider_config_revisions.revision",
            ],
            name="fk_agent_agents_memory_config_revision",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["memory_provider_config_id", "organization_id"],
            ["provider_configs.id", "provider_configs.organization_id"],
            name="fk_agent_agents_memory_config_organization",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organization_organizations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["reranking_provider_config_id", "organization_id"],
            ["provider_configs.id", "provider_configs.organization_id"],
            name="fk_agent_agents_reranking_config_organization",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["reranking_provider_config_id", "reranking_provider_config_revision"],
            [
                "provider_config_revisions.provider_config_id",
                "provider_config_revisions.revision",
            ],
            name="fk_agent_agents_reranking_config_revision",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["webrtc_provider_config_id", "organization_id"],
            ["provider_configs.id", "provider_configs.organization_id"],
            name="fk_agent_agents_webrtc_config_organization",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["webrtc_provider_config_id", "webrtc_provider_config_revision"],
            [
                "provider_config_revisions.provider_config_id",
                "provider_config_revisions.revision",
            ],
            name="fk_agent_agents_webrtc_config_revision",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["voice_config_id", "organization_id"],
            ["voice_configs.id", "voice_configs.organization_id"],
            name="fk_agent_agents_voice_config_organization",
            ondelete="RESTRICT",
            use_alter=True,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "id", "organization_id", name="uq_agent_agents_id_organization_id"
        ),
    )
    op.create_index(
        op.f("ix_agent_agents_created_at"), "agent_agents", ["created_at"], unique=False
    )
    op.create_index(
        op.f("ix_agent_agents_email_provider_config_id"),
        "agent_agents",
        ["email_provider_config_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_agent_agents_file_upload_embedding_provider_config_id"),
        "agent_agents",
        ["file_upload_embedding_provider_config_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_agent_agents_instruction_template_id"),
        "agent_agents",
        ["instruction_template_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_agent_agents_llm_provider_config_id"),
        "agent_agents",
        ["llm_provider_config_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_agent_agents_memory_provider_config_id"),
        "agent_agents",
        ["memory_provider_config_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_agent_agents_organization_id"),
        "agent_agents",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_agent_agents_reranking_provider_config_id"),
        "agent_agents",
        ["reranking_provider_config_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_agent_agents_webrtc_provider_config_id"),
        "agent_agents",
        ["webrtc_provider_config_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_agent_agents_voice_config_id"),
        "agent_agents",
        ["voice_config_id"],
        unique=False,
    )
    op.create_index(
        "ix_unq_agent_agents_ext_id_org_id",
        "agent_agents",
        ["external_id", "organization_id"],
        unique=True,
    )
    op.create_index(
        "uq_agent_agents_org_slug_active",
        "agent_agents",
        ["organization_id", "slug"],
        unique=True,
        postgresql_where=sa.text("deleted = false"),
    )
    _create_table(
        "event_inbox_receipts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("delivery_id", sa.UUID(), nullable=False),
        sa.Column("event_id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("consumer_name", sa.String(length=192), nullable=False),
        sa.Column(
            "processed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["delivery_id", "event_id", "organization_id", "consumer_name"],
            [
                "event_deliveries.id",
                "event_deliveries.event_id",
                "event_deliveries.organization_id",
                "event_deliveries.consumer_name",
            ],
            name="fk_event_inbox_receipts_exact_delivery",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("delivery_id", name="uq_event_inbox_receipts_delivery_id"),
        sa.UniqueConstraint(
            "event_id", "consumer_name", name="uq_event_inbox_receipts_event_consumer"
        ),
    )
    op.create_index(
        op.f("ix_event_inbox_receipts_event_id"),
        "event_inbox_receipts",
        ["event_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_event_inbox_receipts_organization_id"),
        "event_inbox_receipts",
        ["organization_id"],
        unique=False,
    )
    _create_table(
        "knowledgebases",
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("slug", sa.String(length=128), nullable=False),
        sa.Column("vendor", sa.String(length=64), nullable=False),
        sa.Column(
            "scope",
            postgresql.ENUM(
                "organization", "agent", "conversation", name="knowledge_scope_enum"
            ),
            nullable=False,
        ),
        sa.Column("scope_id", sa.String(length=64), nullable=False),
        sa.Column(
            "writable", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column("meta", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("embedding_provider_config_id", sa.UUID(), nullable=True),
        sa.Column("embedding_provider_config_revision", sa.Integer(), nullable=True),
        sa.Column("embedding_provider", sa.String(length=64), nullable=True),
        sa.Column("embedding_endpoint", sa.Text(), nullable=True),
        sa.Column("embedding_model", sa.String(length=255), nullable=True),
        sa.Column("embedding_dimensions", sa.Integer(), nullable=True),
        sa.Column(
            "embedding_semantic_options",
            postgresql.JSONB(none_as_null=True, astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("embedding_space_id", sa.String(length=64), nullable=True),
        sa.Column(
            "reindex_state",
            postgresql.ENUM(
                "active",
                "reindex_required",
                "reindexing",
                "failed",
                name="knowledge_reindex_state_enum",
            ),
            server_default="active",
            nullable=False,
        ),
        sa.Column("target_embedding_provider_config_id", sa.UUID(), nullable=True),
        sa.Column(
            "target_embedding_provider_config_revision", sa.Integer(), nullable=True
        ),
        sa.Column("target_embedding_provider", sa.String(length=64), nullable=True),
        sa.Column("target_embedding_endpoint", sa.Text(), nullable=True),
        sa.Column("target_embedding_model", sa.String(length=255), nullable=True),
        sa.Column("target_embedding_dimensions", sa.Integer(), nullable=True),
        sa.Column(
            "target_embedding_semantic_options",
            postgresql.JSONB(none_as_null=True, astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("target_embedding_space_id", sa.String(length=64), nullable=True),
        sa.Column("reindex_last_error", sa.Text(), nullable=True),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("external_id", sa.String(length=320), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(reindex_state = 'active' AND target_embedding_provider_config_id IS NULL AND target_embedding_provider_config_revision IS NULL AND target_embedding_provider IS NULL AND target_embedding_endpoint IS NULL AND target_embedding_model IS NULL AND target_embedding_dimensions IS NULL AND target_embedding_semantic_options IS NULL AND target_embedding_space_id IS NULL AND reindex_last_error IS NULL) OR (vendor = 'pgvector' AND reindex_state <> 'active' AND target_embedding_provider_config_id IS NOT NULL AND target_embedding_provider_config_revision IS NOT NULL AND target_embedding_provider IS NOT NULL AND target_embedding_endpoint IS NOT NULL AND target_embedding_model IS NOT NULL AND target_embedding_dimensions IS NOT NULL AND target_embedding_semantic_options IS NOT NULL AND target_embedding_space_id IS NOT NULL AND target_embedding_space_id <> embedding_space_id AND ((reindex_state = 'failed' AND reindex_last_error IS NOT NULL) OR (reindex_state <> 'failed' AND reindex_last_error IS NULL)))",
            name="ck_knowledgebases_reindex_state",
        ),
        sa.CheckConstraint(
            "(vendor = 'pgvector' AND embedding_provider_config_id IS NOT NULL AND embedding_provider_config_revision IS NOT NULL AND embedding_provider IS NOT NULL AND embedding_endpoint IS NOT NULL AND embedding_model IS NOT NULL AND embedding_dimensions IS NOT NULL AND embedding_semantic_options IS NOT NULL AND embedding_space_id IS NOT NULL) OR (vendor <> 'pgvector' AND embedding_provider_config_id IS NULL AND embedding_provider_config_revision IS NULL AND embedding_provider IS NULL AND embedding_endpoint IS NULL AND embedding_model IS NULL AND embedding_dimensions IS NULL AND embedding_semantic_options IS NULL AND embedding_space_id IS NULL)",
            name="ck_knowledgebases_embedding_space",
        ),
        sa.ForeignKeyConstraint(
            ["embedding_provider_config_id", "embedding_provider_config_revision"],
            [
                "provider_config_revisions.provider_config_id",
                "provider_config_revisions.revision",
            ],
            name="fk_knowledgebases_embedding_config_revision",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["embedding_provider_config_id", "organization_id"],
            ["provider_configs.id", "provider_configs.organization_id"],
            name="fk_knowledgebases_embedding_config_organization",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organization_organizations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["target_embedding_provider_config_id", "organization_id"],
            ["provider_configs.id", "provider_configs.organization_id"],
            name="fk_knowledgebases_target_embedding_config_organization",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            [
                "target_embedding_provider_config_id",
                "target_embedding_provider_config_revision",
            ],
            [
                "provider_config_revisions.provider_config_id",
                "provider_config_revisions.revision",
            ],
            name="fk_knowledgebases_target_embedding_config_revision",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "id", "organization_id", name="uq_knowledgebases_id_organization_id"
        ),
    )
    op.create_index(
        op.f("ix_knowledgebases_created_at"),
        "knowledgebases",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_knowledgebases_embedding_provider_config_id"),
        "knowledgebases",
        ["embedding_provider_config_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_knowledgebases_embedding_space_id"),
        "knowledgebases",
        ["embedding_space_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_knowledgebases_organization_id"),
        "knowledgebases",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_knowledgebases_scope_id"), "knowledgebases", ["scope_id"], unique=False
    )
    op.create_index(
        op.f("ix_knowledgebases_target_embedding_provider_config_id"),
        "knowledgebases",
        ["target_embedding_provider_config_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_knowledgebases_target_embedding_space_id"),
        "knowledgebases",
        ["target_embedding_space_id"],
        unique=False,
    )
    op.create_index(
        "ix_unq_knowledgebases_ext_id_org_id",
        "knowledgebases",
        ["external_id", "organization_id"],
        unique=True,
    )
    op.create_index(
        "uq_knowledgebases_conversation_scope_active",
        "knowledgebases",
        ["organization_id", "scope_id"],
        unique=True,
        postgresql_where=sa.text("scope = 'conversation' AND deleted = false"),
    )
    _create_table(
        "memory_formation_jobs",
        sa.Column("conversation_id", sa.UUID(), nullable=False),
        sa.Column("generation", sa.Integer(), nullable=False),
        sa.Column("range_start_created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("range_start_message_id", sa.UUID(), nullable=True),
        sa.Column(
            "range_through_created_at", sa.DateTime(timezone=True), nullable=False
        ),
        sa.Column("range_through_message_id", sa.UUID(), nullable=False),
        sa.Column(
            "message_count", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column("memory_provider_config_id", sa.UUID(), nullable=False),
        sa.Column("memory_provider_config_revision", sa.Integer(), nullable=False),
        sa.Column("embedding_provider_config_id", sa.UUID(), nullable=False),
        sa.Column("embedding_provider_config_revision", sa.Integer(), nullable=False),
        sa.Column("embedding_provider", sa.String(length=64), nullable=False),
        sa.Column("embedding_endpoint", sa.Text(), nullable=False),
        sa.Column("embedding_model", sa.String(length=255), nullable=False),
        sa.Column("embedding_dimensions", sa.Integer(), nullable=False),
        sa.Column(
            "embedding_semantic_options",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("embedding_space_id", sa.String(length=64), nullable=False),
        sa.Column("extraction_llm_provider_config_id", sa.UUID(), nullable=False),
        sa.Column(
            "extraction_llm_provider_config_revision", sa.Integer(), nullable=False
        ),
        sa.Column("extraction_llm_provider", sa.String(length=64), nullable=False),
        sa.Column("extraction_llm_model", sa.String(length=255), nullable=False),
        sa.Column("extraction_prompt_revision", sa.String(length=64), nullable=False),
        sa.Column(
            "considered_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "added_count", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column(
            "updated_count", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column(
            "deleted_count", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column(
            "noop_count", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column(
            "failed_count", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("external_id", sa.String(length=320), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "state",
            postgresql.ENUM(
                "pending",
                "running",
                "succeeded",
                "failed",
                "cancelled",
                name="memory_formation_state_enum",
            ),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("absurd_task_id", sa.UUID(), nullable=True),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "(range_start_created_at IS NULL AND range_start_message_id IS NULL) OR (range_start_created_at IS NOT NULL AND range_start_message_id IS NOT NULL)",
            name="ck_memory_jobs_range_start_pair",
        ),
        sa.CheckConstraint(
            "considered_count = added_count + updated_count + deleted_count + noop_count + failed_count",
            name="ck_memory_jobs_outcome_partition",
        ),
        sa.CheckConstraint(
            "considered_count >= 0 AND added_count >= 0 AND updated_count >= 0 AND deleted_count >= 0 AND noop_count >= 0 AND failed_count >= 0",
            name="ck_memory_jobs_outcome_counts_nonnegative",
        ),
        sa.CheckConstraint(
            "generation > 0 AND message_count BETWEEN 1 AND 20",
            name="ck_memory_jobs_generation_count",
        ),
        sa.CheckConstraint(
            "range_start_created_at IS NULL OR ROW(range_through_created_at, range_through_message_id) > ROW(range_start_created_at, range_start_message_id)",
            name="ck_memory_jobs_range_advances",
        ),
        sa.CheckConstraint(
            "range_through_created_at IS NOT NULL AND range_through_message_id IS NOT NULL",
            name="ck_memory_jobs_range_through_pair",
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id", "organization_id"],
            [
                "conversation_conversations.id",
                "conversation_conversations.organization_id",
            ],
            name="fk_memory_jobs_conversation_organization",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["embedding_provider_config_id", "embedding_provider_config_revision"],
            [
                "provider_config_revisions.provider_config_id",
                "provider_config_revisions.revision",
            ],
            name="fk_memory_jobs_embedding_config_revision",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["embedding_provider_config_id", "organization_id"],
            ["provider_configs.id", "provider_configs.organization_id"],
            name="fk_memory_jobs_embedding_config_organization",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            [
                "extraction_llm_provider_config_id",
                "extraction_llm_provider_config_revision",
            ],
            [
                "provider_config_revisions.provider_config_id",
                "provider_config_revisions.revision",
            ],
            name="fk_memory_jobs_extraction_llm_config_revision",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["extraction_llm_provider_config_id", "organization_id"],
            ["provider_configs.id", "provider_configs.organization_id"],
            name="fk_memory_jobs_extraction_llm_config_organization",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["memory_provider_config_id", "memory_provider_config_revision"],
            [
                "provider_config_revisions.provider_config_id",
                "provider_config_revisions.revision",
            ],
            name="fk_memory_jobs_memory_config_revision",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["memory_provider_config_id", "organization_id"],
            ["provider_configs.id", "provider_configs.organization_id"],
            name="fk_memory_jobs_memory_config_organization",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organization_organizations.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("absurd_task_id"),
        sa.UniqueConstraint(
            "id",
            "organization_id",
            "conversation_id",
            name="uq_memory_formation_jobs_id_owner",
        ),
        sa.UniqueConstraint(
            "id", "organization_id", name="uq_memory_formation_jobs_id_organization"
        ),
        sa.UniqueConstraint(
            "organization_id",
            "conversation_id",
            "generation",
            name="uq_memory_formation_jobs_generation",
        ),
    )
    op.create_index(
        op.f("ix_memory_formation_jobs_conversation_id"),
        "memory_formation_jobs",
        ["conversation_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_memory_formation_jobs_created_at"),
        "memory_formation_jobs",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_memory_formation_jobs_embedding_provider_config_id"),
        "memory_formation_jobs",
        ["embedding_provider_config_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_memory_formation_jobs_embedding_space_id"),
        "memory_formation_jobs",
        ["embedding_space_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_memory_formation_jobs_extraction_llm_provider_config_id"),
        "memory_formation_jobs",
        ["extraction_llm_provider_config_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_memory_formation_jobs_memory_provider_config_id"),
        "memory_formation_jobs",
        ["memory_provider_config_id"],
        unique=False,
    )
    op.create_index(
        "ix_memory_formation_jobs_one_active",
        "memory_formation_jobs",
        ["organization_id", "conversation_id"],
        unique=True,
        postgresql_where=sa.text(
            "state IN ('pending', 'running') AND deleted IS FALSE"
        ),
    )
    op.create_index(
        op.f("ix_memory_formation_jobs_organization_id"),
        "memory_formation_jobs",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_memory_formation_jobs_state"),
        "memory_formation_jobs",
        ["state"],
        unique=False,
    )
    op.create_index(
        "ix_unq_memory_formation_jobs_ext_id_org_id",
        "memory_formation_jobs",
        ["external_id", "organization_id"],
        unique=True,
    )
    _create_table(
        "memory_indexes",
        sa.Column("memory_provider_config_id", sa.UUID(), nullable=False),
        sa.Column("embedding_provider_config_id", sa.UUID(), nullable=False),
        sa.Column("embedding_provider_config_revision", sa.Integer(), nullable=False),
        sa.Column("embedding_provider", sa.String(length=64), nullable=False),
        sa.Column("embedding_endpoint", sa.Text(), nullable=False),
        sa.Column("embedding_model", sa.String(length=255), nullable=False),
        sa.Column("embedding_dimensions", sa.Integer(), nullable=False),
        sa.Column(
            "embedding_semantic_options",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("embedding_space_id", sa.String(length=64), nullable=False),
        sa.Column(
            "reindex_state",
            postgresql.ENUM(
                "active",
                "reindex_required",
                "reindexing",
                "failed",
                name="memory_reindex_state_enum",
            ),
            server_default="active",
            nullable=False,
        ),
        sa.Column("target_embedding_provider_config_id", sa.UUID(), nullable=True),
        sa.Column(
            "target_embedding_provider_config_revision", sa.Integer(), nullable=True
        ),
        sa.Column("target_embedding_provider", sa.String(length=64), nullable=True),
        sa.Column("target_embedding_endpoint", sa.Text(), nullable=True),
        sa.Column("target_embedding_model", sa.String(length=255), nullable=True),
        sa.Column("target_embedding_dimensions", sa.Integer(), nullable=True),
        sa.Column(
            "target_embedding_semantic_options",
            postgresql.JSONB(none_as_null=True, astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("target_embedding_space_id", sa.String(length=64), nullable=True),
        sa.Column("reindex_last_error", sa.Text(), nullable=True),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("external_id", sa.String(length=320), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(reindex_state = 'active' AND target_embedding_provider_config_id IS NULL AND target_embedding_provider_config_revision IS NULL AND target_embedding_provider IS NULL AND target_embedding_endpoint IS NULL AND target_embedding_model IS NULL AND target_embedding_dimensions IS NULL AND target_embedding_semantic_options IS NULL AND target_embedding_space_id IS NULL AND reindex_last_error IS NULL) OR (reindex_state <> 'active' AND target_embedding_provider_config_id IS NOT NULL AND target_embedding_provider_config_revision IS NOT NULL AND target_embedding_provider IS NOT NULL AND target_embedding_endpoint IS NOT NULL AND target_embedding_model IS NOT NULL AND target_embedding_dimensions IS NOT NULL AND target_embedding_semantic_options IS NOT NULL AND target_embedding_space_id IS NOT NULL AND target_embedding_space_id <> embedding_space_id AND ((reindex_state = 'failed' AND reindex_last_error IS NOT NULL) OR (reindex_state <> 'failed' AND reindex_last_error IS NULL)))",
            name="ck_memory_indexes_reindex_state",
        ),
        sa.ForeignKeyConstraint(
            ["embedding_provider_config_id", "embedding_provider_config_revision"],
            [
                "provider_config_revisions.provider_config_id",
                "provider_config_revisions.revision",
            ],
            name="fk_memory_indexes_embedding_config_revision",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["embedding_provider_config_id", "organization_id"],
            ["provider_configs.id", "provider_configs.organization_id"],
            name="fk_memory_indexes_embedding_config_organization",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["memory_provider_config_id", "organization_id"],
            ["provider_configs.id", "provider_configs.organization_id"],
            name="fk_memory_indexes_memory_config_organization",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organization_organizations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["target_embedding_provider_config_id", "organization_id"],
            ["provider_configs.id", "provider_configs.organization_id"],
            name="fk_memory_indexes_target_config_organization",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            [
                "target_embedding_provider_config_id",
                "target_embedding_provider_config_revision",
            ],
            [
                "provider_config_revisions.provider_config_id",
                "provider_config_revisions.revision",
            ],
            name="fk_memory_indexes_target_config_revision",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "id", "organization_id", name="uq_memory_indexes_id_organization_id"
        ),
        sa.UniqueConstraint(
            "memory_provider_config_id",
            "organization_id",
            name="uq_memory_indexes_config_organization",
        ),
    )
    op.create_index(
        op.f("ix_memory_indexes_created_at"),
        "memory_indexes",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_memory_indexes_embedding_provider_config_id"),
        "memory_indexes",
        ["embedding_provider_config_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_memory_indexes_embedding_space_id"),
        "memory_indexes",
        ["embedding_space_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_memory_indexes_memory_provider_config_id"),
        "memory_indexes",
        ["memory_provider_config_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_memory_indexes_organization_id"),
        "memory_indexes",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_memory_indexes_target_embedding_provider_config_id"),
        "memory_indexes",
        ["target_embedding_provider_config_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_memory_indexes_target_embedding_space_id"),
        "memory_indexes",
        ["target_embedding_space_id"],
        unique=False,
    )
    op.create_index(
        "ix_unq_memory_indexes_ext_id_org_id",
        "memory_indexes",
        ["external_id", "organization_id"],
        unique=True,
    )
    _create_table(
        "memory_reindex_jobs",
        sa.Column("memory_provider_config_id", sa.UUID(), nullable=False),
        sa.Column("source_embedding_provider_config_id", sa.UUID(), nullable=False),
        sa.Column(
            "source_embedding_provider_config_revision", sa.Integer(), nullable=False
        ),
        sa.Column("source_embedding_provider", sa.String(length=64), nullable=False),
        sa.Column("source_embedding_endpoint", sa.Text(), nullable=False),
        sa.Column("source_embedding_model", sa.String(length=255), nullable=False),
        sa.Column("source_embedding_dimensions", sa.Integer(), nullable=False),
        sa.Column(
            "source_embedding_semantic_options",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("source_embedding_space_id", sa.String(length=64), nullable=False),
        sa.Column("target_embedding_provider_config_id", sa.UUID(), nullable=False),
        sa.Column(
            "target_embedding_provider_config_revision", sa.Integer(), nullable=False
        ),
        sa.Column("target_embedding_provider", sa.String(length=64), nullable=False),
        sa.Column("target_embedding_endpoint", sa.Text(), nullable=False),
        sa.Column("target_embedding_model", sa.String(length=255), nullable=False),
        sa.Column("target_embedding_dimensions", sa.Integer(), nullable=False),
        sa.Column(
            "target_embedding_semantic_options",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("target_embedding_space_id", sa.String(length=64), nullable=False),
        sa.Column(
            "source_fact_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "indexed_fact_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("external_id", sa.String(length=320), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "state",
            postgresql.ENUM(
                "pending",
                "running",
                "succeeded",
                "failed",
                "cancelled",
                name="memory_reindex_job_state_enum",
            ),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("absurd_task_id", sa.UUID(), nullable=True),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "source_embedding_space_id <> target_embedding_space_id",
            name="ck_memory_reindex_jobs_distinct_spaces",
        ),
        sa.ForeignKeyConstraint(
            ["memory_provider_config_id", "organization_id"],
            ["provider_configs.id", "provider_configs.organization_id"],
            name="fk_memory_reindex_jobs_memory_config_organization",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organization_organizations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["source_embedding_provider_config_id", "organization_id"],
            ["provider_configs.id", "provider_configs.organization_id"],
            name="fk_memory_reindex_jobs_source_config_organization",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            [
                "source_embedding_provider_config_id",
                "source_embedding_provider_config_revision",
            ],
            [
                "provider_config_revisions.provider_config_id",
                "provider_config_revisions.revision",
            ],
            name="fk_memory_reindex_jobs_source_config_revision",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["target_embedding_provider_config_id", "organization_id"],
            ["provider_configs.id", "provider_configs.organization_id"],
            name="fk_memory_reindex_jobs_target_config_organization",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            [
                "target_embedding_provider_config_id",
                "target_embedding_provider_config_revision",
            ],
            [
                "provider_config_revisions.provider_config_id",
                "provider_config_revisions.revision",
            ],
            name="fk_memory_reindex_jobs_target_config_revision",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("absurd_task_id"),
        sa.UniqueConstraint(
            "id", "organization_id", name="uq_memory_reindex_jobs_id_organization_id"
        ),
    )
    op.create_index(
        op.f("ix_memory_reindex_jobs_created_at"),
        "memory_reindex_jobs",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_memory_reindex_jobs_memory_provider_config_id"),
        "memory_reindex_jobs",
        ["memory_provider_config_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_memory_reindex_jobs_organization_id"),
        "memory_reindex_jobs",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_memory_reindex_jobs_source_embedding_provider_config_id"),
        "memory_reindex_jobs",
        ["source_embedding_provider_config_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_memory_reindex_jobs_source_embedding_space_id"),
        "memory_reindex_jobs",
        ["source_embedding_space_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_memory_reindex_jobs_state"),
        "memory_reindex_jobs",
        ["state"],
        unique=False,
    )
    op.create_index(
        op.f("ix_memory_reindex_jobs_target_embedding_provider_config_id"),
        "memory_reindex_jobs",
        ["target_embedding_provider_config_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_memory_reindex_jobs_target_embedding_space_id"),
        "memory_reindex_jobs",
        ["target_embedding_space_id"],
        unique=False,
    )
    op.create_index(
        "ix_unq_memory_reindex_jobs_ext_id_org_id",
        "memory_reindex_jobs",
        ["external_id", "organization_id"],
        unique=True,
    )
    op.create_index(
        "uq_memory_reindex_jobs_active_config",
        "memory_reindex_jobs",
        ["memory_provider_config_id"],
        unique=True,
        postgresql_where=sa.text(
            "state IN ('pending', 'running') AND deleted IS FALSE"
        ),
    )
    _create_table(
        "tool_definition_revisions",
        sa.Column("tool_id", sa.UUID(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("slug", sa.String(length=128), nullable=False),
        sa.Column("kind", sa.String(length=50), nullable=False),
        sa.Column("display_name", sa.String(length=256), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("llm_config", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "executor_config", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column(
            "output_schema", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column(
            "execution_mode",
            sa.String(length=32),
            server_default="auto",
            nullable=False,
        ),
        sa.Column("wire_id", sa.String(length=512), nullable=True),
        sa.Column("mcp_server_id", sa.UUID(), nullable=True),
        sa.Column("mcp_server_revision", sa.Integer(), nullable=True),
        sa.Column(
            "availability",
            sa.String(length=16),
            server_default="published",
            nullable=False,
        ),
        sa.Column(
            "published_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("published_by", sa.UUID(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by", sa.UUID(), nullable=True),
        sa.Column("revocation_reason", sa.Text(), nullable=True),
        sa.Column(
            "cancellation_requested_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("external_id", sa.String(length=320), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(availability = 'published' AND revoked_at IS NULL AND revoked_by IS NULL AND revocation_reason IS NULL AND cancellation_requested_at IS NULL) OR (availability = 'revoked' AND revoked_at IS NOT NULL AND revoked_by IS NOT NULL AND revocation_reason IS NOT NULL AND length(btrim(revocation_reason)) BETWEEN 1 AND 2000 AND cancellation_requested_at IS NOT NULL)",
            name="ck_tool_definition_revisions_revocation_metadata",
        ),
        sa.CheckConstraint(
            "(kind = 'MCP' AND mcp_server_id IS NOT NULL AND mcp_server_revision IS NOT NULL AND wire_id IS NOT NULL) OR (kind <> 'MCP' AND mcp_server_id IS NULL AND mcp_server_revision IS NULL AND wire_id IS NULL)",
            name="ck_tool_definition_revisions_exact_mcp_owner",
        ),
        sa.CheckConstraint(
            "availability IN ('published', 'revoked')",
            name="ck_tool_definition_revisions_availability",
        ),
        sa.CheckConstraint(
            "execution_mode IN ('auto', 'requires_approval', 'disabled')",
            name="ck_tool_definition_revisions_execution_mode",
        ),
        sa.CheckConstraint(
            "revision > 0", name="ck_tool_definition_revisions_revision_positive"
        ),
        sa.ForeignKeyConstraint(
            ["mcp_server_id", "mcp_server_revision", "organization_id"],
            [
                "mcp_server_definition_revisions.server_id",
                "mcp_server_definition_revisions.revision",
                "mcp_server_definition_revisions.organization_id",
            ],
            name="fk_tool_definition_revisions_mcp_server_revision",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organization_organizations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["tool_id", "organization_id"],
            ["platform_tools.id", "platform_tools.organization_id"],
            name="fk_tool_definition_revisions_header_organization",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tool_id",
            "revision",
            "organization_id",
            name="uq_tool_definition_revisions_ref_organization",
        ),
        sa.UniqueConstraint(
            "tool_id", "revision", name="uq_tool_definition_revisions_ref"
        ),
    )
    op.create_index(
        op.f("ix_tool_definition_revisions_created_at"),
        "tool_definition_revisions",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tool_definition_revisions_organization_id"),
        "tool_definition_revisions",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tool_definition_revisions_tool_id"),
        "tool_definition_revisions",
        ["tool_id"],
        unique=False,
    )
    op.create_index(
        "ix_unq_tool_definition_revisions_ext_id_org_id",
        "tool_definition_revisions",
        ["external_id", "organization_id"],
        unique=True,
    )
    _create_table(
        "agent_background_agents",
        sa.Column("agent_id", sa.UUID(), nullable=False),
        sa.Column("background_agent_id", sa.UUID(), nullable=False),
        sa.Column(
            "enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["agent_id"], ["agent_agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["background_agent_id"], ["agent_agents.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("agent_id", "background_agent_id"),
    )
    op.create_index(
        op.f("ix_agent_background_agents_agent_id"),
        "agent_background_agents",
        ["agent_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_agent_background_agents_created_at"),
        "agent_background_agents",
        ["created_at"],
        unique=False,
    )
    _create_table(
        "agent_definition_revisions",
        sa.Column("agent_id", sa.UUID(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("slug", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("webhook", sa.Text(), nullable=True),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("implementation", sa.Text(), nullable=True),
        sa.Column("voice_config_id", sa.UUID(), nullable=True),
        sa.Column("voice_config_revision", sa.Integer(), nullable=True),
        sa.Column("instruction_template_id", sa.UUID(), nullable=True),
        sa.Column("instruction_template_revision", sa.Integer(), nullable=True),
        sa.Column("llm_provider_config_id", sa.UUID(), nullable=False),
        sa.Column("llm_provider_config_revision", sa.Integer(), nullable=False),
        sa.Column("email_provider_config_id", sa.UUID(), nullable=True),
        sa.Column("email_provider_config_revision", sa.Integer(), nullable=True),
        sa.Column("webrtc_provider_config_id", sa.UUID(), nullable=True),
        sa.Column("webrtc_provider_config_revision", sa.Integer(), nullable=True),
        sa.Column("reranking_provider_config_id", sa.UUID(), nullable=True),
        sa.Column("reranking_provider_config_revision", sa.Integer(), nullable=True),
        sa.Column("memory_provider_config_id", sa.UUID(), nullable=True),
        sa.Column("memory_provider_config_revision", sa.Integer(), nullable=True),
        sa.Column(
            "allow_file_uploads",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("file_upload_embedding_provider_config_id", sa.UUID(), nullable=True),
        sa.Column(
            "file_upload_embedding_provider_config_revision",
            sa.Integer(),
            nullable=True,
        ),
        sa.Column("stt_provider_config_id", sa.UUID(), nullable=True),
        sa.Column("stt_provider_config_revision", sa.Integer(), nullable=True),
        sa.Column("tts_provider_config_id", sa.UUID(), nullable=True),
        sa.Column("tts_provider_config_revision", sa.Integer(), nullable=True),
        sa.Column("realtime_provider_config_id", sa.UUID(), nullable=True),
        sa.Column("realtime_provider_config_revision", sa.Integer(), nullable=True),
        sa.Column("storage_provider_config_id", sa.UUID(), nullable=True),
        sa.Column("storage_provider_config_revision", sa.Integer(), nullable=True),
        sa.Column(
            "llm_overrides",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "voice_config",
            postgresql.JSONB(astext_type=sa.Text(), none_as_null=True),
            nullable=True,
        ),
        sa.Column(
            "availability",
            sa.String(length=16),
            server_default="published",
            nullable=False,
        ),
        sa.Column(
            "published_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("published_by", sa.UUID(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by", sa.UUID(), nullable=True),
        sa.Column("revocation_reason", sa.Text(), nullable=True),
        sa.Column(
            "cancellation_requested_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("external_id", sa.String(length=320), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(availability = 'published' AND revoked_at IS NULL AND revoked_by IS NULL AND revocation_reason IS NULL AND cancellation_requested_at IS NULL) OR (availability = 'revoked' AND revoked_at IS NOT NULL AND revoked_by IS NOT NULL AND revocation_reason IS NOT NULL AND length(btrim(revocation_reason)) BETWEEN 1 AND 2000 AND cancellation_requested_at IS NOT NULL)",
            name="ck_agent_definition_revisions_revocation_metadata",
        ),
        sa.CheckConstraint(
            "availability IN ('published', 'revoked')",
            name="ck_agent_definition_revisions_availability",
        ),
        sa.CheckConstraint(
            "(allow_file_uploads = false AND file_upload_embedding_provider_config_id IS NULL AND file_upload_embedding_provider_config_revision IS NULL) OR (allow_file_uploads = true AND file_upload_embedding_provider_config_id IS NOT NULL AND file_upload_embedding_provider_config_revision > 0)",
            name="ck_agent_definition_revisions_file_upload_configuration",
        ),
        sa.CheckConstraint(
            "(email_provider_config_id IS NULL AND email_provider_config_revision IS NULL) OR (email_provider_config_id IS NOT NULL AND email_provider_config_revision > 0)",
            name="ck_agent_definition_revisions_email_provider_ref",
        ),
        sa.CheckConstraint(
            "(instruction_template_id IS NULL AND instruction_template_revision IS NULL) OR (instruction_template_id IS NOT NULL AND instruction_template_revision > 0)",
            name="ck_agent_definition_revisions_template_ref",
        ),
        sa.CheckConstraint(
            "(voice_config_id IS NULL AND voice_config_revision IS NULL AND voice_config IS NULL) OR (voice_config_id IS NOT NULL AND voice_config_revision > 0 AND voice_config IS NOT NULL)",
            name="ck_agent_definition_revisions_voice_config_ref",
        ),
        sa.CheckConstraint(
            "kind <> 'BACKGROUND' OR (voice_config_id IS NULL AND voice_config_revision IS NULL AND voice_config IS NULL)",
            name="ck_agent_definition_revisions_background_without_voice_config",
        ),
        sa.CheckConstraint(
            "(memory_provider_config_id IS NULL AND memory_provider_config_revision IS NULL) OR (memory_provider_config_id IS NOT NULL AND memory_provider_config_revision > 0)",
            name="ck_agent_definition_revisions_memory_provider_ref",
        ),
        sa.CheckConstraint(
            "(reranking_provider_config_id IS NULL AND reranking_provider_config_revision IS NULL) OR (reranking_provider_config_id IS NOT NULL AND reranking_provider_config_revision > 0)",
            name="ck_agent_definition_revisions_reranking_provider_ref",
        ),
        sa.CheckConstraint(
            "(storage_provider_config_id IS NULL AND storage_provider_config_revision IS NULL) OR (storage_provider_config_id IS NOT NULL AND storage_provider_config_revision > 0)",
            name="ck_agent_definition_revisions_storage_provider_ref",
        ),
        sa.CheckConstraint(
            "(stt_provider_config_id IS NULL AND stt_provider_config_revision IS NULL) OR (stt_provider_config_id IS NOT NULL AND stt_provider_config_revision > 0)",
            name="ck_agent_definition_revisions_stt_provider_ref",
        ),
        sa.CheckConstraint(
            "(tts_provider_config_id IS NULL AND tts_provider_config_revision IS NULL) OR (tts_provider_config_id IS NOT NULL AND tts_provider_config_revision > 0)",
            name="ck_agent_definition_revisions_tts_provider_ref",
        ),
        sa.CheckConstraint(
            "(realtime_provider_config_id IS NULL AND realtime_provider_config_revision IS NULL) OR (realtime_provider_config_id IS NOT NULL AND realtime_provider_config_revision > 0)",
            name="ck_agent_definition_revisions_realtime_provider_ref",
        ),
        sa.CheckConstraint(
            "(webrtc_provider_config_id IS NULL AND webrtc_provider_config_revision IS NULL) OR (webrtc_provider_config_id IS NOT NULL AND webrtc_provider_config_revision > 0)",
            name="ck_agent_definition_revisions_webrtc_provider_ref",
        ),
        sa.CheckConstraint(
            "llm_provider_config_revision > 0",
            name="ck_agent_definition_revisions_llm_provider_ref",
        ),
        sa.CheckConstraint(
            "revision > 0", name="ck_agent_definition_revisions_revision_positive"
        ),
        sa.ForeignKeyConstraint(
            ["agent_id", "organization_id"],
            ["agent_agents.id", "agent_agents.organization_id"],
            name="fk_agent_definition_revisions_header_organization",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["voice_config_id", "organization_id"],
            ["voice_configs.id", "voice_configs.organization_id"],
            name="fk_agent_definition_revisions_voice_config_organization",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            [
                "email_provider_config_id",
                "email_provider_config_revision",
                "organization_id",
            ],
            [
                "provider_config_revisions.provider_config_id",
                "provider_config_revisions.revision",
                "provider_config_revisions.organization_id",
            ],
            name="fk_agent_definition_revisions_email_provider_config",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            [
                "file_upload_embedding_provider_config_id",
                "file_upload_embedding_provider_config_revision",
                "organization_id",
            ],
            [
                "provider_config_revisions.provider_config_id",
                "provider_config_revisions.revision",
                "provider_config_revisions.organization_id",
            ],
            name="fk_agent_def_revisions_file_upload_embedding_config",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            [
                "instruction_template_id",
                "instruction_template_revision",
                "organization_id",
            ],
            [
                "definition_template_revisions.template_id",
                "definition_template_revisions.revision",
                "definition_template_revisions.organization_id",
            ],
            name="fk_agent_definition_revisions_instruction_template",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            [
                "llm_provider_config_id",
                "llm_provider_config_revision",
                "organization_id",
            ],
            [
                "provider_config_revisions.provider_config_id",
                "provider_config_revisions.revision",
                "provider_config_revisions.organization_id",
            ],
            name="fk_agent_definition_revisions_llm_provider_config",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            [
                "memory_provider_config_id",
                "memory_provider_config_revision",
                "organization_id",
            ],
            [
                "provider_config_revisions.provider_config_id",
                "provider_config_revisions.revision",
                "provider_config_revisions.organization_id",
            ],
            name="fk_agent_definition_revisions_memory_provider_config",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organization_organizations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            [
                "reranking_provider_config_id",
                "reranking_provider_config_revision",
                "organization_id",
            ],
            [
                "provider_config_revisions.provider_config_id",
                "provider_config_revisions.revision",
                "provider_config_revisions.organization_id",
            ],
            name="fk_agent_definition_revisions_reranking_provider_config",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            [
                "storage_provider_config_id",
                "storage_provider_config_revision",
                "organization_id",
            ],
            [
                "provider_config_revisions.provider_config_id",
                "provider_config_revisions.revision",
                "provider_config_revisions.organization_id",
            ],
            name="fk_agent_definition_revisions_storage_provider_config",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            [
                "stt_provider_config_id",
                "stt_provider_config_revision",
                "organization_id",
            ],
            [
                "provider_config_revisions.provider_config_id",
                "provider_config_revisions.revision",
                "provider_config_revisions.organization_id",
            ],
            name="fk_agent_definition_revisions_stt_provider_config",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            [
                "tts_provider_config_id",
                "tts_provider_config_revision",
                "organization_id",
            ],
            [
                "provider_config_revisions.provider_config_id",
                "provider_config_revisions.revision",
                "provider_config_revisions.organization_id",
            ],
            name="fk_agent_definition_revisions_tts_provider_config",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            [
                "realtime_provider_config_id",
                "realtime_provider_config_revision",
                "organization_id",
            ],
            [
                "provider_config_revisions.provider_config_id",
                "provider_config_revisions.revision",
                "provider_config_revisions.organization_id",
            ],
            name="fk_agent_definition_revisions_realtime_provider_config",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            [
                "webrtc_provider_config_id",
                "webrtc_provider_config_revision",
                "organization_id",
            ],
            [
                "provider_config_revisions.provider_config_id",
                "provider_config_revisions.revision",
                "provider_config_revisions.organization_id",
            ],
            name="fk_agent_definition_revisions_webrtc_provider_config",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "agent_id",
            "revision",
            "organization_id",
            name="uq_agent_definition_revisions_ref_organization",
        ),
        sa.UniqueConstraint(
            "agent_id", "revision", name="uq_agent_definition_revisions_ref"
        ),
    )
    op.create_index(
        op.f("ix_agent_definition_revisions_agent_id"),
        "agent_definition_revisions",
        ["agent_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_agent_definition_revisions_created_at"),
        "agent_definition_revisions",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_agent_definition_revisions_organization_id"),
        "agent_definition_revisions",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_agent_definition_revisions_voice_config_id"),
        "agent_definition_revisions",
        ["voice_config_id"],
        unique=False,
    )
    op.create_index(
        "ix_unq_agent_definition_revisions_ext_id_org_id",
        "agent_definition_revisions",
        ["external_id", "organization_id"],
        unique=True,
    )
    _create_table(
        "agent_tools",
        sa.Column("agent_id", sa.UUID(), nullable=False),
        sa.Column("tool_id", sa.UUID(), nullable=True),
        sa.Column("tool_revision", sa.Integer(), nullable=True),
        sa.Column("curated_tool_id", sa.UUID(), nullable=True),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(tool_id IS NOT NULL AND tool_revision IS NOT NULL AND curated_tool_id IS NULL) OR (tool_id IS NULL AND tool_revision IS NULL AND curated_tool_id IS NOT NULL)",
            name="ck_agent_tools_exact_tool",
        ),
        sa.CheckConstraint(
            "tool_revision IS NULL OR tool_revision > 0",
            name="ck_agent_tools_tool_revision_positive",
        ),
        sa.ForeignKeyConstraint(
            ["agent_id", "organization_id"],
            ["agent_agents.id", "agent_agents.organization_id"],
            name="fk_agent_tools_agent_organization",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["curated_tool_id", "organization_id"],
            ["integration_v2_tools.id", "integration_v2_tools.organization_id"],
            name="fk_agent_tools_curated_tool_organization",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tool_id", "tool_revision", "organization_id"],
            [
                "tool_definition_revisions.tool_id",
                "tool_definition_revisions.revision",
                "tool_definition_revisions.organization_id",
            ],
            name="fk_agent_tools_tool_revision_organization",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "agent_id", "curated_tool_id", name="uq_agent_tools_agent_curated_tool"
        ),
        sa.UniqueConstraint("agent_id", "tool_id"),
    )
    op.create_index(
        op.f("ix_agent_tools_created_at"), "agent_tools", ["created_at"], unique=False
    )
    op.create_index(
        op.f("ix_agent_tools_organization_id"),
        "agent_tools",
        ["organization_id"],
        unique=False,
    )
    _create_table(
        "voice_configs",
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("revision", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("stt_provider_config_id", sa.UUID(), nullable=True),
        sa.Column("tts_provider_config_id", sa.UUID(), nullable=True),
        sa.Column("realtime_provider_config_id", sa.UUID(), nullable=True),
        sa.Column("storage_provider_config_id", sa.UUID(), nullable=True),
        sa.Column(
            "definition",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("external_id", sa.String(length=320), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "revision > 0",
            name="ck_voice_configs_revision_positive",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organization_organizations.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["stt_provider_config_id", "organization_id"],
            ["provider_configs.id", "provider_configs.organization_id"],
            name="fk_voice_configs_stt_config_organization",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tts_provider_config_id", "organization_id"],
            ["provider_configs.id", "provider_configs.organization_id"],
            name="fk_voice_configs_tts_config_organization",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["realtime_provider_config_id", "organization_id"],
            ["provider_configs.id", "provider_configs.organization_id"],
            name="fk_voice_configs_realtime_config_organization",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["storage_provider_config_id", "organization_id"],
            ["provider_configs.id", "provider_configs.organization_id"],
            name="fk_voice_configs_storage_config_organization",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "id",
            "organization_id",
            name="uq_voice_configs_id_organization_id",
        ),
    )
    op.create_index(
        op.f("ix_voice_configs_created_at"),
        "voice_configs",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_voice_configs_organization_id"),
        "voice_configs",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_voice_configs_stt_provider_config_id"),
        "voice_configs",
        ["stt_provider_config_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_voice_configs_tts_provider_config_id"),
        "voice_configs",
        ["tts_provider_config_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_voice_configs_realtime_provider_config_id"),
        "voice_configs",
        ["realtime_provider_config_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_voice_configs_storage_provider_config_id"),
        "voice_configs",
        ["storage_provider_config_id"],
        unique=False,
    )
    op.create_index(
        "ix_unq_voice_configs_ext_id_org_id",
        "voice_configs",
        ["external_id", "organization_id"],
        unique=True,
    )
    op.create_index(
        "uq_voice_configs_name_organization_active",
        "voice_configs",
        ["organization_id", "name"],
        unique=True,
        postgresql_where=sa.text("deleted = false"),
    )
    _create_table(
        "knowledge_chunks",
        sa.Column("knowledgebase_id", sa.UUID(), nullable=False),
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("scope", sa.String(length=32), nullable=False),
        sa.Column("scope_id", sa.String(length=64), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=True),
        sa.Column("source_uri", sa.Text(), nullable=True),
        sa.Column("meta", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("search_vector", postgresql.TSVECTOR(), nullable=True),
        sa.Column("embedding", _VectorType(), nullable=True),
        sa.Column("embedding_space_id", sa.String(length=64), nullable=True),
        sa.Column("reindex_source_chunk_id", sa.UUID(), nullable=True),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("external_id", sa.String(length=320), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["knowledgebase_id", "organization_id"],
            ["knowledgebases.id", "knowledgebases.organization_id"],
            name="fk_knowledge_chunks_knowledgebase_organization",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organization_organizations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["reindex_source_chunk_id"], ["knowledge_chunks.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_knowledge_chunks_created_at"),
        "knowledge_chunks",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_knowledge_chunks_document_id"),
        "knowledge_chunks",
        ["document_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_knowledge_chunks_embedding_space_id"),
        "knowledge_chunks",
        ["embedding_space_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_knowledge_chunks_knowledgebase_id"),
        "knowledge_chunks",
        ["knowledgebase_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_knowledge_chunks_organization_id"),
        "knowledge_chunks",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_knowledge_chunks_reindex_source_chunk_id"),
        "knowledge_chunks",
        ["reindex_source_chunk_id"],
        unique=False,
    )
    op.create_index(
        "ix_knowledge_chunks_search_vector",
        "knowledge_chunks",
        ["search_vector"],
        unique=False,
        postgresql_using="gin",
    )
    op.create_index(
        "ix_unq_knowledge_chunks_ext_id_org_id",
        "knowledge_chunks",
        ["external_id", "organization_id"],
        unique=True,
    )
    op.create_index(
        "uq_knowledge_chunks_fts_document_position",
        "knowledge_chunks",
        ["knowledgebase_id", "document_id", "position"],
        unique=True,
        postgresql_where=sa.text("embedding_space_id IS NULL"),
    )
    op.create_index(
        "uq_knowledge_chunks_vector_document_position",
        "knowledge_chunks",
        ["knowledgebase_id", "document_id", "position", "embedding_space_id"],
        unique=True,
        postgresql_where=sa.text("embedding_space_id IS NOT NULL"),
    )
    _create_table(
        "knowledge_corpus_imports",
        sa.Column("knowledgebase_id", sa.UUID(), nullable=False),
        sa.Column("prefix", sa.Text(), server_default="", nullable=False),
        sa.Column("import_key", sa.String(length=64), nullable=False),
        sa.Column("storage_provider_config_id", sa.UUID(), nullable=False),
        sa.Column("storage_provider_config_revision", sa.Integer(), nullable=False),
        sa.Column("storage_provider", sa.String(length=64), nullable=False),
        sa.Column(
            "storage_authority", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column(
            "discovered_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "queued_count", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column("skipped", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("external_id", sa.String(length=320), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "state",
            postgresql.ENUM(
                "pending",
                "running",
                "succeeded",
                "failed",
                "cancelled",
                name="knowledge_corpus_import_state_enum",
            ),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("absurd_task_id", sa.UUID(), nullable=True),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["knowledgebase_id", "organization_id"],
            ["knowledgebases.id", "knowledgebases.organization_id"],
            name="fk_corpus_imports_knowledgebase_organization",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organization_organizations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["storage_provider_config_id", "organization_id"],
            ["provider_configs.id", "provider_configs.organization_id"],
            name="fk_corpus_imports_storage_config_organization",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["storage_provider_config_id", "storage_provider_config_revision"],
            [
                "provider_config_revisions.provider_config_id",
                "provider_config_revisions.revision",
            ],
            name="fk_corpus_imports_storage_config_revision",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("absurd_task_id"),
        sa.UniqueConstraint(
            "id",
            "organization_id",
            name="uq_knowledge_corpus_imports_id_organization_id",
        ),
    )
    op.create_index(
        op.f("ix_knowledge_corpus_imports_created_at"),
        "knowledge_corpus_imports",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_knowledge_corpus_imports_knowledgebase_id"),
        "knowledge_corpus_imports",
        ["knowledgebase_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_knowledge_corpus_imports_organization_id"),
        "knowledge_corpus_imports",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_knowledge_corpus_imports_state"),
        "knowledge_corpus_imports",
        ["state"],
        unique=False,
    )
    op.create_index(
        op.f("ix_knowledge_corpus_imports_storage_provider_config_id"),
        "knowledge_corpus_imports",
        ["storage_provider_config_id"],
        unique=False,
    )
    op.create_index(
        "ix_unq_knowledge_corpus_imports_ext_id_org_id",
        "knowledge_corpus_imports",
        ["external_id", "organization_id"],
        unique=True,
    )
    op.create_index(
        "uq_knowledge_corpus_imports_active_source",
        "knowledge_corpus_imports",
        ["knowledgebase_id", "import_key"],
        unique=True,
        postgresql_where=sa.text(
            "state IN ('pending', 'running') AND deleted IS FALSE"
        ),
    )
    _create_table(
        "knowledge_reindex_jobs",
        sa.Column("knowledgebase_id", sa.UUID(), nullable=False),
        sa.Column("source_embedding_provider_config_id", sa.UUID(), nullable=False),
        sa.Column(
            "source_embedding_provider_config_revision", sa.Integer(), nullable=False
        ),
        sa.Column("source_embedding_provider", sa.String(length=64), nullable=False),
        sa.Column("source_embedding_endpoint", sa.Text(), nullable=False),
        sa.Column("source_embedding_model", sa.String(length=255), nullable=False),
        sa.Column("source_embedding_dimensions", sa.Integer(), nullable=False),
        sa.Column(
            "source_embedding_semantic_options",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("source_embedding_space_id", sa.String(length=64), nullable=False),
        sa.Column("target_embedding_provider_config_id", sa.UUID(), nullable=False),
        sa.Column(
            "target_embedding_provider_config_revision", sa.Integer(), nullable=False
        ),
        sa.Column("target_embedding_provider", sa.String(length=64), nullable=False),
        sa.Column("target_embedding_endpoint", sa.Text(), nullable=False),
        sa.Column("target_embedding_model", sa.String(length=255), nullable=False),
        sa.Column("target_embedding_dimensions", sa.Integer(), nullable=False),
        sa.Column(
            "target_embedding_semantic_options",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("target_embedding_space_id", sa.String(length=64), nullable=False),
        sa.Column(
            "source_chunk_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "indexed_chunk_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("external_id", sa.String(length=320), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "state",
            postgresql.ENUM(
                "pending",
                "running",
                "succeeded",
                "failed",
                "cancelled",
                name="knowledge_reindex_job_state_enum",
            ),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("absurd_task_id", sa.UUID(), nullable=True),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "source_embedding_space_id <> target_embedding_space_id",
            name="ck_knowledge_reindex_jobs_distinct_spaces",
        ),
        sa.ForeignKeyConstraint(
            ["knowledgebase_id", "organization_id"],
            ["knowledgebases.id", "knowledgebases.organization_id"],
            name="fk_knowledge_reindex_jobs_knowledgebase_organization",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organization_organizations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["source_embedding_provider_config_id", "organization_id"],
            ["provider_configs.id", "provider_configs.organization_id"],
            name="fk_knowledge_reindex_jobs_source_config_organization",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            [
                "source_embedding_provider_config_id",
                "source_embedding_provider_config_revision",
            ],
            [
                "provider_config_revisions.provider_config_id",
                "provider_config_revisions.revision",
            ],
            name="fk_knowledge_reindex_jobs_source_config_revision",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["target_embedding_provider_config_id", "organization_id"],
            ["provider_configs.id", "provider_configs.organization_id"],
            name="fk_knowledge_reindex_jobs_target_config_organization",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            [
                "target_embedding_provider_config_id",
                "target_embedding_provider_config_revision",
            ],
            [
                "provider_config_revisions.provider_config_id",
                "provider_config_revisions.revision",
            ],
            name="fk_knowledge_reindex_jobs_target_config_revision",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("absurd_task_id"),
        sa.UniqueConstraint(
            "id", "organization_id", name="uq_knowledge_reindex_jobs_id_organization_id"
        ),
    )
    op.create_index(
        op.f("ix_knowledge_reindex_jobs_created_at"),
        "knowledge_reindex_jobs",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_knowledge_reindex_jobs_knowledgebase_id"),
        "knowledge_reindex_jobs",
        ["knowledgebase_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_knowledge_reindex_jobs_organization_id"),
        "knowledge_reindex_jobs",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_knowledge_reindex_jobs_source_embedding_provider_config_id"),
        "knowledge_reindex_jobs",
        ["source_embedding_provider_config_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_knowledge_reindex_jobs_source_embedding_space_id"),
        "knowledge_reindex_jobs",
        ["source_embedding_space_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_knowledge_reindex_jobs_state"),
        "knowledge_reindex_jobs",
        ["state"],
        unique=False,
    )
    op.create_index(
        op.f("ix_knowledge_reindex_jobs_target_embedding_provider_config_id"),
        "knowledge_reindex_jobs",
        ["target_embedding_provider_config_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_knowledge_reindex_jobs_target_embedding_space_id"),
        "knowledge_reindex_jobs",
        ["target_embedding_space_id"],
        unique=False,
    )
    op.create_index(
        "ix_unq_knowledge_reindex_jobs_ext_id_org_id",
        "knowledge_reindex_jobs",
        ["external_id", "organization_id"],
        unique=True,
    )
    op.create_index(
        "uq_knowledge_reindex_jobs_active_knowledgebase",
        "knowledge_reindex_jobs",
        ["knowledgebase_id"],
        unique=True,
        postgresql_where=sa.text(
            "state IN ('pending', 'running') AND deleted IS FALSE"
        ),
    )
    _create_table(
        "knowledgebase_grants",
        sa.Column("agent_id", sa.UUID(), nullable=False),
        sa.Column("knowledgebase_id", sa.UUID(), nullable=False),
        sa.Column(
            "access",
            postgresql.ENUM("read", "read_write", name="knowledge_access_enum"),
            server_default="read",
            nullable=False,
        ),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("external_id", sa.String(length=320), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["agent_id", "organization_id"],
            ["agent_agents.id", "agent_agents.organization_id"],
            name="fk_knowledgebase_grants_agent_organization",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["knowledgebase_id", "organization_id"],
            ["knowledgebases.id", "knowledgebases.organization_id"],
            name="fk_knowledgebase_grants_knowledgebase_organization",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organization_organizations.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("agent_id", "knowledgebase_id"),
    )
    op.create_index(
        op.f("ix_knowledgebase_grants_agent_id"),
        "knowledgebase_grants",
        ["agent_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_knowledgebase_grants_created_at"),
        "knowledgebase_grants",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_knowledgebase_grants_knowledgebase_id"),
        "knowledgebase_grants",
        ["knowledgebase_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_knowledgebase_grants_organization_id"),
        "knowledgebase_grants",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "ix_unq_knowledgebase_grants_ext_id_org_id",
        "knowledgebase_grants",
        ["external_id", "organization_id"],
        unique=True,
    )
    _create_table(
        "map_agents_to_swarms",
        sa.Column("agent_id", sa.UUID(), nullable=False),
        sa.Column("swarm_id", sa.UUID(), nullable=False),
        sa.Column("agent_description", sa.Text(), nullable=True),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("external_id", sa.String(length=320), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["agent_id", "organization_id"],
            ["agent_agents.id", "agent_agents.organization_id"],
            name="fk_map_agents_to_swarms_agent_organization",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organization_organizations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["swarm_id", "organization_id"],
            ["agent_swarms.id", "agent_swarms.organization_id"],
            name="fk_map_agents_to_swarms_swarm_organization",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_map_agents_to_swarms_agent_swarm",
        "map_agents_to_swarms",
        ["agent_id", "swarm_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_map_agents_to_swarms_created_at"),
        "map_agents_to_swarms",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_map_agents_to_swarms_organization_id"),
        "map_agents_to_swarms",
        ["organization_id"],
        unique=False,
    )
    _create_table(
        "memory_changes",
        sa.Column("memory_id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column(
            "scope_level",
            postgresql.ENUM("agent", "user", "conversation", name="memory_level_enum"),
            nullable=False,
        ),
        sa.Column("agent_id", sa.UUID(), nullable=True),
        sa.Column("contact_id", sa.UUID(), nullable=True),
        sa.Column("conversation_id", sa.UUID(), nullable=True),
        sa.Column("source_conversation_id", sa.UUID(), nullable=True),
        sa.Column(
            "event",
            postgresql.ENUM(
                "add", "update", "expire", "delete", "noop", name="memory_event_enum"
            ),
            nullable=False,
        ),
        sa.Column("before", sa.Text(), nullable=True),
        sa.Column("after", sa.Text(), nullable=True),
        sa.Column(
            "provenance", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("memory_state_revision", sa.Integer(), nullable=False),
        sa.Column("memory_provider_config_id", sa.UUID(), nullable=False),
        sa.Column("memory_provider_config_revision", sa.Integer(), nullable=False),
        sa.Column("embedding_provider_config_id", sa.UUID(), nullable=False),
        sa.Column("embedding_provider_config_revision", sa.Integer(), nullable=False),
        sa.Column("embedding_provider", sa.String(length=64), nullable=False),
        sa.Column("embedding_endpoint", sa.Text(), nullable=False),
        sa.Column("embedding_model", sa.String(length=255), nullable=False),
        sa.Column("embedding_dimensions", sa.Integer(), nullable=False),
        sa.Column(
            "embedding_semantic_options",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("embedding_space_id", sa.String(length=64), nullable=False),
        sa.Column("reconciliation_llm_provider_config_id", sa.UUID(), nullable=False),
        sa.Column(
            "reconciliation_llm_provider_config_revision", sa.Integer(), nullable=False
        ),
        sa.Column("reconciliation_llm_provider", sa.String(length=64), nullable=False),
        sa.Column("reconciliation_llm_model", sa.String(length=255), nullable=False),
        sa.Column(
            "reconciliation_prompt_revision", sa.String(length=64), nullable=False
        ),
        sa.Column("formation_job_id", sa.UUID(), nullable=True),
        sa.Column("formation_operation_index", sa.Integer(), nullable=True),
        sa.Column("reconciliation_job_id", sa.UUID(), nullable=True),
        sa.Column("reconciliation_operation_index", sa.Integer(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(scope_level = 'agent' AND agent_id IS NOT NULL AND contact_id IS NULL AND conversation_id IS NULL) OR (scope_level = 'user' AND contact_id IS NOT NULL AND agent_id IS NULL AND conversation_id IS NULL) OR (scope_level = 'conversation' AND conversation_id IS NOT NULL AND agent_id IS NULL AND contact_id IS NULL)",
            name="ck_memory_changes_exact_scope_owner",
        ),
        sa.CheckConstraint(
            "(formation_job_id IS NULL AND formation_operation_index IS NULL) OR (formation_job_id IS NOT NULL AND formation_operation_index IS NOT NULL)",
            name="ck_memory_changes_formation_operation",
        ),
        sa.CheckConstraint(
            "(reconciliation_job_id IS NULL AND reconciliation_operation_index IS NULL) OR (reconciliation_job_id IS NOT NULL AND reconciliation_operation_index IS NOT NULL)",
            name="ck_memory_changes_reconciliation_operation",
        ),
        sa.CheckConstraint(
            "memory_state_revision > 0 AND embedding_dimensions > 0",
            name="ck_memory_changes_authority_positive",
        ),
        sa.ForeignKeyConstraint(
            ["agent_id", "organization_id"],
            ["agent_agents.id", "agent_agents.organization_id"],
            name="fk_memory_changes_agent_organization",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["contact_id", "organization_id"],
            ["contact_contacts.id", "contact_contacts.organization_id"],
            name="fk_memory_changes_contact_organization",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id", "organization_id"],
            [
                "conversation_conversations.id",
                "conversation_conversations.organization_id",
            ],
            name="fk_memory_changes_conversation_organization",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["embedding_provider_config_id", "embedding_provider_config_revision"],
            [
                "provider_config_revisions.provider_config_id",
                "provider_config_revisions.revision",
            ],
            name="fk_memory_changes_embedding_config_revision",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["embedding_provider_config_id", "organization_id"],
            ["provider_configs.id", "provider_configs.organization_id"],
            name="fk_memory_changes_embedding_config_organization",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["memory_provider_config_id", "memory_provider_config_revision"],
            [
                "provider_config_revisions.provider_config_id",
                "provider_config_revisions.revision",
            ],
            name="fk_memory_changes_memory_config_revision",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["memory_provider_config_id", "organization_id"],
            ["provider_configs.id", "provider_configs.organization_id"],
            name="fk_memory_changes_memory_config_organization",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organization_organizations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["reconciliation_llm_provider_config_id", "organization_id"],
            ["provider_configs.id", "provider_configs.organization_id"],
            name="fk_memory_changes_reconciliation_llm_organization",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            [
                "reconciliation_llm_provider_config_id",
                "reconciliation_llm_provider_config_revision",
            ],
            [
                "provider_config_revisions.provider_config_id",
                "provider_config_revisions.revision",
            ],
            name="fk_memory_changes_reconciliation_llm_revision",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "formation_job_id",
            "formation_operation_index",
            name="uq_memory_changes_formation_operation",
        ),
        sa.UniqueConstraint(
            "reconciliation_job_id",
            "reconciliation_operation_index",
            name="uq_memory_changes_reconciliation_operation",
        ),
    )
    op.create_index(
        op.f("ix_memory_changes_agent_id"), "memory_changes", ["agent_id"], unique=False
    )
    op.create_index(
        op.f("ix_memory_changes_contact_id"),
        "memory_changes",
        ["contact_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_memory_changes_conversation_id"),
        "memory_changes",
        ["conversation_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_memory_changes_created_at"),
        "memory_changes",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_memory_changes_embedding_provider_config_id"),
        "memory_changes",
        ["embedding_provider_config_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_memory_changes_embedding_space_id"),
        "memory_changes",
        ["embedding_space_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_memory_changes_formation_job_id"),
        "memory_changes",
        ["formation_job_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_memory_changes_memory_id"),
        "memory_changes",
        ["memory_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_memory_changes_memory_provider_config_id"),
        "memory_changes",
        ["memory_provider_config_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_memory_changes_organization_id"),
        "memory_changes",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_memory_changes_reconciliation_job_id"),
        "memory_changes",
        ["reconciliation_job_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_memory_changes_reconciliation_llm_provider_config_id"),
        "memory_changes",
        ["reconciliation_llm_provider_config_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_memory_changes_scope_level"),
        "memory_changes",
        ["scope_level"],
        unique=False,
    )
    op.create_index(
        op.f("ix_memory_changes_source_conversation_id"),
        "memory_changes",
        ["source_conversation_id"],
        unique=False,
    )
    _create_table(
        "memory_formation_cursors",
        sa.Column("conversation_id", sa.UUID(), nullable=False),
        sa.Column("memory_provider_config_id", sa.UUID(), nullable=False),
        sa.Column("memory_provider_config_revision", sa.Integer(), nullable=False),
        sa.Column(
            "processed_through_created_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column("processed_through_message_id", sa.UUID(), nullable=True),
        sa.Column(
            "requested_through_created_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column("requested_through_message_id", sa.UUID(), nullable=True),
        sa.Column("active_job_id", sa.UUID(), nullable=True),
        sa.Column(
            "next_generation", sa.Integer(), server_default=sa.text("1"), nullable=False
        ),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("external_id", sa.String(length=320), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(processed_through_created_at IS NULL AND processed_through_message_id IS NULL) OR (processed_through_created_at IS NOT NULL AND processed_through_message_id IS NOT NULL)",
            name="ck_memory_cursors_processed_pair",
        ),
        sa.CheckConstraint(
            "(requested_through_created_at IS NULL AND requested_through_message_id IS NULL) OR (requested_through_created_at IS NOT NULL AND requested_through_message_id IS NOT NULL)",
            name="ck_memory_cursors_requested_pair",
        ),
        sa.CheckConstraint(
            "next_generation > 0", name="ck_memory_cursors_next_generation_positive"
        ),
        sa.CheckConstraint(
            "processed_through_created_at IS NULL OR (requested_through_created_at IS NOT NULL AND ROW(requested_through_created_at, requested_through_message_id) >= ROW(processed_through_created_at, processed_through_message_id))",
            name="ck_memory_cursors_requested_covers_processed",
        ),
        sa.ForeignKeyConstraint(
            ["active_job_id", "organization_id", "conversation_id"],
            [
                "memory_formation_jobs.id",
                "memory_formation_jobs.organization_id",
                "memory_formation_jobs.conversation_id",
            ],
            name="fk_memory_cursors_active_job_owner",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id", "organization_id"],
            [
                "conversation_conversations.id",
                "conversation_conversations.organization_id",
            ],
            name="fk_memory_cursors_conversation_organization",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["memory_provider_config_id", "memory_provider_config_revision"],
            [
                "provider_config_revisions.provider_config_id",
                "provider_config_revisions.revision",
            ],
            name="fk_memory_cursors_memory_config_revision",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["memory_provider_config_id", "organization_id"],
            ["provider_configs.id", "provider_configs.organization_id"],
            name="fk_memory_cursors_memory_config_organization",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organization_organizations.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "active_job_id", name="uq_memory_formation_cursors_active_job"
        ),
        sa.UniqueConstraint(
            "organization_id",
            "conversation_id",
            name="uq_memory_formation_cursors_conversation",
        ),
    )
    op.create_index(
        op.f("ix_memory_formation_cursors_active_job_id"),
        "memory_formation_cursors",
        ["active_job_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_memory_formation_cursors_conversation_id"),
        "memory_formation_cursors",
        ["conversation_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_memory_formation_cursors_created_at"),
        "memory_formation_cursors",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_memory_formation_cursors_memory_provider_config_id"),
        "memory_formation_cursors",
        ["memory_provider_config_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_memory_formation_cursors_organization_id"),
        "memory_formation_cursors",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "ix_unq_memory_formation_cursors_ext_id_org_id",
        "memory_formation_cursors",
        ["external_id", "organization_id"],
        unique=True,
    )
    _create_table(
        "memory_formation_effects",
        sa.Column("formation_job_id", sa.UUID(), nullable=False),
        sa.Column(
            "operations", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column(
            "applied_flags",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "completed_count", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("outcomes", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("external_id", sa.String(length=320), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["formation_job_id", "organization_id"],
            ["memory_formation_jobs.id", "memory_formation_jobs.organization_id"],
            name="fk_memory_formation_effects_job_organization",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organization_organizations.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("formation_job_id", name="uq_memory_formation_effects_job"),
    )
    op.create_index(
        op.f("ix_memory_formation_effects_created_at"),
        "memory_formation_effects",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_memory_formation_effects_formation_job_id"),
        "memory_formation_effects",
        ["formation_job_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_memory_formation_effects_organization_id"),
        "memory_formation_effects",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "ix_unq_memory_formation_effects_ext_id_org_id",
        "memory_formation_effects",
        ["external_id", "organization_id"],
        unique=True,
    )
    _create_table(
        "memory_memories",
        sa.Column(
            "scope_level",
            postgresql.ENUM("agent", "user", "conversation", name="memory_level_enum"),
            nullable=False,
        ),
        sa.Column("agent_id", sa.UUID(), nullable=True),
        sa.Column("contact_id", sa.UUID(), nullable=True),
        sa.Column("conversation_id", sa.UUID(), nullable=True),
        sa.Column("source_conversation_id", sa.UUID(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("meta", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "provenance", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column(
            "state_revision", sa.Integer(), server_default=sa.text("1"), nullable=False
        ),
        sa.Column(
            "reconciled_state_revision",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "recall_count", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column("last_recalled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("memory_provider_config_id", sa.UUID(), nullable=False),
        sa.Column("memory_provider_config_revision", sa.Integer(), nullable=False),
        sa.Column("embedding_provider_config_id", sa.UUID(), nullable=False),
        sa.Column("embedding_provider_config_revision", sa.Integer(), nullable=False),
        sa.Column("embedding_provider", sa.String(length=64), nullable=False),
        sa.Column("embedding_endpoint", sa.Text(), nullable=False),
        sa.Column("embedding_model", sa.String(length=255), nullable=False),
        sa.Column("embedding_dimensions", sa.Integer(), nullable=False),
        sa.Column(
            "embedding_semantic_options",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("embedding", _VectorType(), nullable=True),
        sa.Column("embedding_space_id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("external_id", sa.String(length=320), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(scope_level = 'agent' AND agent_id IS NOT NULL AND contact_id IS NULL AND conversation_id IS NULL) OR (scope_level = 'user' AND contact_id IS NOT NULL AND agent_id IS NULL AND conversation_id IS NULL) OR (scope_level = 'conversation' AND conversation_id IS NOT NULL AND agent_id IS NULL AND contact_id IS NULL)",
            name="ck_memory_memories_exact_scope_owner",
        ),
        sa.CheckConstraint(
            "state_revision > 0 AND reconciled_state_revision >= 0 AND reconciled_state_revision <= state_revision",
            name="ck_memory_memories_reconciliation_revision",
        ),
        sa.ForeignKeyConstraint(
            ["agent_id", "organization_id"],
            ["agent_agents.id", "agent_agents.organization_id"],
            name="fk_memory_memories_agent_organization",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["contact_id", "organization_id"],
            ["contact_contacts.id", "contact_contacts.organization_id"],
            name="fk_memory_memories_contact_organization",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id", "organization_id"],
            [
                "conversation_conversations.id",
                "conversation_conversations.organization_id",
            ],
            name="fk_memory_memories_conversation_organization",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["embedding_provider_config_id", "embedding_provider_config_revision"],
            [
                "provider_config_revisions.provider_config_id",
                "provider_config_revisions.revision",
            ],
            name="fk_memories_embedding_config_revision",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["embedding_provider_config_id", "organization_id"],
            ["provider_configs.id", "provider_configs.organization_id"],
            name="fk_memories_embedding_config_organization",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["memory_provider_config_id", "memory_provider_config_revision"],
            [
                "provider_config_revisions.provider_config_id",
                "provider_config_revisions.revision",
            ],
            name="fk_memories_memory_config_revision",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["memory_provider_config_id", "organization_id"],
            ["provider_configs.id", "provider_configs.organization_id"],
            name="fk_memories_memory_config_organization",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organization_organizations.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "id", "organization_id", name="uq_memory_memories_id_organization_id"
        ),
        sa.UniqueConstraint(
            "organization_id",
            "agent_id",
            "content_hash",
            "memory_provider_config_id",
            name="uq_memory_memories_agent_content_config",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "contact_id",
            "content_hash",
            "memory_provider_config_id",
            name="uq_memory_memories_contact_content_config",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "conversation_id",
            "content_hash",
            "memory_provider_config_id",
            name="uq_memory_memories_conversation_content_config",
        ),
    )
    op.create_index(
        op.f("ix_memory_memories_agent_id"),
        "memory_memories",
        ["agent_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_memory_memories_contact_id"),
        "memory_memories",
        ["contact_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_memory_memories_conversation_id"),
        "memory_memories",
        ["conversation_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_memory_memories_created_at"),
        "memory_memories",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_memory_memories_embedding_provider_config_id"),
        "memory_memories",
        ["embedding_provider_config_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_memory_memories_embedding_space_id"),
        "memory_memories",
        ["embedding_space_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_memory_memories_expires_at"),
        "memory_memories",
        ["expires_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_memory_memories_memory_provider_config_id"),
        "memory_memories",
        ["memory_provider_config_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_memory_memories_organization_id"),
        "memory_memories",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_memory_memories_scope_level"),
        "memory_memories",
        ["scope_level"],
        unique=False,
    )
    op.create_index(
        op.f("ix_memory_memories_source_conversation_id"),
        "memory_memories",
        ["source_conversation_id"],
        unique=False,
    )
    op.create_index(
        "ix_unq_memory_memories_ext_id_org_id",
        "memory_memories",
        ["external_id", "organization_id"],
        unique=True,
    )
    _create_table(
        "memory_reconciliation_jobs",
        sa.Column(
            "scope_level",
            postgresql.ENUM("agent", "user", "conversation", name="memory_level_enum"),
            nullable=False,
        ),
        sa.Column("owner_id", sa.UUID(), nullable=False),
        sa.Column("agent_id", sa.UUID(), nullable=True),
        sa.Column("contact_id", sa.UUID(), nullable=True),
        sa.Column("conversation_id", sa.UUID(), nullable=True),
        sa.Column("generation", sa.Integer(), nullable=False),
        sa.Column("range_start_created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("range_start_change_id", sa.UUID(), nullable=True),
        sa.Column(
            "range_through_created_at", sa.DateTime(timezone=True), nullable=False
        ),
        sa.Column("range_through_change_id", sa.UUID(), nullable=False),
        sa.Column("change_count", sa.Integer(), nullable=False),
        sa.Column("memory_provider_config_id", sa.UUID(), nullable=False),
        sa.Column("memory_provider_config_revision", sa.Integer(), nullable=False),
        sa.Column("embedding_provider_config_id", sa.UUID(), nullable=False),
        sa.Column("embedding_provider_config_revision", sa.Integer(), nullable=False),
        sa.Column("embedding_provider", sa.String(length=64), nullable=False),
        sa.Column("embedding_endpoint", sa.Text(), nullable=False),
        sa.Column("embedding_model", sa.String(length=255), nullable=False),
        sa.Column("embedding_dimensions", sa.Integer(), nullable=False),
        sa.Column(
            "embedding_semantic_options",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("embedding_space_id", sa.String(length=64), nullable=False),
        sa.Column("reconciliation_llm_provider_config_id", sa.UUID(), nullable=False),
        sa.Column(
            "reconciliation_llm_provider_config_revision", sa.Integer(), nullable=False
        ),
        sa.Column("reconciliation_llm_provider", sa.String(length=64), nullable=False),
        sa.Column("reconciliation_llm_model", sa.String(length=255), nullable=False),
        sa.Column(
            "reconciliation_prompt_revision", sa.String(length=64), nullable=False
        ),
        sa.Column(
            "considered_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "duplicate_count", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column(
            "superseded_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "conflict_count", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column(
            "unrelated_count", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column(
            "failed_count", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("external_id", sa.String(length=320), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "state",
            postgresql.ENUM(
                "pending",
                "running",
                "succeeded",
                "failed",
                "cancelled",
                name="memory_reconciliation_job_state_enum",
            ),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("absurd_task_id", sa.UUID(), nullable=True),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "(scope_level = 'agent' AND owner_id = agent_id AND agent_id IS NOT NULL AND contact_id IS NULL AND conversation_id IS NULL) OR (scope_level = 'user' AND owner_id = contact_id AND contact_id IS NOT NULL AND agent_id IS NULL AND conversation_id IS NULL) OR (scope_level = 'conversation' AND owner_id = conversation_id AND conversation_id IS NOT NULL AND agent_id IS NULL AND contact_id IS NULL)",
            name="ck_memory_reconciliation_jobs_exact_owner",
        ),
        sa.CheckConstraint(
            "(range_start_created_at IS NULL AND range_start_change_id IS NULL) OR (range_start_created_at IS NOT NULL AND range_start_change_id IS NOT NULL)",
            name="ck_memory_reconciliation_jobs_range_start_pair",
        ),
        sa.CheckConstraint(
            "considered_count = duplicate_count + superseded_count + conflict_count + unrelated_count + failed_count",
            name="ck_memory_reconciliation_jobs_outcome_partition",
        ),
        sa.CheckConstraint(
            "embedding_dimensions > 0 AND considered_count >= 0 AND duplicate_count >= 0 AND superseded_count >= 0 AND conflict_count >= 0 AND unrelated_count >= 0 AND failed_count >= 0",
            name="ck_memory_reconciliation_jobs_counts_nonnegative",
        ),
        sa.CheckConstraint(
            "generation > 0 AND change_count BETWEEN 1 AND 20",
            name="ck_memory_reconciliation_jobs_generation_count",
        ),
        sa.CheckConstraint(
            "range_start_created_at IS NULL OR ROW(range_through_created_at, range_through_change_id) > ROW(range_start_created_at, range_start_change_id)",
            name="ck_memory_reconciliation_jobs_range_advances",
        ),
        sa.ForeignKeyConstraint(
            ["agent_id", "organization_id"],
            ["agent_agents.id", "agent_agents.organization_id"],
            name="fk_memory_reconciliation_jobs_agent_organization",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["contact_id", "organization_id"],
            ["contact_contacts.id", "contact_contacts.organization_id"],
            name="fk_memory_reconciliation_jobs_contact_organization",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id", "organization_id"],
            [
                "conversation_conversations.id",
                "conversation_conversations.organization_id",
            ],
            name="fk_memory_reconciliation_jobs_conversation_organization",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["embedding_provider_config_id", "embedding_provider_config_revision"],
            [
                "provider_config_revisions.provider_config_id",
                "provider_config_revisions.revision",
            ],
            name="fk_memory_reconciliation_jobs_embedding_config_revision",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["embedding_provider_config_id", "organization_id"],
            ["provider_configs.id", "provider_configs.organization_id"],
            name="fk_memory_reconciliation_jobs_embedding_config_organization",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["memory_provider_config_id", "memory_provider_config_revision"],
            [
                "provider_config_revisions.provider_config_id",
                "provider_config_revisions.revision",
            ],
            name="fk_memory_reconciliation_jobs_memory_config_revision",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["memory_provider_config_id", "organization_id"],
            ["provider_configs.id", "provider_configs.organization_id"],
            name="fk_memory_reconciliation_jobs_memory_config_organization",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organization_organizations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["reconciliation_llm_provider_config_id", "organization_id"],
            ["provider_configs.id", "provider_configs.organization_id"],
            name="fk_memory_reconciliation_jobs_llm_config_organization",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            [
                "reconciliation_llm_provider_config_id",
                "reconciliation_llm_provider_config_revision",
            ],
            [
                "provider_config_revisions.provider_config_id",
                "provider_config_revisions.revision",
            ],
            name="fk_memory_reconciliation_jobs_llm_config_revision",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("absurd_task_id"),
        sa.UniqueConstraint(
            "id",
            "organization_id",
            name="uq_memory_reconciliation_jobs_id_organization",
        ),
    )
    op.create_index(
        op.f("ix_memory_reconciliation_jobs_agent_id"),
        "memory_reconciliation_jobs",
        ["agent_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_memory_reconciliation_jobs_contact_id"),
        "memory_reconciliation_jobs",
        ["contact_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_memory_reconciliation_jobs_conversation_id"),
        "memory_reconciliation_jobs",
        ["conversation_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_memory_reconciliation_jobs_created_at"),
        "memory_reconciliation_jobs",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_memory_reconciliation_jobs_embedding_provider_config_id"),
        "memory_reconciliation_jobs",
        ["embedding_provider_config_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_memory_reconciliation_jobs_embedding_space_id"),
        "memory_reconciliation_jobs",
        ["embedding_space_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_memory_reconciliation_jobs_memory_provider_config_id"),
        "memory_reconciliation_jobs",
        ["memory_provider_config_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_memory_reconciliation_jobs_organization_id"),
        "memory_reconciliation_jobs",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_memory_reconciliation_jobs_owner_id"),
        "memory_reconciliation_jobs",
        ["owner_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_memory_reconciliation_jobs_reconciliation_llm_provider_config_id"),
        "memory_reconciliation_jobs",
        ["reconciliation_llm_provider_config_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_memory_reconciliation_jobs_scope_level"),
        "memory_reconciliation_jobs",
        ["scope_level"],
        unique=False,
    )
    op.create_index(
        op.f("ix_memory_reconciliation_jobs_state"),
        "memory_reconciliation_jobs",
        ["state"],
        unique=False,
    )
    op.create_index(
        "ix_unq_memory_reconciliation_jobs_ext_id_org_id",
        "memory_reconciliation_jobs",
        ["external_id", "organization_id"],
        unique=True,
    )
    op.create_index(
        "uq_memory_reconciliation_jobs_active_partition",
        "memory_reconciliation_jobs",
        ["organization_id", "memory_provider_config_id", "scope_level", "owner_id"],
        unique=True,
        postgresql_where=sa.text(
            "state IN ('pending', 'running') AND deleted IS FALSE"
        ),
    )
    _create_table(
        "sandbox_grants",
        sa.Column("agent_id", sa.UUID(), nullable=False),
        sa.Column("sandbox_provider_config_id", sa.UUID(), nullable=False),
        sa.Column("sandbox_provider_config_revision", sa.Integer(), nullable=False),
        sa.Column(
            "revision", sa.Integer(), server_default=sa.text("1"), nullable=False
        ),
        sa.Column(
            "access", postgresql.ENUM("run", name="sandbox_access_enum"), nullable=False
        ),
        sa.Column("max_sessions", sa.Integer(), nullable=True),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("external_id", sa.String(length=320), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("revision > 0", name="ck_sandbox_grants_revision_positive"),
        sa.CheckConstraint(
            "sandbox_provider_config_revision > 0",
            name="ck_sandbox_grants_config_revision_positive",
        ),
        sa.ForeignKeyConstraint(
            ["agent_id", "organization_id"],
            ["agent_agents.id", "agent_agents.organization_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organization_organizations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["sandbox_provider_config_id", "organization_id"],
            ["provider_configs.id", "provider_configs.organization_id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["sandbox_provider_config_id", "sandbox_provider_config_revision"],
            [
                "provider_config_revisions.provider_config_id",
                "provider_config_revisions.revision",
            ],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("agent_id"),
    )
    op.create_index(
        op.f("ix_sandbox_grants_agent_id"), "sandbox_grants", ["agent_id"], unique=False
    )
    op.create_index(
        op.f("ix_sandbox_grants_created_at"),
        "sandbox_grants",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_sandbox_grants_organization_id"),
        "sandbox_grants",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_sandbox_grants_sandbox_provider_config_id"),
        "sandbox_grants",
        ["sandbox_provider_config_id"],
        unique=False,
    )
    op.create_index(
        "ix_unq_sandbox_grants_ext_id_org_id",
        "sandbox_grants",
        ["external_id", "organization_id"],
        unique=True,
    )
    _create_table(
        "telephony_phone_numbers",
        sa.Column("number", sa.Text(), nullable=False),
        sa.Column("label", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("provider_config_id", sa.UUID(), nullable=False),
        sa.Column("provider_config_revision", sa.Integer(), nullable=False),
        sa.Column("provider_reference", sa.String(length=320), nullable=True),
        sa.Column("provisioning_failure_code", sa.String(length=128), nullable=True),
        sa.Column("inbound_agent_id", sa.UUID(), nullable=True),
        sa.Column("outbound_agent_id", sa.UUID(), nullable=True),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("external_id", sa.String(length=320), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(status = 'PROVISIONING' AND provider_reference IS NULL AND provisioning_failure_code IS NULL) OR (status = 'PROVISIONING_UNKNOWN' AND provisioning_failure_code IS NOT NULL) OR (status = 'PROVISIONING_FAILED' AND provisioning_failure_code IS NOT NULL) OR (status IN ('ACTIVE', 'INACTIVE') AND provisioning_failure_code IS NULL)",
            name="ck_telephony_phone_numbers_provisioning_state",
        ),
        sa.CheckConstraint(
            "provisioning_failure_code IS NULL OR provisioning_failure_code ~ '^[a-z][a-z0-9_.-]*$'",
            name="ck_telephony_phone_numbers_failure_code",
        ),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'INACTIVE', 'PROVISIONING', 'PROVISIONING_UNKNOWN', 'PROVISIONING_FAILED')",
            name="ck_telephony_phone_numbers_status",
        ),
        sa.CheckConstraint(
            "provider_config_revision > 0",
            name="ck_telephony_phone_numbers_provider_config_revision_positive",
        ),
        sa.ForeignKeyConstraint(
            ["inbound_agent_id"], ["agent_agents.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organization_organizations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["outbound_agent_id"], ["agent_agents.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["provider_config_id", "provider_config_revision", "organization_id"],
            [
                "provider_config_revisions.provider_config_id",
                "provider_config_revisions.revision",
                "provider_config_revisions.organization_id",
            ],
            name="fk_telephony_phone_numbers_provider_config_revision_org",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("number"),
    )
    op.create_index(
        op.f("ix_telephony_phone_numbers_created_at"),
        "telephony_phone_numbers",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_telephony_phone_numbers_organization_id"),
        "telephony_phone_numbers",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_telephony_phone_numbers_provider_config_id"),
        "telephony_phone_numbers",
        ["provider_config_id"],
        unique=False,
    )
    op.create_index(
        "ix_unq_telephony_phone_numbers_ext_id_org_id",
        "telephony_phone_numbers",
        ["external_id", "organization_id"],
        unique=True,
    )
    _create_table(
        "agent_revision_background_agents",
        sa.Column("agent_id", sa.UUID(), nullable=False),
        sa.Column("agent_revision", sa.Integer(), nullable=False),
        sa.Column("background_agent_id", sa.UUID(), nullable=False),
        sa.Column("background_agent_revision", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "agent_id <> background_agent_id",
            name="ck_agent_revision_background_agents_not_self",
        ),
        sa.CheckConstraint(
            "agent_revision > 0 AND background_agent_revision > 0",
            name="ck_agent_revision_background_agents_revisions_positive",
        ),
        sa.ForeignKeyConstraint(
            ["agent_id", "agent_revision", "organization_id"],
            [
                "agent_definition_revisions.agent_id",
                "agent_definition_revisions.revision",
                "agent_definition_revisions.organization_id",
            ],
            name="fk_agent_revision_background_agents_owner",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["background_agent_id", "background_agent_revision", "organization_id"],
            [
                "agent_definition_revisions.agent_id",
                "agent_definition_revisions.revision",
                "agent_definition_revisions.organization_id",
            ],
            name="fk_agent_revision_background_agents_target",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("agent_id", "agent_revision", "background_agent_id"),
    )
    op.create_index(
        op.f("ix_agent_revision_background_agents_created_at"),
        "agent_revision_background_agents",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_agent_revision_background_agents_organization_id"),
        "agent_revision_background_agents",
        ["organization_id"],
        unique=False,
    )
    _create_table(
        "agent_revision_tools",
        sa.Column("agent_id", sa.UUID(), nullable=False),
        sa.Column("agent_revision", sa.Integer(), nullable=False),
        sa.Column("tool_id", sa.UUID(), nullable=True),
        sa.Column("tool_revision", sa.Integer(), nullable=True),
        sa.Column("curated_tool_id", sa.UUID(), nullable=True),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(tool_id IS NOT NULL AND tool_revision IS NOT NULL AND curated_tool_id IS NULL) OR (tool_id IS NULL AND tool_revision IS NULL AND curated_tool_id IS NOT NULL)",
            name="ck_agent_revision_tools_exact_tool",
        ),
        sa.CheckConstraint(
            "agent_revision > 0 AND (tool_revision IS NULL OR tool_revision > 0)",
            name="ck_agent_revision_tools_revisions_positive",
        ),
        sa.ForeignKeyConstraint(
            ["agent_id", "agent_revision", "organization_id"],
            [
                "agent_definition_revisions.agent_id",
                "agent_definition_revisions.revision",
                "agent_definition_revisions.organization_id",
            ],
            name="fk_agent_revision_tools_agent_revision",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["curated_tool_id", "organization_id"],
            ["integration_v2_tools.id", "integration_v2_tools.organization_id"],
            name="fk_agent_revision_tools_curated_tool_organization",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tool_id", "tool_revision", "organization_id"],
            [
                "tool_definition_revisions.tool_id",
                "tool_definition_revisions.revision",
                "tool_definition_revisions.organization_id",
            ],
            name="fk_agent_revision_tools_tool_revision",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "agent_id",
            "agent_revision",
            "curated_tool_id",
            name="uq_agent_revision_tools_agent_revision_curated_tool",
        ),
        sa.UniqueConstraint("agent_id", "agent_revision", "tool_id"),
    )
    op.create_index(
        op.f("ix_agent_revision_tools_created_at"),
        "agent_revision_tools",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_agent_revision_tools_organization_id"),
        "agent_revision_tools",
        ["organization_id"],
        unique=False,
    )
    _create_table(
        "agent_swarm_revision_members",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("swarm_id", sa.UUID(), nullable=False),
        sa.Column("swarm_revision", sa.Integer(), nullable=False),
        sa.Column("agent_id", sa.UUID(), nullable=False),
        sa.Column("agent_revision", sa.Integer(), nullable=False),
        sa.Column("agent_description", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "agent_description IS NULL OR length(agent_description) BETWEEN 1 AND 2000",
            name="ck_agent_swarm_revision_members_description",
        ),
        sa.CheckConstraint(
            "swarm_revision > 0 AND agent_revision > 0",
            name="ck_agent_swarm_revision_members_revisions_positive",
        ),
        sa.ForeignKeyConstraint(
            ["agent_id", "agent_revision", "organization_id"],
            [
                "agent_definition_revisions.agent_id",
                "agent_definition_revisions.revision",
                "agent_definition_revisions.organization_id",
            ],
            name="fk_agent_swarm_revision_members_agent_revision",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["swarm_id", "swarm_revision", "organization_id"],
            [
                "agent_swarm_revisions.swarm_id",
                "agent_swarm_revisions.revision",
                "agent_swarm_revisions.organization_id",
            ],
            name="fk_agent_swarm_revision_members_swarm_revision",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "swarm_id",
            "swarm_revision",
            "agent_id",
            name="uq_agent_swarm_revision_members_agent",
        ),
    )
    op.create_index(
        op.f("ix_agent_swarm_revision_members_created_at"),
        "agent_swarm_revision_members",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_agent_swarm_revision_members_organization_id"),
        "agent_swarm_revision_members",
        ["organization_id"],
        unique=False,
    )
    _create_table(
        "auth_widget_invitations",
        sa.Column("contact_id", sa.UUID(), nullable=False),
        sa.Column("agent_id", sa.UUID(), nullable=False),
        sa.Column("agent_revision", sa.Integer(), nullable=False),
        sa.Column("token_digest", sa.String(length=64), nullable=False),
        sa.Column("opener", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("issued_by_kind", sa.String(length=16), nullable=False),
        sa.Column("issued_by_id", sa.UUID(), nullable=False),
        sa.Column("consumed_request_id", sa.UUID(), nullable=True),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("session_id", sa.UUID(), nullable=True),
        sa.Column("conversation_id", sa.UUID(), nullable=True),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("external_id", sa.String(length=320), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "issued_by_kind IN ('member', 'agent')",
            name="ck_auth_widget_invitations_issuer_kind",
        ),
        sa.CheckConstraint(
            "(consumed_at IS NULL AND consumed_request_id IS NULL AND session_id IS NULL AND conversation_id IS NULL) OR (consumed_at IS NOT NULL AND consumed_request_id IS NOT NULL AND session_id IS NOT NULL AND conversation_id IS NOT NULL)",
            name="ck_auth_widget_invitations_consumption_complete",
        ),
        sa.CheckConstraint(
            "agent_revision > 0",
            name="ck_auth_widget_invitations_agent_revision_positive",
        ),
        sa.CheckConstraint(
            "length(btrim(opener)) BETWEEN 1 AND 4096",
            name="ck_auth_widget_invitations_opener_length",
        ),
        sa.ForeignKeyConstraint(
            ["agent_id", "agent_revision", "organization_id"],
            [
                "agent_definition_revisions.agent_id",
                "agent_definition_revisions.revision",
                "agent_definition_revisions.organization_id",
            ],
            name="fk_auth_widget_invitations_agent_revision",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["contact_id", "organization_id"],
            ["contact_contacts.id", "contact_contacts.organization_id"],
            name="fk_auth_widget_invitations_contact_organization",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id", "organization_id"],
            [
                "conversation_conversations.id",
                "conversation_conversations.organization_id",
            ],
            name="fk_auth_widget_invitations_conversation_organization",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organization_organizations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["session_id", "organization_id"],
            ["auth_sessions.id", "auth_sessions.organization_id"],
            name="fk_auth_widget_invitations_session_organization",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("conversation_id"),
        sa.UniqueConstraint(
            "organization_id",
            "consumed_request_id",
            name="uq_auth_widget_invitations_exchange_request",
        ),
        sa.UniqueConstraint("session_id"),
        sa.UniqueConstraint("token_digest"),
    )
    op.create_index(
        "ix_auth_widget_invitations_contact_id",
        "auth_widget_invitations",
        ["contact_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_auth_widget_invitations_created_at"),
        "auth_widget_invitations",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        "ix_auth_widget_invitations_expires_at",
        "auth_widget_invitations",
        ["expires_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_auth_widget_invitations_organization_id"),
        "auth_widget_invitations",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "ix_unq_auth_widget_invitations_ext_id_org_id",
        "auth_widget_invitations",
        ["external_id", "organization_id"],
        unique=True,
    )
    _create_table(
        "campaign_campaigns",
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column(
            "channel", sa.String(length=32), server_default="voice", nullable=False
        ),
        sa.Column(
            "channel_config",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("published_revision", sa.Integer(), nullable=False),
        sa.Column("active_revision", sa.Integer(), nullable=True),
        sa.Column("agent_id", sa.Uuid(), nullable=False),
        sa.Column("agent_revision", sa.Integer(), nullable=False),
        sa.Column("initial_message_template_id", sa.Uuid(), nullable=True),
        sa.Column("initial_message_template_revision", sa.Integer(), nullable=True),
        sa.Column(
            "schedule_config", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column(
            "retry_policy", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column(
            "concurrency_limit", sa.Integer(), server_default="5", nullable=False
        ),
        sa.Column("total_contacts", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "completed_contacts", sa.Integer(), server_default="0", nullable=False
        ),
        sa.Column("failed_contacts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("external_id", sa.String(length=320), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(initial_message_template_id IS NULL AND initial_message_template_revision IS NULL) OR (initial_message_template_id IS NOT NULL AND initial_message_template_revision > 0)",
            name="ck_campaign_campaigns_template_ref",
        ),
        sa.CheckConstraint(
            "active_revision IS NULL OR active_revision > 0",
            name="ck_campaign_campaigns_active_revision_positive",
        ),
        sa.CheckConstraint(
            "agent_revision > 0", name="ck_campaign_campaigns_agent_revision_positive"
        ),
        sa.CheckConstraint(
            "published_revision > 0",
            name="ck_campaign_campaigns_published_revision_positive",
        ),
        sa.ForeignKeyConstraint(
            ["agent_id", "agent_revision", "organization_id"],
            [
                "agent_definition_revisions.agent_id",
                "agent_definition_revisions.revision",
                "agent_definition_revisions.organization_id",
            ],
            name="fk_campaign_campaigns_agent_revision",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["id", "active_revision", "organization_id"],
            [
                "campaign_revisions.campaign_id",
                "campaign_revisions.revision",
                "campaign_revisions.organization_id",
            ],
            name="fk_campaign_campaigns_active_revision",
            ondelete="RESTRICT",
            use_alter=True,
        ),
        sa.ForeignKeyConstraint(
            ["id", "published_revision", "organization_id"],
            [
                "campaign_revisions.campaign_id",
                "campaign_revisions.revision",
                "campaign_revisions.organization_id",
            ],
            name="fk_campaign_campaigns_published_revision",
            ondelete="NO ACTION",
            initially="DEFERRED",
            deferrable=True,
            use_alter=True,
        ),
        sa.ForeignKeyConstraint(
            [
                "initial_message_template_id",
                "initial_message_template_revision",
                "organization_id",
            ],
            [
                "definition_template_revisions.template_id",
                "definition_template_revisions.revision",
                "definition_template_revisions.organization_id",
            ],
            name="fk_campaign_campaigns_template_revision",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organization_organizations.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "id", "organization_id", name="uq_campaign_campaigns_id_organization_id"
        ),
    )
    op.create_index(
        "ix_campaign_campaigns_agent_id",
        "campaign_campaigns",
        ["agent_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_campaign_campaigns_created_at"),
        "campaign_campaigns",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_campaign_campaigns_organization_id"),
        "campaign_campaigns",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "ix_campaign_campaigns_status", "campaign_campaigns", ["status"], unique=False
    )
    op.create_index(
        "ix_unq_campaign_campaigns_ext_id_org_id",
        "campaign_campaigns",
        ["external_id", "organization_id"],
        unique=True,
    )
    _create_table(
        "conversation_participants",
        sa.Column("entity_kind", sa.Text(), nullable=False),
        sa.Column("entity_id", sa.Text(), nullable=False),
        sa.Column("agent_id", sa.UUID(), nullable=True),
        sa.Column("agent_revision", sa.Integer(), nullable=True),
        sa.Column("has_initiated", sa.Boolean(), nullable=False),
        sa.Column("added_by_kind", sa.Text(), nullable=True),
        sa.Column("added_by_id", sa.Text(), nullable=True),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("removed_by_kind", sa.Text(), nullable=True),
        sa.Column("removed_by_id", sa.Text(), nullable=True),
        sa.Column("left_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("conversation_id", sa.UUID(), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(entity_kind = 'AGENT' AND agent_id IS NOT NULL AND agent_revision > 0 AND entity_id = agent_id::text) OR (entity_kind <> 'AGENT' AND agent_id IS NULL AND agent_revision IS NULL)",
            name="ck_conversation_participants_exact_agent_ref",
        ),
        sa.ForeignKeyConstraint(
            ["agent_id", "agent_revision"],
            [
                "agent_definition_revisions.agent_id",
                "agent_definition_revisions.revision",
            ],
            name="fk_conversation_participants_agent_revision",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversation_conversations.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_conversation_participants_created_at"),
        "conversation_participants",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        "ix_participant_conversation_id",
        "conversation_participants",
        ["conversation_id"],
        unique=False,
    )
    _create_table(
        "knowledge_ingestion_jobs",
        sa.Column("knowledgebase_id", sa.UUID(), nullable=False),
        sa.Column("user_session_id", sa.UUID(), nullable=True),
        sa.Column("document_key", sa.Text(), nullable=False),
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("scope", sa.String(length=32), nullable=False),
        sa.Column("scope_id", sa.String(length=64), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("storage_key", sa.Text(), nullable=True),
        sa.Column("storage_provider_config_id", sa.UUID(), nullable=True),
        sa.Column("storage_provider_config_revision", sa.Integer(), nullable=True),
        sa.Column("storage_provider", sa.String(length=64), nullable=True),
        sa.Column(
            "storage_authority",
            postgresql.JSONB(astext_type=sa.Text(), none_as_null=True),
            nullable=True,
        ),
        sa.Column("embedding_provider_config_id", sa.UUID(), nullable=True),
        sa.Column("embedding_provider_config_revision", sa.Integer(), nullable=True),
        sa.Column("embedding_provider", sa.String(length=64), nullable=True),
        sa.Column("embedding_endpoint", sa.Text(), nullable=True),
        sa.Column("embedding_model", sa.String(length=255), nullable=True),
        sa.Column("embedding_dimensions", sa.Integer(), nullable=True),
        sa.Column(
            "embedding_semantic_options",
            postgresql.JSONB(none_as_null=True, astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("embedding_space_id", sa.String(length=64), nullable=True),
        sa.Column("corpus_import_id", sa.UUID(), nullable=True),
        sa.Column("title", sa.String(length=512), nullable=True),
        sa.Column("source_uri", sa.Text(), nullable=True),
        sa.Column("meta", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("external_id", sa.String(length=320), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "state",
            postgresql.ENUM(
                "pending",
                "running",
                "succeeded",
                "failed",
                "cancelled",
                name="knowledge_ingestion_state_enum",
            ),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("absurd_task_id", sa.UUID(), nullable=True),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "(content IS NOT NULL AND storage_key IS NULL AND storage_provider_config_id IS NULL AND storage_provider_config_revision IS NULL AND storage_provider IS NULL AND storage_authority IS NULL) OR (content IS NULL AND storage_key IS NOT NULL AND storage_provider_config_id IS NOT NULL AND storage_provider_config_revision IS NOT NULL AND storage_provider IS NOT NULL AND storage_authority IS NOT NULL)",
            name="ck_knowledge_ingestion_jobs_one_source",
        ),
        sa.CheckConstraint(
            "(embedding_provider_config_id IS NULL AND embedding_provider_config_revision IS NULL AND embedding_provider IS NULL AND embedding_endpoint IS NULL AND embedding_model IS NULL AND embedding_dimensions IS NULL AND embedding_semantic_options IS NULL AND embedding_space_id IS NULL) OR (embedding_provider_config_id IS NOT NULL AND embedding_provider_config_revision IS NOT NULL AND embedding_provider IS NOT NULL AND embedding_endpoint IS NOT NULL AND embedding_model IS NOT NULL AND embedding_dimensions IS NOT NULL AND embedding_semantic_options IS NOT NULL AND embedding_space_id IS NOT NULL)",
            name="ck_knowledge_jobs_embedding_space",
        ),
        sa.ForeignKeyConstraint(
            ["corpus_import_id", "organization_id"],
            ["knowledge_corpus_imports.id", "knowledge_corpus_imports.organization_id"],
            name="fk_knowledge_jobs_corpus_import_organization",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["embedding_provider_config_id", "embedding_provider_config_revision"],
            [
                "provider_config_revisions.provider_config_id",
                "provider_config_revisions.revision",
            ],
            name="fk_knowledge_jobs_embedding_config_revision",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["embedding_provider_config_id", "organization_id"],
            ["provider_configs.id", "provider_configs.organization_id"],
            name="fk_knowledge_jobs_embedding_config_organization",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["knowledgebase_id", "organization_id"],
            ["knowledgebases.id", "knowledgebases.organization_id"],
            name="fk_knowledge_jobs_knowledgebase_organization",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_session_id", "organization_id"],
            ["user_sessions.id", "user_sessions.organization_id"],
            name="fk_knowledge_jobs_user_session_organization",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organization_organizations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["storage_provider_config_id", "organization_id"],
            ["provider_configs.id", "provider_configs.organization_id"],
            name="fk_knowledge_jobs_storage_config_organization",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["storage_provider_config_id", "storage_provider_config_revision"],
            [
                "provider_config_revisions.provider_config_id",
                "provider_config_revisions.revision",
            ],
            name="fk_knowledge_jobs_storage_config_revision",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("absurd_task_id"),
        sa.UniqueConstraint(
            "id",
            "organization_id",
            name="uq_knowledge_ingestion_jobs_id_organization_id",
        ),
    )
    op.create_index(
        op.f("ix_knowledge_ingestion_jobs_corpus_import_id"),
        "knowledge_ingestion_jobs",
        ["corpus_import_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_knowledge_ingestion_jobs_created_at"),
        "knowledge_ingestion_jobs",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_knowledge_ingestion_jobs_embedding_provider_config_id"),
        "knowledge_ingestion_jobs",
        ["embedding_provider_config_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_knowledge_ingestion_jobs_embedding_space_id"),
        "knowledge_ingestion_jobs",
        ["embedding_space_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_knowledge_ingestion_jobs_knowledgebase_id"),
        "knowledge_ingestion_jobs",
        ["knowledgebase_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_knowledge_ingestion_jobs_organization_id"),
        "knowledge_ingestion_jobs",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_knowledge_ingestion_jobs_state"),
        "knowledge_ingestion_jobs",
        ["state"],
        unique=False,
    )
    op.create_index(
        op.f("ix_knowledge_ingestion_jobs_storage_provider_config_id"),
        "knowledge_ingestion_jobs",
        ["storage_provider_config_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_knowledge_ingestion_jobs_user_session_id"),
        "knowledge_ingestion_jobs",
        ["user_session_id"],
        unique=False,
    )
    op.create_index(
        "ix_unq_knowledge_ingestion_jobs_ext_id_org_id",
        "knowledge_ingestion_jobs",
        ["external_id", "organization_id"],
        unique=True,
    )
    op.create_index(
        "uq_knowledge_ingestion_jobs_active_document",
        "knowledge_ingestion_jobs",
        ["knowledgebase_id", "document_id"],
        unique=True,
        postgresql_where=sa.text(
            "state IN ('pending', 'running') AND deleted IS FALSE"
        ),
    )
    _create_table(
        "memory_reconciliation_cursors",
        sa.Column(
            "scope_level",
            postgresql.ENUM("agent", "user", "conversation", name="memory_level_enum"),
            nullable=False,
        ),
        sa.Column("owner_id", sa.UUID(), nullable=False),
        sa.Column("agent_id", sa.UUID(), nullable=True),
        sa.Column("contact_id", sa.UUID(), nullable=True),
        sa.Column("conversation_id", sa.UUID(), nullable=True),
        sa.Column("memory_provider_config_id", sa.UUID(), nullable=False),
        sa.Column("memory_provider_config_revision", sa.Integer(), nullable=False),
        sa.Column("embedding_provider_config_id", sa.UUID(), nullable=False),
        sa.Column("embedding_provider_config_revision", sa.Integer(), nullable=False),
        sa.Column("embedding_provider", sa.String(length=64), nullable=False),
        sa.Column("embedding_endpoint", sa.Text(), nullable=False),
        sa.Column("embedding_model", sa.String(length=255), nullable=False),
        sa.Column("embedding_dimensions", sa.Integer(), nullable=False),
        sa.Column(
            "embedding_semantic_options",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("embedding_space_id", sa.String(length=64), nullable=False),
        sa.Column("reconciliation_llm_provider_config_id", sa.UUID(), nullable=False),
        sa.Column(
            "reconciliation_llm_provider_config_revision", sa.Integer(), nullable=False
        ),
        sa.Column("reconciliation_llm_provider", sa.String(length=64), nullable=False),
        sa.Column("reconciliation_llm_model", sa.String(length=255), nullable=False),
        sa.Column(
            "reconciliation_prompt_revision", sa.String(length=64), nullable=False
        ),
        sa.Column(
            "requested_through_created_at", sa.DateTime(timezone=True), nullable=False
        ),
        sa.Column("requested_through_change_id", sa.UUID(), nullable=False),
        sa.Column(
            "processed_through_created_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column("processed_through_change_id", sa.UUID(), nullable=True),
        sa.Column("active_job_id", sa.UUID(), nullable=True),
        sa.Column(
            "next_generation", sa.Integer(), server_default=sa.text("1"), nullable=False
        ),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("external_id", sa.String(length=320), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(scope_level = 'agent' AND owner_id = agent_id AND agent_id IS NOT NULL AND contact_id IS NULL AND conversation_id IS NULL) OR (scope_level = 'user' AND owner_id = contact_id AND contact_id IS NOT NULL AND agent_id IS NULL AND conversation_id IS NULL) OR (scope_level = 'conversation' AND owner_id = conversation_id AND conversation_id IS NOT NULL AND agent_id IS NULL AND contact_id IS NULL)",
            name="ck_memory_reconciliation_cursors_exact_owner",
        ),
        sa.CheckConstraint(
            "(processed_through_created_at IS NULL AND processed_through_change_id IS NULL) OR (processed_through_created_at IS NOT NULL AND processed_through_change_id IS NOT NULL)",
            name="ck_memory_reconciliation_cursors_processed_pair",
        ),
        sa.CheckConstraint(
            "next_generation > 0 AND embedding_dimensions > 0",
            name="ck_memory_reconciliation_cursors_positive",
        ),
        sa.CheckConstraint(
            "processed_through_created_at IS NULL OR ROW(requested_through_created_at, requested_through_change_id) >= ROW(processed_through_created_at, processed_through_change_id)",
            name="ck_memory_reconciliation_cursors_watermark_order",
        ),
        sa.ForeignKeyConstraint(
            ["active_job_id", "organization_id"],
            [
                "memory_reconciliation_jobs.id",
                "memory_reconciliation_jobs.organization_id",
            ],
            name="fk_memory_reconciliation_cursors_active_job_organization",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["agent_id", "organization_id"],
            ["agent_agents.id", "agent_agents.organization_id"],
            name="fk_memory_reconciliation_cursors_agent_organization",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["contact_id", "organization_id"],
            ["contact_contacts.id", "contact_contacts.organization_id"],
            name="fk_memory_reconciliation_cursors_contact_organization",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id", "organization_id"],
            [
                "conversation_conversations.id",
                "conversation_conversations.organization_id",
            ],
            name="fk_memory_reconciliation_cursors_conversation_organization",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["embedding_provider_config_id", "embedding_provider_config_revision"],
            [
                "provider_config_revisions.provider_config_id",
                "provider_config_revisions.revision",
            ],
            name="fk_memory_reconciliation_cursors_embedding_config_revision",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["embedding_provider_config_id", "organization_id"],
            ["provider_configs.id", "provider_configs.organization_id"],
            name="fk_memory_reconciliation_cursors_embedding_config_organization",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["memory_provider_config_id", "memory_provider_config_revision"],
            [
                "provider_config_revisions.provider_config_id",
                "provider_config_revisions.revision",
            ],
            name="fk_memory_reconciliation_cursors_memory_config_revision",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["memory_provider_config_id", "organization_id"],
            ["provider_configs.id", "provider_configs.organization_id"],
            name="fk_memory_reconciliation_cursors_memory_config_organization",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organization_organizations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["reconciliation_llm_provider_config_id", "organization_id"],
            ["provider_configs.id", "provider_configs.organization_id"],
            name="fk_memory_reconciliation_cursors_llm_config_organization",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            [
                "reconciliation_llm_provider_config_id",
                "reconciliation_llm_provider_config_revision",
            ],
            [
                "provider_config_revisions.provider_config_id",
                "provider_config_revisions.revision",
            ],
            name="fk_memory_reconciliation_cursors_llm_config_revision",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "memory_provider_config_id",
            "scope_level",
            "owner_id",
            name="uq_memory_reconciliation_cursors_partition",
        ),
    )
    op.create_index(
        op.f("ix_memory_reconciliation_cursors_active_job_id"),
        "memory_reconciliation_cursors",
        ["active_job_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_memory_reconciliation_cursors_agent_id"),
        "memory_reconciliation_cursors",
        ["agent_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_memory_reconciliation_cursors_contact_id"),
        "memory_reconciliation_cursors",
        ["contact_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_memory_reconciliation_cursors_conversation_id"),
        "memory_reconciliation_cursors",
        ["conversation_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_memory_reconciliation_cursors_created_at"),
        "memory_reconciliation_cursors",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_memory_reconciliation_cursors_embedding_provider_config_id"),
        "memory_reconciliation_cursors",
        ["embedding_provider_config_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_memory_reconciliation_cursors_embedding_space_id"),
        "memory_reconciliation_cursors",
        ["embedding_space_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_memory_reconciliation_cursors_memory_provider_config_id"),
        "memory_reconciliation_cursors",
        ["memory_provider_config_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_memory_reconciliation_cursors_organization_id"),
        "memory_reconciliation_cursors",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_memory_reconciliation_cursors_owner_id"),
        "memory_reconciliation_cursors",
        ["owner_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_memory_reconciliation_cursors_reconciliation_llm_provider_config_id"),
        "memory_reconciliation_cursors",
        ["reconciliation_llm_provider_config_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_memory_reconciliation_cursors_scope_level"),
        "memory_reconciliation_cursors",
        ["scope_level"],
        unique=False,
    )
    op.create_index(
        "ix_unq_memory_reconciliation_cursors_ext_id_org_id",
        "memory_reconciliation_cursors",
        ["external_id", "organization_id"],
        unique=True,
    )
    _create_table(
        "memory_reconciliation_effects",
        sa.Column("reconciliation_job_id", sa.UUID(), nullable=False),
        sa.Column("inputs", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("proposal", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("outcomes", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("external_id", sa.String(length=320), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organization_organizations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["reconciliation_job_id", "organization_id"],
            [
                "memory_reconciliation_jobs.id",
                "memory_reconciliation_jobs.organization_id",
            ],
            name="fk_memory_reconciliation_effects_job_organization",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "reconciliation_job_id", name="uq_memory_reconciliation_effects_job"
        ),
    )
    op.create_index(
        op.f("ix_memory_reconciliation_effects_created_at"),
        "memory_reconciliation_effects",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_memory_reconciliation_effects_organization_id"),
        "memory_reconciliation_effects",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_memory_reconciliation_effects_reconciliation_job_id"),
        "memory_reconciliation_effects",
        ["reconciliation_job_id"],
        unique=False,
    )
    op.create_index(
        "ix_unq_memory_reconciliation_effects_ext_id_org_id",
        "memory_reconciliation_effects",
        ["external_id", "organization_id"],
        unique=True,
    )
    _create_table(
        "memory_reindex_vectors",
        sa.Column("reindex_job_id", sa.UUID(), nullable=False),
        sa.Column("memory_id", sa.UUID(), nullable=False),
        sa.Column("source_state_revision", sa.Integer(), nullable=False),
        sa.Column("embedding", _VectorType(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("external_id", sa.String(length=320), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "source_state_revision > 0",
            name="ck_memory_reindex_vectors_state_revision_positive",
        ),
        sa.ForeignKeyConstraint(
            ["memory_id", "organization_id"],
            ["memory_memories.id", "memory_memories.organization_id"],
            name="fk_memory_reindex_vectors_memory_organization",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organization_organizations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["reindex_job_id", "organization_id"],
            ["memory_reindex_jobs.id", "memory_reindex_jobs.organization_id"],
            name="fk_memory_reindex_vectors_job_organization",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "reindex_job_id", "memory_id", name="uq_memory_reindex_vectors_job_memory"
        ),
    )
    op.create_index(
        op.f("ix_memory_reindex_vectors_created_at"),
        "memory_reindex_vectors",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_memory_reindex_vectors_memory_id"),
        "memory_reindex_vectors",
        ["memory_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_memory_reindex_vectors_organization_id"),
        "memory_reindex_vectors",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_memory_reindex_vectors_reindex_job_id"),
        "memory_reindex_vectors",
        ["reindex_job_id"],
        unique=False,
    )
    op.create_index(
        "ix_unq_memory_reindex_vectors_ext_id_org_id",
        "memory_reindex_vectors",
        ["external_id", "organization_id"],
        unique=True,
    )
    _create_table(
        "memory_relationships",
        sa.Column("memory_provider_config_id", sa.UUID(), nullable=False),
        sa.Column(
            "scope_level",
            postgresql.ENUM("agent", "user", "conversation", name="memory_level_enum"),
            nullable=False,
        ),
        sa.Column("owner_id", sa.UUID(), nullable=False),
        sa.Column("agent_id", sa.UUID(), nullable=True),
        sa.Column("contact_id", sa.UUID(), nullable=True),
        sa.Column("conversation_id", sa.UUID(), nullable=True),
        sa.Column(
            "kind",
            postgresql.ENUM(
                "duplicate_of",
                "superseded_by",
                "conflicts_with",
                name="memory_relationship_kind_enum",
            ),
            nullable=False,
        ),
        sa.Column("source_memory_id", sa.UUID(), nullable=False),
        sa.Column("source_state_revision", sa.Integer(), nullable=False),
        sa.Column("target_memory_id", sa.UUID(), nullable=False),
        sa.Column("target_state_revision", sa.Integer(), nullable=False),
        sa.Column("reconciliation_job_id", sa.UUID(), nullable=False),
        sa.Column(
            "evidence_change_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("external_id", sa.String(length=320), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(scope_level = 'agent' AND owner_id = agent_id AND agent_id IS NOT NULL AND contact_id IS NULL AND conversation_id IS NULL) OR (scope_level = 'user' AND owner_id = contact_id AND contact_id IS NOT NULL AND agent_id IS NULL AND conversation_id IS NULL) OR (scope_level = 'conversation' AND owner_id = conversation_id AND conversation_id IS NOT NULL AND agent_id IS NULL AND contact_id IS NULL)",
            name="ck_memory_relationships_exact_owner",
        ),
        sa.CheckConstraint(
            "source_memory_id <> target_memory_id AND source_state_revision > 0 AND target_state_revision > 0 AND jsonb_array_length(evidence_change_ids) > 0",
            name="ck_memory_relationships_exact_evidence",
        ),
        sa.ForeignKeyConstraint(
            ["agent_id", "organization_id"],
            ["agent_agents.id", "agent_agents.organization_id"],
            name="fk_memory_relationships_agent_organization",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["contact_id", "organization_id"],
            ["contact_contacts.id", "contact_contacts.organization_id"],
            name="fk_memory_relationships_contact_organization",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id", "organization_id"],
            [
                "conversation_conversations.id",
                "conversation_conversations.organization_id",
            ],
            name="fk_memory_relationships_conversation_organization",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["memory_provider_config_id", "organization_id"],
            ["provider_configs.id", "provider_configs.organization_id"],
            name="fk_memory_relationships_memory_config_organization",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organization_organizations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["reconciliation_job_id", "organization_id"],
            [
                "memory_reconciliation_jobs.id",
                "memory_reconciliation_jobs.organization_id",
            ],
            name="fk_memory_relationships_job_organization",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_memory_id", "organization_id"],
            ["memory_memories.id", "memory_memories.organization_id"],
            name="fk_memory_relationships_source_organization",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["target_memory_id", "organization_id"],
            ["memory_memories.id", "memory_memories.organization_id"],
            name="fk_memory_relationships_target_organization",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "reconciliation_job_id",
            "source_memory_id",
            "target_memory_id",
            "kind",
            name="uq_memory_relationships_job_pair_kind",
        ),
    )
    op.create_index(
        op.f("ix_memory_relationships_agent_id"),
        "memory_relationships",
        ["agent_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_memory_relationships_contact_id"),
        "memory_relationships",
        ["contact_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_memory_relationships_conversation_id"),
        "memory_relationships",
        ["conversation_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_memory_relationships_created_at"),
        "memory_relationships",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_memory_relationships_kind"),
        "memory_relationships",
        ["kind"],
        unique=False,
    )
    op.create_index(
        op.f("ix_memory_relationships_memory_provider_config_id"),
        "memory_relationships",
        ["memory_provider_config_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_memory_relationships_organization_id"),
        "memory_relationships",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_memory_relationships_owner_id"),
        "memory_relationships",
        ["owner_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_memory_relationships_reconciliation_job_id"),
        "memory_relationships",
        ["reconciliation_job_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_memory_relationships_scope_level"),
        "memory_relationships",
        ["scope_level"],
        unique=False,
    )
    op.create_index(
        op.f("ix_memory_relationships_source_memory_id"),
        "memory_relationships",
        ["source_memory_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_memory_relationships_target_memory_id"),
        "memory_relationships",
        ["target_memory_id"],
        unique=False,
    )
    op.create_index(
        "ix_unq_memory_relationships_ext_id_org_id",
        "memory_relationships",
        ["external_id", "organization_id"],
        unique=True,
    )
    _create_table(
        "sandbox_sessions",
        sa.Column("vendor_id", sa.String(length=128), nullable=True),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("image", sa.String(length=512), nullable=False),
        sa.Column("sandbox_provider_config_id", sa.UUID(), nullable=False),
        sa.Column("sandbox_provider_config_revision", sa.Integer(), nullable=False),
        sa.Column("grant_id", sa.UUID(), nullable=True),
        sa.Column("grant_revision", sa.Integer(), nullable=True),
        sa.Column(
            "effective_policy", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column(
            "state",
            postgresql.ENUM(
                "starting",
                "running",
                "paused",
                "stopped",
                "destroyed",
                name="sandbox_state_enum",
            ),
            nullable=False,
        ),
        sa.Column("agent_id", sa.UUID(), nullable=True),
        sa.Column("agent_run_id", sa.UUID(), nullable=True),
        sa.Column("workspace", sa.String(length=256), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("external_id", sa.String(length=320), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "sandbox_provider_config_revision > 0",
            name="ck_sandbox_sessions_config_revision_positive",
        ),
        sa.ForeignKeyConstraint(["agent_id"], ["agent_agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["agent_run_id", "organization_id"],
            ["agent_runs.id", "agent_runs.organization_id"],
            name="fk_sandbox_sessions_agent_run",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["grant_id"], ["sandbox_grants.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organization_organizations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["sandbox_provider_config_id", "organization_id"],
            ["provider_configs.id", "provider_configs.organization_id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["sandbox_provider_config_id", "sandbox_provider_config_revision"],
            [
                "provider_config_revisions.provider_config_id",
                "provider_config_revisions.revision",
            ],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_sandbox_sessions_agent_id"),
        "sandbox_sessions",
        ["agent_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_sandbox_sessions_agent_run_id"),
        "sandbox_sessions",
        ["agent_run_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_sandbox_sessions_created_at"),
        "sandbox_sessions",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_sandbox_sessions_expires_at"),
        "sandbox_sessions",
        ["expires_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_sandbox_sessions_grant_id"),
        "sandbox_sessions",
        ["grant_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_sandbox_sessions_organization_id"),
        "sandbox_sessions",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_sandbox_sessions_sandbox_provider_config_id"),
        "sandbox_sessions",
        ["sandbox_provider_config_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_sandbox_sessions_state"), "sandbox_sessions", ["state"], unique=False
    )
    op.create_index(
        op.f("ix_sandbox_sessions_vendor_id"),
        "sandbox_sessions",
        ["vendor_id"],
        unique=False,
    )
    op.create_index(
        "ix_unq_sandbox_sessions_ext_id_org_id",
        "sandbox_sessions",
        ["external_id", "organization_id"],
        unique=True,
    )
    op.create_index(
        "uq_sandbox_sessions_live_agent_run",
        "sandbox_sessions",
        ["agent_run_id"],
        unique=True,
        postgresql_where=sa.text(
            "agent_run_id IS NOT NULL AND state IN ('starting', 'running', 'paused') AND deleted IS FALSE"
        ),
    )
    _create_table(
        "sandbox_workspace_checkpoints",
        sa.Column("agent_run_id", sa.UUID(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("source_step_key", sa.String(length=256), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("image", sa.String(length=512), nullable=False),
        sa.Column("sandbox_provider_config_id", sa.UUID(), nullable=False),
        sa.Column("sandbox_provider_config_revision", sa.Integer(), nullable=False),
        sa.Column("grant_id", sa.UUID(), nullable=True),
        sa.Column("grant_revision", sa.Integer(), nullable=True),
        sa.Column(
            "effective_policy", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("workspace_digest", sa.String(length=64), nullable=False),
        sa.Column("byte_size", sa.BigInteger(), nullable=False),
        sa.Column("workspace_archive", sa.LargeBinary(), nullable=False),
        sa.Column(
            "tool_result", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("external_id", sa.String(length=320), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "workspace_digest ~ '^[0-9a-f]{64}$'",
            name="ck_sandbox_workspace_checkpoints_digest",
        ),
        sa.CheckConstraint(
            "byte_size > 0 AND octet_length(workspace_archive) = byte_size",
            name="ck_sandbox_workspace_checkpoints_size",
        ),
        sa.CheckConstraint(
            "grant_revision IS NULL OR grant_revision > 0",
            name="ck_sandbox_workspace_checkpoints_grant_revision_positive",
        ),
        sa.CheckConstraint(
            "length(source_step_key) BETWEEN 1 AND 256",
            name="ck_sandbox_workspace_checkpoints_step_key_size",
        ),
        sa.CheckConstraint(
            "revision > 0 AND sandbox_provider_config_revision > 0",
            name="ck_sandbox_workspace_checkpoints_revisions_positive",
        ),
        sa.ForeignKeyConstraint(
            ["agent_run_id", "organization_id"],
            ["agent_runs.id", "agent_runs.organization_id"],
            name="fk_sandbox_workspace_checkpoints_agent_run",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["grant_id"], ["sandbox_grants.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organization_organizations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["sandbox_provider_config_id", "organization_id"],
            ["provider_configs.id", "provider_configs.organization_id"],
            name="fk_sandbox_workspace_checkpoints_config_organization",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["sandbox_provider_config_id", "sandbox_provider_config_revision"],
            [
                "provider_config_revisions.provider_config_id",
                "provider_config_revisions.revision",
            ],
            name="fk_sandbox_workspace_checkpoints_config_revision",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "agent_run_id",
            "revision",
            name="uq_sandbox_workspace_checkpoints_run_revision",
        ),
        sa.UniqueConstraint(
            "agent_run_id",
            "source_step_key",
            name="uq_sandbox_workspace_checkpoints_run_step",
        ),
    )
    op.create_index(
        op.f("ix_sandbox_workspace_checkpoints_agent_run_id"),
        "sandbox_workspace_checkpoints",
        ["agent_run_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_sandbox_workspace_checkpoints_created_at"),
        "sandbox_workspace_checkpoints",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_sandbox_workspace_checkpoints_grant_id"),
        "sandbox_workspace_checkpoints",
        ["grant_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_sandbox_workspace_checkpoints_organization_id"),
        "sandbox_workspace_checkpoints",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_sandbox_workspace_checkpoints_sandbox_provider_config_id"),
        "sandbox_workspace_checkpoints",
        ["sandbox_provider_config_id"],
        unique=False,
    )
    op.create_index(
        "ix_unq_sandbox_workspace_checkpoints_ext_id_org_id",
        "sandbox_workspace_checkpoints",
        ["external_id", "organization_id"],
        unique=True,
    )
    _create_table(
        "scheduler_schedules",
        sa.Column("key", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("published_revision", sa.Integer(), nullable=False),
        sa.Column(
            "lifecycle",
            sa.String(length=16),
            server_default="published",
            nullable=False,
        ),
        sa.Column("agent_id", sa.UUID(), nullable=False),
        sa.Column("agent_revision", sa.Integer(), nullable=False),
        sa.Column("rule", sa.Text(), nullable=True),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "misfire_policy",
            postgresql.ENUM(
                "coalesce", "fire_all", name="scheduler_misfire_policy_enum"
            ),
            server_default="coalesce",
            nullable=False,
        ),
        sa.Column(
            "enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
        sa.Column("next_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_fired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("external_id", sa.String(length=320), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "lifecycle IN ('published', 'withdrawn', 'archived')",
            name="ck_scheduler_schedules_lifecycle",
        ),
        sa.CheckConstraint(
            "agent_revision > 0", name="ck_scheduler_schedules_agent_revision_positive"
        ),
        sa.CheckConstraint(
            "published_revision > 0",
            name="ck_scheduler_schedules_published_revision_positive",
        ),
        sa.ForeignKeyConstraint(
            ["agent_id", "agent_revision", "organization_id"],
            [
                "agent_definition_revisions.agent_id",
                "agent_definition_revisions.revision",
                "agent_definition_revisions.organization_id",
            ],
            name="fk_scheduler_schedules_agent_revision",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["id", "published_revision", "organization_id"],
            [
                "scheduler_schedule_revisions.schedule_id",
                "scheduler_schedule_revisions.revision",
                "scheduler_schedule_revisions.organization_id",
            ],
            name="fk_scheduler_schedules_published_revision",
            ondelete="RESTRICT",
            initially="DEFERRED",
            deferrable=True,
            use_alter=True,
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organization_organizations.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "id", "organization_id", name="uq_scheduler_schedules_id_organization_id"
        ),
        sa.UniqueConstraint(
            "organization_id", "key", name="uq_scheduler_schedules_organization_key"
        ),
    )
    op.create_index(
        op.f("ix_scheduler_schedules_agent_id"),
        "scheduler_schedules",
        ["agent_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_scheduler_schedules_created_at"),
        "scheduler_schedules",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_scheduler_schedules_next_at"),
        "scheduler_schedules",
        ["next_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_scheduler_schedules_organization_id"),
        "scheduler_schedules",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "ix_unq_scheduler_schedules_ext_id_org_id",
        "scheduler_schedules",
        ["external_id", "organization_id"],
        unique=True,
    )
    _create_table(
        "telephony_calls",
        sa.Column("call_sid", sa.String(length=256), nullable=True),
        sa.Column("stream_sid", sa.String(length=256), nullable=True),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("provider_config_id", sa.UUID(), nullable=False),
        sa.Column("provider_config_revision", sa.Integer(), nullable=False),
        sa.Column("direction", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("from_number", sa.String(length=32), nullable=True),
        sa.Column("to_number", sa.String(length=32), nullable=True),
        sa.Column("ended_reason", sa.String(length=64), nullable=True),
        sa.Column("agent_id", sa.UUID(), nullable=True),
        sa.Column("agent_revision", sa.Integer(), nullable=True),
        sa.Column("conversation_id", sa.Uuid(), nullable=True),
        sa.Column("user_session_id", sa.UUID(), nullable=True),
        sa.Column("campaign_id", sa.Uuid(), nullable=True),
        sa.Column("campaign_contact_id", sa.Uuid(), nullable=True),
        sa.Column("campaign_attempt_id", sa.Uuid(), nullable=True),
        sa.Column("phone_number_id", sa.Uuid(), nullable=True),
        sa.Column("voice_session_id", sa.UUID(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("connected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("provider_status", sa.String(length=64), nullable=True),
        sa.Column("media_claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "opener_delivery_status",
            sa.String(length=32),
            server_default="not_requested",
            nullable=False,
        ),
        sa.Column("opener_delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status_history",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("recording_id", sa.Uuid(), nullable=True),
        sa.Column("recording_url", sa.Text(), nullable=True),
        sa.Column("transcript_id", sa.Uuid(), nullable=True),
        sa.Column("transcript_url", sa.Text(), nullable=True),
        sa.Column(
            "transfer_status",
            sa.String(length=32),
            server_default="none",
            nullable=False,
        ),
        sa.Column("transfer_to", sa.String(length=255), nullable=True),
        sa.Column("transfer_reason", sa.String(length=128), nullable=True),
        sa.Column("transferred_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "transfer_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("cost_amount", sa.Numeric(precision=12, scale=4), nullable=True),
        sa.Column("cost_currency", sa.String(length=3), nullable=True),
        sa.Column(
            "latency_metrics",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "provider_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "analysis_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("external_id", sa.String(length=320), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "opener_delivery_status IN ('not_requested', 'pending', 'accepted', 'failed')",
            name="ck_telephony_calls_opener_delivery_status",
        ),
        sa.CheckConstraint(
            "(agent_id IS NULL AND agent_revision IS NULL) OR (agent_id IS NOT NULL AND agent_revision > 0)",
            name="ck_telephony_calls_agent_ref",
        ),
        sa.CheckConstraint(
            "user_session_id IS NULL OR conversation_id IS NOT NULL",
            name="ck_telephony_calls_user_session_conversation",
        ),
        sa.CheckConstraint(
            "provider_config_revision > 0",
            name="ck_telephony_calls_provider_config_revision_positive",
        ),
        sa.ForeignKeyConstraint(
            ["agent_id", "agent_revision", "organization_id"],
            [
                "agent_definition_revisions.agent_id",
                "agent_definition_revisions.revision",
                "agent_definition_revisions.organization_id",
            ],
            name="fk_telephony_calls_agent_revision",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id", "organization_id"],
            [
                "conversation_conversations.id",
                "conversation_conversations.organization_id",
            ],
            name="fk_telephony_calls_conversation_organization",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["user_session_id", "conversation_id"],
            [
                "user_session_conversations.user_session_id",
                "user_session_conversations.conversation_id",
            ],
            name="fk_telephony_calls_user_session_conversation",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organization_organizations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["provider_config_id", "provider_config_revision", "organization_id"],
            [
                "provider_config_revisions.provider_config_id",
                "provider_config_revisions.revision",
                "provider_config_revisions.organization_id",
            ],
            name="fk_telephony_calls_provider_config_revision_org",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["voice_session_id"],
            ["voice_sessions.id"],
            name="fk_telephony_calls_voice_session_id_voice_sessions",
            ondelete="SET NULL",
            use_alter=True,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("call_sid"),
        sa.UniqueConstraint(
            "id",
            "organization_id",
            "conversation_id",
            "call_sid",
            name="uq_telephony_calls_recording_owner",
        ),
        sa.UniqueConstraint(
            "id",
            "organization_id",
            "conversation_id",
            name="uq_telephony_calls_session_owner",
        ),
    )
    op.create_index(
        "ix_telephony_calls_agent_id", "telephony_calls", ["agent_id"], unique=False
    )
    op.create_index(
        "ix_telephony_calls_call_sid", "telephony_calls", ["call_sid"], unique=False
    )
    op.create_index(
        op.f("ix_telephony_calls_campaign_contact_id"),
        "telephony_calls",
        ["campaign_contact_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_telephony_calls_campaign_id"),
        "telephony_calls",
        ["campaign_id"],
        unique=False,
    )
    op.create_index(
        "ix_telephony_calls_conversation_id",
        "telephony_calls",
        ["conversation_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_telephony_calls_created_at"),
        "telephony_calls",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_telephony_calls_organization_id"),
        "telephony_calls",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_telephony_calls_phone_number_id"),
        "telephony_calls",
        ["phone_number_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_telephony_calls_provider_config_id"),
        "telephony_calls",
        ["provider_config_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_telephony_calls_recording_id"),
        "telephony_calls",
        ["recording_id"],
        unique=False,
    )
    op.create_index(
        "ix_telephony_calls_status", "telephony_calls", ["status"], unique=False
    )
    op.create_index(
        op.f("ix_telephony_calls_transcript_id"),
        "telephony_calls",
        ["transcript_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_telephony_calls_user_session_id"),
        "telephony_calls",
        ["user_session_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_telephony_calls_voice_session_id"),
        "telephony_calls",
        ["voice_session_id"],
        unique=False,
    )
    op.create_index(
        "ix_unq_telephony_calls_ext_id_org_id",
        "telephony_calls",
        ["external_id", "organization_id"],
        unique=True,
    )
    op.create_index(
        "uq_telephony_calls_campaign_attempt_id",
        "telephony_calls",
        ["campaign_attempt_id"],
        unique=True,
        postgresql_where=sa.text("campaign_attempt_id IS NOT NULL"),
    )
    _create_table(
        "campaign_revisions",
        sa.Column("campaign_id", sa.Uuid(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column(
            "channel_config",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("agent_id", sa.Uuid(), nullable=False),
        sa.Column("agent_revision", sa.Integer(), nullable=False),
        sa.Column("initial_message_template_id", sa.Uuid(), nullable=True),
        sa.Column("initial_message_template_revision", sa.Integer(), nullable=True),
        sa.Column(
            "schedule_config",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "retry_policy",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("concurrency_limit", sa.Integer(), nullable=False),
        sa.Column(
            "availability",
            sa.String(length=16),
            server_default="published",
            nullable=False,
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_by", sa.Uuid(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by", sa.Uuid(), nullable=True),
        sa.Column("revocation_reason", sa.Text(), nullable=True),
        sa.Column(
            "cancellation_requested_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("external_id", sa.String(length=320), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(availability = 'published' AND revoked_at IS NULL AND revoked_by IS NULL AND revocation_reason IS NULL AND cancellation_requested_at IS NULL) OR (availability = 'revoked' AND revoked_at IS NOT NULL AND revoked_by IS NOT NULL AND revocation_reason IS NOT NULL AND length(btrim(revocation_reason)) BETWEEN 1 AND 2000 AND cancellation_requested_at IS NOT NULL)",
            name="ck_campaign_revisions_revocation_metadata",
        ),
        sa.CheckConstraint(
            "availability IN ('published', 'revoked')",
            name="ck_campaign_revisions_availability",
        ),
        sa.CheckConstraint(
            "(initial_message_template_id IS NULL AND initial_message_template_revision IS NULL) OR (initial_message_template_id IS NOT NULL AND initial_message_template_revision > 0)",
            name="ck_campaign_revisions_template_ref",
        ),
        sa.CheckConstraint(
            "revision > 0 AND agent_revision > 0",
            name="ck_campaign_revisions_revisions_positive",
        ),
        sa.ForeignKeyConstraint(
            ["agent_id", "agent_revision", "organization_id"],
            [
                "agent_definition_revisions.agent_id",
                "agent_definition_revisions.revision",
                "agent_definition_revisions.organization_id",
            ],
            name="fk_campaign_revisions_agent_revision",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["campaign_id", "organization_id"],
            ["campaign_campaigns.id", "campaign_campaigns.organization_id"],
            name="fk_campaign_revisions_header_organization",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            [
                "initial_message_template_id",
                "initial_message_template_revision",
                "organization_id",
            ],
            [
                "definition_template_revisions.template_id",
                "definition_template_revisions.revision",
                "definition_template_revisions.organization_id",
            ],
            name="fk_campaign_revisions_template_revision",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organization_organizations.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "campaign_id",
            "revision",
            "organization_id",
            name="uq_campaign_revisions_ref_organization",
        ),
        sa.UniqueConstraint(
            "campaign_id", "revision", name="uq_campaign_revisions_ref"
        ),
    )
    op.create_index(
        op.f("ix_campaign_revisions_agent_id"),
        "campaign_revisions",
        ["agent_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_campaign_revisions_campaign_id"),
        "campaign_revisions",
        ["campaign_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_campaign_revisions_created_at"),
        "campaign_revisions",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_campaign_revisions_organization_id"),
        "campaign_revisions",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "ix_unq_campaign_revisions_ext_id_org_id",
        "campaign_revisions",
        ["external_id", "organization_id"],
        unique=True,
    )
    _create_table(
        "scheduler_schedule_revisions",
        sa.Column("schedule_id", sa.UUID(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("rule", sa.Text(), nullable=True),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "misfire_policy",
            postgresql.ENUM(
                "coalesce", "fire_all", name="scheduler_misfire_policy_enum"
            ),
            nullable=False,
        ),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("agent_id", sa.UUID(), nullable=False),
        sa.Column("agent_revision", sa.Integer(), nullable=False),
        sa.Column(
            "availability",
            sa.String(length=16),
            server_default="published",
            nullable=False,
        ),
        sa.Column(
            "published_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("published_by", sa.UUID(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by", sa.UUID(), nullable=True),
        sa.Column("revocation_reason", sa.Text(), nullable=True),
        sa.Column(
            "cancellation_requested_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("external_id", sa.String(length=320), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(availability = 'published' AND revoked_at IS NULL AND revoked_by IS NULL AND revocation_reason IS NULL AND cancellation_requested_at IS NULL) OR (availability = 'revoked' AND revoked_at IS NOT NULL AND revoked_by IS NOT NULL AND revocation_reason IS NOT NULL AND length(btrim(revocation_reason)) BETWEEN 1 AND 2000 AND cancellation_requested_at IS NOT NULL)",
            name="ck_scheduler_schedule_revisions_revocation_metadata",
        ),
        sa.CheckConstraint(
            "availability IN ('published', 'revoked')",
            name="ck_scheduler_schedule_revisions_availability",
        ),
        sa.CheckConstraint(
            "agent_revision > 0",
            name="ck_scheduler_schedule_revisions_agent_revision_positive",
        ),
        sa.CheckConstraint(
            "revision > 0", name="ck_scheduler_schedule_revisions_revision_positive"
        ),
        sa.ForeignKeyConstraint(
            ["agent_id", "agent_revision", "organization_id"],
            [
                "agent_definition_revisions.agent_id",
                "agent_definition_revisions.revision",
                "agent_definition_revisions.organization_id",
            ],
            name="fk_scheduler_schedule_revisions_agent_revision",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organization_organizations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["schedule_id", "organization_id"],
            ["scheduler_schedules.id", "scheduler_schedules.organization_id"],
            name="fk_scheduler_schedule_revisions_header_organization",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "schedule_id",
            "revision",
            "organization_id",
            name="uq_scheduler_schedule_revisions_ref_organization",
        ),
        sa.UniqueConstraint(
            "schedule_id", "revision", name="uq_scheduler_schedule_revisions_ref"
        ),
    )
    op.create_index(
        op.f("ix_scheduler_schedule_revisions_agent_id"),
        "scheduler_schedule_revisions",
        ["agent_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_scheduler_schedule_revisions_created_at"),
        "scheduler_schedule_revisions",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_scheduler_schedule_revisions_organization_id"),
        "scheduler_schedule_revisions",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_scheduler_schedule_revisions_schedule_id"),
        "scheduler_schedule_revisions",
        ["schedule_id"],
        unique=False,
    )
    op.create_index(
        "ix_unq_scheduler_schedule_revisions_ext_id_org_id",
        "scheduler_schedule_revisions",
        ["external_id", "organization_id"],
        unique=True,
    )
    _create_table(
        "voice_sessions",
        sa.Column("conversation_id", sa.UUID(), nullable=False),
        sa.Column("user_session_id", sa.UUID(), nullable=True),
        sa.Column("agent_id", sa.UUID(), nullable=True),
        sa.Column("agent_revision", sa.Integer(), nullable=True),
        sa.Column("session_id", sa.String(length=255), nullable=False),
        sa.Column("runtime_mode", sa.String(length=64), nullable=False),
        sa.Column("transport", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("canonical_state", sa.String(length=32), nullable=False),
        sa.Column("canonical_redaction_version", sa.Integer(), nullable=True),
        sa.Column("canonical_failure_code", sa.String(length=64), nullable=True),
        sa.Column("canonical_source_complete", sa.Boolean(), nullable=True),
        sa.Column("canonical_projected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("canonical_message_count", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_reason", sa.String(length=64), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("user_audio_recording_id", sa.UUID(), nullable=True),
        sa.Column("assistant_audio_recording_id", sa.UUID(), nullable=True),
        sa.Column("combined_audio_recording_id", sa.UUID(), nullable=True),
        sa.Column("user_audio_url", sa.Text(), nullable=True),
        sa.Column("assistant_audio_url", sa.Text(), nullable=True),
        sa.Column("combined_audio_url", sa.Text(), nullable=True),
        sa.Column("audio_format", sa.String(length=64), nullable=True),
        sa.Column("stt_vendor", sa.String(length=128), nullable=True),
        sa.Column("stt_model", sa.String(length=128), nullable=True),
        sa.Column("tts_vendor", sa.String(length=128), nullable=True),
        sa.Column("tts_model", sa.String(length=128), nullable=True),
        sa.Column("tts_voice", sa.String(length=128), nullable=True),
        sa.Column("realtime_vendor", sa.String(length=128), nullable=True),
        sa.Column("realtime_model", sa.String(length=128), nullable=True),
        sa.Column("telephony_call_id", sa.UUID(), nullable=True),
        sa.Column("provider_call_id", sa.String(length=255), nullable=True),
        sa.Column("telephony_provider", sa.String(length=64), nullable=True),
        sa.Column("from_number", sa.String(length=64), nullable=True),
        sa.Column("to_number", sa.String(length=64), nullable=True),
        sa.Column("recording_enabled", sa.Boolean(), nullable=False),
        sa.Column("recording_consent", sa.String(length=32), nullable=True),
        sa.Column("segment_count", sa.Integer(), nullable=False),
        sa.Column("partial_segment_count", sa.Integer(), nullable=False),
        sa.Column("user_talk_time_ms", sa.Integer(), nullable=True),
        sa.Column("assistant_talk_time_ms", sa.Integer(), nullable=True),
        sa.Column("silence_time_ms", sa.Integer(), nullable=True),
        sa.Column("interruption_count", sa.Integer(), nullable=False),
        sa.Column("dtmf_count", sa.Integer(), nullable=False),
        sa.Column("transfer_count", sa.Integer(), nullable=False),
        sa.Column("metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("meta", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("external_id", sa.String(length=320), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "canonical_state IN ('not_run', 'clean', 'redacted', 'failed', 'no_storage')",
            name="ck_voice_sessions_canonical_state",
        ),
        sa.CheckConstraint(
            "(agent_id IS NULL AND agent_revision IS NULL) OR (agent_id IS NOT NULL AND agent_revision > 0)",
            name="ck_voice_sessions_agent_ref",
        ),
        sa.CheckConstraint(
            "canonical_message_count >= 0",
            name="ck_voice_sessions_canonical_message_count",
        ),
        sa.CheckConstraint(
            "canonical_redaction_version IS NULL OR canonical_redaction_version > 0",
            name="ck_voice_sessions_canonical_redaction_version",
        ),
        sa.CheckConstraint(
            "ended_reason IS NULL OR length(btrim(ended_reason)) > 0",
            name="ck_voice_sessions_ended_reason",
        ),
        sa.CheckConstraint(
            "(status = 'active' AND ended_at IS NULL "
            "AND ended_reason IS NULL AND duration_ms IS NULL) OR "
            "(status IN ('completed', 'failed') AND ended_at IS NOT NULL "
            "AND ended_reason IS NOT NULL AND duration_ms >= 0)",
            name="ck_voice_sessions_terminal_state",
        ),
        sa.ForeignKeyConstraint(
            ["agent_id", "agent_revision", "organization_id"],
            [
                "agent_definition_revisions.agent_id",
                "agent_definition_revisions.revision",
                "agent_definition_revisions.organization_id",
            ],
            name="fk_voice_sessions_agent_revision",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"], ["conversation_conversations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["user_session_id", "conversation_id"],
            [
                "user_session_conversations.user_session_id",
                "user_session_conversations.conversation_id",
            ],
            name="fk_voice_sessions_user_session_conversation",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organization_organizations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["telephony_call_id", "organization_id", "conversation_id"],
            [
                "telephony_calls.id",
                "telephony_calls.organization_id",
                "telephony_calls.conversation_id",
            ],
            name="fk_voice_sessions_call_owner",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "id",
            "organization_id",
            "conversation_id",
            "session_id",
            name="uq_voice_sessions_recording_owner",
        ),
        sa.UniqueConstraint(
            "id",
            "organization_id",
            "conversation_id",
            name="uq_voice_sessions_segment_owner",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "session_id",
            "runtime_mode",
            name="uq_voice_sessions_org_session_mode",
        ),
    )
    op.create_index(
        "ix_unq_voice_sessions_ext_id_org_id",
        "voice_sessions",
        ["external_id", "organization_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_voice_sessions_conversation_id"),
        "voice_sessions",
        ["conversation_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_voice_sessions_created_at"),
        "voice_sessions",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        "ix_voice_sessions_org_agent_started",
        "voice_sessions",
        ["organization_id", "agent_id", "started_at"],
        unique=False,
    )
    op.create_index(
        "ix_voice_sessions_org_conversation",
        "voice_sessions",
        ["organization_id", "conversation_id"],
        unique=False,
    )
    op.create_index(
        "ix_voice_sessions_org_started",
        "voice_sessions",
        ["organization_id", "started_at"],
        unique=False,
    )
    op.create_index(
        "ix_voice_sessions_org_status_started",
        "voice_sessions",
        ["organization_id", "status", "started_at"],
        unique=False,
    )
    op.create_index(
        "ix_voice_sessions_org_telephony_call",
        "voice_sessions",
        ["organization_id", "telephony_call_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_voice_sessions_organization_id"),
        "voice_sessions",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_voice_sessions_session_id"),
        "voice_sessions",
        ["session_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_voice_sessions_user_session_id"),
        "voice_sessions",
        ["user_session_id"],
        unique=False,
    )
    _create_table(
        "campaign_contacts",
        sa.Column("campaign_id", sa.Uuid(), nullable=False),
        sa.Column("campaign_revision", sa.Integer(), nullable=True),
        sa.Column("contact_id", sa.Uuid(), nullable=True),
        sa.Column("contact_address", sa.String(length=256), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_tracking_id", sa.String(length=256), nullable=True),
        sa.Column("last_outcome_reason", sa.String(length=64), nullable=True),
        sa.Column("variables", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("external_id", sa.String(length=320), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "campaign_revision IS NULL OR campaign_revision > 0",
            name="ck_campaign_contacts_campaign_revision_positive",
        ),
        sa.ForeignKeyConstraint(
            ["campaign_id", "campaign_revision", "organization_id"],
            [
                "campaign_revisions.campaign_id",
                "campaign_revisions.revision",
                "campaign_revisions.organization_id",
            ],
            name="fk_campaign_contacts_campaign_revision",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["campaign_id", "organization_id"],
            ["campaign_campaigns.id", "campaign_campaigns.organization_id"],
            name="fk_campaign_contacts_campaign_organization",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["contact_id", "organization_id"],
            ["contact_contacts.id", "contact_contacts.organization_id"],
            name="fk_campaign_contacts_contact_organization",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organization_organizations.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "campaign_id",
            "contact_address",
            name="uq_campaign_contacts_campaign_address",
        ),
        sa.UniqueConstraint(
            "id",
            "campaign_id",
            "organization_id",
            name="uq_campaign_contacts_id_campaign_organization",
        ),
    )
    op.create_index(
        "ix_campaign_contacts_campaign_id",
        "campaign_contacts",
        ["campaign_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_campaign_contacts_created_at"),
        "campaign_contacts",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_campaign_contacts_organization_id"),
        "campaign_contacts",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "ix_campaign_contacts_retry",
        "campaign_contacts",
        ["campaign_id", "status", "next_retry_at"],
        unique=False,
    )
    op.create_index(
        "ix_campaign_contacts_status", "campaign_contacts", ["status"], unique=False
    )
    op.create_index(
        "ix_unq_campaign_contacts_ext_id_org_id",
        "campaign_contacts",
        ["external_id", "organization_id"],
        unique=True,
    )
    _create_table(
        "scheduler_runs",
        sa.Column("schedule_id", sa.UUID(), nullable=False),
        sa.Column("schedule_revision", sa.Integer(), nullable=False),
        sa.Column("agent_id", sa.UUID(), nullable=False),
        sa.Column("agent_revision", sa.Integer(), nullable=False),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=False),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "misfired_count", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("external_id", sa.String(length=320), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "agent_revision > 0", name="ck_scheduler_runs_agent_revision_positive"
        ),
        sa.CheckConstraint(
            "schedule_revision > 0", name="ck_scheduler_runs_schedule_revision_positive"
        ),
        sa.ForeignKeyConstraint(
            ["agent_id", "agent_revision", "organization_id"],
            [
                "agent_definition_revisions.agent_id",
                "agent_definition_revisions.revision",
                "agent_definition_revisions.organization_id",
            ],
            name="fk_scheduler_runs_agent_revision",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organization_organizations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["schedule_id", "schedule_revision", "organization_id"],
            [
                "scheduler_schedule_revisions.schedule_id",
                "scheduler_schedule_revisions.revision",
                "scheduler_schedule_revisions.organization_id",
            ],
            name="fk_scheduler_runs_schedule_revision",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "id", "organization_id", name="uq_scheduler_runs_id_organization_id"
        ),
        sa.UniqueConstraint(
            "schedule_id", "scheduled_for", name="uq_scheduler_runs_schedule_occurrence"
        ),
    )
    op.create_index(
        op.f("ix_scheduler_runs_agent_id"), "scheduler_runs", ["agent_id"], unique=False
    )
    op.create_index(
        op.f("ix_scheduler_runs_created_at"),
        "scheduler_runs",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_scheduler_runs_organization_id"),
        "scheduler_runs",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_scheduler_runs_schedule_id"),
        "scheduler_runs",
        ["schedule_id"],
        unique=False,
    )
    op.create_index(
        "ix_unq_scheduler_runs_ext_id_org_id",
        "scheduler_runs",
        ["external_id", "organization_id"],
        unique=True,
    )
    _create_table(
        "voice_recordings",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("conversation_id", sa.UUID(), nullable=False),
        sa.Column("session_id", sa.String(length=255), nullable=False),
        sa.Column("voice_session_id", sa.UUID(), nullable=False),
        sa.Column("telephony_call_id", sa.UUID(), nullable=True),
        sa.Column("user_audio_url", sa.Text(), nullable=True),
        sa.Column("agent_audio_url", sa.Text(), nullable=True),
        sa.Column("storage_provider_config_id", sa.UUID(), nullable=True),
        sa.Column("storage_provider_config_revision", sa.Integer(), nullable=True),
        sa.Column("storage_provider", sa.String(length=64), nullable=True),
        sa.Column(
            "storage_authority",
            postgresql.JSONB(astext_type=sa.Text(), none_as_null=True),
            nullable=True,
        ),
        sa.Column("user_storage_key", sa.Text(), nullable=True),
        sa.Column("agent_storage_key", sa.Text(), nullable=True),
        sa.Column("target_user_storage_key", sa.Text(), nullable=True),
        sa.Column("target_agent_storage_key", sa.Text(), nullable=True),
        sa.Column("staged_user_wav", sa.LargeBinary(), nullable=True),
        sa.Column("staged_agent_wav", sa.LargeBinary(), nullable=True),
        sa.Column("user_duration_seconds", sa.Float(), nullable=True),
        sa.Column("agent_duration_seconds", sa.Float(), nullable=True),
        sa.Column("user_sample_rate", sa.Integer(), nullable=True),
        sa.Column("agent_sample_rate", sa.Integer(), nullable=True),
        sa.Column("meta", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "state",
            postgresql.ENUM(
                "pending",
                "running",
                "succeeded",
                "failed",
                "cancelled",
                name="voice_recording_upload_state_enum",
            ),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("absurd_task_id", sa.UUID(), nullable=True),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "(staged_user_wav IS NULL OR target_user_storage_key IS NOT NULL) AND (staged_agent_wav IS NULL OR target_agent_storage_key IS NOT NULL)",
            name="ck_voice_recordings_staged_targets",
        ),
        sa.CheckConstraint(
            "(storage_provider_config_id IS NULL AND storage_provider_config_revision IS NULL AND storage_provider IS NULL AND storage_authority IS NULL AND user_storage_key IS NULL AND agent_storage_key IS NULL) OR (storage_provider_config_id IS NOT NULL AND storage_provider_config_revision IS NOT NULL AND ((storage_provider IS NULL AND storage_authority IS NULL AND user_storage_key IS NULL AND agent_storage_key IS NULL) OR (storage_provider IS NOT NULL AND storage_authority IS NOT NULL AND (user_storage_key IS NOT NULL OR agent_storage_key IS NOT NULL))))",
            name="ck_voice_recordings_storage_locator",
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"], ["conversation_conversations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organization_organizations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["storage_provider_config_id", "organization_id"],
            ["provider_configs.id", "provider_configs.organization_id"],
            name="fk_voice_recordings_storage_config_organization",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["storage_provider_config_id", "storage_provider_config_revision"],
            [
                "provider_config_revisions.provider_config_id",
                "provider_config_revisions.revision",
            ],
            name="fk_voice_recordings_storage_config_revision",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["telephony_call_id", "organization_id", "conversation_id", "session_id"],
            [
                "telephony_calls.id",
                "telephony_calls.organization_id",
                "telephony_calls.conversation_id",
                "telephony_calls.call_sid",
            ],
            name="fk_voice_recordings_call_owner",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["voice_session_id", "organization_id", "conversation_id", "session_id"],
            [
                "voice_sessions.id",
                "voice_sessions.organization_id",
                "voice_sessions.conversation_id",
                "voice_sessions.session_id",
            ],
            name="fk_voice_recordings_session_owner",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("absurd_task_id"),
        sa.UniqueConstraint(
            "id", "organization_id", name="uq_voice_recordings_id_organization_id"
        ),
        sa.UniqueConstraint(
            "organization_id",
            "session_id",
            name="uq_voice_recordings_organization_session",
        ),
    )
    op.create_index(
        op.f("ix_voice_recordings_conversation_id"),
        "voice_recordings",
        ["conversation_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_voice_recordings_created_at"),
        "voice_recordings",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_voice_recordings_organization_id"),
        "voice_recordings",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_voice_recordings_session_id"),
        "voice_recordings",
        ["session_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_voice_recordings_state"), "voice_recordings", ["state"], unique=False
    )
    op.create_index(
        op.f("ix_voice_recordings_storage_provider_config_id"),
        "voice_recordings",
        ["storage_provider_config_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_voice_recordings_telephony_call_id"),
        "voice_recordings",
        ["telephony_call_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_voice_recordings_voice_session_id"),
        "voice_recordings",
        ["voice_session_id"],
        unique=False,
    )
    _create_table(
        "voice_segments",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("voice_session_id", sa.UUID(), nullable=False),
        sa.Column("conversation_id", sa.UUID(), nullable=False),
        sa.Column("message_id", sa.UUID(), nullable=True),
        sa.Column("request_id", sa.UUID(), nullable=True),
        sa.Column("provider_request_id", sa.String(length=255), nullable=True),
        sa.Column("source_created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("segment_type", sa.String(length=32), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("speech_outcome", sa.String(length=32), nullable=True),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("is_partial", sa.Boolean(), nullable=False),
        sa.Column("language", sa.String(length=32), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("words", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("started_at_ms", sa.Integer(), nullable=True),
        sa.Column("ended_at_ms", sa.Integer(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("audio_track", sa.String(length=32), nullable=True),
        sa.Column("audio_start_ms", sa.Integer(), nullable=True),
        sa.Column("audio_end_ms", sa.Integer(), nullable=True),
        sa.Column("audio_start_byte", sa.Integer(), nullable=True),
        sa.Column("audio_end_byte", sa.Integer(), nullable=True),
        sa.Column("tool_name", sa.String(length=255), nullable=True),
        sa.Column("tool_call_id", sa.String(length=255), nullable=True),
        sa.Column("tool_input", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "tool_output", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column("dtmf_digits", sa.String(length=64), nullable=True),
        sa.Column("transfer_to", sa.String(length=255), nullable=True),
        sa.Column("error_code", sa.String(length=128), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("redaction_state", sa.String(length=32), nullable=False),
        sa.Column(
            "vendor_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column("meta", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"], ["conversation_conversations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["message_id"], ["conversation_messages.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organization_organizations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["voice_session_id", "organization_id", "conversation_id"],
            [
                "voice_sessions.id",
                "voice_sessions.organization_id",
                "voice_sessions.conversation_id",
            ],
            name="fk_voice_segments_session_owner",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("message_id", name="uq_voice_segments_message_id"),
        sa.UniqueConstraint(
            "voice_session_id", "sequence", name="uq_voice_segments_session_sequence"
        ),
    )
    op.create_index(
        op.f("ix_voice_segments_created_at"),
        "voice_segments",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        "ix_voice_segments_org_conversation_created",
        "voice_segments",
        ["organization_id", "conversation_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_voice_segments_org_message",
        "voice_segments",
        ["organization_id", "message_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_voice_segments_organization_id"),
        "voice_segments",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "ix_voice_segments_session_role_type",
        "voice_segments",
        ["voice_session_id", "role", "segment_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_voice_segments_voice_session_id"),
        "voice_segments",
        ["voice_session_id"],
        unique=False,
    )
    _create_table(
        "campaign_attempts",
        sa.Column("campaign_id", sa.Uuid(), nullable=False),
        sa.Column("campaign_contact_id", sa.Uuid(), nullable=False),
        sa.Column("campaign_revision", sa.Integer(), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column("effect_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("effect_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("effect_replay_safe", sa.Boolean(), nullable=True),
        sa.Column(
            "dispatch_unknown", sa.Boolean(), server_default="false", nullable=False
        ),
        sa.Column("tracking_id", sa.String(length=320), nullable=True),
        sa.Column("outcome", sa.String(length=128), nullable=True),
        sa.Column("outcome_recorded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("external_id", sa.String(length=320), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "state",
            postgresql.ENUM(
                "pending",
                "running",
                "succeeded",
                "failed",
                "cancelled",
                name="campaign_attempt_state_enum",
            ),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("absurd_task_id", sa.UUID(), nullable=True),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "(outcome IS NULL AND outcome_recorded_at IS NULL) OR (outcome IS NOT NULL AND outcome_recorded_at IS NOT NULL)",
            name="ck_campaign_attempts_outcome_pair",
        ),
        sa.CheckConstraint(
            "campaign_revision > 0 AND attempt_number > 0",
            name="ck_campaign_attempts_revisions_positive",
        ),
        sa.CheckConstraint(
            "dispatch_unknown IS FALSE OR (effect_started_at IS NOT NULL AND effect_completed_at IS NULL)",
            name="ck_campaign_attempts_unknown_effect",
        ),
        sa.CheckConstraint(
            "effect_completed_at IS NULL OR effect_started_at IS NOT NULL",
            name="ck_campaign_attempts_effect_order",
        ),
        sa.ForeignKeyConstraint(
            ["campaign_contact_id", "campaign_id", "organization_id"],
            [
                "campaign_contacts.id",
                "campaign_contacts.campaign_id",
                "campaign_contacts.organization_id",
            ],
            name="fk_campaign_attempts_contact_campaign_organization",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["campaign_id", "campaign_revision", "organization_id"],
            [
                "campaign_revisions.campaign_id",
                "campaign_revisions.revision",
                "campaign_revisions.organization_id",
            ],
            name="fk_campaign_attempts_campaign_revision",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["campaign_id", "organization_id"],
            ["campaign_campaigns.id", "campaign_campaigns.organization_id"],
            name="fk_campaign_attempts_campaign_organization",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organization_organizations.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("absurd_task_id"),
        sa.UniqueConstraint(
            "campaign_contact_id",
            "attempt_number",
            name="uq_campaign_attempts_contact_number",
        ),
    )
    op.create_index(
        "ix_campaign_attempts_campaign_state",
        "campaign_attempts",
        ["campaign_id", "state"],
        unique=False,
    )
    op.create_index(
        "ix_campaign_attempts_contact_tracking",
        "campaign_attempts",
        ["campaign_contact_id", "tracking_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_campaign_attempts_created_at"),
        "campaign_attempts",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_campaign_attempts_organization_id"),
        "campaign_attempts",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_campaign_attempts_state"), "campaign_attempts", ["state"], unique=False
    )
    op.create_index(
        "ix_unq_campaign_attempts_ext_id_org_id",
        "campaign_attempts",
        ["external_id", "organization_id"],
        unique=True,
    )
    _create_table(
        "user_sessions",
        sa.Column("contact_id", sa.UUID(), nullable=False),
        sa.Column(
            "entry_channel",
            postgresql.ENUM(
                "widget",
                "telephony",
                "api",
                name="user_session_entry_channel_enum",
            ),
            nullable=False,
        ),
        sa.Column(
            "state",
            postgresql.ENUM(
                "active",
                "disconnected",
                "ended",
                "failed",
                name="user_session_state_enum",
            ),
            server_default="active",
            nullable=False,
        ),
        sa.Column(
            "connection_sequence",
            sa.Integer(),
            server_default=sa.text("1"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("disconnected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("end_reason", sa.String(length=128), nullable=True),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("external_id", sa.String(length=320), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "connection_sequence >= 1",
            name="ck_user_sessions_connection_sequence",
        ),
        sa.CheckConstraint(
            "end_reason IS NULL OR "
            "(length(end_reason) BETWEEN 1 AND 128 "
            "AND end_reason ~ '^[a-z][a-z0-9_.-]*$')",
            name="ck_user_sessions_end_reason",
        ),
        sa.CheckConstraint(
            "last_activity_at >= started_at AND "
            "(disconnected_at IS NULL OR disconnected_at >= started_at) AND "
            "(ended_at IS NULL OR ended_at >= started_at)",
            name="ck_user_sessions_time_order",
        ),
        sa.CheckConstraint(
            "(state = 'active' AND disconnected_at IS NULL "
            "AND ended_at IS NULL AND end_reason IS NULL) OR "
            "(state = 'disconnected' AND disconnected_at IS NOT NULL "
            "AND ended_at IS NULL AND end_reason IS NULL) OR "
            "(state IN ('ended', 'failed') AND ended_at IS NOT NULL "
            "AND end_reason IS NOT NULL)",
            name="ck_user_sessions_lifecycle",
        ),
        sa.ForeignKeyConstraint(
            ["contact_id", "organization_id"],
            ["contact_contacts.id", "contact_contacts.organization_id"],
            name="fk_user_sessions_contact_organization",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organization_organizations.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "id",
            "organization_id",
            name="uq_user_sessions_id_organization_id",
        ),
    )
    op.create_index(
        op.f("ix_user_sessions_contact_id"),
        "user_sessions",
        ["contact_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_user_sessions_created_at"),
        "user_sessions",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        "ix_user_sessions_org_contact_started",
        "user_sessions",
        ["organization_id", "contact_id", "started_at"],
        unique=False,
    )
    op.create_index(
        "ix_user_sessions_org_started",
        "user_sessions",
        ["organization_id", "started_at"],
        unique=False,
    )
    op.create_index(
        "ix_user_sessions_org_state_activity",
        "user_sessions",
        ["organization_id", "state", "last_activity_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_user_sessions_organization_id"),
        "user_sessions",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_user_sessions_state"),
        "user_sessions",
        ["state"],
        unique=False,
    )
    op.create_index(
        "ix_unq_user_sessions_ext_id_org_id",
        "user_sessions",
        ["external_id", "organization_id"],
        unique=True,
    )
    _create_table(
        "user_session_conversations",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("user_session_id", sa.UUID(), nullable=False),
        sa.Column("conversation_id", sa.UUID(), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "last_seen_at >= first_seen_at",
            name="ck_user_session_conversations_time_order",
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id", "organization_id"],
            [
                "conversation_conversations.id",
                "conversation_conversations.organization_id",
            ],
            name="fk_user_session_conversations_conversation_organization",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organization_organizations.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["user_session_id", "organization_id"],
            ["user_sessions.id", "user_sessions.organization_id"],
            name="fk_user_session_conversations_session_organization",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_session_id",
            "conversation_id",
            name="uq_user_session_conversations_pair",
        ),
    )
    op.create_index(
        op.f("ix_user_session_conversations_created_at"),
        "user_session_conversations",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        "ix_user_session_conversations_org_conversation",
        "user_session_conversations",
        ["organization_id", "conversation_id"],
        unique=False,
    )
    op.create_index(
        "ix_user_session_conversations_org_session",
        "user_session_conversations",
        ["organization_id", "user_session_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_user_session_conversations_organization_id"),
        "user_session_conversations",
        ["organization_id"],
        unique=False,
    )
    _create_deferred_foreign_keys()
    _install_absurd_schema()
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP SCHEMA IF EXISTS absurd CASCADE")
    _drop_public_foreign_keys()
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(
        op.f("ix_user_session_conversations_organization_id"),
        table_name="user_session_conversations",
    )
    op.drop_index(
        "ix_user_session_conversations_org_session",
        table_name="user_session_conversations",
    )
    op.drop_index(
        "ix_user_session_conversations_org_conversation",
        table_name="user_session_conversations",
    )
    op.drop_index(
        op.f("ix_user_session_conversations_created_at"),
        table_name="user_session_conversations",
    )
    op.drop_table("user_session_conversations")
    op.drop_index(
        "ix_unq_user_sessions_ext_id_org_id",
        table_name="user_sessions",
    )
    op.drop_index(op.f("ix_user_sessions_state"), table_name="user_sessions")
    op.drop_index(
        op.f("ix_user_sessions_organization_id"),
        table_name="user_sessions",
    )
    op.drop_index(
        "ix_user_sessions_org_state_activity",
        table_name="user_sessions",
    )
    op.drop_index(
        "ix_user_sessions_org_started",
        table_name="user_sessions",
    )
    op.drop_index(
        "ix_user_sessions_org_contact_started",
        table_name="user_sessions",
    )
    op.drop_index(op.f("ix_user_sessions_created_at"), table_name="user_sessions")
    op.drop_index(op.f("ix_user_sessions_contact_id"), table_name="user_sessions")
    op.drop_table("user_sessions")
    op.drop_index(
        "ix_unq_campaign_attempts_ext_id_org_id", table_name="campaign_attempts"
    )
    op.drop_index(op.f("ix_campaign_attempts_state"), table_name="campaign_attempts")
    op.drop_index(
        op.f("ix_campaign_attempts_organization_id"), table_name="campaign_attempts"
    )
    op.drop_index(
        op.f("ix_campaign_attempts_created_at"), table_name="campaign_attempts"
    )
    op.drop_index(
        "ix_campaign_attempts_contact_tracking", table_name="campaign_attempts"
    )
    op.drop_index("ix_campaign_attempts_campaign_state", table_name="campaign_attempts")
    op.drop_table("campaign_attempts")
    op.drop_index(
        op.f("ix_voice_segments_voice_session_id"), table_name="voice_segments"
    )
    op.drop_index("ix_voice_segments_session_role_type", table_name="voice_segments")
    op.drop_index(
        op.f("ix_voice_segments_organization_id"), table_name="voice_segments"
    )
    op.drop_index("ix_voice_segments_org_message", table_name="voice_segments")
    op.drop_index(
        "ix_voice_segments_org_conversation_created", table_name="voice_segments"
    )
    op.drop_index(op.f("ix_voice_segments_created_at"), table_name="voice_segments")
    op.drop_table("voice_segments")
    op.drop_index(
        op.f("ix_voice_recordings_voice_session_id"), table_name="voice_recordings"
    )
    op.drop_index(
        op.f("ix_voice_recordings_telephony_call_id"), table_name="voice_recordings"
    )
    op.drop_index(
        op.f("ix_voice_recordings_storage_provider_config_id"),
        table_name="voice_recordings",
    )
    op.drop_index(op.f("ix_voice_recordings_state"), table_name="voice_recordings")
    op.drop_index(op.f("ix_voice_recordings_session_id"), table_name="voice_recordings")
    op.drop_index(
        op.f("ix_voice_recordings_organization_id"), table_name="voice_recordings"
    )
    op.drop_index(op.f("ix_voice_recordings_created_at"), table_name="voice_recordings")
    op.drop_index(
        op.f("ix_voice_recordings_conversation_id"), table_name="voice_recordings"
    )
    op.drop_table("voice_recordings")
    op.drop_index("ix_unq_scheduler_runs_ext_id_org_id", table_name="scheduler_runs")
    op.drop_index(op.f("ix_scheduler_runs_schedule_id"), table_name="scheduler_runs")
    op.drop_index(
        op.f("ix_scheduler_runs_organization_id"), table_name="scheduler_runs"
    )
    op.drop_index(op.f("ix_scheduler_runs_created_at"), table_name="scheduler_runs")
    op.drop_index(op.f("ix_scheduler_runs_agent_id"), table_name="scheduler_runs")
    op.drop_table("scheduler_runs")
    op.drop_index(
        "ix_unq_campaign_contacts_ext_id_org_id", table_name="campaign_contacts"
    )
    op.drop_index("ix_campaign_contacts_status", table_name="campaign_contacts")
    op.drop_index("ix_campaign_contacts_retry", table_name="campaign_contacts")
    op.drop_index(
        op.f("ix_campaign_contacts_organization_id"), table_name="campaign_contacts"
    )
    op.drop_index(
        op.f("ix_campaign_contacts_created_at"), table_name="campaign_contacts"
    )
    op.drop_index("ix_campaign_contacts_campaign_id", table_name="campaign_contacts")
    op.drop_table("campaign_contacts")
    op.drop_index(op.f("ix_voice_sessions_session_id"), table_name="voice_sessions")
    op.drop_index(
        op.f("ix_voice_sessions_organization_id"), table_name="voice_sessions"
    )
    op.drop_index("ix_voice_sessions_org_telephony_call", table_name="voice_sessions")
    op.drop_index("ix_voice_sessions_org_status_started", table_name="voice_sessions")
    op.drop_index("ix_voice_sessions_org_started", table_name="voice_sessions")
    op.drop_index("ix_voice_sessions_org_conversation", table_name="voice_sessions")
    op.drop_index("ix_voice_sessions_org_agent_started", table_name="voice_sessions")
    op.drop_index(op.f("ix_voice_sessions_created_at"), table_name="voice_sessions")
    op.drop_index(
        op.f("ix_voice_sessions_conversation_id"), table_name="voice_sessions"
    )
    op.drop_index("ix_unq_voice_sessions_ext_id_org_id", table_name="voice_sessions")
    op.drop_table("voice_sessions")
    op.drop_index(
        "ix_unq_scheduler_schedule_revisions_ext_id_org_id",
        table_name="scheduler_schedule_revisions",
    )
    op.drop_index(
        op.f("ix_scheduler_schedule_revisions_schedule_id"),
        table_name="scheduler_schedule_revisions",
    )
    op.drop_index(
        op.f("ix_scheduler_schedule_revisions_organization_id"),
        table_name="scheduler_schedule_revisions",
    )
    op.drop_index(
        op.f("ix_scheduler_schedule_revisions_created_at"),
        table_name="scheduler_schedule_revisions",
    )
    op.drop_index(
        op.f("ix_scheduler_schedule_revisions_agent_id"),
        table_name="scheduler_schedule_revisions",
    )
    op.drop_table("scheduler_schedule_revisions")
    op.drop_index(
        "ix_unq_campaign_revisions_ext_id_org_id", table_name="campaign_revisions"
    )
    op.drop_index(
        op.f("ix_campaign_revisions_organization_id"), table_name="campaign_revisions"
    )
    op.drop_index(
        op.f("ix_campaign_revisions_created_at"), table_name="campaign_revisions"
    )
    op.drop_index(
        op.f("ix_campaign_revisions_campaign_id"), table_name="campaign_revisions"
    )
    op.drop_index(
        op.f("ix_campaign_revisions_agent_id"), table_name="campaign_revisions"
    )
    op.drop_table("campaign_revisions")
    op.drop_index(
        "uq_telephony_calls_campaign_attempt_id",
        table_name="telephony_calls",
        postgresql_where=sa.text("campaign_attempt_id IS NOT NULL"),
    )
    op.drop_index("ix_unq_telephony_calls_ext_id_org_id", table_name="telephony_calls")
    op.drop_index(
        op.f("ix_telephony_calls_voice_session_id"), table_name="telephony_calls"
    )
    op.drop_index(
        op.f("ix_telephony_calls_transcript_id"), table_name="telephony_calls"
    )
    op.drop_index("ix_telephony_calls_status", table_name="telephony_calls")
    op.drop_index(op.f("ix_telephony_calls_recording_id"), table_name="telephony_calls")
    op.drop_index(
        op.f("ix_telephony_calls_provider_config_id"), table_name="telephony_calls"
    )
    op.drop_index(
        op.f("ix_telephony_calls_phone_number_id"), table_name="telephony_calls"
    )
    op.drop_index(
        op.f("ix_telephony_calls_organization_id"), table_name="telephony_calls"
    )
    op.drop_index(op.f("ix_telephony_calls_created_at"), table_name="telephony_calls")
    op.drop_index("ix_telephony_calls_conversation_id", table_name="telephony_calls")
    op.drop_index(op.f("ix_telephony_calls_campaign_id"), table_name="telephony_calls")
    op.drop_index(
        op.f("ix_telephony_calls_campaign_contact_id"), table_name="telephony_calls"
    )
    op.drop_index("ix_telephony_calls_call_sid", table_name="telephony_calls")
    op.drop_index("ix_telephony_calls_agent_id", table_name="telephony_calls")
    op.drop_table("telephony_calls")
    op.drop_index(
        "ix_unq_scheduler_schedules_ext_id_org_id", table_name="scheduler_schedules"
    )
    op.drop_index(
        op.f("ix_scheduler_schedules_organization_id"), table_name="scheduler_schedules"
    )
    op.drop_index(
        op.f("ix_scheduler_schedules_next_at"), table_name="scheduler_schedules"
    )
    op.drop_index(
        op.f("ix_scheduler_schedules_created_at"), table_name="scheduler_schedules"
    )
    op.drop_index(
        op.f("ix_scheduler_schedules_agent_id"), table_name="scheduler_schedules"
    )
    op.drop_table("scheduler_schedules")
    op.drop_index(
        "ix_unq_sandbox_workspace_checkpoints_ext_id_org_id",
        table_name="sandbox_workspace_checkpoints",
    )
    op.drop_index(
        op.f("ix_sandbox_workspace_checkpoints_sandbox_provider_config_id"),
        table_name="sandbox_workspace_checkpoints",
    )
    op.drop_index(
        op.f("ix_sandbox_workspace_checkpoints_organization_id"),
        table_name="sandbox_workspace_checkpoints",
    )
    op.drop_index(
        op.f("ix_sandbox_workspace_checkpoints_grant_id"),
        table_name="sandbox_workspace_checkpoints",
    )
    op.drop_index(
        op.f("ix_sandbox_workspace_checkpoints_created_at"),
        table_name="sandbox_workspace_checkpoints",
    )
    op.drop_index(
        op.f("ix_sandbox_workspace_checkpoints_agent_run_id"),
        table_name="sandbox_workspace_checkpoints",
    )
    op.drop_table("sandbox_workspace_checkpoints")
    op.drop_index(
        "uq_sandbox_sessions_live_agent_run",
        table_name="sandbox_sessions",
        postgresql_where=sa.text(
            "agent_run_id IS NOT NULL AND state IN ('starting', 'running', 'paused') AND deleted IS FALSE"
        ),
    )
    op.drop_index(
        "ix_unq_sandbox_sessions_ext_id_org_id", table_name="sandbox_sessions"
    )
    op.drop_index(op.f("ix_sandbox_sessions_vendor_id"), table_name="sandbox_sessions")
    op.drop_index(op.f("ix_sandbox_sessions_state"), table_name="sandbox_sessions")
    op.drop_index(
        op.f("ix_sandbox_sessions_sandbox_provider_config_id"),
        table_name="sandbox_sessions",
    )
    op.drop_index(
        op.f("ix_sandbox_sessions_organization_id"), table_name="sandbox_sessions"
    )
    op.drop_index(op.f("ix_sandbox_sessions_grant_id"), table_name="sandbox_sessions")
    op.drop_index(op.f("ix_sandbox_sessions_expires_at"), table_name="sandbox_sessions")
    op.drop_index(op.f("ix_sandbox_sessions_created_at"), table_name="sandbox_sessions")
    op.drop_index(
        op.f("ix_sandbox_sessions_agent_run_id"), table_name="sandbox_sessions"
    )
    op.drop_index(op.f("ix_sandbox_sessions_agent_id"), table_name="sandbox_sessions")
    op.drop_table("sandbox_sessions")
    op.drop_index(
        "ix_unq_memory_relationships_ext_id_org_id", table_name="memory_relationships"
    )
    op.drop_index(
        op.f("ix_memory_relationships_target_memory_id"),
        table_name="memory_relationships",
    )
    op.drop_index(
        op.f("ix_memory_relationships_source_memory_id"),
        table_name="memory_relationships",
    )
    op.drop_index(
        op.f("ix_memory_relationships_scope_level"), table_name="memory_relationships"
    )
    op.drop_index(
        op.f("ix_memory_relationships_reconciliation_job_id"),
        table_name="memory_relationships",
    )
    op.drop_index(
        op.f("ix_memory_relationships_owner_id"), table_name="memory_relationships"
    )
    op.drop_index(
        op.f("ix_memory_relationships_organization_id"),
        table_name="memory_relationships",
    )
    op.drop_index(
        op.f("ix_memory_relationships_memory_provider_config_id"),
        table_name="memory_relationships",
    )
    op.drop_index(
        op.f("ix_memory_relationships_kind"), table_name="memory_relationships"
    )
    op.drop_index(
        op.f("ix_memory_relationships_created_at"), table_name="memory_relationships"
    )
    op.drop_index(
        op.f("ix_memory_relationships_conversation_id"),
        table_name="memory_relationships",
    )
    op.drop_index(
        op.f("ix_memory_relationships_contact_id"), table_name="memory_relationships"
    )
    op.drop_index(
        op.f("ix_memory_relationships_agent_id"), table_name="memory_relationships"
    )
    op.drop_table("memory_relationships")
    op.drop_index(
        "ix_unq_memory_reindex_vectors_ext_id_org_id",
        table_name="memory_reindex_vectors",
    )
    op.drop_index(
        op.f("ix_memory_reindex_vectors_reindex_job_id"),
        table_name="memory_reindex_vectors",
    )
    op.drop_index(
        op.f("ix_memory_reindex_vectors_organization_id"),
        table_name="memory_reindex_vectors",
    )
    op.drop_index(
        op.f("ix_memory_reindex_vectors_memory_id"), table_name="memory_reindex_vectors"
    )
    op.drop_index(
        op.f("ix_memory_reindex_vectors_created_at"),
        table_name="memory_reindex_vectors",
    )
    op.drop_table("memory_reindex_vectors")
    op.drop_index(
        "ix_unq_memory_reconciliation_effects_ext_id_org_id",
        table_name="memory_reconciliation_effects",
    )
    op.drop_index(
        op.f("ix_memory_reconciliation_effects_reconciliation_job_id"),
        table_name="memory_reconciliation_effects",
    )
    op.drop_index(
        op.f("ix_memory_reconciliation_effects_organization_id"),
        table_name="memory_reconciliation_effects",
    )
    op.drop_index(
        op.f("ix_memory_reconciliation_effects_created_at"),
        table_name="memory_reconciliation_effects",
    )
    op.drop_table("memory_reconciliation_effects")
    op.drop_index(
        "ix_unq_memory_reconciliation_cursors_ext_id_org_id",
        table_name="memory_reconciliation_cursors",
    )
    op.drop_index(
        op.f("ix_memory_reconciliation_cursors_scope_level"),
        table_name="memory_reconciliation_cursors",
    )
    op.drop_index(
        op.f("ix_memory_reconciliation_cursors_reconciliation_llm_provider_config_id"),
        table_name="memory_reconciliation_cursors",
    )
    op.drop_index(
        op.f("ix_memory_reconciliation_cursors_owner_id"),
        table_name="memory_reconciliation_cursors",
    )
    op.drop_index(
        op.f("ix_memory_reconciliation_cursors_organization_id"),
        table_name="memory_reconciliation_cursors",
    )
    op.drop_index(
        op.f("ix_memory_reconciliation_cursors_memory_provider_config_id"),
        table_name="memory_reconciliation_cursors",
    )
    op.drop_index(
        op.f("ix_memory_reconciliation_cursors_embedding_space_id"),
        table_name="memory_reconciliation_cursors",
    )
    op.drop_index(
        op.f("ix_memory_reconciliation_cursors_embedding_provider_config_id"),
        table_name="memory_reconciliation_cursors",
    )
    op.drop_index(
        op.f("ix_memory_reconciliation_cursors_created_at"),
        table_name="memory_reconciliation_cursors",
    )
    op.drop_index(
        op.f("ix_memory_reconciliation_cursors_conversation_id"),
        table_name="memory_reconciliation_cursors",
    )
    op.drop_index(
        op.f("ix_memory_reconciliation_cursors_contact_id"),
        table_name="memory_reconciliation_cursors",
    )
    op.drop_index(
        op.f("ix_memory_reconciliation_cursors_agent_id"),
        table_name="memory_reconciliation_cursors",
    )
    op.drop_index(
        op.f("ix_memory_reconciliation_cursors_active_job_id"),
        table_name="memory_reconciliation_cursors",
    )
    op.drop_table("memory_reconciliation_cursors")
    op.drop_index(
        "uq_knowledge_ingestion_jobs_active_document",
        table_name="knowledge_ingestion_jobs",
        postgresql_where=sa.text(
            "state IN ('pending', 'running') AND deleted IS FALSE"
        ),
    )
    op.drop_index(
        "ix_unq_knowledge_ingestion_jobs_ext_id_org_id",
        table_name="knowledge_ingestion_jobs",
    )
    op.drop_index(
        op.f("ix_knowledge_ingestion_jobs_storage_provider_config_id"),
        table_name="knowledge_ingestion_jobs",
    )
    op.drop_index(
        op.f("ix_knowledge_ingestion_jobs_state"), table_name="knowledge_ingestion_jobs"
    )
    op.drop_index(
        op.f("ix_knowledge_ingestion_jobs_organization_id"),
        table_name="knowledge_ingestion_jobs",
    )
    op.drop_index(
        op.f("ix_knowledge_ingestion_jobs_knowledgebase_id"),
        table_name="knowledge_ingestion_jobs",
    )
    op.drop_index(
        op.f("ix_knowledge_ingestion_jobs_embedding_space_id"),
        table_name="knowledge_ingestion_jobs",
    )
    op.drop_index(
        op.f("ix_knowledge_ingestion_jobs_embedding_provider_config_id"),
        table_name="knowledge_ingestion_jobs",
    )
    op.drop_index(
        op.f("ix_knowledge_ingestion_jobs_created_at"),
        table_name="knowledge_ingestion_jobs",
    )
    op.drop_index(
        op.f("ix_knowledge_ingestion_jobs_corpus_import_id"),
        table_name="knowledge_ingestion_jobs",
    )
    op.drop_table("knowledge_ingestion_jobs")
    op.drop_index(
        "ix_participant_conversation_id", table_name="conversation_participants"
    )
    op.drop_index(
        op.f("ix_conversation_participants_created_at"),
        table_name="conversation_participants",
    )
    op.drop_table("conversation_participants")
    op.drop_index(
        "ix_unq_campaign_campaigns_ext_id_org_id", table_name="campaign_campaigns"
    )
    op.drop_index("ix_campaign_campaigns_status", table_name="campaign_campaigns")
    op.drop_index(
        op.f("ix_campaign_campaigns_organization_id"), table_name="campaign_campaigns"
    )
    op.drop_index(
        op.f("ix_campaign_campaigns_created_at"), table_name="campaign_campaigns"
    )
    op.drop_index("ix_campaign_campaigns_agent_id", table_name="campaign_campaigns")
    op.drop_table("campaign_campaigns")
    op.drop_index(
        "ix_unq_auth_widget_invitations_ext_id_org_id",
        table_name="auth_widget_invitations",
    )
    op.drop_index(
        op.f("ix_auth_widget_invitations_organization_id"),
        table_name="auth_widget_invitations",
    )
    op.drop_index(
        "ix_auth_widget_invitations_expires_at", table_name="auth_widget_invitations"
    )
    op.drop_index(
        op.f("ix_auth_widget_invitations_created_at"),
        table_name="auth_widget_invitations",
    )
    op.drop_index(
        "ix_auth_widget_invitations_contact_id", table_name="auth_widget_invitations"
    )
    op.drop_table("auth_widget_invitations")
    op.drop_index(
        op.f("ix_agent_swarm_revision_members_organization_id"),
        table_name="agent_swarm_revision_members",
    )
    op.drop_index(
        op.f("ix_agent_swarm_revision_members_created_at"),
        table_name="agent_swarm_revision_members",
    )
    op.drop_table("agent_swarm_revision_members")
    op.drop_index(
        op.f("ix_agent_revision_tools_organization_id"),
        table_name="agent_revision_tools",
    )
    op.drop_index(
        op.f("ix_agent_revision_tools_created_at"), table_name="agent_revision_tools"
    )
    op.drop_table("agent_revision_tools")
    op.drop_index(
        op.f("ix_agent_revision_background_agents_organization_id"),
        table_name="agent_revision_background_agents",
    )
    op.drop_index(
        op.f("ix_agent_revision_background_agents_created_at"),
        table_name="agent_revision_background_agents",
    )
    op.drop_table("agent_revision_background_agents")
    op.drop_index(
        "ix_unq_telephony_phone_numbers_ext_id_org_id",
        table_name="telephony_phone_numbers",
    )
    op.drop_index(
        op.f("ix_telephony_phone_numbers_provider_config_id"),
        table_name="telephony_phone_numbers",
    )
    op.drop_index(
        op.f("ix_telephony_phone_numbers_organization_id"),
        table_name="telephony_phone_numbers",
    )
    op.drop_index(
        op.f("ix_telephony_phone_numbers_created_at"),
        table_name="telephony_phone_numbers",
    )
    op.drop_table("telephony_phone_numbers")
    op.drop_index("ix_unq_sandbox_grants_ext_id_org_id", table_name="sandbox_grants")
    op.drop_index(
        op.f("ix_sandbox_grants_sandbox_provider_config_id"),
        table_name="sandbox_grants",
    )
    op.drop_index(
        op.f("ix_sandbox_grants_organization_id"), table_name="sandbox_grants"
    )
    op.drop_index(op.f("ix_sandbox_grants_created_at"), table_name="sandbox_grants")
    op.drop_index(op.f("ix_sandbox_grants_agent_id"), table_name="sandbox_grants")
    op.drop_table("sandbox_grants")
    op.drop_index(
        "uq_memory_reconciliation_jobs_active_partition",
        table_name="memory_reconciliation_jobs",
        postgresql_where=sa.text(
            "state IN ('pending', 'running') AND deleted IS FALSE"
        ),
    )
    op.drop_index(
        "ix_unq_memory_reconciliation_jobs_ext_id_org_id",
        table_name="memory_reconciliation_jobs",
    )
    op.drop_index(
        op.f("ix_memory_reconciliation_jobs_state"),
        table_name="memory_reconciliation_jobs",
    )
    op.drop_index(
        op.f("ix_memory_reconciliation_jobs_scope_level"),
        table_name="memory_reconciliation_jobs",
    )
    op.drop_index(
        op.f("ix_memory_reconciliation_jobs_reconciliation_llm_provider_config_id"),
        table_name="memory_reconciliation_jobs",
    )
    op.drop_index(
        op.f("ix_memory_reconciliation_jobs_owner_id"),
        table_name="memory_reconciliation_jobs",
    )
    op.drop_index(
        op.f("ix_memory_reconciliation_jobs_organization_id"),
        table_name="memory_reconciliation_jobs",
    )
    op.drop_index(
        op.f("ix_memory_reconciliation_jobs_memory_provider_config_id"),
        table_name="memory_reconciliation_jobs",
    )
    op.drop_index(
        op.f("ix_memory_reconciliation_jobs_embedding_space_id"),
        table_name="memory_reconciliation_jobs",
    )
    op.drop_index(
        op.f("ix_memory_reconciliation_jobs_embedding_provider_config_id"),
        table_name="memory_reconciliation_jobs",
    )
    op.drop_index(
        op.f("ix_memory_reconciliation_jobs_created_at"),
        table_name="memory_reconciliation_jobs",
    )
    op.drop_index(
        op.f("ix_memory_reconciliation_jobs_conversation_id"),
        table_name="memory_reconciliation_jobs",
    )
    op.drop_index(
        op.f("ix_memory_reconciliation_jobs_contact_id"),
        table_name="memory_reconciliation_jobs",
    )
    op.drop_index(
        op.f("ix_memory_reconciliation_jobs_agent_id"),
        table_name="memory_reconciliation_jobs",
    )
    op.drop_table("memory_reconciliation_jobs")
    op.drop_index("ix_unq_memory_memories_ext_id_org_id", table_name="memory_memories")
    op.drop_index(
        op.f("ix_memory_memories_source_conversation_id"), table_name="memory_memories"
    )
    op.drop_index(op.f("ix_memory_memories_scope_level"), table_name="memory_memories")
    op.drop_index(
        op.f("ix_memory_memories_organization_id"), table_name="memory_memories"
    )
    op.drop_index(
        op.f("ix_memory_memories_memory_provider_config_id"),
        table_name="memory_memories",
    )
    op.drop_index(op.f("ix_memory_memories_expires_at"), table_name="memory_memories")
    op.drop_index(
        op.f("ix_memory_memories_embedding_space_id"), table_name="memory_memories"
    )
    op.drop_index(
        op.f("ix_memory_memories_embedding_provider_config_id"),
        table_name="memory_memories",
    )
    op.drop_index(op.f("ix_memory_memories_created_at"), table_name="memory_memories")
    op.drop_index(
        op.f("ix_memory_memories_conversation_id"), table_name="memory_memories"
    )
    op.drop_index(op.f("ix_memory_memories_contact_id"), table_name="memory_memories")
    op.drop_index(op.f("ix_memory_memories_agent_id"), table_name="memory_memories")
    op.drop_table("memory_memories")
    op.drop_index(
        "ix_unq_memory_formation_effects_ext_id_org_id",
        table_name="memory_formation_effects",
    )
    op.drop_index(
        op.f("ix_memory_formation_effects_organization_id"),
        table_name="memory_formation_effects",
    )
    op.drop_index(
        op.f("ix_memory_formation_effects_formation_job_id"),
        table_name="memory_formation_effects",
    )
    op.drop_index(
        op.f("ix_memory_formation_effects_created_at"),
        table_name="memory_formation_effects",
    )
    op.drop_table("memory_formation_effects")
    op.drop_index(
        "ix_unq_memory_formation_cursors_ext_id_org_id",
        table_name="memory_formation_cursors",
    )
    op.drop_index(
        op.f("ix_memory_formation_cursors_organization_id"),
        table_name="memory_formation_cursors",
    )
    op.drop_index(
        op.f("ix_memory_formation_cursors_memory_provider_config_id"),
        table_name="memory_formation_cursors",
    )
    op.drop_index(
        op.f("ix_memory_formation_cursors_created_at"),
        table_name="memory_formation_cursors",
    )
    op.drop_index(
        op.f("ix_memory_formation_cursors_conversation_id"),
        table_name="memory_formation_cursors",
    )
    op.drop_index(
        op.f("ix_memory_formation_cursors_active_job_id"),
        table_name="memory_formation_cursors",
    )
    op.drop_table("memory_formation_cursors")
    op.drop_index(
        op.f("ix_memory_changes_source_conversation_id"), table_name="memory_changes"
    )
    op.drop_index(op.f("ix_memory_changes_scope_level"), table_name="memory_changes")
    op.drop_index(
        op.f("ix_memory_changes_reconciliation_llm_provider_config_id"),
        table_name="memory_changes",
    )
    op.drop_index(
        op.f("ix_memory_changes_reconciliation_job_id"), table_name="memory_changes"
    )
    op.drop_index(
        op.f("ix_memory_changes_organization_id"), table_name="memory_changes"
    )
    op.drop_index(
        op.f("ix_memory_changes_memory_provider_config_id"), table_name="memory_changes"
    )
    op.drop_index(op.f("ix_memory_changes_memory_id"), table_name="memory_changes")
    op.drop_index(
        op.f("ix_memory_changes_formation_job_id"), table_name="memory_changes"
    )
    op.drop_index(
        op.f("ix_memory_changes_embedding_space_id"), table_name="memory_changes"
    )
    op.drop_index(
        op.f("ix_memory_changes_embedding_provider_config_id"),
        table_name="memory_changes",
    )
    op.drop_index(op.f("ix_memory_changes_created_at"), table_name="memory_changes")
    op.drop_index(
        op.f("ix_memory_changes_conversation_id"), table_name="memory_changes"
    )
    op.drop_index(op.f("ix_memory_changes_contact_id"), table_name="memory_changes")
    op.drop_index(op.f("ix_memory_changes_agent_id"), table_name="memory_changes")
    op.drop_table("memory_changes")
    op.drop_index(
        op.f("ix_map_agents_to_swarms_organization_id"),
        table_name="map_agents_to_swarms",
    )
    op.drop_index(
        op.f("ix_map_agents_to_swarms_created_at"), table_name="map_agents_to_swarms"
    )
    op.drop_index(
        "ix_map_agents_to_swarms_agent_swarm", table_name="map_agents_to_swarms"
    )
    op.drop_table("map_agents_to_swarms")
    op.drop_index(
        "ix_unq_knowledgebase_grants_ext_id_org_id", table_name="knowledgebase_grants"
    )
    op.drop_index(
        op.f("ix_knowledgebase_grants_organization_id"),
        table_name="knowledgebase_grants",
    )
    op.drop_index(
        op.f("ix_knowledgebase_grants_knowledgebase_id"),
        table_name="knowledgebase_grants",
    )
    op.drop_index(
        op.f("ix_knowledgebase_grants_created_at"), table_name="knowledgebase_grants"
    )
    op.drop_index(
        op.f("ix_knowledgebase_grants_agent_id"), table_name="knowledgebase_grants"
    )
    op.drop_table("knowledgebase_grants")
    op.drop_index(
        "uq_knowledge_reindex_jobs_active_knowledgebase",
        table_name="knowledge_reindex_jobs",
        postgresql_where=sa.text(
            "state IN ('pending', 'running') AND deleted IS FALSE"
        ),
    )
    op.drop_index(
        "ix_unq_knowledge_reindex_jobs_ext_id_org_id",
        table_name="knowledge_reindex_jobs",
    )
    op.drop_index(
        op.f("ix_knowledge_reindex_jobs_target_embedding_space_id"),
        table_name="knowledge_reindex_jobs",
    )
    op.drop_index(
        op.f("ix_knowledge_reindex_jobs_target_embedding_provider_config_id"),
        table_name="knowledge_reindex_jobs",
    )
    op.drop_index(
        op.f("ix_knowledge_reindex_jobs_state"), table_name="knowledge_reindex_jobs"
    )
    op.drop_index(
        op.f("ix_knowledge_reindex_jobs_source_embedding_space_id"),
        table_name="knowledge_reindex_jobs",
    )
    op.drop_index(
        op.f("ix_knowledge_reindex_jobs_source_embedding_provider_config_id"),
        table_name="knowledge_reindex_jobs",
    )
    op.drop_index(
        op.f("ix_knowledge_reindex_jobs_organization_id"),
        table_name="knowledge_reindex_jobs",
    )
    op.drop_index(
        op.f("ix_knowledge_reindex_jobs_knowledgebase_id"),
        table_name="knowledge_reindex_jobs",
    )
    op.drop_index(
        op.f("ix_knowledge_reindex_jobs_created_at"),
        table_name="knowledge_reindex_jobs",
    )
    op.drop_table("knowledge_reindex_jobs")
    op.drop_index(
        "uq_knowledge_corpus_imports_active_source",
        table_name="knowledge_corpus_imports",
        postgresql_where=sa.text(
            "state IN ('pending', 'running') AND deleted IS FALSE"
        ),
    )
    op.drop_index(
        "ix_unq_knowledge_corpus_imports_ext_id_org_id",
        table_name="knowledge_corpus_imports",
    )
    op.drop_index(
        op.f("ix_knowledge_corpus_imports_storage_provider_config_id"),
        table_name="knowledge_corpus_imports",
    )
    op.drop_index(
        op.f("ix_knowledge_corpus_imports_state"), table_name="knowledge_corpus_imports"
    )
    op.drop_index(
        op.f("ix_knowledge_corpus_imports_organization_id"),
        table_name="knowledge_corpus_imports",
    )
    op.drop_index(
        op.f("ix_knowledge_corpus_imports_knowledgebase_id"),
        table_name="knowledge_corpus_imports",
    )
    op.drop_index(
        op.f("ix_knowledge_corpus_imports_created_at"),
        table_name="knowledge_corpus_imports",
    )
    op.drop_table("knowledge_corpus_imports")
    op.drop_index(
        "uq_knowledge_chunks_vector_document_position",
        table_name="knowledge_chunks",
        postgresql_where=sa.text("embedding_space_id IS NOT NULL"),
    )
    op.drop_index(
        "uq_knowledge_chunks_fts_document_position",
        table_name="knowledge_chunks",
        postgresql_where=sa.text("embedding_space_id IS NULL"),
    )
    op.drop_index(
        "ix_unq_knowledge_chunks_ext_id_org_id", table_name="knowledge_chunks"
    )
    op.drop_index(
        "ix_knowledge_chunks_search_vector",
        table_name="knowledge_chunks",
        postgresql_using="gin",
    )
    op.drop_index(
        op.f("ix_knowledge_chunks_reindex_source_chunk_id"),
        table_name="knowledge_chunks",
    )
    op.drop_index(
        op.f("ix_knowledge_chunks_organization_id"), table_name="knowledge_chunks"
    )
    op.drop_index(
        op.f("ix_knowledge_chunks_knowledgebase_id"), table_name="knowledge_chunks"
    )
    op.drop_index(
        op.f("ix_knowledge_chunks_embedding_space_id"), table_name="knowledge_chunks"
    )
    op.drop_index(
        op.f("ix_knowledge_chunks_document_id"), table_name="knowledge_chunks"
    )
    op.drop_index(op.f("ix_knowledge_chunks_created_at"), table_name="knowledge_chunks")
    op.drop_table("knowledge_chunks")
    op.drop_index(
        "uq_voice_configs_name_organization_active",
        table_name="voice_configs",
        postgresql_where=sa.text("deleted = false"),
    )
    op.drop_index(
        "ix_unq_voice_configs_ext_id_org_id",
        table_name="voice_configs",
    )
    op.drop_index(
        op.f("ix_voice_configs_storage_provider_config_id"),
        table_name="voice_configs",
    )
    op.drop_index(
        op.f("ix_voice_configs_realtime_provider_config_id"),
        table_name="voice_configs",
    )
    op.drop_index(
        op.f("ix_voice_configs_tts_provider_config_id"),
        table_name="voice_configs",
    )
    op.drop_index(
        op.f("ix_voice_configs_stt_provider_config_id"),
        table_name="voice_configs",
    )
    op.drop_index(
        op.f("ix_voice_configs_organization_id"),
        table_name="voice_configs",
    )
    op.drop_index(
        op.f("ix_voice_configs_created_at"),
        table_name="voice_configs",
    )
    op.drop_table("voice_configs")
    op.drop_index(op.f("ix_agent_tools_organization_id"), table_name="agent_tools")
    op.drop_index(op.f("ix_agent_tools_created_at"), table_name="agent_tools")
    op.drop_table("agent_tools")
    op.drop_index(
        "ix_unq_agent_definition_revisions_ext_id_org_id",
        table_name="agent_definition_revisions",
    )
    op.drop_index(
        op.f("ix_agent_definition_revisions_organization_id"),
        table_name="agent_definition_revisions",
    )
    op.drop_index(
        op.f("ix_agent_definition_revisions_voice_config_id"),
        table_name="agent_definition_revisions",
    )
    op.drop_index(
        op.f("ix_agent_definition_revisions_created_at"),
        table_name="agent_definition_revisions",
    )
    op.drop_index(
        op.f("ix_agent_definition_revisions_agent_id"),
        table_name="agent_definition_revisions",
    )
    op.drop_table("agent_definition_revisions")
    op.drop_index(
        op.f("ix_agent_background_agents_created_at"),
        table_name="agent_background_agents",
    )
    op.drop_index(
        op.f("ix_agent_background_agents_agent_id"),
        table_name="agent_background_agents",
    )
    op.drop_table("agent_background_agents")
    op.drop_index(
        "ix_unq_tool_definition_revisions_ext_id_org_id",
        table_name="tool_definition_revisions",
    )
    op.drop_index(
        op.f("ix_tool_definition_revisions_tool_id"),
        table_name="tool_definition_revisions",
    )
    op.drop_index(
        op.f("ix_tool_definition_revisions_organization_id"),
        table_name="tool_definition_revisions",
    )
    op.drop_index(
        op.f("ix_tool_definition_revisions_created_at"),
        table_name="tool_definition_revisions",
    )
    op.drop_table("tool_definition_revisions")
    op.drop_index(
        "uq_memory_reindex_jobs_active_config",
        table_name="memory_reindex_jobs",
        postgresql_where=sa.text(
            "state IN ('pending', 'running') AND deleted IS FALSE"
        ),
    )
    op.drop_index(
        "ix_unq_memory_reindex_jobs_ext_id_org_id", table_name="memory_reindex_jobs"
    )
    op.drop_index(
        op.f("ix_memory_reindex_jobs_target_embedding_space_id"),
        table_name="memory_reindex_jobs",
    )
    op.drop_index(
        op.f("ix_memory_reindex_jobs_target_embedding_provider_config_id"),
        table_name="memory_reindex_jobs",
    )
    op.drop_index(
        op.f("ix_memory_reindex_jobs_state"), table_name="memory_reindex_jobs"
    )
    op.drop_index(
        op.f("ix_memory_reindex_jobs_source_embedding_space_id"),
        table_name="memory_reindex_jobs",
    )
    op.drop_index(
        op.f("ix_memory_reindex_jobs_source_embedding_provider_config_id"),
        table_name="memory_reindex_jobs",
    )
    op.drop_index(
        op.f("ix_memory_reindex_jobs_organization_id"), table_name="memory_reindex_jobs"
    )
    op.drop_index(
        op.f("ix_memory_reindex_jobs_memory_provider_config_id"),
        table_name="memory_reindex_jobs",
    )
    op.drop_index(
        op.f("ix_memory_reindex_jobs_created_at"), table_name="memory_reindex_jobs"
    )
    op.drop_table("memory_reindex_jobs")
    op.drop_index("ix_unq_memory_indexes_ext_id_org_id", table_name="memory_indexes")
    op.drop_index(
        op.f("ix_memory_indexes_target_embedding_space_id"), table_name="memory_indexes"
    )
    op.drop_index(
        op.f("ix_memory_indexes_target_embedding_provider_config_id"),
        table_name="memory_indexes",
    )
    op.drop_index(
        op.f("ix_memory_indexes_organization_id"), table_name="memory_indexes"
    )
    op.drop_index(
        op.f("ix_memory_indexes_memory_provider_config_id"), table_name="memory_indexes"
    )
    op.drop_index(
        op.f("ix_memory_indexes_embedding_space_id"), table_name="memory_indexes"
    )
    op.drop_index(
        op.f("ix_memory_indexes_embedding_provider_config_id"),
        table_name="memory_indexes",
    )
    op.drop_index(op.f("ix_memory_indexes_created_at"), table_name="memory_indexes")
    op.drop_table("memory_indexes")
    op.drop_index(
        "ix_unq_memory_formation_jobs_ext_id_org_id", table_name="memory_formation_jobs"
    )
    op.drop_index(
        op.f("ix_memory_formation_jobs_state"), table_name="memory_formation_jobs"
    )
    op.drop_index(
        op.f("ix_memory_formation_jobs_organization_id"),
        table_name="memory_formation_jobs",
    )
    op.drop_index(
        "ix_memory_formation_jobs_one_active",
        table_name="memory_formation_jobs",
        postgresql_where=sa.text(
            "state IN ('pending', 'running') AND deleted IS FALSE"
        ),
    )
    op.drop_index(
        op.f("ix_memory_formation_jobs_memory_provider_config_id"),
        table_name="memory_formation_jobs",
    )
    op.drop_index(
        op.f("ix_memory_formation_jobs_extraction_llm_provider_config_id"),
        table_name="memory_formation_jobs",
    )
    op.drop_index(
        op.f("ix_memory_formation_jobs_embedding_space_id"),
        table_name="memory_formation_jobs",
    )
    op.drop_index(
        op.f("ix_memory_formation_jobs_embedding_provider_config_id"),
        table_name="memory_formation_jobs",
    )
    op.drop_index(
        op.f("ix_memory_formation_jobs_created_at"), table_name="memory_formation_jobs"
    )
    op.drop_index(
        op.f("ix_memory_formation_jobs_conversation_id"),
        table_name="memory_formation_jobs",
    )
    op.drop_table("memory_formation_jobs")
    op.drop_index(
        "uq_knowledgebases_conversation_scope_active",
        table_name="knowledgebases",
        postgresql_where=sa.text("scope = 'conversation' AND deleted = false"),
    )
    op.drop_index("ix_unq_knowledgebases_ext_id_org_id", table_name="knowledgebases")
    op.drop_index(
        op.f("ix_knowledgebases_target_embedding_space_id"), table_name="knowledgebases"
    )
    op.drop_index(
        op.f("ix_knowledgebases_target_embedding_provider_config_id"),
        table_name="knowledgebases",
    )
    op.drop_index(op.f("ix_knowledgebases_scope_id"), table_name="knowledgebases")
    op.drop_index(
        op.f("ix_knowledgebases_organization_id"), table_name="knowledgebases"
    )
    op.drop_index(
        op.f("ix_knowledgebases_embedding_space_id"), table_name="knowledgebases"
    )
    op.drop_index(
        op.f("ix_knowledgebases_embedding_provider_config_id"),
        table_name="knowledgebases",
    )
    op.drop_index(op.f("ix_knowledgebases_created_at"), table_name="knowledgebases")
    op.drop_table("knowledgebases")
    op.drop_index(
        op.f("ix_event_inbox_receipts_organization_id"),
        table_name="event_inbox_receipts",
    )
    op.drop_index(
        op.f("ix_event_inbox_receipts_event_id"), table_name="event_inbox_receipts"
    )
    op.drop_table("event_inbox_receipts")
    op.drop_index(
        "uq_agent_agents_org_slug_active",
        table_name="agent_agents",
        postgresql_where=sa.text("deleted = false"),
    )
    op.drop_index("ix_unq_agent_agents_ext_id_org_id", table_name="agent_agents")
    op.drop_index(
        op.f("ix_agent_agents_webrtc_provider_config_id"), table_name="agent_agents"
    )
    op.drop_index(
        op.f("ix_agent_agents_voice_config_id"), table_name="agent_agents"
    )
    op.drop_index(
        op.f("ix_agent_agents_reranking_provider_config_id"), table_name="agent_agents"
    )
    op.drop_index(op.f("ix_agent_agents_organization_id"), table_name="agent_agents")
    op.drop_index(
        op.f("ix_agent_agents_memory_provider_config_id"), table_name="agent_agents"
    )
    op.drop_index(
        op.f("ix_agent_agents_llm_provider_config_id"), table_name="agent_agents"
    )
    op.drop_index(
        op.f("ix_agent_agents_instruction_template_id"), table_name="agent_agents"
    )
    op.drop_index(
        op.f("ix_agent_agents_file_upload_embedding_provider_config_id"),
        table_name="agent_agents",
    )
    op.drop_index(
        op.f("ix_agent_agents_email_provider_config_id"), table_name="agent_agents"
    )
    op.drop_index(op.f("ix_agent_agents_created_at"), table_name="agent_agents")
    op.drop_table("agent_agents")
    op.drop_index(
        "ix_unq_provider_config_revisions_ext_id_org_id",
        table_name="provider_config_revisions",
    )
    op.drop_index(
        op.f("ix_provider_config_revisions_provider_config_id"),
        table_name="provider_config_revisions",
    )
    op.drop_index(
        op.f("ix_provider_config_revisions_organization_id"),
        table_name="provider_config_revisions",
    )
    op.drop_index(
        op.f("ix_provider_config_revisions_created_at"),
        table_name="provider_config_revisions",
    )
    op.drop_table("provider_config_revisions")
    op.drop_index(
        "uq_platform_tools_org_slug_unbound_active",
        table_name="platform_tools",
        postgresql_where=sa.text("mcp_server_id IS NULL AND deleted = false"),
    )
    op.drop_index(
        "uq_platform_tools_mcp_wire_active",
        table_name="platform_tools",
        postgresql_where=sa.text(
            "mcp_server_id IS NOT NULL AND wire_id IS NOT NULL AND deleted = false"
        ),
    )
    op.drop_index("ix_unq_platform_tools_ext_id_org_id", table_name="platform_tools")
    op.drop_index(
        op.f("ix_platform_tools_organization_id"), table_name="platform_tools"
    )
    op.drop_index(op.f("ix_platform_tools_mcp_server_id"), table_name="platform_tools")
    op.drop_index(op.f("ix_platform_tools_created_at"), table_name="platform_tools")
    op.drop_table("platform_tools")
    op.drop_index(
        "ix_unq_organization_execution_reservations_ext_id_org_id",
        table_name="organization_execution_reservations",
    )
    op.drop_index(
        op.f("ix_organization_execution_reservations_run_id"),
        table_name="organization_execution_reservations",
    )
    op.drop_index(
        op.f("ix_organization_execution_reservations_organization_id"),
        table_name="organization_execution_reservations",
    )
    op.drop_index(
        op.f("ix_organization_execution_reservations_memory_reconciliation_job_id"),
        table_name="organization_execution_reservations",
    )
    op.drop_index(
        op.f("ix_organization_execution_reservations_memory_formation_job_id"),
        table_name="organization_execution_reservations",
    )
    op.drop_index(
        op.f("ix_organization_execution_reservations_created_at"),
        table_name="organization_execution_reservations",
    )
    op.drop_table("organization_execution_reservations")
    op.drop_index(
        "ix_unq_mcp_server_definition_revisions_ext_id_org_id",
        table_name="mcp_server_definition_revisions",
    )
    op.drop_index(
        op.f("ix_mcp_server_definition_revisions_server_id"),
        table_name="mcp_server_definition_revisions",
    )
    op.drop_index(
        op.f("ix_mcp_server_definition_revisions_organization_id"),
        table_name="mcp_server_definition_revisions",
    )
    op.drop_index(
        op.f("ix_mcp_server_definition_revisions_created_at"),
        table_name="mcp_server_definition_revisions",
    )
    op.drop_table("mcp_server_definition_revisions")
    op.drop_index(
        "uq_integration_v2_tools_org_wire_active",
        table_name="integration_v2_tools",
        postgresql_where="deleted = false",
    )
    op.drop_index(
        "ix_unq_integration_v2_tools_ext_id_org_id", table_name="integration_v2_tools"
    )
    op.drop_index(
        op.f("ix_integration_v2_tools_organization_id"),
        table_name="integration_v2_tools",
    )
    op.drop_index(
        op.f("ix_integration_v2_tools_installation_id"),
        table_name="integration_v2_tools",
    )
    op.drop_index(
        op.f("ix_integration_v2_tools_created_at"), table_name="integration_v2_tools"
    )
    op.drop_table("integration_v2_tools")
    op.drop_index(op.f("ix_event_deliveries_state"), table_name="event_deliveries")
    op.drop_index(
        op.f("ix_event_deliveries_organization_id"), table_name="event_deliveries"
    )
    op.drop_index(op.f("ix_event_deliveries_event_id"), table_name="event_deliveries")
    op.drop_table("event_deliveries")
    op.drop_index("ix_unq_deletion_jobs_ext_id_org_id", table_name="deletion_jobs")
    op.drop_index(op.f("ix_deletion_jobs_target_type"), table_name="deletion_jobs")
    op.drop_index(op.f("ix_deletion_jobs_target_id"), table_name="deletion_jobs")
    op.drop_index(op.f("ix_deletion_jobs_status"), table_name="deletion_jobs")
    op.drop_index(
        op.f("ix_deletion_jobs_requested_by_member_id"), table_name="deletion_jobs"
    )
    op.drop_index(op.f("ix_deletion_jobs_organization_id"), table_name="deletion_jobs")
    op.drop_index(op.f("ix_deletion_jobs_created_at"), table_name="deletion_jobs")
    op.drop_table("deletion_jobs")
    op.drop_index(
        "ix_unq_definition_template_revisions_ext_id_org_id",
        table_name="definition_template_revisions",
    )
    op.drop_index(
        op.f("ix_definition_template_revisions_template_id"),
        table_name="definition_template_revisions",
    )
    op.drop_index(
        op.f("ix_definition_template_revisions_organization_id"),
        table_name="definition_template_revisions",
    )
    op.drop_index(
        op.f("ix_definition_template_revisions_created_at"),
        table_name="definition_template_revisions",
    )
    op.drop_table("definition_template_revisions")
    op.drop_index("ix_oauth_states_state", table_name="connection_oauth_states")
    op.drop_index("ix_oauth_states_expires_at", table_name="connection_oauth_states")
    op.drop_index(
        op.f("ix_connection_oauth_states_organization_id"),
        table_name="connection_oauth_states",
    )
    op.drop_index(
        op.f("ix_connection_oauth_states_integration_id"),
        table_name="connection_oauth_states",
    )
    op.drop_index(
        op.f("ix_connection_oauth_states_expires_at"),
        table_name="connection_oauth_states",
    )
    op.drop_index(
        op.f("ix_connection_oauth_states_created_at"),
        table_name="connection_oauth_states",
    )
    op.drop_table("connection_oauth_states")
    op.drop_index(
        "ix_unq_connection_connections_ext_id_org_id",
        table_name="connection_connections",
    )
    op.drop_index(
        op.f("ix_connection_connections_organization_id"),
        table_name="connection_connections",
    )
    op.drop_index(
        op.f("ix_connection_connections_last_refresh_success_at"),
        table_name="connection_connections",
    )
    op.drop_index(
        op.f("ix_connection_connections_last_refresh_failure_at"),
        table_name="connection_connections",
    )
    op.drop_index(
        op.f("ix_connection_connections_integration_id"),
        table_name="connection_connections",
    )
    op.drop_index(
        op.f("ix_connection_connections_credentials_expires_at"),
        table_name="connection_connections",
    )
    op.drop_index(
        op.f("ix_connection_connections_created_at"),
        table_name="connection_connections",
    )
    op.drop_index(
        op.f("ix_connection_connections_contact_id"),
        table_name="connection_connections",
    )
    op.drop_table("connection_connections")
    op.drop_index("ix_unq_auth_sessions_ext_id_org_id", table_name="auth_sessions")
    op.drop_index(op.f("ix_auth_sessions_session_token"), table_name="auth_sessions")
    op.drop_index(op.f("ix_auth_sessions_organization_id"), table_name="auth_sessions")
    op.drop_index(op.f("ix_auth_sessions_created_at"), table_name="auth_sessions")
    op.drop_index("ix_auth_sessions_contact_id", table_name="auth_sessions")
    op.drop_table("auth_sessions")
    op.drop_index(
        "uq_provider_configs_org_capability_name_active",
        table_name="provider_configs",
        postgresql_where=sa.text("deleted = false"),
    )
    op.drop_index(
        "ix_unq_provider_configs_ext_id_org_id", table_name="provider_configs"
    )
    op.drop_index(
        op.f("ix_provider_configs_organization_id"), table_name="provider_configs"
    )
    op.drop_index(op.f("ix_provider_configs_created_at"), table_name="provider_configs")
    op.drop_table("provider_configs")
    op.drop_index(op.f("ix_outbound_attempts_state"), table_name="outbound_attempts")
    op.drop_index(op.f("ix_outbound_attempts_owner_id"), table_name="outbound_attempts")
    op.drop_index(
        op.f("ix_outbound_attempts_organization_id"), table_name="outbound_attempts"
    )
    op.drop_table("outbound_attempts")
    op.drop_index(
        "ix_unq_organization_execution_budgets_ext_id_org_id",
        table_name="organization_execution_budgets",
    )
    op.drop_index(
        op.f("ix_organization_execution_budgets_organization_id"),
        table_name="organization_execution_budgets",
    )
    op.drop_index(
        op.f("ix_organization_execution_budgets_created_at"),
        table_name="organization_execution_budgets",
    )
    op.drop_table("organization_execution_budgets")
    op.drop_index("ix_unq_member_members_ext_id_org_id", table_name="member_members")
    op.drop_index(
        op.f("ix_member_members_organization_id"), table_name="member_members"
    )
    op.drop_index(op.f("ix_member_members_created_at"), table_name="member_members")
    op.drop_table("member_members")
    op.drop_index(
        "uq_mcp_servers_org_slug_active",
        table_name="mcp_servers",
        postgresql_where=sa.text("deleted = false"),
    )
    op.drop_index("ix_unq_mcp_servers_ext_id_org_id", table_name="mcp_servers")
    op.drop_index(op.f("ix_mcp_servers_organization_id"), table_name="mcp_servers")
    op.drop_index(op.f("ix_mcp_servers_created_at"), table_name="mcp_servers")
    op.drop_table("mcp_servers")
    op.drop_index(
        "uq_integration_v2_installations_org_vendor_active",
        table_name="integration_v2_installations",
        postgresql_where="deleted = false",
    )
    op.drop_index(
        "ix_unq_integration_v2_installations_ext_id_org_id",
        table_name="integration_v2_installations",
    )
    op.drop_index(
        op.f("ix_integration_v2_installations_organization_id"),
        table_name="integration_v2_installations",
    )
    op.drop_index(
        op.f("ix_integration_v2_installations_created_at"),
        table_name="integration_v2_installations",
    )
    op.drop_table("integration_v2_installations")
    op.drop_index(op.f("ix_event_outbox_subject_id"), table_name="event_outbox")
    op.drop_index(op.f("ix_event_outbox_recorded_at"), table_name="event_outbox")
    op.drop_index(op.f("ix_event_outbox_organization_id"), table_name="event_outbox")
    op.drop_index(op.f("ix_event_outbox_event_type"), table_name="event_outbox")
    op.drop_table("event_outbox")
    op.drop_index(
        "uq_definition_templates_org_slug_active",
        table_name="definition_templates",
        postgresql_where=sa.text("deleted = false"),
    )
    op.drop_index(
        "ix_unq_definition_templates_ext_id_org_id", table_name="definition_templates"
    )
    op.drop_index(
        op.f("ix_definition_templates_organization_id"),
        table_name="definition_templates",
    )
    op.drop_index(
        op.f("ix_definition_templates_created_at"), table_name="definition_templates"
    )
    op.drop_table("definition_templates")
    op.drop_index(
        "ix_unq_conversation_conversations_ext_id_org_id",
        table_name="conversation_conversations",
    )
    op.drop_index(
        op.f("ix_conversation_conversations_organization_id"),
        table_name="conversation_conversations",
    )
    op.drop_index(
        op.f("ix_conversation_conversations_created_at"),
        table_name="conversation_conversations",
    )
    op.drop_table("conversation_conversations")
    op.drop_index("ix_unqc_contact_phone_org_id", table_name="contact_contacts")
    op.drop_index("ix_unqc_contact_email_org_id", table_name="contact_contacts")
    op.drop_index(
        "ix_unq_contact_contacts_ext_id_org_id", table_name="contact_contacts"
    )
    op.drop_index(
        op.f("ix_contact_contacts_organization_id"), table_name="contact_contacts"
    )
    op.drop_index(op.f("ix_contact_contacts_lifecycle"), table_name="contact_contacts")
    op.drop_index(op.f("ix_contact_contacts_created_at"), table_name="contact_contacts")
    op.drop_table("contact_contacts")
    op.drop_index("ix_unq_auth_api_keys_ext_id_org_id", table_name="auth_api_keys")
    op.drop_index(op.f("ix_auth_api_keys_organization_id"), table_name="auth_api_keys")
    op.drop_index("ix_auth_api_keys_org_id", table_name="auth_api_keys")
    op.drop_index(op.f("ix_auth_api_keys_key_prefix"), table_name="auth_api_keys")
    op.drop_index(op.f("ix_auth_api_keys_hashed_key"), table_name="auth_api_keys")
    op.drop_index(op.f("ix_auth_api_keys_created_at"), table_name="auth_api_keys")
    op.drop_table("auth_api_keys")
    op.drop_index(
        "ix_unq_agent_run_transcript_items_ext_id_org_id",
        table_name="agent_run_transcript_items",
    )
    op.drop_index(
        op.f("ix_agent_run_transcript_items_run_id"),
        table_name="agent_run_transcript_items",
    )
    op.drop_index(
        op.f("ix_agent_run_transcript_items_organization_id"),
        table_name="agent_run_transcript_items",
    )
    op.drop_index(
        op.f("ix_agent_run_transcript_items_created_at"),
        table_name="agent_run_transcript_items",
    )
    op.drop_table("agent_run_transcript_items")
    op.drop_index("ix_unq_agent_run_steps_ext_id_org_id", table_name="agent_run_steps")
    op.drop_index(op.f("ix_agent_run_steps_run_id"), table_name="agent_run_steps")
    op.drop_index(
        op.f("ix_agent_run_steps_organization_id"), table_name="agent_run_steps"
    )
    op.drop_index(op.f("ix_agent_run_steps_created_at"), table_name="agent_run_steps")
    op.drop_table("agent_run_steps")
    op.drop_index(
        "ix_unq_agent_input_requests_ext_id_org_id", table_name="agent_input_requests"
    )
    op.drop_index(
        op.f("ix_agent_input_requests_run_id"), table_name="agent_input_requests"
    )
    op.drop_index(
        op.f("ix_agent_input_requests_organization_id"),
        table_name="agent_input_requests",
    )
    op.drop_index(
        op.f("ix_agent_input_requests_created_at"), table_name="agent_input_requests"
    )
    op.drop_table("agent_input_requests")
    op.drop_index(
        op.f("ix_organization_organizations_created_at"),
        table_name="organization_organizations",
    )
    op.drop_table("organization_organizations")
    op.drop_index(
        "uq_conversation_messages_task_result_agent_run",
        table_name="conversation_messages",
        postgresql_where=sa.text(
            "kind = 'SYSTEM' AND content_kind = 'TASK_RESULT' AND deleted IS FALSE"
        ),
    )
    op.drop_index(
        op.f("ix_conversation_messages_sender_participant_id"),
        table_name="conversation_messages",
    )
    op.drop_index(
        op.f("ix_conversation_messages_request_id"), table_name="conversation_messages"
    )
    op.drop_index(
        op.f("ix_conversation_messages_external_id"), table_name="conversation_messages"
    )
    op.drop_index(
        op.f("ix_conversation_messages_created_at"), table_name="conversation_messages"
    )
    op.drop_index(
        op.f("ix_conversation_messages_conversation_id"),
        table_name="conversation_messages",
    )
    op.drop_index(
        op.f("ix_conversation_messages_agent_run_id"),
        table_name="conversation_messages",
    )
    op.drop_table("conversation_messages")
    op.drop_index(
        "uq_agent_swarms_org_slug_active",
        table_name="agent_swarms",
        postgresql_where=sa.text("deleted = false"),
    )
    op.drop_index("ix_unq_agent_swarms_ext_id_org_id", table_name="agent_swarms")
    op.drop_index(op.f("ix_agent_swarms_organization_id"), table_name="agent_swarms")
    op.drop_index(op.f("ix_agent_swarms_created_at"), table_name="agent_swarms")
    op.drop_table("agent_swarms")
    op.drop_index(
        "ix_unq_agent_swarm_revisions_ext_id_org_id", table_name="agent_swarm_revisions"
    )
    op.drop_index(
        op.f("ix_agent_swarm_revisions_swarm_id"), table_name="agent_swarm_revisions"
    )
    op.drop_index(
        op.f("ix_agent_swarm_revisions_organization_id"),
        table_name="agent_swarm_revisions",
    )
    op.drop_index(
        op.f("ix_agent_swarm_revisions_created_at"), table_name="agent_swarm_revisions"
    )
    op.drop_table("agent_swarm_revisions")
    op.drop_index("ix_unq_agent_runs_ext_id_org_id", table_name="agent_runs")
    op.drop_index(op.f("ix_agent_runs_organization_id"), table_name="agent_runs")
    op.drop_index(op.f("ix_agent_runs_lifecycle"), table_name="agent_runs")
    op.drop_index(
        op.f("ix_agent_runs_initiating_principal_id"), table_name="agent_runs"
    )
    op.drop_index(op.f("ix_agent_runs_created_at"), table_name="agent_runs")
    op.drop_index(op.f("ix_agent_runs_agent_id"), table_name="agent_runs")
    op.drop_table("agent_runs")
    _drop_public_enum_types()
    op.execute("DROP EXTENSION IF EXISTS vector")
    # ### end Alembic commands ###
