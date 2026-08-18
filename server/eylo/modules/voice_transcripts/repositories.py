"""Repository layer for voice transcript sessions and segments."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import func, select, text, update

from eylo.common.repositories import BaseORMRepository
from eylo.modules.voice_transcripts.models import VoiceSegmentModel, VoiceSessionModel
from eylo.modules.voice_transcripts.schemas.indb import (
    VoiceSegmentCreate,
    VoiceSessionCreate,
    VoiceSessionUpdate,
)


@dataclass(frozen=True, slots=True)
class VoiceSegmentRollup:
    segment_count: int
    partial_segment_count: int
    user_talk_time_ms: int | None
    assistant_talk_time_ms: int | None
    interruption_count: int
    dtmf_count: int
    transfer_count: int


class VoiceSessionRepository(BaseORMRepository[VoiceSessionModel]):
    """Data access for voice_sessions rows."""

    @property
    def model(self) -> type[VoiceSessionModel]:
        return VoiceSessionModel

    async def create(self, data: VoiceSessionCreate) -> VoiceSessionModel:
        entity = self.model(**data.model_dump(exclude_none=True))
        return await self.save_(entity)

    async def get_by_session_key(
        self, *, organization_id: UUID, session_id: str, runtime_mode: str
    ) -> VoiceSessionModel | None:
        result = await self.db_session.execute(
            select(self.model)
            .where(self.model.organization_id == organization_id)
            .where(self.model.session_id == session_id)
            .where(self.model.runtime_mode == runtime_mode)
            .where(self.model.deleted.is_(False))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_by_id(
        self, *, organization_id: UUID, session_id: UUID
    ) -> VoiceSessionModel | None:
        result = await self.db_session.execute(
            select(self.model)
            .where(self.model.organization_id == organization_id)
            .where(self.model.id == session_id)
            .where(self.model.deleted.is_(False))
        )
        return result.scalar_one_or_none()

    async def get_by_conversation(
        self,
        *,
        organization_id: UUID,
        conversation_id: UUID,
    ) -> VoiceSessionModel | None:
        result = await self.db_session.execute(
            select(self.model)
            .where(self.model.organization_id == organization_id)
            .where(self.model.conversation_id == conversation_id)
            .where(self.model.deleted.is_(False))
            .order_by(self.model.started_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_by_conversation_session(
        self,
        *,
        organization_id: UUID,
        conversation_id: UUID,
        session_id: str,
        runtime_mode: str | None = None,
    ) -> VoiceSessionModel | None:
        filters = [
            self.model.organization_id == organization_id,
            self.model.conversation_id == conversation_id,
            self.model.session_id == session_id,
            self.model.deleted.is_(False),
        ]
        if runtime_mode:
            filters.append(self.model.runtime_mode == runtime_mode)
        result = await self.db_session.execute(
            select(self.model)
            .where(*filters)
            .order_by(self.model.started_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def list_by_organization(
        self,
        *,
        organization_id: UUID,
        limit: int,
        offset: int,
        conversation_id: UUID | None = None,
        agent_id: UUID | None = None,
        status: str | None = None,
        runtime_mode: str | None = None,
    ) -> list[VoiceSessionModel]:
        filters = [
            self.model.organization_id == organization_id,
            self.model.deleted.is_(False),
        ]
        if conversation_id:
            filters.append(self.model.conversation_id == conversation_id)
        if agent_id:
            filters.append(self.model.agent_id == agent_id)
        if status:
            filters.append(self.model.status == status)
        if runtime_mode:
            filters.append(self.model.runtime_mode == runtime_mode)
        result = await self.db_session.execute(
            select(self.model)
            .where(*filters)
            .order_by(self.model.started_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def count_by_organization(
        self,
        *,
        organization_id: UUID,
        conversation_id: UUID | None = None,
        agent_id: UUID | None = None,
        status: str | None = None,
        runtime_mode: str | None = None,
    ) -> int:
        filters = [
            self.model.organization_id == organization_id,
            self.model.deleted.is_(False),
        ]
        if conversation_id:
            filters.append(self.model.conversation_id == conversation_id)
        if agent_id:
            filters.append(self.model.agent_id == agent_id)
        if status:
            filters.append(self.model.status == status)
        if runtime_mode:
            filters.append(self.model.runtime_mode == runtime_mode)
        result = await self.db_session.execute(
            select(func.count()).select_from(self.model).where(*filters)
        )
        return int(result.scalar_one() or 0)

    async def update(
        self, session_id: UUID, data: VoiceSessionUpdate
    ) -> VoiceSessionModel | None:
        values = data.model_dump(exclude_unset=True)
        if not values:
            return await self.get_(session_id)
        result = await self.db_session.execute(
            update(self.model)
            .where(self.model.id == session_id)
            .values(**values)
            .returning(self.model)
        )
        return result.scalar_one_or_none()


class VoiceSegmentRepository(BaseORMRepository[VoiceSegmentModel]):
    """Data access for voice_segments rows."""

    @property
    def model(self) -> type[VoiceSegmentModel]:
        return VoiceSegmentModel

    async def create(self, data: VoiceSegmentCreate) -> VoiceSegmentModel:
        payload = data.model_dump(exclude_none=True)
        if payload.get("sequence") is None:
            await self._lock_session_sequence(data.voice_session_id)
            payload["sequence"] = await self.next_sequence(data.voice_session_id)
        entity = self.model(**payload)
        return await self.save_(entity)

    async def _lock_session_sequence(self, voice_session_id: UUID) -> None:
        """Serialize per-session sequence allocation on PostgreSQL."""
        bind = self.db_session.get_bind()
        if bind and bind.dialect.name == "postgresql":
            await self.db_session.execute(
                text("SELECT pg_advisory_xact_lock(hashtext(:lock_key))"),
                {"lock_key": f"voice-segments:{voice_session_id}"},
            )

    async def next_sequence(self, voice_session_id: UUID) -> int:
        result = await self.db_session.execute(
            select(func.coalesce(func.max(self.model.sequence), -1) + 1).where(
                self.model.voice_session_id == voice_session_id
            )
        )
        return int(result.scalar_one() or 0)

    async def list_by_session(
        self,
        voice_session_id: UUID,
        *,
        limit: int,
        offset: int,
    ) -> list[VoiceSegmentModel]:
        result = await self.db_session.execute(
            select(self.model)
            .where(self.model.voice_session_id == voice_session_id)
            .where(self.model.deleted.is_(False))
            .order_by(
                self.model.source_created_at.asc().nulls_last(),
                self.model.sequence.asc(),
                self.model.message_id.asc().nulls_last(),
                self.model.created_at.asc(),
                self.model.id.asc(),
            )
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def get_by_message_id(self, message_id: UUID) -> VoiceSegmentModel | None:
        return await self.db_session.scalar(
            select(self.model).where(
                self.model.message_id == message_id,
                self.model.deleted.is_(False),
            )
        )

    async def get_by_session_sequence(
        self,
        voice_session_id: UUID,
        sequence: int,
    ) -> VoiceSegmentModel | None:
        return await self.db_session.scalar(
            select(self.model).where(
                self.model.voice_session_id == voice_session_id,
                self.model.sequence == sequence,
                self.model.deleted.is_(False),
            )
        )

    async def count_by_session(self, voice_session_id: UUID) -> int:
        result = await self.db_session.execute(
            select(func.count())
            .select_from(self.model)
            .where(self.model.voice_session_id == voice_session_id)
            .where(self.model.deleted.is_(False))
        )
        return int(result.scalar_one() or 0)

    async def summarize(self, voice_session_id: UUID) -> VoiceSegmentRollup:
        row = (
            await self.db_session.execute(
                select(
                    func.count(),
                    func.count().filter(self.model.is_partial.is_(True)),
                    func.count().filter(self.model.role == "user"),
                    func.count(self.model.duration_ms).filter(
                        self.model.role == "user"
                    ),
                    func.sum(self.model.duration_ms).filter(self.model.role == "user"),
                    func.count().filter(self.model.role == "assistant"),
                    func.count(self.model.duration_ms).filter(
                        self.model.role == "assistant"
                    ),
                    func.sum(self.model.duration_ms).filter(
                        self.model.role == "assistant"
                    ),
                    func.count().filter(self.model.speech_outcome == "interrupted"),
                    func.count().filter(self.model.dtmf_digits.is_not(None)),
                    func.count().filter(self.model.transfer_to.is_not(None)),
                )
                .where(self.model.voice_session_id == voice_session_id)
                .where(self.model.deleted.is_(False))
            )
        ).one()
        (
            segment_count,
            partial_segment_count,
            user_count,
            user_timed_count,
            user_duration,
            assistant_count,
            assistant_timed_count,
            assistant_duration,
            interruption_count,
            dtmf_count,
            transfer_count,
        ) = row
        return VoiceSegmentRollup(
            segment_count=int(segment_count or 0),
            partial_segment_count=int(partial_segment_count or 0),
            user_talk_time_ms=_complete_duration(
                count=user_count,
                timed_count=user_timed_count,
                duration=user_duration,
            ),
            assistant_talk_time_ms=_complete_duration(
                count=assistant_count,
                timed_count=assistant_timed_count,
                duration=assistant_duration,
            ),
            interruption_count=int(interruption_count or 0),
            dtmf_count=int(dtmf_count or 0),
            transfer_count=int(transfer_count or 0),
        )


def _complete_duration(
    *, count: int, timed_count: int, duration: int | None
) -> int | None:
    if not count:
        return 0
    if timed_count != count:
        return None
    return int(duration or 0)
