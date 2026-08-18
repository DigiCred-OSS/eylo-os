"""Privacy-safe durable fact filing for user-session timelines."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from pydantic import JsonValue, TypeAdapter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from eylo.events.durable.domain import DurableEventEnvelope
from eylo.events.durable.service import DurableEventFiling, DurableEventService
from eylo.modules.user_sessions.domain import (
    TERMINAL_USER_SESSION_STATES,
    UserSessionNotFound,
)
from eylo.modules.user_sessions.models import UserSessionModel
from eylo.modules.user_sessions.timeline import TIMELINE_EVENT_CATALOG

_SAFE_PAYLOAD = TypeAdapter(dict[str, JsonValue])


async def file_user_session_fact(
    session: AsyncSession,
    *,
    organization_id: UUID,
    user_session_id: UUID,
    subject_type: str,
    subject_id: UUID,
    event_type: str,
    payload: dict[str, Any] | None = None,
    occurred_at: datetime | None = None,
    causation_id: UUID | None = None,
    event_id: UUID | None = None,
) -> DurableEventFiling:
    """File one validated, unordered timeline fact in the source transaction."""
    recorded_at = datetime.now(timezone.utc)
    occurred_at = occurred_at or recorded_at
    definition = TIMELINE_EVENT_CATALOG.get(event_type)
    if definition is None:
        raise ValueError(f"Unsupported user-session timeline event: {event_type}")
    safe_payload = _SAFE_PAYLOAD.validate_python(payload or {})
    unexpected_keys = safe_payload.keys() - definition.detail_keys
    if unexpected_keys:
        raise ValueError(
            "Unsupported user-session timeline payload keys: "
            f"{', '.join(sorted(unexpected_keys))}"
        )

    user_session = await session.scalar(
        select(UserSessionModel)
        .where(
            UserSessionModel.id == user_session_id,
            UserSessionModel.organization_id == organization_id,
            UserSessionModel.deleted.is_(False),
        )
        .with_for_update()
    )
    if user_session is None:
        raise UserSessionNotFound
    if (
        user_session.state not in TERMINAL_USER_SESSION_STATES
        and occurred_at > user_session.last_activity_at
    ):
        user_session.last_activity_at = occurred_at

    envelope = DurableEventEnvelope(
        event_id=event_id or uuid4(),
        organization_id=organization_id,
        subject_type=subject_type,
        subject_id=subject_id,
        event_type=event_type,
        event_version=1,
        occurred_at=occurred_at,
        recorded_at=recorded_at,
        correlation_id=user_session_id,
        causation_id=causation_id,
        payload=safe_payload,
    )
    return await DurableEventService(session).file(
        envelope=envelope,
        consumer_names=(),
    )
