"""Project canonical terminal calls onto exact campaign attempts."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from eylo.events.durable.domain import DurableEventEnvelope
from eylo.events.durable.registry import (
    EventConsumerRegistry,
    PermanentEventConsumerError,
)
from eylo.modules.telephony.lifecycle import (
    CALL_ENDED_EVENT_TYPE,
    CALL_ENDED_EVENT_VERSION,
    CALL_SUBJECT_TYPE,
    CAMPAIGN_CALL_OUTCOME_CONSUMER,
    is_terminal_call_status,
)
from eylo.modules.telephony.models import TelephonyCallModel
from eylo.products.campaigns.constants import (
    CHANNEL_CONNECTED_OUTCOMES,
    CampaignChannel,
)
from eylo.products.campaigns.outcomes import (
    CampaignOutcomeAuthorityMissing,
    CampaignOutreachOutcome,
    apply_campaign_outreach_outcome,
)


def register_campaign_call_outcome_consumer(
    registry: EventConsumerRegistry,
) -> None:
    """Register the exact supported call-fact contract."""
    registry.register(
        consumer_name=CAMPAIGN_CALL_OUTCOME_CONSUMER,
        event_type=CALL_ENDED_EVENT_TYPE,
        event_version=CALL_ENDED_EVENT_VERSION,
        handler=consume_campaign_call_outcome,
    )


async def consume_campaign_call_outcome(
    session: AsyncSession,
    envelope: DurableEventEnvelope,
) -> None:
    """Reload one canonical call and apply its campaign outcome atomically."""
    if envelope.subject_type != CALL_SUBJECT_TYPE:
        raise PermanentEventConsumerError(
            "Durable call fact has an unsupported subject type."
        )
    call = await session.scalar(
        select(TelephonyCallModel)
        .where(
            TelephonyCallModel.id == envelope.subject_id,
            TelephonyCallModel.organization_id == envelope.organization_id,
            TelephonyCallModel.deleted.is_(False),
        )
        .with_for_update()
    )
    if call is None:
        raise PermanentEventConsumerError(
            "Canonical campaign call authority is unavailable."
        )
    if not is_terminal_call_status(call.status) or call.ended_at is None:
        raise PermanentEventConsumerError("Canonical campaign call is not terminal.")
    if call.ended_reason is None:
        raise PermanentEventConsumerError(
            "Canonical campaign call is missing its outcome reason."
        )
    if (
        call.campaign_id is None
        or call.campaign_contact_id is None
        or call.campaign_attempt_id is None
    ):
        raise PermanentEventConsumerError(
            "Canonical campaign call has incomplete campaign authority."
        )

    channel = CampaignChannel.VOICE.value
    outcome = CampaignOutreachOutcome(
        organization_id=call.organization_id,
        campaign_id=call.campaign_id,
        campaign_contact_id=call.campaign_contact_id,
        campaign_attempt_id=call.campaign_attempt_id,
        tracking_id=call.call_sid,
        channel=channel,
        outcome=call.ended_reason,
        connected=call.ended_reason
        in CHANNEL_CONNECTED_OUTCOMES[CampaignChannel.VOICE],
        duration_seconds=(
            float(call.duration_seconds)
            if call.duration_seconds is not None
            else None
        ),
    )
    try:
        await apply_campaign_outreach_outcome(session=session, outcome=outcome)
    except CampaignOutcomeAuthorityMissing as error:
        raise PermanentEventConsumerError(str(error)) from error
