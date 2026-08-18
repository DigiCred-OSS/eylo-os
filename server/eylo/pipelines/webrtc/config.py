"""Compose validated platform WebRTC values into socket adapter configs."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from aiortc import RTCIceServer
from pydantic import ValidationError

from eylo.common.database import start_transaction
from eylo.modules.provider_configs.constants import Capability
from eylo.modules.provider_configs.errors import NotConfiguredError
from eylo.modules.webrtc_configs.catalog import WebRTCProviders
from eylo.modules.webrtc_configs.domain import (
    InvalidWebRTCConfig,
    WebRTCProviderConfig,
)
from eylo.modules.webrtc_configs.wiring import build_webrtc_config_resolver
from eylo.pipelines.websocket.schemas import WSSessionState
from eylo.sockets.stun_turn.config import MeteredConfig, StunTurnConfig, TurnixConfig
from eylo.sockets.stun_turn.factory import StunTurnFactory


@dataclass(frozen=True)
class ResolvedIceConfiguration:
    """Exact provider result plus any provider-declared credential expiry."""

    ice_servers: tuple[RTCIceServer, ...]
    credential_expires_at: float | None


def build_stun_turn_config(config: WebRTCProviderConfig) -> StunTurnConfig:
    values = {**config.config, "api_key": config.secret}
    try:
        if config.provider is WebRTCProviders.METERED:
            return MeteredConfig.model_validate(values)
        if config.provider is WebRTCProviders.TURNIX:
            return TurnixConfig.model_validate(values)
    except ValidationError:
        raise InvalidWebRTCConfig(
            f"Invalid runtime config for {config.provider.value}."
        ) from None
    raise InvalidWebRTCConfig(f"Unsupported WebRTC provider: {config.provider}")


async def resolve_ice_configuration(
    session_state: WSSessionState,
) -> ResolvedIceConfiguration:
    """Resolve the exact published org config once, before either peer is built."""
    config_id = session_state.webrtc_provider_config_id
    config_revision = session_state.webrtc_provider_config_revision
    if config_id is None or config_revision is None:
        raise NotConfiguredError(
            capability=Capability.WEBRTC,
            missing=["provider_config", "provider_config_revision"],
            configure_via="/api/webrtc-configs",
        )

    async with start_transaction(ro=True):
        resolved = await build_webrtc_config_resolver().resolve_pinned(
            session_state.organization_id,
            provider_config_id=config_id,
            revision=config_revision,
        )
    provider_config = WebRTCProviderConfig.validate(
        provider=resolved.provider.value,
        config=resolved.config,
        secrets=resolved.secrets,
    )
    adapter_config = build_stun_turn_config(provider_config)
    credential_expires_at = (
        time.time() + adapter_config.ttl
        if isinstance(adapter_config, TurnixConfig) and adapter_config.ttl is not None
        else None
    )
    return ResolvedIceConfiguration(
        ice_servers=tuple(await StunTurnFactory(adapter_config).get_ice_servers()),
        credential_expires_at=credential_expires_at,
    )


def browser_ice_servers(ice_servers: tuple[RTCIceServer, ...]) -> list[dict[str, Any]]:
    """Serialize resolved ICE values for browser construction without logging them."""
    return [
        {
            "urls": server.urls,
            **({"username": server.username} if server.username else {}),
            **({"credential": server.credential} if server.credential else {}),
        }
        for server in ice_servers
    ]
