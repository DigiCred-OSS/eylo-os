"""Aggregate lifecycle for organization-owned knowledgebases."""

from __future__ import annotations

import logging
from collections.abc import Iterable
from uuid import UUID

from eylo.common.database import start_transaction
from eylo.durable_runtime import PlatformDurableRuntime
from eylo.modules.knowledgebase.services.knowledgebases import KnowledgebaseService

logger = logging.getLogger(__name__)


async def notify_cancelled_tasks(
    task_ids: Iterable[UUID],
    *,
    resource_kind: str,
    resource_id: UUID,
) -> None:
    """Best-effort engine notification after product state has committed."""
    pending = tuple(task_ids)
    if not pending:
        return
    try:
        runtime = PlatformDurableRuntime()
    except Exception as error:  # noqa: BLE001 - product state is authority
        logger.error(
            "Could not open %s cancellation runtime id=%s error_type=%s",
            resource_kind,
            resource_id,
            type(error).__name__,
        )
        return

    try:
        for task_id in pending:
            try:
                await runtime.cancel_task(task_id)
            except Exception as error:  # noqa: BLE001 - product state is authority
                logger.error(
                    "Could not notify cancelled %s id=%s task_id=%s error_type=%s",
                    resource_kind,
                    resource_id,
                    task_id,
                    type(error).__name__,
                )
    finally:
        try:
            await runtime.close()
        except Exception as error:  # noqa: BLE001 - cancellation is committed
            logger.error(
                "Could not close %s cancellation runtime id=%s error_type=%s",
                resource_kind,
                resource_id,
                type(error).__name__,
            )


async def delete_knowledgebase(
    *,
    organization_id: UUID,
    knowledgebase_id: UUID,
) -> None:
    """Commit the aggregate tombstone, then notify bound execution tasks."""
    async with start_transaction() as session:
        deletion = await KnowledgebaseService(session).delete(
            knowledgebase_id,
            organization_id,
        )

    await notify_cancelled_tasks(
        deletion.task_ids,
        resource_kind="knowledgebase",
        resource_id=knowledgebase_id,
    )
