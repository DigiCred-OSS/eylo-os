"""Authenticated, readiness-gated media sessions for every phone provider."""

from __future__ import annotations

import asyncio
import logging
from typing import Literal
from uuid import UUID

import arrow
from fastapi import APIRouter, WebSocket, status
from starlette.websockets import WebSocketDisconnect, WebSocketState

from eylo.common.config import Environment, settings
from eylo.common.database import start_transaction
from eylo.modules.agents.domain import ResolvedExecutableAgent
from eylo.modules.telephony.lifecycle import (
    claim_outbound_media_session,
    record_call_status,
    record_opener_delivery,
)
from eylo.modules.telephony.schemas import CallStatus, TelephonyCallInDb
from eylo.modules.telephony.services import PhoneNumberService
from eylo.modules.telephony.webhook_security import (
    is_ip_allowlisted,
    verify_media_stream_token,
)
from eylo.modules.telephony.wiring import build_telephony_config_resolver
from eylo.modules.user_sessions.domain import UserSessionState
from eylo.modules.user_sessions.service import UserSessionService
from eylo.pipelines.session_timeline import try_file_runtime_fact
from eylo.pipelines.telephony.conversation import (
    init_conversation,
    persist_delivered_outbound_opener,
)
from eylo.pipelines.telephony.lifecycle import (
    emit_call_started,
    finalize_call_session,
    handle_inbound_dtmf,
    handle_media_packet,
    tts_producer_task,
)
from eylo.pipelines.telephony.sessions import S_CALLS, CallSession
from eylo.pipelines.telephony.voice import (
    VoicePipelineBundle,
    apply_voice_bundle_to_session,
    bind_telephony_voice_activity,
    init_voice_pipeline,
    maybe_initialize_telephony_recorder,
    start_telephony_agent_greeting,
    start_telephony_voice_policy_tasks,
    start_telephony_voice_session,
    start_transcriptor,
    teardown_voice_pipeline_bundle,
    wait_for_voice_pipeline_ready,
)
from eylo.pipelines.voice import consent as _consent
from eylo.pipelines.websocket.singleton import S_ws_manager
from eylo.sockets.telephony.base import CallEndedReason, CallMetadata
from eylo.sockets.telephony.dtmf import DTMFCollector
from eylo.sockets.telephony.manager import TelephonyRealtime

router = APIRouter()
logger = logging.getLogger(__name__)


def validate_call_metadata(
    metadata: CallMetadata | None,
) -> tuple[CallMetadata, str, str | None, str, str, UUID, UUID, str | None]:
    """Return required canonical fields without inventing caller speech."""
    if metadata is None:
        raise ValueError("Call metadata is unavailable.")
    if not metadata.call_sid:
        raise ValueError("Provider call identity is required.")
    if metadata.organization_id is None or metadata.agent_id is None:
        raise ValueError("Organization and agent identity are required.")
    if metadata.provider_config_id is None or metadata.provider_config_revision is None:
        raise ValueError("Pinned telephony authority is required.")
    return (
        metadata,
        metadata.call_sid,
        metadata.stream_sid,
        metadata.from_number or "",
        metadata.to_number or "",
        metadata.organization_id,
        metadata.agent_id,
        metadata.initial_message,
    )


