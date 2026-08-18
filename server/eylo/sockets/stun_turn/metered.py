"""Metered STUN/TURN credential adapter."""

from __future__ import annotations

import asyncio
import logging

import httpx
from aiortc import RTCIceServer

from eylo.sockets.stun_turn.config import MeteredConfig
from eylo.sockets.stun_turn.exceptions import StunTurnCredentialsFailed
from eylo.sockets.stun_turn.parsing import parse_ice_servers

logger = logging.getLogger(__name__)


class MeteredStunTurn:
    """Fetch ephemeral ICE credentials from one fixed Metered app endpoint."""

    def __init__(self, config: MeteredConfig) -> None:
        self.config = config

    async def get_ice_servers(self) -> list[RTCIceServer]:
        url = f"https://{self.config.app_name}.metered.live/api/v1/turn/credentials"
        timeout = httpx.Timeout(self.config.timeout)
        total_attempts = self.config.max_retries + 1

        for attempt in range(total_attempts):
            try:
                # Metered serves underscore app hosts with a certificate that
                # Python rejects. Keep this TLS exception local to Metered.
                async with httpx.AsyncClient(
                    timeout=timeout,
                    verify=False,
                ) as client:
                    response = await client.get(
                        url,
                        params={"apiKey": self.config.api_key},
                    )
                    response.raise_for_status()
                    return parse_ice_servers(response.json())
            except Exception as error:
                _log_failure(
                    provider="metered",
                    attempt=attempt + 1,
                    total_attempts=total_attempts,
                    error=error,
                )
                if attempt < total_attempts - 1:
                    await asyncio.sleep(self.config.retry_delay * (attempt + 1))

        raise StunTurnCredentialsFailed("TURN credential fetch failed.") from None


def _log_failure(
    *,
    provider: str,
    attempt: int,
    total_attempts: int,
    error: Exception,
) -> None:
    status_code = (
        error.response.status_code if isinstance(error, httpx.HTTPStatusError) else None
    )
    logger.warning(
        "TURN credential fetch failed provider=%s attempt=%d total=%d category=%s status=%s",
        provider,
        attempt,
        total_attempts,
        type(error).__name__,
        status_code,
    )
