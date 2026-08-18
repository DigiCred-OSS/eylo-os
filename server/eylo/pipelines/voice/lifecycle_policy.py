"""Transport-neutral timing policy for humane voice sessions."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Protocol

from eylo.modules.voice.schemas.api import SilenceConfig
from eylo.modules.voice_transcripts.constants import VoiceSessionStatus

_COMPLETED_BROWSER_END_REASONS = frozenset(
    {
        "client_hangup",
        "ice_closed",
        "ice_disconnected",
        "max_duration",
        "peer_closed",
        "peer_disconnected",
        "silence_timeout",
        "track_ended",
        "user_end_call_phrase",
        "websocket_disconnected",
    }
)


def browser_voice_session_status(reason: str | None) -> VoiceSessionStatus:
    """Classify a browser call conservatively from its terminal observation."""
    if reason in _COMPLETED_BROWSER_END_REASONS:
        return VoiceSessionStatus.COMPLETED
    return VoiceSessionStatus.FAILED


class VoiceActivityState(Protocol):
    def mark_user_activity(self) -> None: ...

    @property
    def is_awaiting_user(self) -> bool: ...

    @property
    def awaiting_user_seconds(self) -> float: ...


def matches_end_call_phrase(transcript: str, phrases: list[str]) -> bool:
    """Match a complete caller utterance against configured terminal phrases."""
    if not phrases:
        return False
    cleaned = transcript.strip().casefold()
    return any(cleaned == phrase.strip().casefold() for phrase in phrases)


def should_start_silence_monitor(config: SilenceConfig) -> bool:
    reminders_enabled = (
        config.reminder_trigger_ms > 0
        and config.reminder_max_count > 0
        and bool(config.reminder_messages)
    )
    return reminders_enabled or config.end_call_after_silence_ms > 0


async def monitor_silence(
    *,
    config: SilenceConfig,
    speech_activity_event: asyncio.Event,
    activity: VoiceActivityState,
    is_agent_thinking: Callable[[], bool],
    is_tts_active: Callable[[], bool],
    on_reminder: Callable[[str], Awaitable[None]],
    on_timeout: Callable[[float], Awaitable[None]],
) -> None:
    """Run reminder/timeout policy while the session is awaiting the user."""
    trigger_seconds = config.reminder_trigger_ms / 1000.0
    end_call_seconds = (
        config.end_call_after_silence_ms / 1000.0
        if config.end_call_after_silence_ms > 0
        else 0
    )
    reminder_messages = config.reminder_messages
    reminders_sent = 0

    while True:
        await asyncio.sleep(1.0)
        if speech_activity_event.is_set():
            activity.mark_user_activity()
            reminders_sent = 0
            speech_activity_event.clear()
            continue
        if is_agent_thinking() or is_tts_active() or not activity.is_awaiting_user:
            continue

        elapsed = activity.awaiting_user_seconds
        if end_call_seconds > 0 and elapsed >= end_call_seconds:
            await on_timeout(elapsed)
            return
        if not reminder_messages or elapsed < trigger_seconds:
            continue
        if reminders_sent >= config.reminder_max_count:
            if end_call_seconds <= 0:
                await on_timeout(elapsed)
                return
            continue

        await on_reminder(reminder_messages[reminders_sent % len(reminder_messages)])
        reminders_sent += 1
