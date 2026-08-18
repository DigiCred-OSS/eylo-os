"""Construct the STUN/TURN adapter selected by an explicit typed config."""

from __future__ import annotations

from aiortc import RTCIceServer

from eylo.sockets.stun_turn.config import MeteredConfig, StunTurnConfig, TurnixConfig
from eylo.sockets.stun_turn.metered import MeteredStunTurn
from eylo.sockets.stun_turn.turnix import TurnixStunTurn

StunTurnService = MeteredStunTurn | TurnixStunTurn


class StunTurnFactory:
    """Own one provider adapter and its credentials for one config use."""

    def __init__(self, config: StunTurnConfig) -> None:
        self._service = _build_service(config)

    @property
    def service(self) -> StunTurnService:
        return self._service

    async def get_ice_servers(self) -> list[RTCIceServer]:
        return await self._service.get_ice_servers()


def _build_service(config: StunTurnConfig) -> StunTurnService:
    if isinstance(config, MeteredConfig):
        return MeteredStunTurn(config)
    if isinstance(config, TurnixConfig):
        return TurnixStunTurn(config)
    raise TypeError(f"Unsupported STUN/TURN config type: {type(config).__name__}")
