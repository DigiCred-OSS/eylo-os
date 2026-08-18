"""Channel adapter protocol and dispatch result model."""

from typing import Optional, Protocol
from uuid import UUID

from pydantic import BaseModel

from eylo.products.campaigns.schemas.indb import CampaignContactInDb, CampaignInDb


class ChannelDispatchResult(BaseModel):
    """Result of dispatching outreach to a single contact."""

    tracking_id: str
    error: Optional[str] = None
    dispatch_unknown: bool = False


class CampaignChannelAdapter(Protocol):
    """Protocol that every campaign channel must implement.

    Adapters are responsible for:
    - Validating campaign-level configuration for their channel
    - Validating individual contacts (correct address format)
    - Dispatching the actual outreach (call, email, chat message)
    """

    channel: str
    replay_safe: bool

    async def validate_campaign(self, campaign: CampaignInDb) -> list[str]:
        """Return a list of validation error messages. Empty list = valid."""
        ...

    async def validate_contact(self, contact: CampaignContactInDb) -> bool:
        """Return True if the contact has a valid address for this channel."""
        ...

    async def dispatch(
        self,
        campaign: CampaignInDb,
        contact: CampaignContactInDb,
        rendered_message: Optional[str],
        attempt_id: UUID,
    ) -> ChannelDispatchResult:
        """Send the outreach. Returns a tracking ID for status tracking."""
        ...

    async def recover_dispatch(
        self,
        campaign: CampaignInDb,
        contact: CampaignContactInDb,
        attempt_id: UUID,
    ) -> ChannelDispatchResult | None:
        """Return a durable provider receipt after a worker restart, if any."""
        ...
