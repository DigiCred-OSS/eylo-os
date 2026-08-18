"""Channel adapter factory — resolves channel name to adapter instance."""

from eylo.products.campaigns.channels.base import CampaignChannelAdapter
from eylo.products.campaigns.constants import CampaignChannel


def get_channel_adapter(channel: str) -> CampaignChannelAdapter:
    """Return a channel adapter instance for the given channel name.

    Args:
        channel: One of "voice", "email", "widget".

    Raises:
        ValueError: If the channel is not supported.

    """
    if channel == CampaignChannel.VOICE.value:
        from eylo.products.campaigns.channels.voice import VoiceChannelAdapter

        return VoiceChannelAdapter()  # type: ignore[return-value]

    if channel == CampaignChannel.EMAIL.value:
        from eylo.products.campaigns.channels.email import EmailChannelAdapter

        return EmailChannelAdapter()  # type: ignore[return-value]

    if channel == CampaignChannel.WIDGET.value:
        from eylo.products.campaigns.channels.widget import WidgetChannelAdapter

        return WidgetChannelAdapter()  # type: ignore[return-value]

    raise ValueError(f"Unsupported campaign channel: {channel}")
