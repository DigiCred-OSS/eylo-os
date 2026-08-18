"""Explicit-authority orchestration for telephony call effects."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any
from urllib.parse import urlencode
from uuid import UUID

from fastapi import HTTPException

from eylo.common.config import settings
from eylo.common.database import start_transaction
from eylo.common.outbound import (
    OutboundAttemptIdentity,
    OutboundAttemptSpec,
    OutboundAttemptState,
    OutboundOwnerKind,
    fingerprint_outbound_input,
)
from eylo.common.utils.dict import to_json_str
from eylo.modules.telephony.lifecycle import (
    apply_outbound_call_outcome,
    bind_outbound_provider_call,
    prepare_outbound_call,
)
from eylo.modules.telephony.provider_config_domain import (
    ResolvedTelephony,
    TelephonyOperation,
    supports_telephony_operation,
)
from eylo.modules.telephony.services import PhoneNumberService, TelephonyCallService
from eylo.modules.telephony.webhook_security import create_media_stream_token
from eylo.modules.telephony.wiring import build_telephony_config_resolver
from eylo.pipelines.outbound.durable_execution import (
    DurableStepContext,
    execute_outbound_attempt,
)
from eylo.pipelines.outbound.service import OutboundAttemptService
from eylo.sockets.telephony.base import (
    BaseTelephonyService,
    TelephonyControlAccepted,
    TelephonyControlRejected,
    TelephonyControlResult,
    TelephonyControlUnknown,
    TelephonyControlUnsupported,
)
from eylo.sockets.telephony.factory import TelephonyFactory

logger = logging.getLogger(__name__)


class _InlineDurableContext:
    """DB-fenced send for callers already owned by another durable record."""

    async def step(
        self,
        *,
        key: str,
        version: int,
        operation: Callable[[], Awaitable[Any]],
    ) -> Any:
        del key, version
        return await operation()


class VoiceService:
    """Resolve one exact carrier config before every provider effect."""

    async def initiate_outbound_call(
        self,
        *,
        call_id: UUID,
        to_number: str,
        agent_id: UUID,
        organization_id: UUID,
        agent_revision: int | None = None,
        initial_message: str | None = None,
        context: dict[str, Any] | None = None,
        durable_context: DurableStepContext | None = None,
    ) -> dict[str, Any]:
        """Place a new call through the config owned by the agent's number."""
        async with start_transaction(ro=True) as db:
            phone_number = await PhoneNumberService(db=db).get_by_outbound_agent_id(
                str(agent_id),
                organization_id=organization_id,
            )
            if phone_number is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"No outbound phone number found for agent {agent_id}.",
                )
            if phone_number.organization_id != organization_id:
                raise HTTPException(
                    status_code=404,
                    detail=f"No outbound phone number found for agent {agent_id}.",
                )
            from eylo.modules.templates.domain import TemplateConsumerKind
            from eylo.pipelines.agents import build_executable_agent_resolver

            resolver = build_executable_agent_resolver(db)
            if agent_revision is None:
                executable_agent = await resolver.resolve_for_new_work(
                    organization_id=organization_id,
                    agent_id=agent_id,
                    consumer_kind=TemplateConsumerKind.REALTIME_VOICE,
                )
            else:
                executable_agent = await resolver.resolve_exact(
                    organization_id=organization_id,
                    agent_id=agent_id,
                    revision=agent_revision,
                    consumer_kind=TemplateConsumerKind.REALTIME_VOICE,
                )
            resolved = await build_telephony_config_resolver(db).resolve_pinned(
                organization_id,
                provider_config_id=phone_number.provider_config_id,
                revision=phone_number.provider_config_revision,
            )

        if resolved.provider.value != phone_number.provider:
            raise ValueError("Phone number provider does not match its carrier config.")
        self._require_operation(resolved, TelephonyOperation.OUTBOUND_CALL)
        adapter = self._adapter(resolved)
        profile = adapter.outbound_call_profile()

        await prepare_outbound_call(
            call_id=call_id,
            organization_id=organization_id,
            provider=resolved.provider.value,
            provider_config_id=resolved.provider_config_id,
            provider_config_revision=resolved.provider_config_revision,
            from_number=phone_number.number,
            to_number=to_number,
            phone_number_id=phone_number.id,
            agent_id=agent_id,
            agent_revision=executable_agent.ref.revision,
            conversation_id=None,
            campaign_id=_context_uuid(context, "campaign_id"),
            campaign_contact_id=_context_uuid(context, "campaign_contact_id"),
            campaign_attempt_id=_context_uuid(context, "campaign_attempt_id"),
        )

        server_domain = settings.SERVER_DOMAIN
        if not server_domain:
            raise ValueError("SERVER_DOMAIN environment variable is not set.")

        stream_token = create_media_stream_token(
            provider=resolved.provider.value,
            call_id=str(call_id),
            organization_id=str(resolved.organization_id),
            agent_id=str(agent_id),
            agent_revision=executable_agent.ref.revision,
            provider_config_id=str(resolved.provider_config_id),
            provider_config_revision=resolved.provider_config_revision,
            direction="OUTBOUND",
            initial_message=initial_message,
        )
        query = {
            "provider": resolved.provider.value,
            "org_id": str(resolved.organization_id),
            "agent_id": str(agent_id),
            "agent_revision": str(executable_agent.ref.revision),
            "provider_config_id": str(resolved.provider_config_id),
            "provider_config_revision": str(resolved.provider_config_revision),
            "call_id": str(call_id),
            "direction": "OUTBOUND",
            "stream_token": stream_token,
        }
        if initial_message:
            query["initial_message"] = initial_message
        ws_url = f"wss://{server_domain}/api/media/stream?{urlencode(query)}"

        custom_params: dict[str, Any] = {
            "Direction": "OUTBOUND",
            "agent_id": str(agent_id),
            "agent_revision": executable_agent.ref.revision,
            "org_id": str(resolved.organization_id),
            "provider_config_id": str(resolved.provider_config_id),
            "provider_config_revision": str(resolved.provider_config_revision),
            "call_id": str(call_id),
            "stream_token": stream_token,
        }
        if resolved.provider.value == "exotel":
            custom_params["CustomField"] = to_json_str(custom_params)
        if initial_message:
            custom_params["InitialMessage"] = initial_message
        logger.info(
            "Initiating %s outbound call: To=%s From=%s Agent=%s config=%s@%d",
            resolved.provider.value,
            to_number,
            phone_number.number,
            agent_id,
            resolved.provider_config_id,
            resolved.provider_config_revision,
        )
        identity = OutboundAttemptIdentity(
            organization_id=organization_id,
            owner_kind=OutboundOwnerKind.TELEPHONY_CALL,
            owner_id=call_id,
            operation_key="telephony.call.create",
        )
        spec = OutboundAttemptSpec(
            identity=identity,
            provider_operation=profile.provider_operation,
            transport_kind=profile.transport_kind,
            destination_origin=profile.destination_origin,
            request_fingerprint=fingerprint_outbound_input(
                {
                    "call_id": str(call_id),
                    "to_number": to_number,
                    "from_number": phone_number.number,
                    "agent_id": str(agent_id),
                    "agent_revision": executable_agent.ref.revision,
                    "provider": resolved.provider.value,
                    "provider_config_id": str(resolved.provider_config_id),
                    "provider_config_revision": resolved.provider_config_revision,
                    "initial_message": initial_message,
                    "context": context or {},
                }
            ),
        )
        status_callback_url = (
            f"{resolved.config['webhook_base_url']}/telephony/webhooks/"
            f"{resolved.provider.value}/status?{urlencode({'call_id': str(call_id)})}"
        )

        async def send(authorization):
            return await adapter.initiate_outbound_call(
                to_number=to_number,
                from_number=phone_number.number,
                ws_url=ws_url,
                custom_params=custom_params,
                authorization=authorization,
                status_callback_url=status_callback_url,
            )

        receipt = await execute_outbound_attempt(
            spec=spec,
            context=durable_context or _InlineDurableContext(),
            sender=send,
        )
        await apply_outbound_call_outcome(
            call_id=call_id,
            organization_id=organization_id,
            state=receipt.state,
            provider_reference=receipt.provider_reference,
            failure_code=receipt.failure_code,
        )
        return {
            "call_id": str(call_id),
            "call_sid": receipt.provider_reference,
            "status": receipt.state.value,
            "failure_code": receipt.failure_code,
            "outbound_attempt_id": str(receipt.attempt_id),
            "agent_revision": executable_agent.ref.revision,
            "provider": resolved.provider.value,
            "provider_config_id": str(resolved.provider_config_id),
            "provider_config_revision": resolved.provider_config_revision,
            "from_number": phone_number.number,
        }

    async def require_control_supported(
        self,
        *,
        call_sid: str,
        organization_id: UUID,
        operation: TelephonyOperation,
    ) -> None:
        """Authorize the persisted call and fail unsupported controls pre-intent."""
        resolved = await self._resolve_call_control(organization_id, call_sid)
        self._require_operation(resolved, operation)

    async def end_call(
        self,
        *,
        call_sid: str,
        organization_id: UUID,
    ) -> dict[str, Any]:
        resolved = await self._resolve_call_control(
            organization_id,
            call_sid,
        )
        self._require_operation(resolved, TelephonyOperation.END_CALL)
        result = await self._adapter(resolved).end_call(call_sid)
        return self._require_accepted_control(result, TelephonyOperation.END_CALL)

    async def transfer_call(
        self,
        *,
        call_sid: str,
        to_number: str,
        organization_id: UUID,
    ) -> dict[str, Any]:
        resolved = await self._resolve_call_control(
            organization_id,
            call_sid,
        )
        self._require_operation(resolved, TelephonyOperation.TRANSFER_CALL)
        result = await self._adapter(resolved).transfer_call(call_sid, to_number)
        return self._require_accepted_control(
            result,
            TelephonyOperation.TRANSFER_CALL,
        )

    async def send_dtmf(
        self,
        *,
        call_sid: str,
        digits: str,
        organization_id: UUID,
    ) -> dict[str, Any]:
        resolved = await self._resolve_call_control(
            organization_id,
            call_sid,
        )
        self._require_operation(resolved, TelephonyOperation.SEND_DTMF)
        result = await self._adapter(resolved).send_dtmf(call_sid, digits)
        return self._require_accepted_control(result, TelephonyOperation.SEND_DTMF)

    @staticmethod
    async def _resolve_call_control(
        organization_id: UUID,
        call_sid: str,
    ) -> ResolvedTelephony:
        async with start_transaction(ro=True) as db:
            call = await TelephonyCallService(db=db).get_by_call_sid_for_organization(
                call_sid=call_sid,
                organization_id=organization_id,
            )
            if call is None:
                raise HTTPException(status_code=404, detail="Call not found.")
            resolved = await build_telephony_config_resolver(db).resolve_pinned(
                organization_id,
                provider_config_id=call.provider_config_id,
                revision=call.provider_config_revision,
            )
            if resolved.provider.value != call.provider:
                raise ValueError("Call provider does not match its carrier authority.")
            return resolved

    @staticmethod
    def _require_accepted_control(
        result: TelephonyControlResult,
        operation: TelephonyOperation,
    ) -> dict[str, Any]:
        if isinstance(result, TelephonyControlAccepted):
            return {
                "status": "accepted",
                "operation": operation.value,
                "provider_status": result.status_code,
            }
        if isinstance(result, TelephonyControlUnsupported):
            raise HTTPException(
                status_code=501,
                detail={"code": "UNSUPPORTED", "operation": operation.value},
            )
        if isinstance(result, TelephonyControlRejected):
            raise HTTPException(
                status_code=502,
                detail={"code": "REJECTED", "operation": operation.value},
            )
        if isinstance(result, TelephonyControlUnknown):
            raise HTTPException(
                status_code=409,
                detail={"code": "UNKNOWN", "operation": operation.value},
            )
        raise TypeError("Carrier returned an invalid call-control result.")

    @staticmethod
    def _adapter(resolved: ResolvedTelephony) -> BaseTelephonyService:
        return TelephonyFactory(
            provider=resolved.provider.value,
            telephony_config=resolved.as_provider_config().adapter_settings(),
        ).service

    @staticmethod
    def _require_operation(
        resolved: ResolvedTelephony,
        operation: TelephonyOperation,
    ) -> None:
        if supports_telephony_operation(resolved.provider, operation):
            return
        raise HTTPException(
            status_code=501,
            detail={
                "code": "UNSUPPORTED",
                "operation": operation.value,
                "provider": resolved.provider.value,
            },
        )


