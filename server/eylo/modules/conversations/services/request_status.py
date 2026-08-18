"""Application services for the `conversations` domain."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from eylo.modules.conversations.message_facts import file_voice_message_fact
from eylo.modules.conversations.repositories.messages import MessageRepository
from eylo.modules.conversations.schemas.messages import MessageKind, RequestStatus
from eylo.modules.conversations.schemas.request_status import (
    RequestStatusTransitionResult,
)
from eylo.modules.user_sessions.events import file_user_session_fact

_TERMINAL_REQUEST_STATUSES = (
    RequestStatus.COMPLETED,
    RequestStatus.FAILED,
    RequestStatus.INTERRUPTED,
    # A worker that looked and found nothing to do is finished, same as one
    # that did the work. Leaving SKIPPED out would let a skipped task be
    # re-entered and re-run.
    RequestStatus.SKIPPED,
)

_VALID_REQUEST_STATUS_TRANSITIONS: dict[str, tuple[RequestStatus, ...]] = {
    RequestStatus.PENDING.value: (
        RequestStatus.PROCESSING,
        RequestStatus.FAILED,
        RequestStatus.INTERRUPTED,
    ),
    RequestStatus.PROCESSING.value: (
        RequestStatus.AWAITING_TOOL_RESULTS,
        RequestStatus.COMPLETED,
        RequestStatus.FAILED,
        RequestStatus.INTERRUPTED,
        # Only reachable from PROCESSING: deciding the work is unnecessary
        # requires having picked it up and looked.
        RequestStatus.SKIPPED,
    ),
    RequestStatus.AWAITING_TOOL_RESULTS.value: (
        RequestStatus.PROCESSING,
        RequestStatus.FAILED,
        RequestStatus.INTERRUPTED,
    ),
    RequestStatus.COMPLETED.value: (),
    RequestStatus.FAILED.value: (),
    RequestStatus.INTERRUPTED.value: (),
    RequestStatus.SKIPPED.value: (),
}


class RequestStatusService:
    def __init__(self, db: AsyncSession | None = None) -> None:
        self.repository = MessageRepository(db)

    async def transition_to(
        self,
        request_id: UUID,
        requested_status: RequestStatus,
        *,
        conversation_id: UUID,
    ) -> RequestStatusTransitionResult:
        """Validate the request transition and converge every active message row."""
        current_status = await self.repository.get_latest_request_status(
            request_id,
            conversation_id,
        )
        is_idempotent = current_status == requested_status

        if not is_idempotent and not self.can_transition(
            current_status, requested_status
        ):
            return self._result(
                request_id=request_id,
                previous_status=current_status,
                requested_status=requested_status,
                current_status=current_status,
                changed=False,
                valid=False,
            )

        updated_count = await self.repository.update_request_status_by_request_id(
            request_id=request_id,
            conversation_id=conversation_id,
            request_status=requested_status,
        )
        if updated_count and requested_status in _TERMINAL_REQUEST_STATUSES:
            for message in await self.repository.list_by_request_id(
                request_id,
                conversation_id,
            ):
                kind = (
                    message.kind.value
                    if hasattr(message.kind, "value")
                    else str(message.kind)
                )
                if kind != MessageKind.ASSISTANT.value:
                    continue
                await file_voice_message_fact(
                    session=self.repository.db_session,
                    message=message,
                )
        if updated_count:
            authority = await self.repository.get_request_timeline_authority(
                request_id,
                conversation_id,
            )
            if authority is not None:
                await file_user_session_fact(
                    self.repository.db_session,
                    organization_id=authority.organization_id,
                    user_session_id=authority.user_session_id,
                    subject_type="message.request",
                    subject_id=request_id,
                    event_type=(
                        "message.request."
                        f"{requested_status.value.lower()}"
                    ),
                    payload={
                        "conversation_id": str(authority.conversation_id),
                        "previous_status": (
                            current_status.value if current_status is not None else None
                        ),
                        "current_status": requested_status.value,
                    },
                )

        return self._result(
            request_id=request_id,
            previous_status=current_status,
            requested_status=requested_status,
            current_status=(
                requested_status if is_idempotent or updated_count else current_status
            ),
            changed=updated_count > 0,
            valid=is_idempotent or updated_count > 0,
        )

    async def mark_failed_if_non_terminal(
        self,
        request_id: UUID,
        *,
        conversation_id: UUID,
    ) -> int:
        result = await self.transition_to(
            request_id,
            RequestStatus.FAILED,
            conversation_id=conversation_id,
        )
        return int(result.changed)

    @staticmethod
    def can_transition(
        current_status: RequestStatus | None,
        requested_status: RequestStatus,
    ) -> bool:
        if current_status is None:
            return False
        if current_status in _TERMINAL_REQUEST_STATUSES:
            return False
        return (
            requested_status in _VALID_REQUEST_STATUS_TRANSITIONS[current_status.value]
        )

    @staticmethod
    def _result(
        *,
        request_id: UUID,
        previous_status: RequestStatus | None,
        requested_status: RequestStatus,
        current_status: RequestStatus | None,
        changed: bool,
        valid: bool,
    ) -> RequestStatusTransitionResult:
        return RequestStatusTransitionResult(
            request_id=request_id,
            previous_status=previous_status,
            requested_status=requested_status,
            current_status=current_status,
            changed=changed,
            valid=valid,
        )
