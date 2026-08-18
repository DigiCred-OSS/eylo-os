"""Route the Agent's end-call request to the exact live voice transport."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, TypeVar

from eylo.common.contracts.telephony import CallEndedReason
from eylo.modules.session_context.schemas import SessionChannel, SessionContext
from eylo.modules.voice_transcripts.constants import VoiceRuntimeMode
from eylo.pipelines.voice.live_buffer import LiveVoiceBufferIdentity
from eylo.pipelines.voice.request_state import VoiceRequestSource

if TYPE_CHECKING:
    from eylo.modules.conversations.schemas.conversations import ConversationContext
    from eylo.pipelines.telephony.sessions import CallSession
    from eylo.pipelines.websocket.schemas import WSSessionState

logger = logging.getLogger(__name__)

END_CALL_TOOL_NAME = "end_call"
SessionT = TypeVar("SessionT")


@dataclass(frozen=True, slots=True)
class AgentVoiceTerminationOutcome:
    """Safe tool result for one exact live voice termination request."""

    content: dict[str, Any]
    is_error: bool
    metadata: dict[str, Any] = field(default_factory=dict)


async def is_live_voice_session_active(identity: LiveVoiceBufferIdentity) -> bool:
    """Return whether the exact in-memory voice authority is still active."""
    if identity.runtime_mode is VoiceRuntimeMode.TELEPHONY:
        return _resolve_telephony_session(identity) is not None
    return await _resolve_browser_session(identity) is not None


async def execute_agent_end_call_tool(
    *,
    conversation_context: ConversationContext,
    identity: LiveVoiceBufferIdentity,
) -> AgentVoiceTerminationOutcome:
    """Request teardown through the owner of the exact active voice transport."""
    conversation = conversation_context.conversation
    if (
        identity.organization_id != conversation.organization_id
        or identity.conversation_id != conversation.id
    ):
        logger.error("Live voice end-call authority did not match the conversation.")
        return _error_outcome("voice_session_not_available")

    if identity.runtime_mode is VoiceRuntimeMode.TELEPHONY:
        return await _end_telephony_session(identity)
    return await _end_browser_session(identity)


async def _end_telephony_session(
    identity: LiveVoiceBufferIdentity,
) -> AgentVoiceTerminationOutcome:
    from eylo.pipelines.telephony.voice import terminate_telephony_voice

    session = _resolve_telephony_session(identity)
    if session is None or session.telephony_manager is None:
        return _error_outcome("voice_session_not_available")

    accepted = await terminate_telephony_voice(
        sess=session,
        telephony_manager=session.telephony_manager,
        ended_reason=CallEndedReason.AGENT_ENDED_CALL,
        source=VoiceRequestSource.END_CALL,
    )
    return _termination_outcome(accepted, identity.runtime_mode)


async def _end_browser_session(
    identity: LiveVoiceBufferIdentity,
) -> AgentVoiceTerminationOutcome:
    from eylo.pipelines.voice.browser import request_browser_voice_termination

    session = await _resolve_browser_session(identity)
    if session is None:
        return _error_outcome("voice_session_not_available")

    context = SessionContext(
        channel=SessionChannel.WEBSOCKET,
        organization_id=identity.organization_id,
        session_id=session.session_id,
        contact_id=session.contact_id,
        voice_session_id=identity.voice_session_id,
        authorized_conversation_id=identity.conversation_id,
        ws=session,
    )
    accepted = await request_browser_voice_termination(
        context,
        reason=CallEndedReason.AGENT_ENDED_CALL.value,
        notify_client=True,
        source=VoiceRequestSource.END_CALL,
    )
    return _termination_outcome(accepted, identity.runtime_mode)


def _resolve_telephony_session(
    identity: LiveVoiceBufferIdentity,
) -> CallSession | None:
    from eylo.pipelines.telephony.sessions import S_CALLS

    matches = [
        session
        for session in S_CALLS.active_sessions()
        if session.is_active
        and not session.termination_requested
        and session.organization_id == identity.organization_id
        and session.conversation_id == identity.conversation_id
        and session.call_sid == identity.session_id
        and session.voice_session_id == identity.voice_session_id
        and session.live_voice_buffer is not None
        and session.live_voice_buffer.identity == identity
    ]
    return _one_exact_session(matches, identity.runtime_mode)


async def _resolve_browser_session(
    identity: LiveVoiceBufferIdentity,
) -> WSSessionState | None:
    from eylo.pipelines.websocket.singleton import S_ws_manager

    session_ids = await S_ws_manager.get_sessions_for_conversation(
        identity.organization_id,
        identity.conversation_id,
    )
    matches: list[WSSessionState] = []
    for session_id in session_ids:
        session = S_ws_manager.get_session_state(
            identity.organization_id,
            str(session_id),
        )
        if (
            session is not None
            and session.is_voice_mode
            and not session.voice_termination_complete
            and session.voice_call_id == identity.session_id
            and session.voice_session_id == identity.voice_session_id
            and session.live_voice_buffer is not None
            and session.live_voice_buffer.identity == identity
        ):
            matches.append(session)
    return _one_exact_session(matches, identity.runtime_mode)


def _one_exact_session(
    matches: list[SessionT],
    runtime_mode: VoiceRuntimeMode,
) -> SessionT | None:
    if len(matches) > 1:
        logger.error(
            "Live voice end-call authority was ambiguous runtime_mode=%s.",
            runtime_mode.value,
        )
        return None
    return matches[0] if matches else None


def _termination_outcome(
    accepted: bool,
    runtime_mode: VoiceRuntimeMode,
) -> AgentVoiceTerminationOutcome:
    if not accepted:
        return _error_outcome("voice_termination_not_accepted")
    return AgentVoiceTerminationOutcome(
        content={
            "status": "success",
            "message": "Voice session termination requested.",
        },
        is_error=False,
        metadata={
            "voice_termination": True,
            "runtime_mode": runtime_mode.value,
        },
    )


def _error_outcome(code: str) -> AgentVoiceTerminationOutcome:
    return AgentVoiceTerminationOutcome(
        content={
            "status": "error",
            "error": code,
            "message": "The active voice session could not be ended.",
        },
        is_error=True,
        metadata={"voice_termination": True},
    )


__all__ = [
    "END_CALL_TOOL_NAME",
    "AgentVoiceTerminationOutcome",
    "execute_agent_end_call_tool",
    "is_live_voice_session_active",
]