def _context_uuid(context: dict[str, Any] | None, key: str) -> UUID | None:
    value = (context or {}).get(key)
    if value is None or value == "":
        return None
    return UUID(str(value))


async def reconcile_outbound_call_acceptance(
    *,
    call_id: UUID,
    organization_id: UUID,
    provider_reference: str,
) -> None:
    """Let an authenticated callback resolve an in-flight/unknown call send."""
    identity = OutboundAttemptIdentity(
        organization_id=organization_id,
        owner_kind=OutboundOwnerKind.TELEPHONY_CALL,
        owner_id=call_id,
        operation_key="telephony.call.create",
    )
    async with start_transaction() as session:
        service = OutboundAttemptService(session)
        attempt = await service.get(
            organization_id=organization_id,
            attempt_id=identity.attempt_id,
            for_update=True,
        )
        if attempt.state is OutboundAttemptState.IN_FLIGHT:
            await service.record_outcome(
                organization_id=organization_id,
                attempt_id=identity.attempt_id,
                state=OutboundAttemptState.SUCCEEDED,
                provider_reference=provider_reference,
            )
        elif attempt.state is OutboundAttemptState.UNKNOWN:
            await service.reconcile(
                organization_id=organization_id,
                attempt_id=identity.attempt_id,
                state=OutboundAttemptState.SUCCEEDED,
                provider_reference=provider_reference,
            )
    await bind_outbound_provider_call(
        call_id=call_id,
        organization_id=organization_id,
        provider_reference=provider_reference,
    )
