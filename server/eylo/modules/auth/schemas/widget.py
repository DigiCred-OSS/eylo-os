"""Widget Authentication Schemas.

This module defines schemas specific to widget authentication.
Widget users are contacts (end users), not organization members.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from eylo.common.schemas import EyloBaseApiSchema


class CurrentContactSchema(BaseModel):
    """Schema representing an authenticated widget contact (end user).

    This is distinct from CurrentUserSchema which represents an
    authenticated organization member (web API user).

    Attributes:
        contact_id: UUID of the contact
        organization_id: UUID of the organization the contact belongs to
        email: Contact's primary email address
        session_id: The session token for this contact

    """

    contact_id: UUID = Field(..., description="Contact ID")
    organization_id: UUID = Field(..., description="Organization ID")
    session_id: str = Field(..., description="Session token")


class WidgetDevelopmentSessionResponse(EyloBaseApiSchema):
    """Normal contact session issued to the standalone local widget."""

    organization_id: UUID
    contact_id: UUID
    session_token: str
    session_expires_at: datetime
