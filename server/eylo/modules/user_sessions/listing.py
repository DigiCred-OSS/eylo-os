"""Tenant-scoped aggregate queries for user sessions and timeline facts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import String, asc, cast, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from eylo.events.durable.models import EventOutboxModel
from eylo.modules.agent_runs.models import AgentRunModel
from eylo.modules.contacts.models import ContactsModel
from eylo.modules.conversations.models.messages import MessagesModel
from eylo.modules.telephony.models import TelephonyCallModel
from eylo.modules.user_sessions.domain import (
    UserSessionEntryChannel,
    UserSessionNotFound,
    UserSessionState,
)
from eylo.modules.user_sessions.models import (
    UserSessionConversationModel,
    UserSessionModel,
)
from eylo.modules.user_sessions.schemas import (
    TimelineCategory,
    UserSessionContactRead,
    UserSessionCountsRead,
    UserSessionPage,
    UserSessionRead,
    UserSessionTimelinePage,
)
from eylo.modules.user_sessions.timeline import (
    ALLOWED_TIMELINE_EVENT_TYPES,
    TECHNICAL_TIMELINE_EVENT_TYPES,
    event_types_for_categories,
    project_timeline_event,
)
from eylo.modules.voice_transcripts.models import VoiceSessionModel


class UserSessionSortField(StrEnum):
    STARTED_AT = "started_at"
    LAST_ACTIVITY_AT = "last_activity_at"
    STATE = "state"
    CONTACT = "contact"


class UserSessionSortDirection(StrEnum):
    ASC = "asc"
    DESC = "desc"


@dataclass(frozen=True, slots=True)
class UserSessionListQuery:
    search: str | None = None
    contact_id: UUID | None = None
    states: tuple[UserSessionState, ...] = ()
    entry_channels: tuple[UserSessionEntryChannel, ...] = ()
    started_from: datetime | None = None
    started_to: datetime | None = None
    sort_by: UserSessionSortField = UserSessionSortField.STARTED_AT
    sort_direction: UserSessionSortDirection = UserSessionSortDirection.DESC


class UserSessionQueryService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list(
        self,
        *,
        organization_id: UUID,
        query: UserSessionListQuery,
        page: int,
        limit: int,
    ) -> UserSessionPage:
        predicates = self._list_predicates(organization_id, query)
        conversation_count = (
            select(func.count(UserSessionConversationModel.id))
            .where(
                UserSessionConversationModel.organization_id == organization_id,
                UserSessionConversationModel.user_session_id == UserSessionModel.id,
                UserSessionConversationModel.deleted.is_(False),
            )
            .correlate(UserSessionModel)
            .scalar_subquery()
        )
        event_count = (
            select(func.count(EventOutboxModel.id))
            .where(
                EventOutboxModel.organization_id == organization_id,
                EventOutboxModel.correlation_id == UserSessionModel.id,
                EventOutboxModel.event_type.in_(ALLOWED_TIMELINE_EVENT_TYPES),
            )
            .correlate(UserSessionModel)
            .scalar_subquery()
        )
        order_column = {
            UserSessionSortField.STARTED_AT: UserSessionModel.started_at,
            UserSessionSortField.LAST_ACTIVITY_AT: UserSessionModel.last_activity_at,
            UserSessionSortField.STATE: UserSessionModel.state,
            UserSessionSortField.CONTACT: func.coalesce(
                func.lower(ContactsModel.name),
                func.lower(ContactsModel.primary_email),
                func.lower(ContactsModel.primary_phone),
                "",
            ),
        }[query.sort_by]
        order = asc if query.sort_direction is UserSessionSortDirection.ASC else desc
        rows = (
            await self.session.execute(
                select(
                    UserSessionModel,
                    ContactsModel,
                    conversation_count.label("conversation_count"),
                    event_count.label("event_count"),
                )
                .join(
                    ContactsModel,
                    (ContactsModel.id == UserSessionModel.contact_id)
                    & (
                        ContactsModel.organization_id
                        == UserSessionModel.organization_id
                    ),
                )
                .where(*predicates)
                .order_by(order(order_column), order(UserSessionModel.id))
                .offset((page - 1) * limit)
                .limit(limit)
            )
        ).all()
        total = await self.session.scalar(
            select(func.count(UserSessionModel.id))
            .join(
                ContactsModel,
                (ContactsModel.id == UserSessionModel.contact_id)
                & (ContactsModel.organization_id == UserSessionModel.organization_id),
            )
            .where(*predicates)
        )
        return UserSessionPage(
            items=[
                self._session_read(
                    user_session,
                    contact,
                    UserSessionCountsRead(
                        conversations=conversation_count_value,
                        timeline_events=event_count_value,
                    ),
                )
                for user_session, contact, conversation_count_value, event_count_value in rows
            ],
            page=page,
            limit=limit,
            total=int(total or 0),
        )

    async def get(
        self,
        *,
        organization_id: UUID,
        user_session_id: UUID,
    ) -> UserSessionRead:
        result = await self.session.execute(
            select(UserSessionModel, ContactsModel)
            .join(
                ContactsModel,
                (ContactsModel.id == UserSessionModel.contact_id)
                & (ContactsModel.organization_id == UserSessionModel.organization_id),
            )
            .where(
                UserSessionModel.id == user_session_id,
                UserSessionModel.organization_id == organization_id,
                UserSessionModel.deleted.is_(False),
                ContactsModel.deleted.is_(False),
            )
        )
        row = result.one_or_none()
        if row is None:
            raise UserSessionNotFound
        user_session, contact = row
        counts = await self._counts(
            organization_id=organization_id,
            user_session_id=user_session_id,
        )
        return self._session_read(user_session, contact, counts)

    async def timeline(
        self,
        *,
        organization_id: UUID,
        user_session_id: UUID,
        categories: set[TimelineCategory],
        event_types: set[str],
        include_technical: bool,
        page: int,
        limit: int,
    ) -> UserSessionTimelinePage:
        exists = await self.session.scalar(
            select(UserSessionModel.id).where(
                UserSessionModel.id == user_session_id,
                UserSessionModel.organization_id == organization_id,
                UserSessionModel.deleted.is_(False),
            )
        )
        if exists is None:
            raise UserSessionNotFound
        visible_categories = set(categories)
        if include_technical and visible_categories:
            visible_categories.add(TimelineCategory.TECHNICAL)
        allowed = set(event_types_for_categories(visible_categories))
        if event_types:
            allowed.intersection_update(event_types)
        if not include_technical:
            allowed.difference_update(TECHNICAL_TIMELINE_EVENT_TYPES)
        predicates = (
            EventOutboxModel.organization_id == organization_id,
            EventOutboxModel.correlation_id == user_session_id,
            EventOutboxModel.event_type.in_(allowed),
        )
        rows = (
            await self.session.scalars(
                select(EventOutboxModel)
                .where(*predicates)
                .order_by(
                    EventOutboxModel.occurred_at.asc(),
                    EventOutboxModel.id.asc(),
                )
                .offset((page - 1) * limit)
                .limit(limit)
            )
        ).all()
        total = await self.session.scalar(
            select(func.count(EventOutboxModel.id)).where(*predicates)
        )
        return UserSessionTimelinePage(
            items=[project_timeline_event(row) for row in rows],
            page=page,
            limit=limit,
            total=int(total or 0),
        )

    async def _counts(
        self,
        *,
        organization_id: UUID,
        user_session_id: UUID,
    ) -> UserSessionCountsRead:
        def count(model, predicate):
            return (
                select(func.count(model.id))
                .where(predicate)
                .where(model.deleted.is_(False))
                .scalar_subquery()
            )

        row = (
            await self.session.execute(
                select(
                    count(
                        UserSessionConversationModel,
                        (
                            UserSessionConversationModel.organization_id
                            == organization_id
                        )
                        & (
                            UserSessionConversationModel.user_session_id
                            == user_session_id
                        ),
                    ).label("conversations"),
                    count(
                        MessagesModel,
                        MessagesModel.user_session_id == user_session_id,
                    ).label("messages"),
                    count(
                        AgentRunModel,
                        (AgentRunModel.organization_id == organization_id)
                        & (AgentRunModel.user_session_id == user_session_id),
                    ).label("agent_runs"),
                    count(
                        VoiceSessionModel,
                        (VoiceSessionModel.organization_id == organization_id)
                        & (VoiceSessionModel.user_session_id == user_session_id),
                    ).label("voice_sessions"),
                    count(
                        TelephonyCallModel,
                        (TelephonyCallModel.organization_id == organization_id)
                        & (TelephonyCallModel.user_session_id == user_session_id),
                    ).label("telephony_calls"),
                    (
                        select(func.count(EventOutboxModel.id))
                        .where(
                            EventOutboxModel.organization_id == organization_id,
                            EventOutboxModel.correlation_id == user_session_id,
                            EventOutboxModel.event_type.in_(
                                ALLOWED_TIMELINE_EVENT_TYPES
                            ),
                        )
                        .scalar_subquery()
                    ).label("timeline_events"),
                )
            )
        ).one()
        return UserSessionCountsRead(
            conversations=int(row.conversations or 0),
            messages=int(row.messages or 0),
            agent_runs=int(row.agent_runs or 0),
            voice_sessions=int(row.voice_sessions or 0),
            telephony_calls=int(row.telephony_calls or 0),
            timeline_events=int(row.timeline_events or 0),
        )

    @staticmethod
    def _list_predicates(
        organization_id: UUID,
        query: UserSessionListQuery,
    ) -> list:
        predicates = [
            UserSessionModel.organization_id == organization_id,
            UserSessionModel.deleted.is_(False),
            ContactsModel.deleted.is_(False),
        ]
        if query.contact_id is not None:
            predicates.append(UserSessionModel.contact_id == query.contact_id)
        if query.states:
            predicates.append(UserSessionModel.state.in_(query.states))
        if query.entry_channels:
            predicates.append(
                UserSessionModel.entry_channel.in_(query.entry_channels)
            )
        if query.started_from is not None:
            predicates.append(UserSessionModel.started_at >= query.started_from)
        if query.started_to is not None:
            predicates.append(UserSessionModel.started_at <= query.started_to)
        if query.search:
            term = query.search.strip()
            if term:
                predicates.append(
                    or_(
                        ContactsModel.name.icontains(term, autoescape=True),
                        ContactsModel.primary_email.icontains(term, autoescape=True),
                        ContactsModel.primary_phone.icontains(term, autoescape=True),
                        cast(UserSessionModel.id, String).icontains(
                            term, autoescape=True
                        ),
                    )
                )
        return predicates

    @staticmethod
    def _session_read(
        user_session: UserSessionModel,
        contact: ContactsModel,
        counts: UserSessionCountsRead,
    ) -> UserSessionRead:
        return UserSessionRead(
            id=user_session.id,
            organization_id=user_session.organization_id,
            contact=UserSessionContactRead(
                id=contact.id,
                name=contact.name,
                primary_email=contact.primary_email,
                primary_phone=contact.primary_phone,
            ),
            entry_channel=user_session.entry_channel,
            state=user_session.state,
            connection_sequence=user_session.connection_sequence,
            started_at=user_session.started_at,
            last_activity_at=user_session.last_activity_at,
            disconnected_at=user_session.disconnected_at,
            ended_at=user_session.ended_at,
            end_reason=user_session.end_reason,
            created_at=user_session.created_at,
            updated_at=user_session.updated_at,
            counts=counts,
        )


__all__ = [
    "UserSessionListQuery",
    "UserSessionQueryService",
    "UserSessionSortDirection",
    "UserSessionSortField",
]
