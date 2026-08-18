"""Periodic work for curated vendor connections."""

from __future__ import annotations

import logging

from eylo.common.database import start_transaction

from .refresh import refresh_expiring_curated_connections

logger = logging.getLogger(__name__)


async def refresh_expiring_curated_tokens() -> dict:
    """Renew curated OAuth credentials expiring inside the refresh window."""
    logger.info("[CuratedRefreshTask] Starting curated token refresh cycle")
    try:
        async with start_transaction():
            outcome = await refresh_expiring_curated_connections()
    except Exception as error:  # noqa: BLE001 - the next tick retries the cycle
        logger.error("[CuratedRefreshTask] Failed error_type=%s", type(error).__name__)
        return {"status": "error", "error": "Curated token refresh failed."}
    logger.info(
        "[CuratedRefreshTask] considered=%d refreshed=%d failed=%d",
        outcome.considered,
        len(outcome.refreshed),
        len(outcome.failed),
    )
    return {
        "status": "success",
        "refreshed_count": len(outcome.refreshed),
        "failed_count": len(outcome.failed),
    }


__all__ = ["refresh_expiring_curated_tokens"]
