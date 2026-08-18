"""Turnix STUN/TURN credential adapter."""

from __future__ import annotations

import asyncio
import logging

import httpx
from aiortc import RTCIceServer

from eylo.sockets.stun_turn.config import TurnixConfig
from eylo.sockets.stun_turn.exceptions import StunTurnCredentialsFailed
from eylo.sockets.stun_turn.parsing import parse_ice_servers

logger = logging.getLogger(__name__)

_CREDENTIAL_ENDPOINT = "https://turnix.io/api/v1/credentials/ice"


class TurnixStunTurn:
    """Fetch ephemeral ICE credentials from the fixed Turnix endpoint."""

    def __init__(self, config: TurnixConfig) -> None:
        self.config = config

    async def get_ice_servers(self) -> list[RTCIceServer]:
        timeout = httpx.Timeout(self.config.timeout)
        total_attempts = self.config.max_retries + 1
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }
        if self.config.client_ip:
            headers["X-TURN-CLIENT-IP"] = self.config.client_ip
        body = _credential_request(self.config)

        for attempt in range(total_attempts):
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.post(
                        _CREDENTIAL_ENDPOINT,
                        headers=headers,
                        json=body,
                    )
                    response.raise_for_status()
                    return parse_ice_servers(response.json())
            except Exception as error:
                _log_failure(
                    attempt=attempt + 1,
                    total_attempts=total_attempts,
                    error=error,
                )
                if attempt < total_attempts - 1:
                    await asyncio.sleep(self.config.retry_delay * (attempt + 1))

        raise StunTurnCredentialsFailed("TURN credential fetch failed.") from None


def _credential_request(config: TurnixConfig) -> dict[str, str | int]:
    fields = (
        "initiator_client",
        "receiver_client",
        "room",
        "ttl",
        "preferred_region",
        "fixed_region",
    )
    return {
        field_name: value
        for field_name in fields
        if (value := getattr(config, field_name)) is not None
    }


def _log_failure(
    *,
    attempt: int,
    total_attempts: int,
    error: Exception,
) -> None:
    status_code = (
        error.response.status_code if isinstance(error, httpx.HTTPStatusError) else None
    )
    logger.warning(
        "TURN credential fetch failed provider=turnix attempt=%d total=%d category=%s status=%s",
        attempt,
        total_attempts,
        type(error).__name__,
        status_code,
    )
