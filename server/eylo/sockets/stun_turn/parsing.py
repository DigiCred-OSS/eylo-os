"""Strict conversion of provider credential payloads into aiortc values."""

from __future__ import annotations

from collections.abc import Mapping

from aiortc import RTCIceServer

from eylo.sockets.stun_turn.exceptions import StunTurnCredentialsFailed


def parse_ice_servers(payload: object) -> list[RTCIceServer]:
    """Accept provider list/envelope shapes and require at least one TURN URL."""
    raw_servers = payload.get("iceServers") if isinstance(payload, Mapping) else payload
    if not isinstance(raw_servers, list) or not raw_servers:
        raise _invalid_credentials()

    ice_servers: list[RTCIceServer] = []
    has_turn_server = False
    for raw_server in raw_servers:
        if not isinstance(raw_server, Mapping):
            raise _invalid_credentials()
        urls = _parse_urls(raw_server.get("urls"))
        has_turn_server = has_turn_server or any(
            url.startswith(("turn:", "turns:")) for url in urls
        )
        username = raw_server.get("username")
        credential = raw_server.get("credential")
        if username is not None and not isinstance(username, str):
            raise _invalid_credentials()
        if credential is not None and not isinstance(credential, str):
            raise _invalid_credentials()
        ice_servers.append(
            RTCIceServer(
                urls=urls,
                username=username,
                credential=credential,
            )
        )

    if not has_turn_server:
        raise _invalid_credentials()
    return ice_servers


def _parse_urls(value: object) -> list[str]:
    urls = [value] if isinstance(value, str) else value
    if not isinstance(urls, list) or not urls:
        raise _invalid_credentials()
    if not all(
        isinstance(url, str) and url.startswith(("stun:", "stuns:", "turn:", "turns:"))
        for url in urls
    ):
        raise _invalid_credentials()
    return urls


def _invalid_credentials() -> StunTurnCredentialsFailed:
    return StunTurnCredentialsFailed("TURN provider returned invalid credentials.")
