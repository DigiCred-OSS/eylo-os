"""Campaign email channel backed by explicit organization email authority."""

from __future__ import annotations

import logging
import re
from typing import Optional
from uuid import UUID

from eylo.common.outbound import OutboundAttemptState, OutboundOwnerKind
from eylo.modules.provider_configs.errors import NotConfiguredError
from eylo.pipelines.email import (
    EmailDeliveryUnsupported,
    require_organization_email,
    send_organization_email,
)
from eylo.products.campaigns.channels.base import (
    CampaignChannelAdapter,
    ChannelDispatchResult,
)
from eylo.products.campaigns.constants import CampaignChannel
from eylo.products.campaigns.schemas.indb import CampaignContactInDb, CampaignInDb

logger = logging.getLogger(__name__)

_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PROVIDER_CONFIG_FIELD = "provider_config_id"
_PROVIDER_CONFIG_REVISION_FIELD = "provider_config_revision"


class EmailChannelAdapter:
    """Validate and dispatch campaign email through the selected config."""

    channel: str = CampaignChannel.EMAIL.value
    # Replays re-enter the same shared outbound attempt; ambiguous sends are fenced.
    replay_safe = True

    async def validate_campaign(self, campaign: CampaignInDb) -> list[str]:
        errors: list[str] = []
        config = campaign.channel_config or {}
        if not config.get("subject_template"):
            errors.append(
                "Email campaigns require a subject_template in channel config."
            )
        if not config.get("body_template"):
            errors.append("Email campaigns require a body_template in channel config.")

        provider_config_id = _provider_config_id(config)
        provider_config_revision = _provider_config_revision(config)
        if provider_config_id is None or provider_config_revision is None:
            errors.append("Email campaigns require an exact provider config revision.")
            return errors
        try:
            await require_organization_email(
                organization_id=campaign.organization_id,
                provider_config_id=provider_config_id,
                provider_config_revision=provider_config_revision,
            )
        except NotConfiguredError as error:
            errors.append(
                "Email provider config is not ready: " + ", ".join(error.missing)
            )
        return errors

    async def validate_contact(self, contact: CampaignContactInDb) -> bool:
        return bool(_EMAIL_PATTERN.fullmatch(contact.contact_address))

    async def recover_dispatch(
        self,
        campaign: CampaignInDb,
        contact: CampaignContactInDb,
        attempt_id: UUID,
    ) -> ChannelDispatchResult | None:
        del campaign, contact, attempt_id
        return None

    async def dispatch(
        self,
        campaign: CampaignInDb,
        contact: CampaignContactInDb,
        rendered_message: Optional[str],
        attempt_id: UUID,
    ) -> ChannelDispatchResult:
        from eylo.products.campaigns.services.campaign_service import CampaignService

        config = campaign.channel_config or {}
        provider_config_id = _provider_config_id(config)
        provider_config_revision = _provider_config_revision(config)
        if provider_config_id is None or provider_config_revision is None:
            return ChannelDispatchResult(
                tracking_id="",
                error="Exact email provider config is missing.",
            )

        variables = contact.variables or {}
        subject = CampaignService.render_template(
            str(config.get("subject_template", "")),
            variables,
        )
        body = CampaignService.render_template(
            str(config.get("body_template", "")),
            variables,
        )
        if not subject or not body:
            return ChannelDispatchResult(
                tracking_id="",
                error="Rendered email subject and body must not be empty.",
            )

        try:
            response = await send_organization_email(
                organization_id=campaign.organization_id,
                owner_kind=OutboundOwnerKind.CAMPAIGN_ATTEMPT,
                owner_id=attempt_id,
                provider_config_id=provider_config_id,
                provider_config_revision=provider_config_revision,
                to_email=contact.contact_address,
                subject=subject,
                html_body=body,
            )
        except NotConfiguredError:
            return ChannelDispatchResult(
                tracking_id="",
                error="Email provider config is not ready.",
            )
        except EmailDeliveryUnsupported:
            return ChannelDispatchResult(
                tracking_id="",
                error="Email delivery request is unsupported.",
            )
        except Exception as error:
            logger.error(
                "Campaign email delivery failed campaign=%s contact=%s category=%s",
                campaign.id,
                contact.id,
                type(error).__name__,
            )
            raise

        logger.info(
            "Campaign email delivered campaign=%s contact=%s message_id=%s",
            campaign.id,
            contact.id,
            response.tracking_id,
        )
        if response.state is OutboundAttemptState.UNKNOWN:
            return ChannelDispatchResult(
                tracking_id=response.tracking_id,
                error="Email delivery outcome is unconfirmed.",
                dispatch_unknown=True,
            )
        if response.state is not OutboundAttemptState.SUCCEEDED:
            return ChannelDispatchResult(
                tracking_id=response.tracking_id,
                error="Email provider rejected delivery.",
            )
        return ChannelDispatchResult(tracking_id=response.tracking_id)


def _provider_config_id(config: dict) -> UUID | None:
    value = config.get(_PROVIDER_CONFIG_FIELD)
    try:
        return value if isinstance(value, UUID) else UUID(str(value))
    except (TypeError, ValueError):
        return None


def _provider_config_revision(config: dict) -> int | None:
    value = config.get(_PROVIDER_CONFIG_REVISION_FIELD)
    return (
        value
        if isinstance(value, int) and not isinstance(value, bool) and value > 0
        else None
    )


_: CampaignChannelAdapter = EmailChannelAdapter()  # type: ignore[assignment]
