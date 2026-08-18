"""FastAPI dependencies for SessionContext injection."""

from __future__ import annotations

from fastapi import Depends

from eylo.modules.auth.dependencies.widget_auth import get_current_contact
from eylo.modules.auth.schemas.widget import CurrentContactSchema
from eylo.modules.session_context.schemas import SessionContext
from eylo.modules.session_context.service import SessionContextHydrator


async def get_session_context(
    contact: CurrentContactSchema = Depends(get_current_contact),
) -> SessionContext:
    """FastAPI dependency that builds SessionContext for HTTP widget routes.

    Replaces direct use of CurrentContactSchema in widget controllers.
    Wraps the existing get_current_contact() dependency — no new DB queries.
    """
    return SessionContextHydrator.for_http(
        organization_id=contact.organization_id,
        session_id=contact.session_id,
        contact_id=contact.contact_id,
    )
