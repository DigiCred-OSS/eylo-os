"""Local-only public bootstrap for the standalone widget development UI."""

from fastapi import APIRouter, HTTPException, Request

from eylo.modules.auth.schemas.widget import WidgetDevelopmentSessionResponse
from eylo.pipelines.widget_development import (
    WidgetDevelopmentSessionUnavailable,
    create_widget_development_session,
)

router = APIRouter(prefix="/public/widget-development", tags=["Widget Development"])


@router.post("/session", response_model=WidgetDevelopmentSessionResponse)
async def create_development_session(
    request: Request,
) -> WidgetDevelopmentSessionResponse:
    """Issue a real contact session using server-owned local configuration."""
    user_agent = (request.headers.get("user-agent") or "")[:1024] or None
    ip_address = (request.client.host if request.client else "")[:64] or None
    try:
        session = await create_widget_development_session(
            user_agent=user_agent,
            ip_address=ip_address,
        )
    except WidgetDevelopmentSessionUnavailable as error:
        raise HTTPException(status_code=404, detail="Not found.") from error
    return WidgetDevelopmentSessionResponse(
        organization_id=session.organization_id,
        contact_id=session.contact_id,
        session_token=session.session_token,
        session_expires_at=session.session_expires_at,
    )


__all__ = ["router"]
