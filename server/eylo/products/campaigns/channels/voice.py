"""Voice channel adapter — dispatches campaign outreach as phone calls."""

import logging
import re
from typing import Optional
from uuid import UUID

from sqlalchemy import select

from eylo.common.database import start_transaction
from eylo.modules.telephony.models import TelephonyCallModel
from eylo.products.campaigns.channels.base import (
    CampaignChannelAdapter,
    ChannelDispatchResult,
)
from eylo.products.campaigns.constants import CampaignChannel
from eylo.products.campaigns.schemas.indb import CampaignContactInDb, CampaignInDb

logger = logging.getLogger(__name__)

_E164_PATTERN = re.compile(r"^\+?[1-9]\d{1,14}$")


class VoiceChannelAdapter:
    """Dispatches campaign outreach as outbound phone calls.

    The campaign is already the durable scheduling authority. The adapter
    places one exact outbound call and records its provider identity before
    reporting acceptance.
    """

    channel: str = CampaignChannel.VOICE.value
    replay_safe = True

    async def validate_campaign(self, campaign: CampaignInDb) -> list[str]:
        from eylo.modules.telephony.services import PhoneNumberService

        errors: list[str] = []
        phone = await PhoneNumberService().get_by_outbound_agent_id(
            str(campaign.agent_id),
            organization_id=campaign.organization_id,
        )
        if not phone:
            errors.append(
                "The assigned agent has no outbound phone number configured. "
                "Assign a phone number to this agent first."
            )
        return errors

    async def validate_contact(self, contact: CampaignContactInDb) -> bool:
        return bool(_E164_PATTERN.match(contact.contact_address))

    async def recover_dispatch(
        self,
        campaign: CampaignInDb,
        contact: CampaignContactInDb,
        attempt_id: UUID,
    ) -> ChannelDispatchResult | None:
        async with start_transaction(ro=True) as session:
            call = await session.scalar(
                select(TelephonyCallModel).where(
                    TelephonyCallModel.organization_id == campaign.organization_id,
                    TelephonyCallModel.campaign_id == campaign.id,
                    TelephonyCallModel.campaign_contact_id == contact.id,
                    TelephonyCallModel.campaign_attempt_id == attempt_id,
                    TelephonyCallModel.deleted.is_(False),
                )
            )
        if call is None:
            return None
        if call.call_sid:
            return ChannelDispatchResult(tracking_id=call.call_sid)
        if call.provider_status == "initiation-unknown":
            return ChannelDispatchResult(
                tracking_id=str(call.id),
                dispatch_unknown=True,
            )
        if call.status == "failed":
            return ChannelDispatchResult(
                tracking_id=str(call.id),
                error=call.ended_reason or "provider_rejected",
            )
        return None

    async def dispatch(
        self,
        campaign: CampaignInDb,
        contact: CampaignContactInDb,
        rendered_message: Optional[str],
        attempt_id: UUID,
    ) -> ChannelDispatchResult:
        meta = {
            "kind": "outbound_call",
            "to_number": contact.contact_address,
            "initial_message": rendered_message,
            "campaign_id": str(campaign.id),
            "campaign_contact_id": str(contact.id),
            "campaign_attempt_id": str(attempt_id),
        }

        from eylo.pipelines.telephony.call_control import VoiceService

        response = await VoiceService().initiate_outbound_call(
            call_id=attempt_id,
            to_number=contact.contact_address,
            agent_id=campaign.agent_id,
            agent_revision=campaign.agent_revision,
            organization_id=campaign.organization_id,
            initial_message=rendered_message,
            context=meta,
        )
        tracking_id = str(response.get("call_sid") or response["call_id"])
        if response["status"] == "unknown":
            return ChannelDispatchResult(
                tracking_id=tracking_id,
                dispatch_unknown=True,
            )
        if response["status"] != "succeeded":
            return ChannelDispatchResult(
                tracking_id=tracking_id,
                error=str(response.get("failure_code") or "provider_rejected"),
            )

        logger.info(
            "Voice dispatch: campaign=%s contact=%s call_id=%s",
            campaign.id,
            contact.id,
            tracking_id,
        )
        return ChannelDispatchResult(tracking_id=tracking_id)


# Type check: ensure VoiceChannelAdapter satisfies the protocol
_: CampaignChannelAdapter = VoiceChannelAdapter()  # type: ignore[assignment]