async def _handle_start_event(
    telephony_manager: TelephonyRealtime,
    ws: WebSocket,
    provider: str,
    canonical_call: TelephonyCallInDb | None,
) -> tuple[CallSession, str, str]:
    """Build one private runtime, publish only after every dependency is ready."""
    (
        metadata,
        call_sid,
        stream_sid,
        from_number,
        to_number,
        organization_id,
        agent_id,
        initial_message,
    ) = validate_call_metadata(telephony_manager.call_metadata)
    executable_agent = await _resolve_call_agent(
        metadata,
        organization_id=organization_id,
        agent_id=agent_id,
    )
    sess = CallSession(
        call_sid=call_sid,
        call_id=canonical_call.id if canonical_call else None,
        stream_sid=stream_sid or "",
        organization_id=organization_id,
        agent_id=agent_id,
        agent_revision=executable_agent.ref.revision,
        from_number=from_number,
        to_number=to_number,
        direction=metadata.direction.lower(),
        provider=provider,
        provider_config_id=metadata.provider_config_id,
        provider_config_revision=metadata.provider_config_revision,
        telephony_manager=telephony_manager,
        started_at=arrow.utcnow().datetime,
        opener_text=(
            initial_message
            if metadata.direction.upper() == "OUTBOUND" and initial_message
            else None
        ),
    )
    if canonical_call is not None:
        for key in ("campaign_id", "campaign_contact_id", "campaign_attempt_id"):
            value = getattr(canonical_call, key)
            if value is not None:
                sess.extra_data[key] = str(value)

    voice_bundle: VoicePipelineBundle | None = None
    auth_session_token: str | None = None
    published = False
    try:
        voice_bundle = await init_voice_pipeline(
            organization_id=organization_id,
            executable_agent=executable_agent,
            call_sid=call_sid,
            telephony_manager=telephony_manager,
        )
        await wait_for_voice_pipeline_ready(voice_bundle)
        conversation = await init_conversation(
            organization_id=organization_id,
            agent_id=agent_id,
            executable_agent=executable_agent,
            from_number=from_number,
            to_number=to_number,
            call_metadata=metadata,
            stream_sid=stream_sid,
            wire_ws=ws,
            provider=provider,
        )
        auth_session_token = conversation.auth_session_token
        sess.auth_session_token = auth_session_token
        sess.conversation_id = conversation.conversation_id
        sess.user_session_id = conversation.user_session_id
        apply_voice_bundle_to_session(sess, voice_bundle)

        ws_state = S_ws_manager.get_session_state(
            organization_id,
            auth_session_token,
        )
        if ws_state is None:
            raise RuntimeError("Registered telephony WS session is unavailable.")
        ws_state.tts_socket = sess.tts
        ws_state.tts_manager = sess.tts
        ws_state.tts_request_queue = sess.tts_request_queue
        ws_state.tts_response_queue = sess.tts_response_queue
        bind_telephony_voice_activity(sess)

        sess.tts_tasks["producer"] = asyncio.create_task(
            tts_producer_task(sess, telephony_manager)
        )
        if not await emit_call_started(sess, provider):
            raise RuntimeError("Call start could not be persisted.")
        maybe_initialize_telephony_recorder(sess, telephony_manager)
        await start_telephony_voice_session(
            sess,
            provider,
            voice_bundle.runtime_identity,
        )
        for provider_kind, vendor in (
            ("stt", voice_bundle.runtime_identity.stt_vendor),
            ("tts", voice_bundle.runtime_identity.tts_vendor),
        ):
            await try_file_runtime_fact(
                organization_id=organization_id,
                user_session_id=sess.user_session_id,
                subject_type=f"provider.{provider_kind}",
                subject_id=sess.voice_session_id,
                event_type=f"provider.{provider_kind}.connected",
                payload={"provider_kind": provider_kind, "vendor": vendor},
            )
        start_transcriptor(
            sess=sess,
            telephony_manager=telephony_manager,
            stream_sid=stream_sid,
        )
        S_CALLS.publish(sess)
        published = True

        if _consent.is_pending(sess):
            from eylo.pipelines.voice.browser import _compliance_plan

            await _consent.announce_and_grant(
                sess,
                sess.tts,
                _compliance_plan(sess.voice_config).recording_consent_message,
            )
        if sess.opener_text:
            await _start_outbound_opener(sess)
        else:
            await start_telephony_agent_greeting(sess)
        start_telephony_voice_policy_tasks(
            sess=sess,
            telephony_manager=telephony_manager,
        )

        logger.info(
            "Telephony runtime ready provider=%s call_sid=%s",
            provider,
            call_sid,
        )
        return sess, call_sid, auth_session_token
    except BaseException:
        await _rollback_start_event(
            sess=sess,
            voice_bundle=voice_bundle,
            auth_session_token=auth_session_token,
            published=published,
        )
        raise


async def _start_outbound_opener(sess: CallSession) -> None:
    if (
        sess.tts is None
        or sess.call_id is None
        or sess.organization_id is None
        or sess.conversation_id is None
        or not sess.opener_text
    ):
        raise RuntimeError("Outbound opener state is incomplete.")
    turn_id = f"outbound-opener-{sess.call_id}"
    try:
        await sess.tts.add_to_request_queue(
            {"type": "text", "text": sess.opener_text, "turn_id": turn_id}
        )
        await sess.tts.add_to_request_queue({"type": "finalize", "turn_id": turn_id})
    except Exception:
        await record_opener_delivery(
            call_id=sess.call_id,
            organization_id=sess.organization_id,
            accepted=False,
        )
        logger.warning("Outbound opener could not be queued.")
        return
    sess.tts_tasks["opener_delivery"] = asyncio.create_task(
        _observe_outbound_opener(sess)
    )


