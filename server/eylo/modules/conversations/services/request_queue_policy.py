"""Conversation request queue policy.

The conversation runtime service is the mechanism: it owns Redis claims,
heartbeats, wakeups, and release. This service is the policy boundary: it
decides which pending user request the active runtime owner should process
next. FIFO is the default policy.
"""

import logging
from typing import Protocol
from uuid import UUID

from eylo.modules.conversations.schemas.messages import MessageInDb, RequestStatus
from eylo.modules.conversations.schemas.request_queue import (
    RequestQueueBusyDecision,
    RequestQueueDecision,
    RequestQueuePolicyMode,
)
from eylo.modules.conversations.schemas.request_status import (
    RequestStatusTransitionResult,
)
from eylo.modules.conversations.services.messages import MessageService

logger = logging.getLogger(__name__)


class RequestQueueMessageService(Protocol):
    async def get_next_pending_user_message(
        self,
        conversation_id: UUID,
    ) -> MessageInDb | None: ...

    async def get_newest_pending_user_message(
        self,
        conversation_id: UUID,
    ) -> MessageInDb | None: ...

    async def list_pending_user_messages(
        self,
        conversation_id: UUID,
    ) -> list[MessageInDb]: ...

    async def count_pending_user_messages(self, conversation_id: UUID) -> int: ...

    async def update_request_status_by_request_id(
        self,
        request_id: UUID,
        request_status: RequestStatus,
        *,
        conversation_id: UUID,
    ) -> RequestStatusTransitionResult: ...


class RequestQueuePolicyService:
    """Select the next user request without owning runtime coordination.

    Runtime ownership, wakeups, and heartbeats live in
    ConversationRuntimeStatusService. This service owns only the queue policy
    decision so the drainer mechanism does not hard-code FIFO behavior.
    """

    def __init__(
        self,
        message_service: RequestQueueMessageService | None = None,
        policy_mode: RequestQueuePolicyMode = RequestQueuePolicyMode.FIFO,
    ) -> None:
        self.message_service = message_service or MessageService()
        self.policy_mode = RequestQueuePolicyMode(policy_mode)

    async def next_pending_user_message(
        self,
        conversation_id: UUID,
    ) -> RequestQueueDecision:
        if self.policy_mode is RequestQueuePolicyMode.FILO:
            return await self._next_filo_user_message(conversation_id)
        if self.policy_mode is RequestQueuePolicyMode.LATEST_ONLY:
            return await self._next_latest_only_user_message(conversation_id)
        return await self._next_fifo_user_message(conversation_id)

    async def handle_runtime_busy_user_message(
        self,
        message: MessageInDb,
    ) -> RequestQueueBusyDecision:
        if self.policy_mode is not RequestQueuePolicyMode.REJECT_WHILE_BUSY:
            return self._busy_decision(message=message, rejected=False)

        if message.request_id is None:
            logger.error(
                "[RequestQueuePolicy] Cannot reject busy user message %s "
                "without request_id",
                message.id,
            )
            return self._busy_decision(message=message, rejected=False)

        result = await self.message_service.update_request_status_by_request_id(
            request_id=message.request_id,
            request_status=RequestStatus.FAILED,
            conversation_id=message.conversation_id,
        )
        return self._busy_decision(
            message=message,
            rejected=result.changed,
            current_status=result.current_status,
        )

    async def _next_fifo_user_message(
        self,
        conversation_id: UUID,
    ) -> RequestQueueDecision:
        message = await self.message_service.get_next_pending_user_message(
            conversation_id
        )
        return await self._decision(
            conversation_id=conversation_id,
            next_message=message,
        )

    async def _next_filo_user_message(
        self,
        conversation_id: UUID,
    ) -> RequestQueueDecision:
        message = await self.message_service.get_newest_pending_user_message(
            conversation_id
        )
        return await self._decision(
            conversation_id=conversation_id,
            next_message=message,
        )

    async def _next_latest_only_user_message(
        self,
        conversation_id: UUID,
    ) -> RequestQueueDecision:
        pending_messages = await self.message_service.list_pending_user_messages(
            conversation_id
        )
        if not pending_messages:
            return await self._decision(
                conversation_id=conversation_id,
                next_message=None,
            )

        latest_message = pending_messages[-1]
        interrupted_request_ids = await self._interrupt_stale_pending_requests(
            pending_messages[:-1],
            latest_message,
        )
        return await self._decision(
            conversation_id=conversation_id,
            next_message=latest_message,
            interrupted_request_ids=tuple(interrupted_request_ids),
        )

    async def _interrupt_stale_pending_requests(
        self,
        stale_messages: list[MessageInDb],
        latest_message: MessageInDb,
    ) -> list[UUID]:
        interrupted_request_ids: list[UUID] = []
        latest_request_id = latest_message.request_id
        for message in stale_messages:
            if message.request_id is None:
                logger.error(
                    "[RequestQueuePolicy] Cannot interrupt pending user message %s "
                    "without request_id",
                    message.id,
                )
                continue
            if message.request_id == latest_request_id:
                continue
            result = await self.message_service.update_request_status_by_request_id(
                request_id=message.request_id,
                request_status=RequestStatus.INTERRUPTED,
                conversation_id=message.conversation_id,
            )
            if result.changed:
                interrupted_request_ids.append(message.request_id)
        return interrupted_request_ids

    async def _decision(
        self,
        *,
        conversation_id: UUID,
        next_message: MessageInDb | None,
        interrupted_request_ids: tuple[UUID, ...] = (),
    ) -> RequestQueueDecision:
        pending_count = await self.message_service.count_pending_user_messages(
            conversation_id
        )
        return RequestQueueDecision(
            conversation_id=conversation_id,
            policy_mode=self.policy_mode,
            next_message=next_message,
            pending_count=pending_count,
            interrupted_request_ids=interrupted_request_ids,
        )

    def _busy_decision(
        self,
        *,
        message: MessageInDb,
        rejected: bool,
        current_status: RequestStatus | None = None,
    ) -> RequestQueueBusyDecision:
        return RequestQueueBusyDecision(
            conversation_id=message.conversation_id,
            policy_mode=self.policy_mode,
            request_id=message.request_id,
            rejected=rejected,
            current_status=current_status or message.request_status,
        )
