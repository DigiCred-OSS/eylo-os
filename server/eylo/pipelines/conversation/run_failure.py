"""Atomic convergence for failed message-backed AgentRuns."""

from __future__ import annotations

import logging
from uuid import UUID

from eylo.common.database import start_transaction
from eylo.modules.agent_runs.domain import AgentRunOriginKind
from eylo.modules.agent_runs.service import fail_agent_run_in_transaction
from eylo.modules.conversations.repositories.messages import (
    MessageAgentRunRepository,
)
from eylo.modules.conversations.schemas.messages import RequestStatus
from eylo.modules.conversations.services.request_status import RequestStatusService

logger = logging.getLogger(__name__)


async def fail_agent_run_and_converge_message(
    *,
    organization_id: UUID,
    run_id: UUID,
    failure_summary: str,
) -> None:
    """Fail one run and its message request in the same transaction."""
    async with start_transaction() as session:
        run = await fail_agent_run_in_transaction(
            session,
            organization_id=organization_id,
            run_id=run_id,
            failure_summary=failure_summary,
        )
        if run.origin_kind is not AgentRunOriginKind.MESSAGE:
            return
        if run.origin_message_id is None:
            logger.error("Message AgentRun=%s has no origin message.", run_id)
            return

        origin = await MessageAgentRunRepository(session).get_origin_message(
            organization_id=organization_id,
            message_id=run.origin_message_id,
        )
        if origin is None or origin.request_id is None:
            logger.error("Message AgentRun=%s has no active request authority.", run_id)
            return

        transition = await RequestStatusService(session).transition_to(
            origin.request_id,
            RequestStatus.FAILED,
            conversation_id=origin.conversation_id,
        )
        if not transition.valid:
            logger.error(
                "Message AgentRun=%s could not converge request=%s from status=%s "
                "to FAILED.",
                run_id,
                origin.request_id,
                transition.current_status,
            )


__all__ = ["fail_agent_run_and_converge_message"]