async def _observe_outbound_opener(sess: CallSession) -> None:
    assert sess.tts is not None
    assert sess.call_id is not None
    assert sess.organization_id is not None
    assert sess.conversation_id is not None
    assert sess.opener_text is not None
    accepted = await sess.tts.wait_until_flushed(timeout=20.0)
    producer = sess.tts_tasks.get("producer")
    if producer is not None and producer.done():
        producer.result()
    if not accepted:
        await record_opener_delivery(
            call_id=sess.call_id,
            organization_id=sess.organization_id,
            accepted=False,
        )
        return
    await persist_delivered_outbound_opener(
        conversation_id=sess.conversation_id,
        organization_id=sess.organization_id,
        call_id=sess.call_id,
        text=sess.opener_text,
    )


async def _rollback_start_event(
    *,
    sess: CallSession,
    voice_bundle: VoicePipelineBundle | None,
    auth_session_token: str | None,
    published: bool,
) -> None:
    sess.is_active = False
    if published:
        S_CALLS.remove(sess)
    if sess.organization_id is not None and sess.call_id is not None:
        try:
            await record_call_status(
                organization_id=sess.organization_id,
                call_sid=sess.call_sid,
                status=CallStatus.FAILED,
                ended_reason=CallEndedReason.ERROR_SYSTEM.value,
                ended_at=arrow.utcnow().datetime,
                conversation_id=sess.conversation_id,
            )
        except Exception:
            logger.warning("Call setup failure could not be persisted.")
    if sess.audio_recorder is not None:
        try:
            await sess.audio_recorder.finalize()
        except Exception:
            logger.warning("Call setup recorder rollback failed.")
        sess.audio_recorder = None
    try:
        await teardown_voice_pipeline_bundle(voice_bundle)
    except Exception:
        logger.warning("Voice provider rollback failed.")
    if auth_session_token is not None and sess.organization_id is not None:
        try:
            await S_ws_manager.disconnect(
                sess.organization_id,
                auth_session_token,
                reason="telephony_setup_failed",
            )
        except Exception:
            logger.warning("Telephony WS rollback failed.")
    if sess.organization_id is not None and sess.user_session_id is not None:
        try:
            async with start_transaction() as db_session:
                await UserSessionService(db_session).finish(
                    organization_id=sess.organization_id,
                    user_session_id=sess.user_session_id,
                    state=UserSessionState.FAILED,
                    reason="telephony_setup_failed",
                )
        except Exception:
            logger.warning("Telephony user-session rollback failed.")


def _enrich_metadata_from_query_params(metadata: CallMetadata, ws: WebSocket) -> None:
    """Fill provider-omitted outbound fields; the signature authenticates them."""
    uuid_fields = {
        "organization_id": "org_id",
        "call_id": "call_id",
        "agent_id": "agent_id",
        "provider_config_id": "provider_config_id",
    }
    for attribute, query_key in uuid_fields.items():
        if getattr(metadata, attribute) is None and (
            value := ws.query_params.get(query_key)
        ):
            setattr(metadata, attribute, UUID(value))
            metadata.requires_media_stream_token = True
    if metadata.agent_revision is None and (
        value := ws.query_params.get("agent_revision")
    ):
        metadata.agent_revision = int(value)
        metadata.requires_media_stream_token = True
    if metadata.provider_config_revision is None and (
        value := ws.query_params.get("provider_config_revision")
    ):
        metadata.provider_config_revision = int(value)
        metadata.requires_media_stream_token = True
    if metadata.direction == "INBOUND" and (value := ws.query_params.get("direction")):
        metadata.direction = value
        metadata.requires_media_stream_token = True
    if not metadata.initial_message and (
        value := ws.query_params.get("initial_message")
    ):
        metadata.initial_message = value
        metadata.requires_media_stream_token = True
    if not metadata.media_stream_token and (
        value := ws.query_params.get("stream_token")
    ):
        metadata.media_stream_token = value


async def _enrich_inbound_metadata_from_phone_number(
    metadata: CallMetadata,
    provider: str,
    lookup=None,
) -> None:
    """Resolve inbound routing only from an organization-owned number row."""
    if not metadata.to_number:
        return
    if lookup is None:
        async with start_transaction() as session:
            phone_number = await PhoneNumberService(db=session).get_by_number(
                metadata.to_number
            )
    else:
        phone_number = await lookup(metadata.to_number)
    if phone_number is None:
        return
    if phone_number.provider != provider:
        raise ValueError("Phone number provider does not match the media provider.")
    metadata.organization_id = phone_number.organization_id
    metadata.agent_id = phone_number.inbound_agent_id
    metadata.provider_config_id = phone_number.provider_config_id
    metadata.provider_config_revision = phone_number.provider_config_revision


