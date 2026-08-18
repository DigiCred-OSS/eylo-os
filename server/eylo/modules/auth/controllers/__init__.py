"""Authentication controller for platform users."""

from datetime import timedelta
from typing import Dict, Union

from fastapi import HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from jwt import PyJWTError as JWTError
from uuid_utils import uuid7

from eylo.common.database import get_transaction
from eylo.common.schemas import BaseResponseStatus
from eylo.modules.auth.schemas import (
    AcceptInviteRequestSchema,
    CurrentUserSchema,
    ForgotPasswordRequestSchema,
    InviteMemberRequestSchema,
    LoginRequestSchema,
    ResetPasswordRequestSchema,
    SessionInitiateRequest,
    SessionInitiateResponse,
    SessionInitiateResponseData,
    TokenResponseSchema,
    WaitlistRequestSchema,
)
from eylo.modules.auth.services.auth_service import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    AuthService,
)
from eylo.modules.auth.services.session_service import AuthSessionService
from eylo.modules.contacts.domain import ContactDeletionPending, ContactIdentityInvalid
from eylo.modules.members.exceptions import (
    MemberDuplicateException,
    MemberNotFound,
    MemberPasswordMismatch,
)
from eylo.modules.members.schemas.api import (
    MemberApiResponseSchema,
    MemberRegisterSchema,
)
from eylo.modules.members.services import MemberService


class AuthController:
    """Controller for authentication endpoints.

    Handles:
    - User registration
    - User login
    - TokenSchema validation
    """

    def __init__(self):
        db_session = get_transaction()
        self.auth_service = AuthService(db=db_session)
        self.member_service = MemberService(db=db_session)
        self.session_service = AuthSessionService(db=db_session)

    async def add_to_waitlist(
        self, request: WaitlistRequestSchema
    ) -> MemberApiResponseSchema:
        temp_password = uuid7().hex
        return await self.register(
            MemberRegisterSchema(
                email=request.email,
                password=temp_password,
            )
        )

    async def register(self, request: MemberRegisterSchema) -> MemberApiResponseSchema:
        request.password = self.auth_service.get_password_hash(request.password)
        try:
            member = await self.auth_service.register(request)
        except MemberDuplicateException:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unable to register user",
            )
        if not member:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Registered user not found",
            )
        return MemberApiResponseSchema.model_validate(member.model_dump())

    async def login(
        self, request: Union[LoginRequestSchema, OAuth2PasswordRequestForm]
    ) -> TokenResponseSchema:
        if isinstance(request, OAuth2PasswordRequestForm):
            email = request.username
            password = request.password
        else:
            email = request.email
            password = request.password

        try:
            member = await self.auth_service.authenticate_member(email, password)
        except (MemberPasswordMismatch, MemberNotFound):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not member:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = self.auth_service.create_member_access_token(
            member.id,
            expires_delta=access_token_expires,
        )

        return TokenResponseSchema(access_token=access_token, token_type="bearer")

    async def get_me(self, member: CurrentUserSchema) -> MemberApiResponseSchema:
        organization_id = member.organization_id
        member_id = member.member_id
        member = await self.member_service.get_by_id_email_organization(
            member_id, member.email, organization_id
        )
        if not member:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Member not found",
            )
        return MemberApiResponseSchema.model_validate(member.model_dump())

    async def initiate_widget_session(
        self, request: SessionInitiateRequest
    ) -> SessionInitiateResponse:
        """Initiate a widget session by calling the session service."""
        try:
            initiation = (
                await self.session_service.initiate_widget_session_with_resolution(
                    request
                )
            )
        except ContactDeletionPending as error:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Contact deletion is pending",
            ) from error
        except ContactIdentityInvalid as error:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Contact identifier is invalid",
            ) from error
        return SessionInitiateResponse(
            status=BaseResponseStatus.SUCCESS,
            data=SessionInitiateResponseData(
                session_id=initiation.session.session_token,
                warnings=list(initiation.contact_resolution.warning_codes),
            ),
        )

    async def invite_member(
        self,
        current_user: CurrentUserSchema,
        request: InviteMemberRequestSchema,
    ) -> Dict[str, str]:
        """Generate an invite token for a new member."""
        token = await self.auth_service.invite_member(
            organization_id=current_user.organization_id,
            email=request.email,
        )
        return {"token": token, "email": request.email}

    async def accept_invite(
        self,
        request: AcceptInviteRequestSchema,
    ) -> MemberApiResponseSchema:
        """Accept an organization invite and create the member."""
        try:
            member = await self.auth_service.accept_invite(
                token=request.token,
                password=request.password,
            )
        except JWTError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired invite token.",
            )
        except MemberDuplicateException:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This email is already registered.",
            )
        return MemberApiResponseSchema.model_validate(member.model_dump())

    async def forgot_password(
        self,
        request: ForgotPasswordRequestSchema,
    ) -> Dict[str, str]:
        """Request a password reset token.

        Always returns the same response regardless of whether the email
        exists to avoid email enumeration.
        """
        await self.auth_service.request_password_reset(request.email)
        return {"message": "If the email exists, a reset link has been sent."}

    async def reset_password(
        self,
        request: ResetPasswordRequestSchema,
    ) -> Dict[str, str]:
        """Reset a member's password using a reset token."""
        try:
            await self.auth_service.reset_password(
                token=request.token,
                new_password=request.new_password,
            )
        except JWTError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired reset token.",
            )
        except MemberNotFound:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired reset token.",
            )
        return {"message": "Password has been reset."}
