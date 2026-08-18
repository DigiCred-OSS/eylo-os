"""Typed configuration for the supported STUN/TURN providers."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class _StunTurnConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    api_key: str = Field(min_length=1, repr=False)
    timeout: float = Field(default=5.0, gt=0, le=30)
    max_retries: int = Field(default=2, ge=0, le=5)
    retry_delay: float = Field(default=0.2, ge=0, le=10)


class MeteredConfig(_StunTurnConfig):
    """Metered app identity and bounded request controls."""

    app_name: str = Field(
        min_length=1,
        max_length=63,
        pattern=r"^[a-z0-9](?:[a-z0-9_-]{0,61}[a-z0-9])?$",
    )


class TurnixConfig(_StunTurnConfig):
    """Turnix request context and bounded request controls."""

    initiator_client: str | None = Field(default=None, min_length=1, max_length=255)
    receiver_client: str | None = Field(default=None, min_length=1, max_length=255)
    room: str | None = Field(default=None, min_length=1, max_length=255)
    ttl: int | None = Field(default=None, gt=0, le=86_400)
    preferred_region: str | None = Field(default=None, min_length=1, max_length=64)
    fixed_region: str | None = Field(default=None, min_length=1, max_length=64)
    client_ip: str | None = Field(default=None, min_length=1, max_length=45)


StunTurnConfig = MeteredConfig | TurnixConfig
