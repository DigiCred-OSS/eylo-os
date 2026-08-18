"""Contact-owned conversation read state."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from eylo.modules.conversations.exceptions import ConversationNotFound
from eylo.modules.conversations.repositories.participants import (
    ConversationParticipantRepository,
)


class ConversationReadService:
    def __init__(self, db: AsyncSession | None = None) -> None:
        self._participants = ConversationParticipantRepository(db)

    async def mark_read(
        self,
        *,
        organization_id: UUID,
        contact_id: UUID,
        conversation_id: UUID,
    ) -> datetime:
        read_at = await self._participants.mark_contact_read(
            organization_id=organization_id,
            contact_id=contact_id,
            conversation_id=conversation_id,
            read_at=datetime.now(timezone.utc),
        )
        if read_at is None:
            raise ConversationNotFound
        return read_at

    async def unread_counts(
        self,
        *,
        organization_id: UUID,
        contact_id: UUID,
        conversation_ids: list[UUID],
    ) -> dict[UUID, int]:
        return await self._participants.unread_assistant_counts(
            organization_id=organization_id,
            contact_id=contact_id,
            conversation_ids=conversation_ids,
        )


__all__ = ["ConversationReadService"]
