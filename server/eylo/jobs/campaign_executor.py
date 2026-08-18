"""Periodic filer and DB-outbox nudge for Absurd-owned campaign attempts."""

from __future__ import annotations

from eylo.pipelines.campaigns import (
    file_due_campaign_attempts,
    spawn_unbound_campaign_attempts,
)


async def process_campaign_calls() -> dict[str, int]:
    """File due product rows and repeat lost spawns; never dispatch providers."""
    result = await file_due_campaign_attempts()
    result["outbox_spawned"] = await spawn_unbound_campaign_attempts()
    return result


__all__ = ["process_campaign_calls"]
