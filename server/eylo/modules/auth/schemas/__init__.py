"""Authentication schemas package."""

from __future__ import annotations

from .api_key import (
    ApiKeyCreate,
    ApiKeyInDb,
    ApiKeyResponse,
)
from .widget import CurrentContactSchema

__all__ = [
    "CurrentContactSchema",
    "ApiKeyCreate",
    "ApiKeyInDb",
    "ApiKeyResponse",
    "WaitlistRequestSchema",
    "RegistrationRequestSchema",
    "LoginRequestSchema",
    "InviteMemberRequestSchema",
    "AcceptInviteRequestSchema",
    "ForgotPasswordRequestSchema",
    "ResetPasswordRequestSchema",
    "TokenResponseSchema",
    "CurrentUserSchema",
]


from datetime import datetime
from typing import Any, Dict, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from eylo.common.schemas import (
    BaseResponseSchema,
    EyloBaseApiSchema,
    EyloBaseModelSchema,
    EyloBaseRequestSchema,
    EyloBaseSchema,
)


class CurrentUserSchema(BaseModel):
    """Schema representing an authenticated organization member (web API user).

    Used for private/member API endpoints with JWT authentication.
    """

    member_id: UUID = Field(..., description="Member ID")
    organization_id: UUID = Field(..., description="Organization ID")
    email: EmailStr = Field(..., description="Member email")


class TokenDataSchema(BaseModel):
    """Minimal payload for a member access token.

    The token proves only the member identifier. The current member row is the
    authority for organization, email and account status.
    """

    member_id: UUID = Field(..., description="Member ID")
    token_type: Literal["member"] = Field(..., description="Access-token kind")
    exp: datetime = Field(..., description="Token expiration time")


class WaitlistRequestSchema(EyloBaseRequestSchema):
    email: EmailStr = Field(..., description="Member's email address")


class RegistrationRequestSchema(EyloBaseRequestSchema):
    password: str = Field(..., min_length=8, description="Member's password")
    email: EmailStr = Field(..., description="Member's email address")


class LoginRequestSchema(EyloBaseRequestSchema):
    """Schema for user login request."""

    email: EmailStr = Field(..., description="Member's email address")
    password: str = Field(..., description="Member's password")


class InviteMemberRequestSchema(EyloBaseRequestSchema):
    """Request schema for inviting a member to an organization."""

    email: EmailStr = Field(..., description="Invitee email address")


class AcceptInviteRequestSchema(EyloBaseRequestSchema):
    """Request schema for accepting an organization invite."""

    token: str = Field(..., description="Invite JWT token")
    password: str = Field(..., min_length=8, description="New member password")


class ForgotPasswordRequestSchema(EyloBaseRequestSchema):
    """Request schema for initiating a password reset."""

    email: EmailStr = Field(..., description="Member email address")


class ResetPasswordRequestSchema(EyloBaseRequestSchema):
    """Request schema for resetting a password with a token."""

    token: str = Field(..., description="Reset JWT token")
    new_password: str = Field(..., min_length=8, description="New password")


class TokenResponseSchema(EyloBaseApiSchema):
    """Schema for authentication token."""

    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field("bearer", description="Token type")


# --- Schemas for Widget Session Initiation ---


class SessionInitiateRequest(EyloBaseRequestSchema):
    """Request schema for initiating a widget session."""

    organization_id: UUID = Field(..., description="The ID of the organization.")
    external_id: str = Field(
        ..., description="The external identifier for the contact."
    )
    name: Optional[str] = Field(None, description="Contact's full name.")
    primary_email: Optional[EmailStr] = Field(
        None, description="Contact's primary email."
    )
    primary_phone: Optional[str] = Field(None, description="Contact's primary phone.")
    preferences: Optional[Dict[str, Any]] = Field(
        None, description="Contact's preferences."
    )
    user_agent: Optional[str] = Field(None, description="Client's user agent.")
    ip_address: Optional[str] = Field(None, description="Client's IP address.")


class SessionInitiateResponseData(EyloBaseApiSchema):
    session_id: str = Field(
        ..., description="The secure session token for the WebSocket connection."
    )
    warnings: list[str] = Field(
        default_factory=list,
        description=(
            "Safe identify-time ambiguity warnings. They never expose another "
            "contact ID or prevent session creation."
        ),
    )


class SessionInitiateResponse(BaseResponseSchema):
    """Response schema after successfully initiating a session."""

    data: SessionInitiateResponseData


class AuthSessionCreate(EyloBaseSchema):
    """Schema for creating a new session record in the database."""

    organization_id: UUID
    contact_id: UUID
    expires_at: datetime
    user_agent: Optional[str] = None
    ip_address: Optional[str] = None


class AuthSessionInDb(AuthSessionCreate, EyloBaseModelSchema):
    """Schema representing a session object retrieved from the database."""

    session_token: str
