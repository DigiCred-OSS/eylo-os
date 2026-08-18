"""Factory for creating telephony service instances.

This module provides a factory pattern for initializing telephony services
from different providers (Twilio, Plivo, Exotel, etc.), following the same
pattern as STT and TTS factories.
"""

import importlib
import logging
from collections.abc import Mapping
from typing import Any, Dict, Literal, Optional

from eylo.sockets.telephony.base import (
    BaseTelephonyService,
    TelephonyConfig,
    TelephonyProvider,
)

logger = logging.getLogger(__name__)

PROVIDER_MAP: dict[str, tuple[TelephonyProvider, str]] = {
    "twilio": (
        TelephonyProvider.TWILIO,
        "eylo.sockets.telephony.twilio.service.TwilioService",
    ),
    "plivo": (
        TelephonyProvider.PLIVO,
        "eylo.sockets.telephony.plivo.service.PlivoService",
    ),
    "vonage": (
        TelephonyProvider.VONAGE,
        "eylo.sockets.telephony.vonage.service.VonageService",
    ),
    "exotel": (
        TelephonyProvider.EXOTEL,
        "eylo.sockets.telephony.exotel.service.ExotelService",
    ),
}

_REQUIRED_CONFIG_FIELDS = {
    "twilio": frozenset({"webhook_base_url", "account_sid", "auth_token"}),
    "plivo": frozenset({"webhook_base_url", "auth_id", "auth_token"}),
    "vonage": frozenset(
        {
            "webhook_base_url",
            "application_id",
            "api_key",
            "api_secret",
            "private_key",
            "signature_secret",
        }
    ),
    "exotel": frozenset(
        {
            "webhook_base_url",
            "application_id",
            "api_host",
            "api_key",
            "api_token",
            "account_sid",
            "exotel_app_id",
            "subdomain",
        }
    ),
}


class TelephonyFactory:
    """Factory for creating telephony service instances.

    Currently supports:
    - Twilio
    - Plivo
    - Vonage
    - Exotel (stub)
    """

    def __init__(
        self,
        provider: Literal["twilio", "plivo", "vonage", "exotel"],
        telephony_config: Mapping[str, object],
    ):
        """Initialize the telephony factory.

        Args:
            provider: Telephony provider name
            telephony_config: Configuration for the telephony service

        """
        self._provider = provider
        self._telephony_config = _validated_config(provider, telephony_config)
        self._telephony_service: Optional[BaseTelephonyService] = None

    def create_telephony_service(self) -> BaseTelephonyService:
        """Create a telephony service instance based on the provider.

        Returns:
            Initialized telephony service

        Raises:
            ValueError: If the provider is not supported

        """
        provider_entry = PROVIDER_MAP.get(self._provider)
        if not provider_entry:
            raise ValueError(f"Unsupported telephony provider: {self._provider}")
        provider, import_path = provider_entry
        module_path, class_name = import_path.rsplit(".", 1)
        module = importlib.import_module(module_path)
        service_cls = getattr(module, class_name)
        config = TelephonyConfig(
            provider=provider,
            extra_config=self._telephony_config,
        )
        return service_cls(config=config)

    def initialize_service(self) -> BaseTelephonyService:
        """Initialize the telephony service.

        Returns:
            Initialized telephony service

        """
        if not self._telephony_service:
            self._telephony_service = self.create_telephony_service()
        return self._telephony_service

    @property
    def service(self) -> BaseTelephonyService:
        """Get the current telephony service, initializing if needed.

        Returns:
            Telephony service instance

        """
        if self._telephony_service:
            return self._telephony_service
        return self.initialize_service()

    @property
    def provider(self) -> str:
        """Get the provider name.

        Returns:
            Provider name

        """
        return self._provider

    def get_config(self) -> Dict[str, Any]:
        """Return a copy of the provider-specific base configuration."""
        return self.service.get_config()

    async def disconnect(self):
        """Disconnect the telephony service."""
        if self._telephony_service:
            await self._telephony_service.disconnect()
            self._telephony_service = None


def _validated_config(
    provider: str,
    values: Mapping[str, object],
) -> dict[str, object]:
    expected = _REQUIRED_CONFIG_FIELDS.get(provider)
    if expected is None:
        raise ValueError(f"Unsupported telephony provider: {provider}")
    missing = sorted(
        name
        for name in expected
        if not isinstance(values.get(name), str) or not str(values[name]).strip()
    )
    if missing:
        raise ValueError(
            f"Telephony config for {provider} is missing required fields: {missing}"
        )
    return dict(values)
