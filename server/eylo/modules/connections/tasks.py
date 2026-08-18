"""Periodic tasks for connection management."""

import logging
from datetime import datetime, timezone

from eylo.common.database import start_transaction
from eylo.modules.connections.repositories.oauth_state import OAuthStateRepository
from eylo.modules.connections.services.indb import ConnectionService

logger = logging.getLogger(__name__)


async def cleanup_invalidated_connections() -> dict:
    """Delete REVOKED/FAILED/INACTIVE connections older than 30 days."""
    logger.info("[CleanupConnectionsTask] Starting cleanup")
    try:
        async with start_transaction() as db:
            deleted_count, connection_ids = await ConnectionService(
                db
            ).cleanup_old_invalidated_connections(retention_days=30)
        logger.info(f"[CleanupConnectionsTask] Deleted {deleted_count} connections")
        return {"status": "success", "deleted_count": deleted_count}
    except Exception as error:
        logger.error(
            "[CleanupConnectionsTask] Failed error_type=%s",
            type(error).__name__,
        )
        return {"status": "error", "error": "Connection cleanup failed."}


async def cleanup_expired_oauth_states() -> dict:
    """Delete expired OAuth state records."""
    logger.info("[CleanupOAuthStatesTask] Starting cleanup")
    try:
        async with start_transaction():
            state_ids = await OAuthStateRepository().delete_expired_states(
                datetime.now(timezone.utc)
            )
            deleted_count = len(state_ids)
        logger.info(f"[CleanupOAuthStatesTask] Deleted {deleted_count} states")
        return {"status": "success", "deleted_count": deleted_count}
    except Exception as error:
        logger.error(
            "[CleanupOAuthStatesTask] Failed error_type=%s",
            type(error).__name__,
        )
        return {"status": "error", "error": "OAuth state cleanup failed."}