async def _resolve_metadata_authority(metadata: CallMetadata, provider: str):
    if metadata.organization_id is None or metadata.provider_config_id is None:
        raise ValueError("Media stream is missing telephony config authority.")
    async with start_transaction(ro=True) as db:
        resolver = build_telephony_config_resolver(db)
        if metadata.provider_config_revision is None:
            resolved = await resolver.resolve(
                metadata.organization_id,
                provider_config_id=metadata.provider_config_id,
            )
        else:
            resolved = await resolver.resolve_pinned(
                metadata.organization_id,
                provider_config_id=metadata.provider_config_id,
                revision=metadata.provider_config_revision,
            )
    if resolved.provider.value != provider:
        raise ValueError("Media provider does not match telephony config authority.")
    metadata.provider_config_revision = resolved.provider_config_revision
    return resolved


def _has_query_metadata(ws: WebSocket) -> bool:
    return any(
        key in ws.query_params
        for key in (
            "org_id",
            "call_id",
            "agent_id",
            "agent_revision",
            "provider_config_id",
            "provider_config_revision",
            "direction",
            "initial_message",
        )
    )


def _is_media_stream_metadata_authorized(
    metadata: CallMetadata,
    ws: WebSocket,
    provider: str,
    *,
    client_ip_allowlisted: bool,
) -> bool:
    """Authenticate caller-selectable routing before resolving its authority."""
    requires_token = (
        metadata.requires_media_stream_token
        or _has_query_metadata(ws)
        or bool(metadata.media_stream_token)
        or metadata.direction.upper() == "OUTBOUND"
    )
    if not requires_token:
        return client_ip_allowlisted
    return verify_media_stream_token(
        metadata.media_stream_token,
        provider=provider,
        call_id=str(metadata.call_id) if metadata.call_id else None,
        organization_id=(
            str(metadata.organization_id) if metadata.organization_id else None
        ),
        agent_id=str(metadata.agent_id) if metadata.agent_id else None,
        agent_revision=metadata.agent_revision,
        provider_config_id=(
            str(metadata.provider_config_id) if metadata.provider_config_id else None
        ),
        provider_config_revision=metadata.provider_config_revision,
        direction=metadata.direction,
        call_sid=metadata.call_sid,
        initial_message=metadata.initial_message,
    )


async def _claim_and_canonicalize_outbound_metadata(
    metadata: CallMetadata,
    provider: str,
) -> TelephonyCallInDb:
    if (
        metadata.call_id is None
        or metadata.organization_id is None
        or metadata.agent_id is None
        or metadata.agent_revision is None
        or metadata.provider_config_id is None
        or metadata.provider_config_revision is None
    ):
        raise ValueError("Outbound media claim is incomplete.")
    call = await claim_outbound_media_session(
        call_id=metadata.call_id,
        organization_id=metadata.organization_id,
        provider=provider,
        provider_call_sid=metadata.call_sid,
        provider_config_id=metadata.provider_config_id,
        provider_config_revision=metadata.provider_config_revision,
        agent_id=metadata.agent_id,
        agent_revision=metadata.agent_revision,
        initial_message=metadata.initial_message,
    )
    metadata.call_sid = call.call_sid or metadata.call_sid
    metadata.from_number = call.from_number
    metadata.to_number = call.to_number
    metadata.organization_id = call.organization_id
    metadata.agent_id = call.agent_id
    metadata.agent_revision = call.agent_revision
    metadata.provider_config_id = call.provider_config_id
    metadata.provider_config_revision = call.provider_config_revision
    metadata.conversation_id = None
    return call


async def _resolve_call_agent(
    metadata: CallMetadata,
    *,
    organization_id: UUID,
    agent_id: UUID,
) -> ResolvedExecutableAgent:
    """Resolve one published exact agent before creating realtime resources."""
    from eylo.modules.templates.domain import TemplateConsumerKind
    from eylo.pipelines.agents import build_executable_agent_resolver

    async with start_transaction(ro=True) as db:
        resolver = build_executable_agent_resolver(db)
        if metadata.agent_revision is not None:
            executable = await resolver.resolve_exact(
                organization_id=organization_id,
                agent_id=agent_id,
                revision=metadata.agent_revision,
                consumer_kind=TemplateConsumerKind.REALTIME_VOICE,
            )
        else:
            executable = await resolver.resolve_for_new_work(
                organization_id=organization_id,
                agent_id=agent_id,
                consumer_kind=TemplateConsumerKind.REALTIME_VOICE,
            )
    metadata.agent_revision = executable.ref.revision
    return executable


