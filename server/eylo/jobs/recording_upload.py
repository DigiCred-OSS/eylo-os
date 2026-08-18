"""Periodic DB-outbox nudge for Absurd-owned recording uploads."""

from __future__ import annotations

from eylo.pipelines.voice.recording_durable_execution import (
    spawn_unbound_voice_recording_uploads,
)


async def nudge_unbound_recording_uploads() -> dict[str, int]:
    """Repeat lost producer spawns; never upload recording data."""
    return {"spawned": await spawn_unbound_voice_recording_uploads()}


__all__ = ["nudge_unbound_recording_uploads"]
