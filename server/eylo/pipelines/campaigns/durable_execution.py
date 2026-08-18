"""Absurd workflow for one exact campaign outreach attempt."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from absurd_sdk import AsyncTaskContext, CancelledTask
from sqlalchemy import select

from eylo.absurd_work import (
    AbsurdBoundWorkService,
    DurableState,
    DurableWorkBindingPending,
    spawn_bound_work,
    spawn_unbound_work,
)
from eylo.common.database import start_transaction
from eylo.durable_runtime import PlatformDurableRuntime, run_with_durable_heartbeat
from eylo.modules.contacts.domain import ContactLifecycle
from eylo.modules.contacts.models import ContactsModel
from eylo.products.campaigns.channels import get_channel_adapter
from eylo.products.campaigns.constants import (
    IMMEDIATE_DELIVERY_CHANNELS,
    CampaignContactStatus,
    CampaignStatus,
)
from eylo.products.campaigns.models import (
    CampaignAttemptModel,
    CampaignContactModel,
    CampaignModel,
)
from eylo.products.campaigns.repositories import (
    CampaignContactRepository,
)
from eylo.products.campaigns.schemas.indb import CampaignContactInDb, CampaignInDb
from eylo.products.campaigns.services.campaign_service import CampaignService
from eylo.products.campaigns.services.execution_service import (
    CampaignExecutionService,
)

logger = logging.getLogger(__name__)

CAMPAIGN_ATTEMPT_WORKFLOW = "eylo.campaign.attempt.v1"
_RECOVER_DISPATCH = "recover_dispatch"


class CampaignDispatchContractError(Exception):
    """An adapter returned an unusable accepted-effect result."""


def register_campaign_attempt_workflow(runtime: PlatformDurableRuntime) -> None:
    workflow = CampaignAttemptWorkflow()
    runtime.register_task(name=CAMPAIGN_ATTEMPT_WORKFLOW, handler=workflow.execute)


async def spawn_campaign_attempt(
    *,
    organization_id: UUID,
    attempt_id: UUID,
) -> UUID:
    return await spawn_bound_work(
        model=CampaignAttemptModel,
        organization_id=organization_id,
        work_id=attempt_id,
        workflow_name=CAMPAIGN_ATTEMPT_WORKFLOW,
        params_name="attempt_id",
        idempotency_prefix="campaign-attempt",
    )


async def spawn_unbound_campaign_attempts(*, limit: int = 100) -> int:
    async def spawn(organization_id: UUID, attempt_id: UUID) -> UUID:
        return await spawn_campaign_attempt(
            organization_id=organization_id,
            attempt_id=attempt_id,
        )

    spawned, failures = await spawn_unbound_work(
        model=CampaignAttemptModel,
        spawn=spawn,
        limit=limit,
    )
    for attempt_id, error in failures:
        logger.error(
            "Could not spawn campaign attempt id=%s error_type=%s",
            attempt_id,
            type(error).__name__,
        )
    return spawned


async def file_due_campaign_attempts() -> dict[str, int]:
    """File bounded product attempts, commit, then best-effort direct spawn."""
    async with start_transaction(ro=True) as session:
        campaigns = list(
            (
                await session.execute(
                    select(CampaignModel.organization_id, CampaignModel.id)
                    .where(
                        CampaignModel.status == CampaignStatus.RUNNING.value,
                        CampaignModel.deleted.is_(False),
                    )
                    .order_by(CampaignModel.created_at.asc())
                )
            ).all()
        )

    filed: list[tuple[UUID, UUID]] = []
    now = datetime.now(timezone.utc)
    for organization_id, campaign_id in campaigns:
        try:
            async with start_transaction() as session:
                attempts = await CampaignExecutionService(session).file_due_attempts(
                    organization_id=organization_id,
                    campaign_id=campaign_id,
                    now=now,
                )
                filed.extend(
                    (UUID(str(attempt.organization_id)), UUID(str(attempt.id)))
                    for attempt in attempts
                )
        except Exception as error:
            logger.error(
                "Could not file attempts campaign=%s error_type=%s",
                campaign_id,
                type(error).__name__,
            )

    spawned = 0
    for organization_id, attempt_id in filed:
        try:
            await spawn_campaign_attempt(
                organization_id=organization_id,
                attempt_id=attempt_id,
            )
            spawned += 1
        except Exception as error:
            logger.error(
                "Campaign attempt filed; DB outbox will repeat spawn "
                "attempt=%s error_type=%s",
                attempt_id,
                type(error).__name__,
            )
    return {"filed": len(filed), "spawned": spawned}


class CampaignAttemptWorkflow:
    """Execute one provider effect with an explicit ambiguity boundary."""

    async def execute(
        self,
        params: dict[str, Any],
        task_context: AsyncTaskContext,
    ) -> dict[str, Any]:
        organization_id, attempt_id = _parse_params(params)
        try:
            return await self._execute(
                organization_id=organization_id,
                attempt_id=attempt_id,
                task_context=task_context,
            )
        except CancelledTask:
            async with start_transaction() as session:
                await AbsurdBoundWorkService(
                    CampaignAttemptModel,
                    session,
                ).cancel(work_id=attempt_id, organization_id=organization_id)
            raise

    async def _execute(
        self,
        *,
        organization_id: UUID,
        attempt_id: UUID,
        task_context: AsyncTaskContext,
    ) -> dict[str, Any]:
        try:
            prepared = await _prepare_attempt(
                organization_id=organization_id,
                attempt_id=attempt_id,
            )
        except DurableWorkBindingPending:
            raise
        except Exception as error:  # noqa: BLE001 - load failure is product state
            return await _reject_attempt(
                organization_id=organization_id,
                attempt_id=attempt_id,
                error=error,
                skipped=False,
            )
        if isinstance(prepared, dict):
            return prepared

        adapter, campaign, contact, initial_message = prepared
        boundary = await _start_effect(
            organization_id=organization_id,
            attempt_id=attempt_id,
            replay_safe=adapter.replay_safe,
        )
        if boundary is not None:
            if boundary.get(_RECOVER_DISPATCH):
                recovered = await adapter.recover_dispatch(
                    campaign,
                    contact,
                    attempt_id,
                )
                if recovered is not None and recovered.tracking_id:
                    return await _complete_dispatch(
                        organization_id=organization_id,
                        attempt_id=attempt_id,
                        tracking_id=recovered.tracking_id,
                    )
                return await _mark_dispatch_unknown(
                    organization_id=organization_id,
                    attempt_id=attempt_id,
                    error=CampaignDispatchContractError(
                        "Worker stopped after a non-replay-safe effect began."
                    ),
                )
            return boundary

        async def dispatch() -> dict[str, Any]:
            result = await adapter.dispatch(
                campaign,
                contact,
                initial_message,
                attempt_id,
            )
            return result.model_dump(mode="json")

        try:
            result = await task_context.step(
                f"campaign-attempt:{attempt_id}:dispatch:v1",
                lambda: run_with_durable_heartbeat(task_context, dispatch),
            )
            tracking_id = str(result.get("tracking_id") or "").strip()
            error = result.get("error")
            if result.get("dispatch_unknown"):
                return await _mark_dispatch_unknown(
                    organization_id=organization_id,
                    attempt_id=attempt_id,
                    error=CampaignDispatchContractError(
                        "Provider delivery outcome is unconfirmed."
                    ),
                )
            if error:
                return await _reject_attempt(
                    organization_id=organization_id,
                    attempt_id=attempt_id,
                    error=CampaignDispatchContractError(
                        "Campaign adapter rejected delivery."
                    ),
                    skipped=False,
                )
            if not tracking_id:
                raise CampaignDispatchContractError(
                    "Campaign adapter accepted work without a tracking ID."
                )
        except Exception as error:  # noqa: BLE001 - provider ambiguity is explicit
            if adapter.replay_safe:
                return await _retry_replay_safe_attempt(
                    organization_id=organization_id,
                    attempt_id=attempt_id,
                    error=error,
                )
            return await _mark_dispatch_unknown(
                organization_id=organization_id,
                attempt_id=attempt_id,
                error=error,
            )

        return await _complete_dispatch(
            organization_id=organization_id,
            attempt_id=attempt_id,
            tracking_id=tracking_id,
        )


async def _prepare_attempt(
    *,
    organization_id: UUID,
    attempt_id: UUID,
):
    async with start_transaction() as session:
        work = AbsurdBoundWorkService(
            CampaignAttemptModel,
            session,
        )
        attempt = await work.begin_attempt(
            work_id=attempt_id,
            organization_id=organization_id,
        )
        if attempt.state in {
            DurableState.SUCCEEDED,
            DurableState.FAILED,
            DurableState.CANCELLED,
        }:
            return _receipt(attempt)

        campaign = await session.scalar(
            select(CampaignModel).where(
                CampaignModel.id == attempt.campaign_id,
                CampaignModel.organization_id == organization_id,
                CampaignModel.deleted.is_(False),
            )
        )
        contact = await session.scalar(
            select(CampaignContactModel).where(
                CampaignContactModel.id == attempt.campaign_contact_id,
                CampaignContactModel.campaign_id == attempt.campaign_id,
                CampaignContactModel.organization_id == organization_id,
                CampaignContactModel.deleted.is_(False),
            )
        )
        if campaign is None or contact is None:
            raise CampaignDispatchContractError(
                "Campaign attempt authority is missing."
            )
        if not await _contact_allows_campaign_effect(
            session,
            organization_id=organization_id,
            contact=contact,
        ):
            await work.cancel(
                work_id=attempt_id,
                organization_id=organization_id,
            )
            contact.status = CampaignContactStatus.CANCELLED.value
            return _receipt(attempt)
        if campaign.status not in {
            CampaignStatus.RUNNING.value,
            CampaignStatus.CANCELED.value,
            CampaignStatus.PAUSED.value,
        }:
            raise CampaignDispatchContractError(
                f"Campaign is not executable from {campaign.status}."
            )
        if campaign.status != CampaignStatus.RUNNING.value:
            await AbsurdBoundWorkService(CampaignAttemptModel, session).cancel(
                work_id=attempt_id,
                organization_id=organization_id,
            )
            contact.status = (
                CampaignContactStatus.PENDING.value
                if campaign.status == CampaignStatus.PAUSED.value
                else CampaignContactStatus.CANCELLED.value
            )
            return _receipt(attempt)

        campaign_service = CampaignService(session)
        definition = await campaign_service.get_definition_revision(
            organization_id=organization_id,
            campaign_id=attempt.campaign_id,
            revision=attempt.campaign_revision,
        )
        await campaign_service.require_execution_authority(definition)
        campaign_view = CampaignInDb.model_validate(campaign).model_copy(
            update={
                "name": definition.name,
                "description": definition.description,
                "channel": definition.channel,
                "channel_config": dict(definition.channel_config or {}),
                "agent_id": definition.agent_id,
                "agent_revision": definition.agent_revision,
                "published_revision": definition.revision,
                "initial_message_template_id": definition.initial_message_template_id,
                "initial_message_template_revision": (
                    definition.initial_message_template_revision
                ),
                "schedule_config": dict(definition.schedule_config or {}),
                "retry_policy": dict(definition.retry_policy or {}),
                "concurrency_limit": definition.concurrency_limit,
            }
        )
        contact_view = CampaignContactInDb.model_validate(contact)
        adapter = get_channel_adapter(definition.channel)
        campaign_errors = await adapter.validate_campaign(campaign_view)
        if campaign_errors:
            raise CampaignDispatchContractError(campaign_errors[0])
        if not await adapter.validate_contact(contact_view):
            return await _reject_locked_attempt(
                session=session,
                attempt=attempt,
                campaign=campaign,
                contact=contact,
                error="invalid_contact_address",
                skipped=True,
            )
        initial_message = await campaign_service.render_initial_message(
            definition,
            contact.variables or {},
        )
        return adapter, campaign_view, contact_view, initial_message


async def _start_effect(
    *,
    organization_id: UUID,
    attempt_id: UUID,
    replay_safe: bool,
) -> dict[str, Any] | None:
    async with start_transaction() as session:
        campaign_id = await session.scalar(
            select(CampaignAttemptModel.campaign_id).where(
                CampaignAttemptModel.id == attempt_id,
                CampaignAttemptModel.organization_id == organization_id,
            )
        )
        if campaign_id is None:
            raise CampaignDispatchContractError(
                "Campaign attempt authority is missing."
            )
        campaign = await session.scalar(
            select(CampaignModel)
            .where(
                CampaignModel.id == campaign_id,
                CampaignModel.organization_id == organization_id,
            )
            .with_for_update()
        )
        if campaign is None:
            raise CampaignDispatchContractError("Campaign authority is missing.")
        service = AbsurdBoundWorkService(CampaignAttemptModel, session)
        attempt = await service.get(
            work_id=attempt_id,
            organization_id=organization_id,
            for_update=True,
        )
        if attempt.state in {
            DurableState.SUCCEEDED,
            DurableState.FAILED,
            DurableState.CANCELLED,
        }:
            return _receipt(attempt)
        contact = await session.scalar(
            select(CampaignContactModel)
            .where(
                CampaignContactModel.id == attempt.campaign_contact_id,
                CampaignContactModel.campaign_id == attempt.campaign_id,
                CampaignContactModel.organization_id == organization_id,
            )
            .with_for_update()
        )
        if contact is None:
            raise CampaignDispatchContractError(
                "Campaign attempt contact authority is missing."
            )
        if attempt.effect_started_at is None and (
            campaign.deleted or campaign.status != CampaignStatus.RUNNING.value
        ):
            await service.cancel(
                work_id=attempt_id,
                organization_id=organization_id,
            )
            contact.status = (
                CampaignContactStatus.PENDING.value
                if campaign.status == CampaignStatus.PAUSED.value
                else CampaignContactStatus.CANCELLED.value
            )
            return _receipt(attempt)
        if attempt.effect_started_at is not None:
            # Historical safety is the upper bound. If a deployment changes
            # this channel to non-replay-safe, an effect started under the old
            # adapter must not be resent through the new one.
            if not attempt.effect_replay_safe or not replay_safe:
                return {_RECOVER_DISPATCH: True}
            return None
        if not await _contact_allows_campaign_effect(
            session,
            organization_id=organization_id,
            contact=contact,
            for_update=True,
        ):
            await service.cancel(
                work_id=attempt_id,
                organization_id=organization_id,
            )
            contact.status = CampaignContactStatus.CANCELLED.value
            return _receipt(attempt)
        attempt.effect_started_at = datetime.now(timezone.utc)
        attempt.effect_replay_safe = replay_safe
        await session.flush()
        return None


async def _contact_allows_campaign_effect(
    session,
    *,
    organization_id: UUID,
    contact: CampaignContactModel,
    for_update: bool = False,
) -> bool:
    """Repeat the contact fence immediately before a queued provider effect."""
    if contact.contact_id is None:
        return True
    query = select(ContactsModel.lifecycle).where(
        ContactsModel.id == contact.contact_id,
        ContactsModel.organization_id == organization_id,
        ContactsModel.deleted.is_(False),
    )
    if for_update:
        query = query.with_for_update()
    lifecycle = await session.scalar(query)
    return lifecycle == ContactLifecycle.ACTIVE.value


async def _complete_dispatch(
    *,
    organization_id: UUID,
    attempt_id: UUID,
    tracking_id: str,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    async with start_transaction() as session:
        service = AbsurdBoundWorkService(CampaignAttemptModel, session)
        attempt = await service.get(
            work_id=attempt_id,
            organization_id=organization_id,
            for_update=True,
        )
        contact = await session.scalar(
            select(CampaignContactModel)
            .where(
                CampaignContactModel.id == attempt.campaign_contact_id,
                CampaignContactModel.campaign_id == attempt.campaign_id,
                CampaignContactModel.organization_id == organization_id,
            )
            .with_for_update()
        )
        campaign = await session.scalar(
            select(CampaignModel)
            .where(
                CampaignModel.id == attempt.campaign_id,
                CampaignModel.organization_id == organization_id,
            )
            .with_for_update()
        )
        if contact is None or campaign is None:
            attempt.effect_completed_at = now
            attempt.tracking_id = tracking_id
            await service.fail(
                work_id=attempt_id,
                organization_id=organization_id,
                error="Campaign projection target is missing after provider acceptance.",
                permanent=True,
            )
            return _receipt(attempt)

        attempt.effect_completed_at = now
        attempt.tracking_id = tracking_id
        row = await service.succeed(
            work_id=attempt_id,
            organization_id=organization_id,
        )
        contact.attempt_count = max(contact.attempt_count or 0, attempt.attempt_number)
        contact.last_attempt_at = now
        contact.last_tracking_id = tracking_id
        if attempt.channel in IMMEDIATE_DELIVERY_CHANNELS:
            attempt.outcome = "delivered"
            attempt.outcome_recorded_at = now
            contact.status = CampaignContactStatus.COMPLETED.value
            contact.last_outcome_reason = "delivered"
            campaign.completed_contacts += 1
        elif contact.status not in {
            CampaignContactStatus.COMPLETED.value,
            CampaignContactStatus.FAILED.value,
            CampaignContactStatus.SKIPPED.value,
            CampaignContactStatus.CANCELLED.value,
        }:
            contact.status = CampaignContactStatus.IN_PROGRESS.value
        await _complete_campaign_if_terminal(session, campaign)
        return _receipt(row)


async def _retry_replay_safe_attempt(
    *,
    organization_id: UUID,
    attempt_id: UUID,
    error: Exception,
) -> dict[str, Any]:
    summary = _campaign_failure_code(error)
    async with start_transaction() as session:
        service = AbsurdBoundWorkService(CampaignAttemptModel, session)
        attempt = await service.get(
            work_id=attempt_id,
            organization_id=organization_id,
            for_update=True,
        )
        if attempt.state in {
            DurableState.SUCCEEDED,
            DurableState.FAILED,
            DurableState.CANCELLED,
        }:
            return _receipt(attempt)
        state = await service.fail(
            work_id=attempt_id,
            organization_id=organization_id,
            error=summary,
            permanent=False,
        )
        if state is DurableState.PENDING:
            should_retry = True
        else:
            should_retry = False
            campaign, contact = await _load_projection_targets(
                session=session,
                attempt=attempt,
            )
            if campaign is not None and contact is not None:
                await _project_failed_attempt_locked(
                    session=session,
                    attempt=attempt,
                    campaign=campaign,
                    contact=contact,
                    error=summary,
                    skipped=False,
                )
        receipt = _receipt(attempt)
    if should_retry:
        raise error
    return receipt


async def _reject_attempt(
    *,
    organization_id: UUID,
    attempt_id: UUID,
    error: Exception,
    skipped: bool,
) -> dict[str, Any]:
    async with start_transaction() as session:
        service = AbsurdBoundWorkService(CampaignAttemptModel, session)
        attempt = await service.get(
            work_id=attempt_id,
            organization_id=organization_id,
            for_update=True,
        )
        if attempt.state in {
            DurableState.SUCCEEDED,
            DurableState.FAILED,
            DurableState.CANCELLED,
        }:
            return _receipt(attempt)
        campaign, contact = await _load_projection_targets(
            session=session,
            attempt=attempt,
        )
        if campaign is None or contact is None:
            await service.fail(
                work_id=attempt_id,
                organization_id=organization_id,
                error=_campaign_failure_code(error, skipped=skipped),
                permanent=True,
            )
            return _receipt(attempt)
        return await _reject_locked_attempt(
            session=session,
            attempt=attempt,
            campaign=campaign,
            contact=contact,
            error=_campaign_failure_code(error, skipped=skipped),
            skipped=skipped,
        )


async def _reject_locked_attempt(
    *,
    session,
    attempt: CampaignAttemptModel,
    campaign: CampaignModel,
    contact: CampaignContactModel,
    error: str,
    skipped: bool,
) -> dict[str, Any]:
    if attempt.state in {
        DurableState.SUCCEEDED,
        DurableState.FAILED,
        DurableState.CANCELLED,
    }:
        return _receipt(attempt)
    await AbsurdBoundWorkService(CampaignAttemptModel, session).fail(
        work_id=attempt.id,
        organization_id=attempt.organization_id,
        error=error,
        permanent=True,
    )
    await _project_failed_attempt_locked(
        session=session,
        attempt=attempt,
        campaign=campaign,
        contact=contact,
        error=error,
        skipped=skipped,
    )
    return _receipt(attempt)


async def _project_failed_attempt_locked(
    *,
    session,
    attempt: CampaignAttemptModel,
    campaign: CampaignModel,
    contact: CampaignContactModel,
    error: str,
    skipped: bool,
) -> None:
    contact.status = (
        CampaignContactStatus.SKIPPED.value
        if skipped
        else CampaignContactStatus.FAILED.value
    )
    contact.attempt_count = max(contact.attempt_count or 0, attempt.attempt_number)
    contact.last_attempt_at = datetime.now(timezone.utc)
    contact.last_outcome_reason = error[:64]
    campaign.failed_contacts += 1
    await _complete_campaign_if_terminal(session, campaign)


async def _mark_dispatch_unknown(
    *,
    organization_id: UUID,
    attempt_id: UUID,
    error: Exception,
) -> dict[str, Any]:
    async with start_transaction() as session:
        attempt = await AbsurdBoundWorkService(
            CampaignAttemptModel,
            session,
        ).get(
            work_id=attempt_id,
            organization_id=organization_id,
            for_update=True,
        )
        return await _mark_dispatch_unknown_locked(
            session=session,
            attempt=attempt,
            error="campaign_dispatch_unknown",
        )


def _campaign_failure_code(error: Exception, *, skipped: bool = False) -> str:
    if skipped:
        return "campaign_attempt_skipped"
    if isinstance(error, CampaignDispatchContractError):
        return "campaign_dispatch_contract_error"
    return "campaign_dispatch_failed"


async def _mark_dispatch_unknown_locked(
    *,
    session,
    attempt: CampaignAttemptModel,
    error: str,
) -> dict[str, Any]:
    if attempt.state in {
        DurableState.SUCCEEDED,
        DurableState.FAILED,
        DurableState.CANCELLED,
    }:
        return _receipt(attempt)
    campaign, contact = await _load_projection_targets(
        session=session,
        attempt=attempt,
    )
    if campaign is None or contact is None:
        await AbsurdBoundWorkService(CampaignAttemptModel, session).fail(
            work_id=attempt.id,
            organization_id=attempt.organization_id,
            error=error,
            permanent=True,
        )
        attempt.dispatch_unknown = True
        return _receipt(attempt)
    await AbsurdBoundWorkService(CampaignAttemptModel, session).fail(
        work_id=attempt.id,
        organization_id=attempt.organization_id,
        error=error,
        permanent=True,
    )
    attempt.dispatch_unknown = True
    contact.status = CampaignContactStatus.FAILED.value
    contact.attempt_count = max(contact.attempt_count or 0, attempt.attempt_number)
    contact.last_attempt_at = datetime.now(timezone.utc)
    contact.last_outcome_reason = "dispatch_unknown"
    campaign.failed_contacts += 1
    await _complete_campaign_if_terminal(session, campaign)
    return _receipt(attempt)


async def _load_projection_targets(
    *,
    session,
    attempt: CampaignAttemptModel,
) -> tuple[CampaignModel | None, CampaignContactModel | None]:
    campaign = await session.scalar(
        select(CampaignModel)
        .where(
            CampaignModel.id == attempt.campaign_id,
            CampaignModel.organization_id == attempt.organization_id,
            CampaignModel.deleted.is_(False),
        )
        .with_for_update()
    )
    contact = await session.scalar(
        select(CampaignContactModel)
        .where(
            CampaignContactModel.id == attempt.campaign_contact_id,
            CampaignContactModel.campaign_id == attempt.campaign_id,
            CampaignContactModel.organization_id == attempt.organization_id,
            CampaignContactModel.deleted.is_(False),
        )
        .with_for_update()
    )
    return campaign, contact


async def _complete_campaign_if_terminal(session, campaign: CampaignModel) -> None:
    if campaign.status != CampaignStatus.RUNNING.value:
        return
    counts = await CampaignContactRepository(session).count_by_status(campaign.id)
    non_terminal = sum(
        counts.get(state.value, 0)
        for state in (
            CampaignContactStatus.PENDING,
            CampaignContactStatus.QUEUED,
            CampaignContactStatus.IN_PROGRESS,
            CampaignContactStatus.RETRY,
        )
    )
    if non_terminal == 0 and sum(counts.values()) > 0:
        campaign.status = CampaignStatus.COMPLETED.value
        campaign.completed_at = datetime.now(timezone.utc)


def _parse_params(params: dict[str, Any]) -> tuple[UUID, UUID]:
    if set(params) != {"organization_id", "attempt_id"}:
        raise ValueError("Campaign attempt params must contain IDs only.")
    try:
        return UUID(str(params["organization_id"])), UUID(str(params["attempt_id"]))
    except (TypeError, ValueError) as error:
        raise ValueError("Campaign attempt params contain an invalid UUID.") from error


def _receipt(attempt: CampaignAttemptModel) -> dict[str, Any]:
    return {
        "organization_id": str(attempt.organization_id),
        "attempt_id": str(attempt.id),
        "state": attempt.state.value,
        "tracking_id": attempt.tracking_id,
        "dispatch_unknown": attempt.dispatch_unknown,
    }


__all__ = [
    "CAMPAIGN_ATTEMPT_WORKFLOW",
    "CampaignAttemptWorkflow",
    "file_due_campaign_attempts",
    "register_campaign_attempt_workflow",
    "spawn_campaign_attempt",
    "spawn_unbound_campaign_attempts",
]
