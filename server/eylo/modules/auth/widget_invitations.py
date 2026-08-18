"""Auth-owned persistence and token rules for guest-chat invitations."""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from eylo.modules.auth.models import WidgetInvitationModel

MAX_WIDGET_INVITATION_LIFETIME = timedelta(hours=24)
_TOKEN_BYTES = 32


class WidgetInvitationIssuerKind(StrEnum):
    MEMBER = "member"
    AGENT = "agent"


class WidgetInvitationError(Exception):
    """Base invitation command failure."""


class WidgetInvitationUnavailable(WidgetInvitationError):
    """Unknown, expired, consumed, or otherwise unusable invitation."""


class WidgetInvitationInvalid(WidgetInvitationError, ValueError):
    """Issuance input cannot produce a bounded invitation."""


class WidgetInvitationConfigurationError(WidgetInvitationError):
    """Deployment configuration cannot produce a safe guest URL."""


@dataclass(frozen=True, slots=True)
class WidgetSessionAuthority:
    """Immutable Agent and conversation boundary granted to one widget session."""

    agent_id: UUID
    agent_revision: int
    conversation_id: UUID


class WidgetInvitationService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def issue(
        self,
        *,
        organization_id: UUID,
        contact_id: UUID,
        agent_id: UUID,
        agent_revision: int,
        opener: str,
        expires_at: datetime,
        issued_by_kind: WidgetInvitationIssuerKind,
        issued_by_id: UUID,
        now: datetime,
    ) -> tuple[WidgetInvitationModel, str]:
        _validate_expiry(expires_at, now=now)
        normalized_opener = opener.strip()
        if not normalized_opener or len(normalized_opener) > 4096:
            raise WidgetInvitationInvalid(
                "Invitation opener must contain between 1 and 4096 characters."
            )
        token = secrets.token_urlsafe(_TOKEN_BYTES)
        row = WidgetInvitationModel(
            organization_id=organization_id,
            contact_id=contact_id,
            agent_id=agent_id,
            agent_revision=agent_revision,
            token_digest=_token_digest(token),
            opener=normalized_opener,
            expires_at=expires_at,
            issued_by_kind=issued_by_kind.value,
            issued_by_id=issued_by_id,
        )
        self._db.add(row)
        await self._db.flush()
        return row, token

    async def lock_for_exchange(self, token: str) -> WidgetInvitationModel:
        row = await self._db.scalar(
            select(WidgetInvitationModel)
            .where(
                WidgetInvitationModel.token_digest == _token_digest(token),
                WidgetInvitationModel.deleted.is_(False),
            )
            .with_for_update()
        )
        if row is None:
            raise WidgetInvitationUnavailable
        return row

    async def record_consumed(
        self,
        invitation: WidgetInvitationModel,
        *,
        request_id: UUID,
        session_id: UUID,
        conversation_id: UUID,
        consumed_at: datetime,
    ) -> None:
        if invitation.consumed_at is not None:
            raise WidgetInvitationUnavailable
        invitation.consumed_request_id = request_id
        invitation.session_id = session_id
        invitation.conversation_id = conversation_id
        invitation.consumed_at = consumed_at
        await self._db.flush()

    async def get_session_authority(
        self,
        *,
        organization_id: UUID,
        contact_id: UUID,
        session_id: UUID,
    ) -> WidgetSessionAuthority | None:
        """Resolve the exact grant that created an authenticated widget session."""
        row = await self._db.scalar(
            select(WidgetInvitationModel).where(
                WidgetInvitationModel.organization_id == organization_id,
                WidgetInvitationModel.contact_id == contact_id,
                WidgetInvitationModel.session_id == session_id,
                WidgetInvitationModel.consumed_at.is_not(None),
                WidgetInvitationModel.deleted.is_(False),
            )
        )
        if row is None or row.conversation_id is None:
            return None
        return WidgetSessionAuthority(
            agent_id=row.agent_id,
            agent_revision=row.agent_revision,
            conversation_id=row.conversation_id,
        )


def _validate_expiry(expires_at: datetime, *, now: datetime) -> None:
    if expires_at.tzinfo is None or expires_at.utcoffset() is None:
        raise WidgetInvitationInvalid("Invitation expiry must be timezone-aware.")
    if expires_at <= now:
        raise WidgetInvitationInvalid("Invitation expiry must be in the future.")
    if expires_at > now + MAX_WIDGET_INVITATION_LIFETIME:
        raise WidgetInvitationInvalid(
            "Invitation expiry exceeds the 24-hour security ceiling."
        )


def _token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


__all__ = [
    "MAX_WIDGET_INVITATION_LIFETIME",
    "WidgetInvitationConfigurationError",
    "WidgetInvitationError",
    "WidgetInvitationInvalid",
    "WidgetInvitationIssuerKind",
    "WidgetInvitationService",
    "WidgetInvitationUnavailable",
    "WidgetSessionAuthority",
]
