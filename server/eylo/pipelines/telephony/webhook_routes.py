"""Authenticated provider status callback composition."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Response, status
from sqlalchemy import select

from eylo.common.database import start_transaction
from eylo.modules.telephony.models import TelephonyCallModel
from eylo.modules.telephony.services import TelephonyCallService
from eylo.modules.telephony.webhook_controller import WebhookController
from eylo.modules.telephony.wiring import build_telephony_config_resolver
from eylo.pipelines.telephony.call_control import (
    reconcile_outbound_call_acceptance,
)
from eylo.sockets.telephony.webhook_signatures import verify_status_callback

router = APIRouter(
    prefix="/telephony/webhooks",
    tags=["Telephony Webhooks"],
)

_CALL_SID_FIELDS = {
    "twilio": "CallSid",
    "plivo": "CallUUID",
    "vonage": "uuid",
    "exotel": "CallSid",
}


@router.post("/{provider}/status")
async def status_callback(
    provider: Literal["twilio", "plivo", "vonage", "exotel"],
    request: Request,
) -> Response:
    payload = await _payload(provider, request)
    call_sid = str(payload.get(_CALL_SID_FIELDS[provider], "")).strip()
    if not call_sid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provider call ID is required.",
        )
    if provider == "exotel":
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Authenticated Exotel status callbacks are not supported.",
        )

    raw_call_id = request.query_params.get("call_id")
    try:
        call_id = UUID(raw_call_id) if raw_call_id else None
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST) from None

    async with start_transaction(ro=True) as db:
        if call_id is None:
            call = await TelephonyCallService(db=db).get_by_call_sid(call_sid)
        else:
            row = await db.scalar(
                select(TelephonyCallModel).where(
                    TelephonyCallModel.id == call_id,
                    TelephonyCallModel.deleted.is_(False),
                )
            )
            call = (
                TelephonyCallService(db=db).orm_to_schema(row)
                if row is not None
                else None
            )
        if call is None or call.provider != provider:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
        resolved = await build_telephony_config_resolver(db).resolve_pinned(
            call.organization_id,
            provider_config_id=call.provider_config_id,
            revision=call.provider_config_revision,
        )

    provider_config = resolved.as_provider_config()
    public_url = (
        f"{provider_config.config['webhook_base_url']}"
        f"/telephony/webhooks/{provider}/status"
    )
    if request.url.query:
        public_url = f"{public_url}?{request.url.query}"
    if not verify_status_callback(
        provider=provider,
        config=provider_config.config,
        secrets=provider_config.secrets,
        method=request.method,
        public_url=public_url,
        headers=request.headers,
        params=payload,
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    if call_id is not None:
        await reconcile_outbound_call_acceptance(
            call_id=call_id,
            organization_id=call.organization_id,
            provider_reference=call_sid,
        )

    controller = WebhookController()
    handlers = {
        "twilio": controller.handle_twilio_status,
        "plivo": controller.handle_plivo_status,
        "vonage": controller.handle_vonage_status,
    }
    await handlers[provider](payload)
    return Response(status_code=status.HTTP_200_OK)


async def _payload(provider: str, request: Request) -> dict:
    if provider == "vonage":
        value = await request.json()
        if not isinstance(value, dict):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Provider callback payload must be an object.",
            )
        return value
    return dict(await request.form())
