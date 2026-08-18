"""Application services for the `auth` domain."""

from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, Header, status
from fastapi.security import OAuth2PasswordBearer
from jwt import PyJWTError as JWTError
from passlib.context import CryptContext
from pydantic import EmailStr, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession
from uuid_utils import uuid7

from eylo.common.database import start_transaction
from eylo.modules.auth.schemas import CurrentUserSchema, TokenDataSchema
from eylo.modules.members.constants import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    ALGORITHM,
    SECRET_KEY,
)
from eylo.modules.members.exceptions import (
    MemberDuplicateException,
    MemberNotFound,
    MemberPasswordMismatch,
)
from eylo.modules.members.schemas.api import MemberRegisterSchema
from eylo.modules.members.schemas.indb import MemberCreateSchema, MemberInDb
from eylo.modules.organizations.schemas import OrganisationCreateSchema

# Set up password context for hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Set up OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def _member_credentials_exception() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


class AuthService:
    """AuthService behavior for the "auth" domain."""

    def __init__(self, db: Optional[AsyncSession] = None):
        """Initialize Authentication Service."""
        from eylo.modules.members.services import MemberService
        from eylo.modules.organizations.services import OrganizationService

        self.member_service = MemberService(db=db)
        self.organization_service = OrganizationService(db=db)

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify password for the "auth" domain."""
        return pwd_context.verify(plain_password, hashed_password)

    def get_password_hash(self, plain_password: str) -> str:
        """Generate Password Hash."""
        return pwd_context.hash(plain_password)

    async def authenticate_member(
        self, email: str, plain_password: str
    ) -> Optional[MemberInDb]:
        """Authenticate member for the "auth" domain."""
        member = await self.member_service.get_active_by_email(email)
        if not await self.member_service.verify_password(member, plain_password):
            raise MemberPasswordMismatch
        return member

    def create_member_access_token(
        self, member_id: UUID, expires_delta: Optional[timedelta] = None
    ) -> str:
        """Create an access token that proves one member identifier.

        Organization, email and account state are intentionally absent. The
        request resolver reloads those values from durable member authority.
        """
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(
                minutes=ACCESS_TOKEN_EXPIRE_MINUTES
            )

        return jwt.encode(
            {
                "member_id": str(member_id),
                "token_type": "member",
                "exp": expire,
            },
            SECRET_KEY,
            algorithm=ALGORITHM,
        )

    async def get_current_user(self, token: str) -> CurrentUserSchema:
        """Get Current User."""
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            token_data = TokenDataSchema.model_validate(payload)
            member = await self.member_service.get_active_by_id(token_data.member_id)
        except (JWTError, MemberNotFound, ValidationError):
            raise _member_credentials_exception()

        return CurrentUserSchema(
            member_id=member.id,
            organization_id=member.organization_id,
            email=member.email,
        )

    async def register(self, request: MemberRegisterSchema) -> MemberInDb:
        """Register New Member."""

        def _get_domain_from_email(email: EmailStr) -> str:
            """Extract the domain from an email address."""
            return email.split("@")[-1]

        def _get_random_hex(length: int) -> str:
            """Generate a random hex string of the specified length."""
            return uuid7().hex[:length]

        # Check if user already exists
        existing_user = None
        try:
            existing_user = await self.member_service.get_by_email(request.email)
            if existing_user:
                raise MemberDuplicateException(f"{request.email=} already registered")
        except MemberNotFound:
            pass

        # Create organization with name based on email domain + random suffix
        organization = await self.organization_service.create(
            OrganisationCreateSchema(
                name="{}-{}".format(
                    _get_domain_from_email(request.email), _get_random_hex(4)
                )
            )
        )

        # Create the member linked to the organization
        return await self.member_service.create_(organization.id, request)

    async def invite_member(
        self,
        *,
        organization_id: UUID,
        email: str,
    ) -> str:
        """Create an invite token for a new member.

        Does not persist anything; the token carries organization scope and
        email.  The invitee calls ``accept_invite`` with the token plus a
        password to create the member row.
        """
        return create_invite_token(organization_id=organization_id, email=email)

    async def accept_invite(
        self,
        *,
        token: str,
        password: str,
    ) -> MemberInDb:
        """Validate an invite token and create the member.

        Raises JWTError on invalid/expired tokens, MemberDuplicateException if
        the email is already registered.
        """
        payload = decode_invite_token(token)
        email = payload["email"]
        organization_id = UUID(payload["organization_id"])

        existing = None
        try:
            existing = await self.member_service.get_by_email(email)
            if existing:
                raise MemberDuplicateException(f"{email=} already registered")
        except MemberNotFound:
            pass

        hashed = self.get_password_hash(password)
        return await self.member_service.create_(
            organization_id,
            MemberCreateSchema(
                organization_id=organization_id,
                email=email,
                password=hashed,
            ),
        )

    async def request_password_reset(self, email: str) -> str | None:
        """Create a password-reset token for the member if the email exists.

        Returns None when the email is unknown so the caller can return the same
        response regardless (avoids email enumeration).
        """
        try:
            member = await self.member_service.get_by_email(email)
        except MemberNotFound:
            return None
        return create_reset_token(member_id=member.id, email=email)

    async def reset_password(
        self,
        *,
        token: str,
        new_password: str,
    ) -> None:
        """Validate a reset token and update the member's password.

        Raises JWTError on invalid/expired tokens, MemberNotFound if the member
        no longer exists.
        """
        payload = decode_reset_token(token)
        member_id = UUID(payload["member_id"])

        member = await self.member_service.get_(member_id)
        member.password = self.get_password_hash(new_password)

        raw = await self.member_service.repository.get_(member_id)
        raw.password = member.password
        await self.member_service.repository.save_(raw)


# Dependency for getting the current authenticated user using dependency injection
async def get_current_user(
    token: str = Depends(oauth2_scheme),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    x_session_id: Optional[str] = Header(None, alias="X-Session-ID"),
) -> CurrentUserSchema:
    """Get Current User Dependency."""
    if x_api_key is not None or x_session_id is not None:
        raise _member_credentials_exception()

    async with start_transaction(ro=True):
        return await AuthService().get_current_user(token)


# --- Token constants for invite / reset ---

_INVITE_TOKEN_EXPIRE_HOURS = 168  # 7 days
_RESET_TOKEN_EXPIRE_HOURS = 1
_INVITE_TOKEN_TYPE = "invite"
_RESET_TOKEN_TYPE = "reset"


def create_invite_token(
    *,
    organization_id: UUID,
    email: str,
    secret_key: str = SECRET_KEY,
    algorithm: str = ALGORITHM,
) -> str:
    """Create a signed JWT invite token for joining an organization."""
    expire = datetime.now(timezone.utc) + timedelta(hours=_INVITE_TOKEN_EXPIRE_HOURS)
    payload = {
        "type": _INVITE_TOKEN_TYPE,
        "organization_id": str(organization_id),
        "email": email,
        "exp": expire,
    }
    return jwt.encode(payload, secret_key, algorithm=algorithm)


def decode_invite_token(
    token: str,
    *,
    secret_key: str = SECRET_KEY,
    algorithm: str = ALGORITHM,
) -> dict:
    """Decode and validate an invite token.  Raises JWTError on failure."""
    payload = jwt.decode(token, secret_key, algorithms=[algorithm])
    if payload.get("type") != _INVITE_TOKEN_TYPE:
        raise JWTError("Invalid token type")
    return payload


def create_reset_token(
    *,
    member_id: UUID,
    email: str,
    secret_key: str = SECRET_KEY,
    algorithm: str = ALGORITHM,
) -> str:
    """Create a signed JWT password-reset token."""
    expire = datetime.now(timezone.utc) + timedelta(hours=_RESET_TOKEN_EXPIRE_HOURS)
    payload = {
        "type": _RESET_TOKEN_TYPE,
        "member_id": str(member_id),
        "email": email,
        "exp": expire,
    }
    return jwt.encode(payload, secret_key, algorithm=algorithm)


def decode_reset_token(
    token: str,
    *,
    secret_key: str = SECRET_KEY,
    algorithm: str = ALGORITHM,
) -> dict:
    """Decode and validate a password-reset token.  Raises JWTError on failure."""
    payload = jwt.decode(token, secret_key, algorithms=[algorithm])
    if payload.get("type") != _RESET_TOKEN_TYPE:
        raise JWTError("Invalid token type")
    return payload
