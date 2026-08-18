"""Capture and play platform-owned voice policy messages."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import Protocol
from uuid import UUID, uuid4

from eylo.common.contracts.voice import VoiceSpeechOutcome
from eylo.pipelines.voice.live_buffer import (
    LiveVoiceBuffer,
    LiveVoiceDraft,
    LiveVoiceItemKind,
)
from eylo.pipelines.voice.request_state import (
    VoiceRequestSource,
    VoiceRequestStatus,
)
from eylo.pipelines.voice.tts import TTSRealtime


class PolicySpeechState(Protocol):
    def start_voice_request(
        self,
        *,
        request_id: UUID,
        conversation_id: UUID,
        source: VoiceRequestSource,
        status: VoiceRequestStatus,
    ) -> object: ...

    def mark_voice_request(
        self,
        request_id: UUID | str | None,
        status: VoiceRequestStatus,
        *,
        conversation_id: UUID | None = None,
        source: VoiceRequestSource = VoiceRequestSource.USER,
        turn_id: str | None = None,
    ) -> object | None: ...


class RealtimePolicySpeaker(Protocol):
    async def request_speech(
        self,
        text: str,
        *,
        request_id: UUID,
        wait_until_played: bool,
        timeout_seconds: float,
    ) -> bool: ...


async def play_policy_speech(
    *,
    tts_manager: TTSRealtime | None = None,
    realtime_speaker: RealtimePolicySpeaker | None = None,
    live_buffer: LiveVoiceBuffer,
    conversation_id: UUID,
    text: str,
    source: VoiceRequestSource,
    session_state: PolicySpeechState | None = None,
    request_id: UUID | None = None,
    wait_until_played: bool = False,
    timeout_seconds: float = 10.0,
    wait_for_transport_drain: Callable[[float], Awaitable[bool]] | None = None,
) -> UUID:
    """Queue auditable platform speech without creating an Agent message."""
    if (tts_manager is None) == (realtime_speaker is None):
        raise ValueError("Exactly one voice policy speaker is required.")

    deadline = time.monotonic() + timeout_seconds

    def remaining_timeout() -> float:
        return max(0.0, deadline - time.monotonic())

    request_id = request_id or uuid4()
    turn_id = f"{source.value}-{request_id}"
    await live_buffer.append_turn(
        [
            LiveVoiceDraft(
                kind=LiveVoiceItemKind.SYSTEM_SPEECH,
                payload=text,
                request_id=request_id,
                policy_source=source,
            )
        ]
    )
    if session_state is not None:
        session_state.start_voice_request(
            request_id=request_id,
            conversation_id=conversation_id,
            source=source,
            status=VoiceRequestStatus.TTS_QUEUED,
        )

    if realtime_speaker is not None:
        try:
            played = await realtime_speaker.request_speech(
                text,
                request_id=request_id,
                wait_until_played=wait_until_played,
                timeout_seconds=remaining_timeout(),
            )
        except Exception:
            live_buffer.mark_speech_outcome(
                request_id,
                VoiceSpeechOutcome.FAILED.value,
            )
            raise
        if played and wait_until_played and wait_for_transport_drain is not None:
            played = await wait_for_transport_drain(remaining_timeout())
        if not played:
            live_buffer.mark_speech_outcome(
                request_id,
                VoiceSpeechOutcome.FAILED.value,
            )
        if session_state is not None:
            session_state.mark_voice_request(
                request_id,
                (
                    VoiceRequestStatus.COMPLETED
                    if played and wait_until_played
                    else VoiceRequestStatus.TTS_PLAYING
                    if played
                    else VoiceRequestStatus.FAILED
                ),
                conversation_id=conversation_id,
                source=source,
                turn_id=turn_id,
            )
        if not played:
            raise RuntimeError("Realtime policy speech was not accepted.")
        return request_id

    assert tts_manager is not None
    await tts_manager.add_to_request_queue(
        {
            "type": "text",
            "text": text,
            "turn_id": turn_id,
            "request_id": str(request_id),
        }
    )
    await tts_manager.add_to_request_queue(
        {
            "type": "finalize",
            "turn_id": turn_id,
            "request_id": str(request_id),
        }
    )
    if not wait_until_played:
        return request_id

    played = await tts_manager.wait_until_flushed(timeout=remaining_timeout())
    if played and wait_for_transport_drain is not None:
        played = await wait_for_transport_drain(remaining_timeout())
    outcome = VoiceSpeechOutcome.DRAINED if played else VoiceSpeechOutcome.FAILED
    live_buffer.mark_speech_outcome(request_id, outcome.value)
    if session_state is not None:
        session_state.mark_voice_request(
            request_id,
            VoiceRequestStatus.COMPLETED if played else VoiceRequestStatus.FAILED,
            conversation_id=conversation_id,
            source=source,
            turn_id=turn_id,
        )
    return request_id
