"""PostgreSQL persistence for durable event facts and exact delivery receipts."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    SmallInteger,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ENUM, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from eylo.common.models import Base, server_now
from eylo.events.durable.domain import EventDeliveryState


def _delivery_state_enum() -> ENUM:
    return ENUM(
        EventDeliveryState,
        name="event_delivery_state_enum",
        values_callable=lambda enum: [member.value for member in enum],
        create_type=False,
    )


class EventOutboxModel(Base):
    """One immutable organization-owned event envelope."""

    __tablename__ = "event_outbox"

    __table_args__ = (
        UniqueConstraint(
            "id",
            "organization_id",
            name="uq_event_outbox_id_organization_id",
        ),
        CheckConstraint(
            "subject_type ~ '^[a-z][a-z0-9_.-]*$'",
            name="ck_event_outbox_subject_type",
        ),
        CheckConstraint(
            "event_type ~ '^[a-z][a-z0-9_.-]*$'",
            name="ck_event_outbox_event_type",
        ),
        CheckConstraint(
            "event_version BETWEEN 1 AND 32767",
            name="ck_event_outbox_version",
        ),
        CheckConstraint(
            "recorded_at >= occurred_at",
            name="ck_event_outbox_recorded_after_occurrence",
        ),
        CheckConstraint(
            "causation_id IS NULL OR causation_id <> id",
            name="ck_event_outbox_not_self_caused",
        ),
        CheckConstraint(
            "jsonb_typeof(payload) = 'object'",
            name="ck_event_outbox_payload_object",
        ),
        CheckConstraint(
            "octet_length(payload::text) <= 65536",
            name="ck_event_outbox_payload_size",
        ),
        Index(
            "ix_event_outbox_org_correlation_occurred",
            "organization_id",
            "correlation_id",
            "occurred_at",
            "id",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organization_organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    subject_type: Mapped[str] = mapped_column(String(128), nullable=False)
    subject_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(String(192), nullable=False, index=True)
    event_version: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )
    correlation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    causation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)


class EventDeliveryModel(Base):
    """Independent delivery state for one named required consumer."""

    __tablename__ = "event_deliveries"

    __table_args__ = (
        ForeignKeyConstraint(
            ["event_id", "organization_id"],
            ["event_outbox.id", "event_outbox.organization_id"],
            name="fk_event_deliveries_event",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "event_id",
            "consumer_name",
            name="uq_event_deliveries_event_consumer",
        ),
        UniqueConstraint(
            "id",
            "event_id",
            "organization_id",
            "consumer_name",
            name="uq_event_deliveries_exact_authority",
        ),
        UniqueConstraint(
            "absurd_task_id",
            name="uq_event_deliveries_absurd_task_id",
        ),
        CheckConstraint(
            "consumer_name ~ '^[a-z][a-z0-9_.-]*$'",
            name="ck_event_deliveries_consumer_name",
        ),
        CheckConstraint(
            "max_attempts BETWEEN 1 AND 100 AND attempts BETWEEN 0 AND max_attempts",
            name="ck_event_deliveries_attempts",
        ),
        CheckConstraint(
            "finished_at IS NULL OR "
            "(started_at IS NOT NULL AND finished_at >= started_at)",
            name="ck_event_deliveries_time_order",
        ),
        CheckConstraint(
            "(state = 'pending' AND attempts = 0 AND started_at IS NULL "
            "AND finished_at IS NULL AND last_error IS NULL) OR "
            "(state = 'running' AND absurd_task_id IS NOT NULL "
            "AND attempts BETWEEN 1 AND max_attempts "
            "AND started_at IS NOT NULL AND finished_at IS NULL) OR "
            "(state = 'succeeded' AND absurd_task_id IS NOT NULL "
            "AND attempts BETWEEN 1 AND max_attempts "
            "AND started_at IS NOT NULL AND finished_at IS NOT NULL "
            "AND last_error IS NULL) OR "
            "(state = 'dead_letter' AND absurd_task_id IS NOT NULL "
            "AND attempts BETWEEN 1 AND max_attempts AND started_at IS NOT NULL "
            "AND finished_at IS NOT NULL AND last_error IS NOT NULL "
            "AND length(btrim(last_error)) BETWEEN 1 AND 2000)",
            name="ck_event_deliveries_lifecycle",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), default=uuid.uuid4, primary_key=True
    )
    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    consumer_name: Mapped[str] = mapped_column(String(192), nullable=False)
    absurd_task_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    state: Mapped[EventDeliveryState] = mapped_column(
        _delivery_state_enum(),
        nullable=False,
        default=EventDeliveryState.PENDING,
        server_default=EventDeliveryState.PENDING.value,
        index=True,
    )
    attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    max_attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, default=3, server_default=text("3")
    )
    last_error: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=server_now,
    )


class EventInboxReceiptModel(Base):
    """Proof that the exact consumer delivery committed its transition."""

    __tablename__ = "event_inbox_receipts"

    __table_args__ = (
        ForeignKeyConstraint(
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
        UniqueConstraint(
            "delivery_id",
            name="uq_event_inbox_receipts_delivery_id",
        ),
        UniqueConstraint(
            "event_id",
            "consumer_name",
            name="uq_event_inbox_receipts_event_consumer",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), default=uuid.uuid4, primary_key=True
    )
    delivery_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    consumer_name: Mapped[str] = mapped_column(String(192), nullable=False)
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
