"""Widget Session Authentication Dependency.

This module provides FastAPI dependencies for authenticating widget API requests
using session-based authentication.

Widget users are contacts (end users), not organization members.
This is completely separate from JWT-based member authentication.
"""

from datetime import datetime, timezone

from fastapi import Depends, HTTPException, Header, status
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from eylo.common.database import get_db
from eylo.modules.auth.models import AuthSessionModel
from eylo.modules.auth.schemas import CurrentContactSchema
from eylo.modules.contacts.schemas.indb import ContactRef
from eylo.modules.contacts.service import ContactService


async def get_current_contact(
    x_session_id: str | None = Header(None, alias="X-Session-ID"),
    db: AsyncSession = Depends(get_db),
) -> CurrentContactSchema:
    """Authenticate a widget API request using session ID.

    Validates the session ID from the X-Session-ID header and returns
    a CurrentContactSchema representing the authenticated contact (end user).

    This is for widget/end-user APIs only, NOT for web/member APIs.

    Args:
        x_session_id: Session ID from X-Session-ID header
        db: Database session

    Returns:
        CurrentContactSchema with contact information

    Raises:
        HTTPException: If session is invalid, expired, or not found

    """
    if not x_session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
        )

    # Query for active session
    query = select(AuthSessionModel).where(
        and_(
            AuthSessionModel.session_token == x_session_id,
            AuthSessionModel.deleted.is_(False),
        )
    )
    result = await db.execute(query)
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
        )

    # Check if session is expired
    # Type ignore: SQLAlchemy model datetime comparison is valid at runtime
    if session.expires_at < datetime.now(timezone.utc):  # type: ignore[operator]
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired",
        )

    # Get contact details
    contact_service = ContactService(db=db)
    contact = await contact_service.get_by_ref(
        ContactRef(
            organization_id=session.organization_id,
            contact_id=session.contact_id,
        )
    )

    if not contact:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Contact not found for session",
        )

    # Return CurrentContactSchema for widget authentication
    return CurrentContactSchema(
        contact_id=contact.id,
        organization_id=session.organization_id,
        session_id=x_session_id,
    )
