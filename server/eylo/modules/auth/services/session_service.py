"""Application services for the `auth` domain."""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional, override

from fastapi import Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from eylo.common.database import get_db
from eylo.common.services import EyloBaseService
from eylo.modules.auth.repository import AuthSessionRepository
from eylo.modules.auth.schemas import (
    AuthSessionCreate,
    AuthSessionInDb,
    SessionInitiateRequest,
)
from eylo.modules.contacts.domain import ContactDeletionPending, ContactIdentityInvalid
from eylo.modules.contacts.schemas.indb import (
    ContactCreateSchema,
    ContactInDb,
    ContactRef,
)
from eylo.modules.contacts.service import (
    ContactResolution,
    ContactService,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class AuthSessionInitiation:
    """A session plus safe identify-time warnings for product presentation."""

    session: AuthSessionInDb
    contact_resolution: ContactResolution


class AuthSessionService(EyloBaseService[AuthSessionInDb]):
    """Service for handling widget sessions."""

    def __init__(self, db: AsyncSession | None = None):
        self._repository = AuthSessionRepository(db=db)
        self._contact_service = ContactService(db=db)

    @property
    @override
    def schema(self) -> type[AuthSessionInDb]:
        """Returns the schema class for auth session entities."""
        return AuthSessionInDb

    @property
    def repository(self) -> AuthSessionRepository:
        return self._repository

    async def initiate_widget_session_with_resolution(
        self,
        request: SessionInitiateRequest,
    ) -> AuthSessionInitiation:
        """Identify once, preserve safe ambiguity facts, then mint a session."""
        contact_create_request = ContactCreateSchema(
            organization_id=request.organization_id,
            external_id=request.external_id,
            primary_email=request.primary_email,
            primary_phone=request.primary_phone,
            name=request.name,
            preferences=request.preferences,
        )

        try:
            resolution = await self.resolve_or_create_contact(contact_create_request)
            contact = resolution.contact
            if contact is None:
                raise RuntimeError("Contact resolution returned no contact.")
        except ContactIdentityInvalid:
            logger.info(
                "Widget contact identity input was rejected.",
                extra={"organization_id": str(request.organization_id)},
            )
            raise
        except ContactDeletionPending:
            raise
        except IntegrityError:
            logger.warning(
                "Widget contact persistence was rejected.",
                extra={"organization_id": str(request.organization_id)},
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization not found.",
            ) from None
        except Exception as error:
            logger.error(
                "Failed to resolve visitor contact.",
                extra={
                    "organization_id": str(request.organization_id),
                    "error_type": type(error).__name__,
                },
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to initiate session.",
            ) from None

        try:
            session = await self.create_session_for_contact(
                contact=contact,
                user_agent=request.user_agent,
                ip_address=request.ip_address,
            )
            return AuthSessionInitiation(
                session=session,
                contact_resolution=resolution,
            )
        except Exception as error:
            logger.error(
                "Failed to create session for contact.",
                extra={
                    "organization_id": str(request.organization_id),
                    "error_type": type(error).__name__,
                },
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to initiate session.",
            ) from None

    async def resolve_or_create_contact(
        self,
        contact_create_request: ContactCreateSchema,
    ) -> ContactResolution:
        """Delegate identify-time deduplication to the contact aggregate."""
        return await self._contact_service.resolve_or_create(contact_create_request)

    async def create_session_for_contact(
        self,
        contact: ContactInDb,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> AuthSessionInDb:
        """Create a session for a contact.

        Reuse point:
        - After obtaining a `ContactInDb` (e.g., via `_get_or_create_contact`),
          call this helper to mint a short-lived session token used by the
          agent chat widget or similar flows.

        Parameters
        ----------
        - contact: An existing contact with a valid `organization_id`.
        - user_agent, ip_address: Optional metadata (pass through from request).

        Example:
            ```python
            session = await self.create_session_for_contact(
                contact,
                user_agent=request.user_agent,
                ip_address=request.ip_address,
            )
            ```

        """
        session_create_request = AuthSessionCreate(
            organization_id=contact.organization_id,
            contact_id=contact.id,
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
            user_agent=user_agent,
            ip_address=ip_address,
        )

        new_session = await self.repository.create_(session_create_request)
        return self.orm_to_schema(new_session)

    async def validate_session_token(self, token: str) -> AuthSessionInDb | None:
        """Validates a session token and returns the session if valid."""
        entity = await self.repository.get_by_token(token)
        if not entity:
            return None
        session = self.orm_to_schema(entity)
        if session.expires_at < datetime.now(timezone.utc):
            # Optionally, you could delete the expired session here
            await self.repository.delete_(entity)
            session = None
        if session and not await self._contact_service.get_by_ref(
            ContactRef(
                organization_id=session.organization_id,
                contact_id=session.contact_id,
            )
        ):
            session = None
        return session

async def get_auth_session_service(
    db: AsyncSession = Depends(get_db),
) -> AuthSessionService:
    """Dependency provider for the AuthSessionService."""
    return AuthSessionService(db=db)
