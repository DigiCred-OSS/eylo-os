"""Failure-contained runtime facts for the user-session timeline."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from eylo.common.database import start_transaction
from eylo.modules.user_sessions.events import file_user_session_fact

logger = logging.getLogger(__name__)


async def try_file_runtime_fact(
    *,
    organization_id: UUID,
    user_session_id: UUID | None,
    subject_type: str,
    subject_id: UUID | None,
    event_type: str,
    payload: dict[str, Any] | None = None,
) -> None:
    """File observability without letting it interrupt the product flow."""
    if user_session_id is None:
        return
    try:
        async with start_transaction() as session:
            await file_user_session_fact(
                session,
                organization_id=organization_id,
                user_session_id=user_session_id,
                subject_type=subject_type,
                subject_id=subject_id or user_session_id,
                event_type=event_type,
                payload=payload,
            )
    except Exception as error:  # noqa: BLE001 - observability is secondary
        logger.error(
            "Runtime timeline fact failed event_type=%s organization_id=%s "
            "error_type=%s",
            event_type,
            organization_id,
            type(error).__name__,
        )


__all__ = ["try_file_runtime_fact"]
