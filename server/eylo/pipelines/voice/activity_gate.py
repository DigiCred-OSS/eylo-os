"""Local voice activity coordination for browser voice sessions."""

from __future__ import annotations

import asyncio
import time


class VoiceActivityGate:
    """Tracks when a voice session is actually waiting for the user.

    The gate deliberately does not replace request lifecycle tracking. It only
    coordinates audible agent activity with user speech so silence checks start
    after the agent has finished speaking.
    """

    def __init__(self) -> None:
        self._agent_activity_active = False
        self._awaiting_user_since: float | None = None

    def reset(self) -> None:
        self._agent_activity_active = False
        self._awaiting_user_since = None

    def mark_agent_activity_started(self) -> None:
        self._agent_activity_active = True
        self._awaiting_user_since = None

    def mark_agent_activity_finished(self) -> None:
        self._agent_activity_active = False
        self._awaiting_user_since = time.monotonic()

    def mark_user_activity(self) -> None:
        self._agent_activity_active = False
        self._awaiting_user_since = time.monotonic()

    @property
    def is_agent_active(self) -> bool:
        return self._agent_activity_active

    @property
    def is_awaiting_user(self) -> bool:
        return not self._agent_activity_active and self._awaiting_user_since is not None

    @property
    def awaiting_user_seconds(self) -> float:
        if self._agent_activity_active or self._awaiting_user_since is None:
            return 0.0
        return time.monotonic() - self._awaiting_user_since


class TransportPlaybackGate:
    """Separate provider completion from audio drained by the transport.

    TTS and realtime providers finish before WebRTC has necessarily emitted its
    buffered PCM frames. One active generation covers contiguous agent audio;
    a later start before drain extends that same audible window.
    """

    def __init__(self) -> None:
        self._generation = 0
        self._active_generation: int | None = None
        self._producer_finished_generation: int | None = None
        self._last_drained_generation: int | None = None
        self._change = asyncio.Event()

    def reset(self) -> None:
        self._active_generation = None
        self._producer_finished_generation = None
        self._last_drained_generation = None
        self._change.set()

    def mark_started(self) -> int:
        if self._active_generation is None:
            self._generation += 1
            self._active_generation = self._generation
        self._producer_finished_generation = None
        self._change.set()
        return self._active_generation

    def mark_producer_finished(self) -> None:
        if self._active_generation is None:
            return
        self._producer_finished_generation = self._active_generation
        self._change.set()

    def cancel(self) -> None:
        self._active_generation = None
        self._producer_finished_generation = None
        self._change.set()

    def complete_if_drained(self) -> bool:
        generation = self._active_generation
        if generation is None or self._producer_finished_generation != generation:
            return False
        self._last_drained_generation = generation
        self._active_generation = None
        self._producer_finished_generation = None
        self._change.set()
        return True

    async def wait_until_drained(self, *, timeout: float) -> bool:
        """Wait for the current audible window; cancellation is not a drain."""
        generation = self._active_generation
        if generation is None:
            return self._last_drained_generation == self._generation

        async def wait() -> bool:
            while self._active_generation == generation:
                self._change.clear()
                if self._active_generation != generation:
                    break
                await self._change.wait()
            return self._last_drained_generation == generation

        try:
            async with asyncio.timeout(timeout):
                return await wait()
        except TimeoutError:
            return False

    @property
    def is_active(self) -> bool:
        return self._active_generation is not None