async def _receive_provider_message(ws: WebSocket, provider: str) -> str | bytes:
    if provider != "vonage":
        return await ws.receive_text()
    message = await ws.receive()
    if message.get("bytes") is not None:
        return message["bytes"]
    if message.get("text") is not None:
        return message["text"]
    raise WebSocketDisconnect


def _raise_failed_runtime_task(sess: CallSession) -> None:
    for task in (*sess.stt_tasks.values(), *sess.tts_tasks.values()):
        if task.done() and not task.cancelled() and task.exception() is not None:
            raise RuntimeError(
                "Telephony runtime background task failed."
            ) from task.exception()


@router.websocket("/media/stream")
async def generic_media_ws(
    ws: WebSocket,
    provider: Literal["twilio", "plivo", "vonage", "exotel"],
) -> None:
    """Run one authenticated 1:1 provider media session."""
    verification_enabled = getattr(
        settings,
        "TELEPHONY_WEBHOOK_VERIFICATION_ENABLED",
        True,
    )
    client_ip = ws.client.host if ws.client else None
    client_ip_allowlisted = is_ip_allowlisted(client_ip)
    if not verification_enabled and getattr(settings, "ENV", None) != Environment.LOCAL:
        await ws.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await ws.accept()
    sess: CallSession | None = None
    auth_session_token: str | None = None
    manager_closed_ws = False
    telephony_manager = TelephonyRealtime(websocket=ws, provider=provider)
    dtmf_collector = DTMFCollector()
    try:
        while True:
            if sess is not None:
                _raise_failed_runtime_task(sess)
            raw = await _receive_provider_message(ws, provider)
            if sess is not None:
                digits = telephony_manager.extract_dtmf(raw)
                if digits:
                    await handle_inbound_dtmf(
                        sess=sess,
                        collector=dtmf_collector,
                        digits=digits,
                    )
                    continue

            media_message = await telephony_manager.handle_message(raw)
            if telephony_manager.call_metadata is not None and sess is None:
                metadata = telephony_manager.call_metadata
                _enrich_metadata_from_query_params(metadata, ws)
                if metadata.direction.upper() != "OUTBOUND":
                    await _enrich_inbound_metadata_from_phone_number(
                        metadata,
                        provider,
                    )
                if verification_enabled and not _is_media_stream_metadata_authorized(
                    metadata,
                    ws,
                    provider,
                    client_ip_allowlisted=client_ip_allowlisted,
                ):
                    await ws.close(code=status.WS_1008_POLICY_VIOLATION)
                    return

                canonical_call = None
                if metadata.direction.upper() == "OUTBOUND":
                    canonical_call = await _claim_and_canonicalize_outbound_metadata(
                        metadata,
                        provider,
                    )
                resolved = await _resolve_metadata_authority(metadata, provider)
                telephony_manager.activate(
                    organization_id=resolved.organization_id,
                    session_id=metadata.call_sid,
                    telephony_config=resolved.as_provider_config().adapter_settings(),
                )
                sess, _, auth_session_token = await _handle_start_event(
                    telephony_manager,
                    ws,
                    provider,
                    canonical_call,
                )
                dtmf_collector = DTMFCollector(
                    digit_limit=16,
                    termination_key="#",
                    timeout_ms=5000,
                )
            elif media_message is not None and sess is not None:
                await handle_media_packet(
                    sess=sess,
                    media_message=media_message,
                    provider=provider,
                )
    except WebSocketDisconnect:
        if sess is not None and sess.ended_reason is None:
            sess.ended_reason = CallEndedReason.ERROR_PROVIDER_DISCONNECTED
        logger.info(
            "Carrier media transport disconnected provider=%s call_sid=%s",
            provider,
            sess.call_sid if sess else None,
        )
    except Exception:
        if sess is not None and sess.ended_reason is None:
            sess.ended_reason = CallEndedReason.ERROR_SYSTEM
        logger.error(
            "Telephony media runtime failed provider=%s call_sid=%s",
            provider,
            sess.call_sid if sess else None,
        )
    finally:
        if sess is not None:
            try:
                manager_closed_ws = await finalize_call_session(
                    sess=sess,
                    provider=provider,
                    auth_session_token=auth_session_token,
                )
            except Exception:
                logger.error("Call finalization failed.")
        await telephony_manager.disconnect()
        if not manager_closed_ws and ws.client_state == WebSocketState.CONNECTED:
            try:
                await ws.close()
            except RuntimeError:
                logger.debug("WebSocket already closed.")
