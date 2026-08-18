"""PostgreSQL audit state for organization-owned external effects."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ENUM, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from eylo.common.models import Base, server_now
from eylo.common.outbound import (
    OUTBOUND_DESTINATION_ORIGIN_MAX_LENGTH,
    OUTBOUND_FAILURE_CODE_MAX_LENGTH,
    OUTBOUND_OPERATION_MAX_LENGTH,
    OUTBOUND_PROVIDER_REFERENCE_MAX_LENGTH,
    OUTBOUND_REQUEST_FINGERPRINT_LENGTH,
    OutboundAttemptState,
)


def _attempt_state_enum() -> ENUM:
    return ENUM(
        OutboundAttemptState,
        name="outbound_attempt_state_enum",
        values_callable=lambda enum: [member.value for member in enum],
        create_type=False,
    )


class OutboundAttemptModel(Base):
    """One stable logical mutation; no request content or engine claim state."""

    __tablename__ = "outbound_attempts"

    __table_args__ = (
        UniqueConstraint(
            "id",
            "organization_id",
            name="uq_outbound_attempts_id_organization",
        ),
        UniqueConstraint(
            "organization_id",
            "owner_kind",
            "owner_id",
            "operation_key",
            name="uq_outbound_attempts_owner_operation",
        ),
        UniqueConstraint(
            "provider_idempotency_key",
            name="uq_outbound_attempts_provider_idempotency",
        ),
        CheckConstraint(
            "owner_kind ~ '^[a-z][a-z0-9_.-]*$'",
            name="ck_outbound_attempts_owner_kind",
        ),
        CheckConstraint(
            "operation_key ~ '^[a-z][a-z0-9_.-]*$'",
            name="ck_outbound_attempts_operation_key",
        ),
        CheckConstraint(
            "provider_operation ~ '^[a-z][a-z0-9_.-]*$'",
            name="ck_outbound_attempts_provider_operation",
        ),
        CheckConstraint(
            "transport_kind ~ '^[a-z][a-z0-9_.-]*$'",
            name="ck_outbound_attempts_transport_kind",
        ),
        CheckConstraint(
            "request_fingerprint ~ '^[0-9a-f]{64}$'",
            name="ck_outbound_attempts_request_fingerprint",
        ),
        CheckConstraint(
            "send_count BETWEEN 0 AND 100",
            name="ck_outbound_attempts_send_count",
        ),
        CheckConstraint(
            "status_code IS NULL OR status_code BETWEEN 100 AND 599",
            name="ck_outbound_attempts_status_code",
        ),
        CheckConstraint(
            "failure_code IS NULL OR failure_code ~ '^[a-z][a-z0-9_.-]*$'",
            name="ck_outbound_attempts_failure_code",
        ),
        CheckConstraint(
            "(send_count = 0 AND started_at IS NULL) OR "
            "(send_count > 0 AND started_at IS NOT NULL)",
            name="ck_outbound_attempts_send_start_pair",
        ),
        CheckConstraint(
            "outcome_at IS NULL OR started_at IS NULL OR outcome_at >= started_at",
            name="ck_outbound_attempts_outcome_order",
        ),
        CheckConstraint(
            "reconciled_at IS NULL OR "
            "(started_at IS NOT NULL AND outcome_at IS NOT NULL "
            "AND reconciled_at >= outcome_at)",
            name="ck_outbound_attempts_reconciliation_order",
        ),
        CheckConstraint(
            "(state = 'prepared' AND send_count = 0 AND outcome_at IS NULL "
            "AND failure_code IS NULL) OR "
            "(state = 'in_flight' AND send_count > 0 AND outcome_at IS NULL "
            "AND failure_code IS NULL) OR "
            "(state = 'succeeded' AND send_count > 0 AND outcome_at IS NOT NULL "
            "AND failure_code IS NULL) OR "
            "(state = 'retryable' AND send_count > 0 AND outcome_at IS NOT NULL "
            "AND failure_code IS NOT NULL) OR "
            "(state = 'terminal' AND outcome_at IS NOT NULL "
            "AND failure_code IS NOT NULL) OR "
            "(state = 'unknown' AND send_count > 0 AND outcome_at IS NOT NULL "
            "AND failure_code IS NOT NULL) OR "
            "(state = 'cancelled' AND cancel_requested_at IS NOT NULL "
            "AND outcome_at IS NOT NULL)",
            name="ck_outbound_attempts_lifecycle",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organization_organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    owner_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    operation_key: Mapped[str] = mapped_column(
        String(OUTBOUND_OPERATION_MAX_LENGTH), nullable=False
    )
    provider_operation: Mapped[str] = mapped_column(
        String(OUTBOUND_OPERATION_MAX_LENGTH), nullable=False
    )
    transport_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    destination_origin: Mapped[str] = mapped_column(
        String(OUTBOUND_DESTINATION_ORIGIN_MAX_LENGTH), nullable=False
    )
    request_fingerprint: Mapped[str] = mapped_column(
        String(OUTBOUND_REQUEST_FINGERPRINT_LENGTH), nullable=False
    )
    provider_idempotency_key: Mapped[str] = mapped_column(String(64), nullable=False)
    state: Mapped[OutboundAttemptState] = mapped_column(
        _attempt_state_enum(),
        nullable=False,
        default=OutboundAttemptState.PREPARED,
        server_default=OutboundAttemptState.PREPARED.value,
        index=True,
    )
    send_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    provider_reference: Mapped[str | None] = mapped_column(
        String(OUTBOUND_PROVIDER_REFERENCE_MAX_LENGTH), nullable=True
    )
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    failure_code: Mapped[str | None] = mapped_column(
        String(OUTBOUND_FAILURE_CODE_MAX_LENGTH), nullable=True
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    outcome_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cancel_requested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    reconciled_at: Mapped[datetime | None] = mapped_column(
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
