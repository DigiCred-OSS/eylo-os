"""Idempotent campaign outcome projection from exact channel attempts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from eylo.products.campaigns.constants import (
    CampaignContactStatus,
    CampaignStatus,
)
from eylo.products.campaigns.models import (
    CampaignAttemptModel,
    CampaignContactModel,
    CampaignModel,
    CampaignRevisionModel,
)
from eylo.products.campaigns.repositories import CampaignContactRepository

_TERMINAL_CONTACT_STATES = frozenset(
    {
        CampaignContactStatus.COMPLETED.value,
        CampaignContactStatus.FAILED.value,
        CampaignContactStatus.SKIPPED.value,
        CampaignContactStatus.CANCELLED.value,
    }
)


class CampaignOutcomeAuthorityMissing(Exception):
    """The exact organization/campaign/contact/attempt authority is unavailable."""


@dataclass(frozen=True, slots=True)
class CampaignOutreachOutcome:
    """One exact channel result derived from canonical provider state."""

    organization_id: UUID
    campaign_id: UUID
    campaign_contact_id: UUID
    campaign_attempt_id: UUID
    tracking_id: str
    channel: str
    outcome: str
    connected: bool
    duration_seconds: float | None = None


async def apply_campaign_outreach_outcome(
    *,
    session: AsyncSession,
    outcome: CampaignOutreachOutcome,
) -> bool:
    """Apply one attempt once; return false when replay already converged."""
    attempt = await session.scalar(
        select(CampaignAttemptModel)
        .where(
            CampaignAttemptModel.id == outcome.campaign_attempt_id,
            CampaignAttemptModel.organization_id == outcome.organization_id,
            CampaignAttemptModel.campaign_id == outcome.campaign_id,
            CampaignAttemptModel.campaign_contact_id
            == outcome.campaign_contact_id,
            CampaignAttemptModel.channel == outcome.channel,
            CampaignAttemptModel.deleted.is_(False),
        )
        .with_for_update()
    )
    if attempt is None:
        raise CampaignOutcomeAuthorityMissing("Campaign attempt is unavailable.")
    if attempt.outcome_recorded_at is not None:
        return False

    campaign = await session.scalar(
        select(CampaignModel)
        .where(
            CampaignModel.id == outcome.campaign_id,
            CampaignModel.organization_id == outcome.organization_id,
            CampaignModel.deleted.is_(False),
        )
        .with_for_update()
    )
    contact = await session.scalar(
        select(CampaignContactModel)
        .where(
            CampaignContactModel.id == outcome.campaign_contact_id,
            CampaignContactModel.campaign_id == outcome.campaign_id,
            CampaignContactModel.organization_id == outcome.organization_id,
            CampaignContactModel.deleted.is_(False),
        )
        .with_for_update()
    )
    revision = await session.scalar(
        select(CampaignRevisionModel).where(
            CampaignRevisionModel.campaign_id == outcome.campaign_id,
            CampaignRevisionModel.revision == attempt.campaign_revision,
            CampaignRevisionModel.organization_id == outcome.organization_id,
            CampaignRevisionModel.deleted.is_(False),
        )
    )
    if campaign is None or contact is None or revision is None:
        raise CampaignOutcomeAuthorityMissing(
            "Campaign outcome projection authority is unavailable."
        )

    now = datetime.now(timezone.utc)
    attempt.tracking_id = outcome.tracking_id
    attempt.outcome = outcome.outcome
    attempt.outcome_recorded_at = now

    if contact.status in _TERMINAL_CONTACT_STATES:
        return True

    contact.attempt_count = max(contact.attempt_count or 0, attempt.attempt_number)
    contact.last_tracking_id = outcome.tracking_id
    contact.last_outcome_reason = outcome.outcome
    contact.last_attempt_at = now
    contact.next_retry_at = None

    if outcome.connected:
        contact.status = CampaignContactStatus.COMPLETED.value
        campaign.completed_contacts += 1
    elif _should_retry(
        campaign=campaign,
        revision=revision,
        attempt=attempt,
        outcome=outcome,
    ):
        policy = revision.retry_policy or {}
        backoff_seconds = int(policy.get("backoff_seconds", 0))
        delay = backoff_seconds * (2 ** max(attempt.attempt_number - 1, 0))
        contact.status = CampaignContactStatus.RETRY.value
        contact.next_retry_at = now + timedelta(seconds=delay)
    else:
        contact.status = CampaignContactStatus.FAILED.value
        campaign.failed_contacts += 1

    await _complete_campaign_if_terminal(session=session, campaign=campaign)
    return True


def _should_retry(
    *,
    campaign: CampaignModel,
    revision: CampaignRevisionModel,
    attempt: CampaignAttemptModel,
    outcome: CampaignOutreachOutcome,
) -> bool:
    if campaign.status != CampaignStatus.RUNNING.value:
        return False
    policy = revision.retry_policy or {}
    max_retries = int(policy.get("max_retries", 0))
    retry_on = set(policy.get("retry_on") or [])
    return attempt.attempt_number <= max_retries and (
        not retry_on or outcome.outcome in retry_on
    )


async def _complete_campaign_if_terminal(
    *,
    session: AsyncSession,
    campaign: CampaignModel,
) -> None:
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
