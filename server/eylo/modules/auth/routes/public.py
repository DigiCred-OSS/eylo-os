"""Authentication routes for platform users."""

from typing import Annotated, Dict

from fastapi import APIRouter, Depends, Response, status

from eylo.common.database import start_transaction
from eylo.modules.auth.controllers import AuthController
from eylo.modules.auth.schemas import (
    AcceptInviteRequestSchema,
    CurrentUserSchema,
    ForgotPasswordRequestSchema,
    InviteMemberRequestSchema,
    LoginRequestSchema,
    RegistrationRequestSchema,
    ResetPasswordRequestSchema,
    TokenResponseSchema,
    WaitlistRequestSchema,
)
from eylo.modules.auth.services.auth_service import get_current_user
from eylo.modules.members.schemas.api import MemberApiResponseSchema

router = APIRouter(tags=["auth"], prefix="/auth")


@router.post("/waitlist", response_model=MemberApiResponseSchema)
async def waitlist(
    waitlist_request: WaitlistRequestSchema,
) -> MemberApiResponseSchema:
    """Add a user to the waitlist."""
    async with start_transaction():
        return await AuthController().add_to_waitlist(waitlist_request)


@router.post("/register", response_model=MemberApiResponseSchema)
async def register(
    request: RegistrationRequestSchema,
) -> MemberApiResponseSchema:
    """Add a user to the waitlist."""
    async with start_transaction():
        return await AuthController().register(request)


@router.post("/login", response_model=TokenResponseSchema)
async def login(
    request: LoginRequestSchema,
) -> TokenResponseSchema:
    """Authenticate a user and return a JWT TokenResponseSchema."""
    async with start_transaction():
        return await AuthController().login(request)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout() -> Response:
    """Complete stateless logout; clients discard their bearer token locally."""
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/invite")
async def invite_member(
    request: InviteMemberRequestSchema,
    current_user: Annotated[CurrentUserSchema, Depends(get_current_user)],
) -> Dict[str, str]:
    """Invite a member to the authenticated member's organization."""
    async with start_transaction():
        return await AuthController().invite_member(current_user, request)


@router.post("/accept-invite", response_model=MemberApiResponseSchema)
async def accept_invite(
    request: AcceptInviteRequestSchema,
) -> MemberApiResponseSchema:
    """Accept an organization invite and create a new member."""
    async with start_transaction():
        return await AuthController().accept_invite(request)


@router.post("/forgot-password")
async def forgot_password(
    request: ForgotPasswordRequestSchema,
) -> Dict[str, str]:
    """Request a password reset link."""
    async with start_transaction():
        return await AuthController().forgot_password(request)


@router.post("/reset-password")
async def reset_password(
    request: ResetPasswordRequestSchema,
) -> Dict[str, str]:
    """Reset a member's password using a reset token."""
    async with start_transaction():
        return await AuthController().reset_password(request)
