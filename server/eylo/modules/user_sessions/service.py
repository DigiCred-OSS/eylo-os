"""Canonical user-session lifecycle and conversation membership."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from eylo.modules.user_sessions.domain import (
    TERMINAL_USER_SESSION_STATES,
    UserSessionEntryChannel,
    UserSessionNotFound,
    UserSessionState,
    UserSessionTerminal,
)
from eylo.modules.user_sessions.events import file_user_session_fact
from eylo.modules.user_sessions.models import (
    UserSessionConversationModel,
    UserSessionModel,
)


@dataclass(frozen=True, slots=True)
class UserSessionStartResult:
    user_session: UserSessionModel
    created: bool
    reconnected: bool


class UserSessionService:
    """Own lifecycle rules; callers only supply authenticated authority."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def start_or_resume(
        self,
        *,
        organization_id: UUID,
        contact_id: UUID,
        entry_channel: UserSessionEntryChannel,
        requested_session_id: UUID | None = None,
    ) -> UserSessionStartResult:
        now = datetime.now(timezone.utc)
        if requested_session_id is None:
            user_session = UserSessionModel(
                organization_id=organization_id,
                contact_id=contact_id,
                entry_channel=entry_channel,
                state=UserSessionState.ACTIVE,
                connection_sequence=1,
                started_at=now,
                last_activity_at=now,
            )
            self.session.add(user_session)
            await self.session.flush()
            await file_user_session_fact(
                self.session,
                organization_id=organization_id,
                user_session_id=user_session.id,
                subject_type="user.session",
                subject_id=user_session.id,
                event_type="user.session.started",
                occurred_at=now,
                payload={
                    "entry_channel": entry_channel.value,
                    "connection_sequence": 1,
                },
            )
            return UserSessionStartResult(user_session, True, False)

        user_session = await self._get_exact(
            organization_id=organization_id,
            contact_id=contact_id,
            entry_channel=entry_channel,
            user_session_id=requested_session_id,
            for_update=True,
        )
        if user_session.state in TERMINAL_USER_SESSION_STATES:
            raise UserSessionTerminal
        user_session.state = UserSessionState.ACTIVE
        user_session.connection_sequence += 1
        user_session.last_activity_at = now
        user_session.disconnected_at = None
        await self.session.flush()
        await file_user_session_fact(
            self.session,
            organization_id=organization_id,
            user_session_id=user_session.id,
            subject_type="user.session",
            subject_id=user_session.id,
            event_type="user.session.reconnected",
            occurred_at=now,
            payload={"connection_sequence": user_session.connection_sequence},
        )
        return UserSessionStartResult(user_session, False, True)

    async def get_owned(
        self,
        *,
        organization_id: UUID,
        user_session_id: UUID,
        for_update: bool = False,
    ) -> UserSessionModel:
        query = select(UserSessionModel).where(
            UserSessionModel.id == user_session_id,
            UserSessionModel.organization_id == organization_id,
            UserSessionModel.deleted.is_(False),
        )
        if for_update:
            query = query.with_for_update()
        user_session = await self.session.scalar(query)
        if user_session is None:
            raise UserSessionNotFound
        return user_session

    async def require_contact_session(
        self,
        *,
        organization_id: UUID,
        contact_id: UUID,
        user_session_id: UUID,
    ) -> UserSessionModel:
        return await self._get_exact(
            organization_id=organization_id,
            contact_id=contact_id,
            user_session_id=user_session_id,
        )

    async def touch(
        self,
        *,
        organization_id: UUID,
        user_session_id: UUID,
    ) -> bool:
        result = await self.session.execute(
            update(UserSessionModel)
            .where(
                UserSessionModel.id == user_session_id,
                UserSessionModel.organization_id == organization_id,
                UserSessionModel.state == UserSessionState.ACTIVE,
                UserSessionModel.deleted.is_(False),
            )
            .values(last_activity_at=datetime.now(timezone.utc))
        )
        return bool(result.rowcount)

    async def disconnect(
        self,
        *,
        organization_id: UUID,
        user_session_id: UUID,
        reason: str,
        expected_connection_sequence: int | None = None,
    ) -> bool:
        now = datetime.now(timezone.utc)
        user_session = await self.get_owned(
            organization_id=organization_id,
            user_session_id=user_session_id,
            for_update=True,
        )
        if (
            expected_connection_sequence is not None
            and user_session.connection_sequence != expected_connection_sequence
        ):
            return False
        if user_session.state is not UserSessionState.ACTIVE:
            return False
        user_session.state = UserSessionState.DISCONNECTED
        user_session.last_activity_at = now
        user_session.disconnected_at = now
        await self.session.flush()
        await file_user_session_fact(
            self.session,
            organization_id=organization_id,
            user_session_id=user_session.id,
            subject_type="user.session",
            subject_id=user_session.id,
            event_type="user.session.disconnected",
            occurred_at=now,
            payload={
                "reason": reason,
                "connection_sequence": user_session.connection_sequence,
            },
        )
        return True

    async def finish(
        self,
        *,
        organization_id: UUID,
        user_session_id: UUID,
        state: UserSessionState,
        reason: str,
        expected_connection_sequence: int | None = None,
    ) -> bool:
        if state not in TERMINAL_USER_SESSION_STATES:
            raise ValueError("A finished user session must be ended or failed.")
        now = datetime.now(timezone.utc)
        user_session = await self.get_owned(
            organization_id=organization_id,
            user_session_id=user_session_id,
            for_update=True,
        )
        if (
            expected_connection_sequence is not None
            and user_session.connection_sequence != expected_connection_sequence
        ):
            return False
        if user_session.state in TERMINAL_USER_SESSION_STATES:
            return False
        user_session.state = state
        user_session.last_activity_at = now
        user_session.ended_at = now
        user_session.end_reason = reason
        await self.session.flush()
        await file_user_session_fact(
            self.session,
            organization_id=organization_id,
            user_session_id=user_session.id,
            subject_type="user.session",
            subject_id=user_session.id,
            event_type=(
                "user.session.ended"
                if state is UserSessionState.ENDED
                else "user.session.failed"
            ),
            occurred_at=now,
            payload={
                "reason": reason,
                "connection_sequence": user_session.connection_sequence,
            },
        )
        return True

    async def link_conversation(
        self,
        *,
        organization_id: UUID,
        user_session_id: UUID,
        conversation_id: UUID,
    ) -> bool:
        """Link a conversation and report whether the session/conversation pair is new."""
        now = datetime.now(timezone.utc)
        inserted_id = await self.session.scalar(
            insert(UserSessionConversationModel)
            .values(
                organization_id=organization_id,
                user_session_id=user_session_id,
                conversation_id=conversation_id,
                first_seen_at=now,
                last_seen_at=now,
            )
            .on_conflict_do_nothing(
                constraint="uq_user_session_conversations_pair",
            )
            .returning(UserSessionConversationModel.id)
        )
        if inserted_id is None:
            await self.session.execute(
                update(UserSessionConversationModel)
                .where(
                    UserSessionConversationModel.organization_id == organization_id,
                    UserSessionConversationModel.user_session_id == user_session_id,
                    UserSessionConversationModel.conversation_id == conversation_id,
                )
                .values(
                    last_seen_at=now,
                    updated_at=now,
                    deleted=False,
                )
            )
        await self.touch(
            organization_id=organization_id,
            user_session_id=user_session_id,
        )
        return inserted_id is not None

    async def require_conversation_link(
        self,
        *,
        organization_id: UUID,
        contact_id: UUID,
        user_session_id: UUID,
        conversation_id: UUID,
    ) -> UserSessionModel:
        user_session = await self.require_contact_session(
            organization_id=organization_id,
            contact_id=contact_id,
            user_session_id=user_session_id,
        )
        if user_session.state is not UserSessionState.ACTIVE:
            raise UserSessionNotFound
        link = await self.session.scalar(
            select(UserSessionConversationModel.id).where(
                UserSessionConversationModel.organization_id == organization_id,
                UserSessionConversationModel.user_session_id == user_session_id,
                UserSessionConversationModel.conversation_id == conversation_id,
                UserSessionConversationModel.deleted.is_(False),
            )
        )
        if link is None:
            raise UserSessionNotFound
        return user_session

    async def _get_exact(
        self,
        *,
        organization_id: UUID,
        contact_id: UUID,
        user_session_id: UUID,
        entry_channel: UserSessionEntryChannel | None = None,
        for_update: bool = False,
    ) -> UserSessionModel:
        predicates = [
            UserSessionModel.id == user_session_id,
            UserSessionModel.organization_id == organization_id,
            UserSessionModel.contact_id == contact_id,
            UserSessionModel.deleted.is_(False),
        ]
        if entry_channel is not None:
            predicates.append(UserSessionModel.entry_channel == entry_channel)
        query = select(UserSessionModel).where(*predicates)
        if for_update:
            query = query.with_for_update()
        user_session = await self.session.scalar(query)
        if user_session is None:
            raise UserSessionNotFound
        return user_session
