"""Typed encrypted configuration for one MCP Streamable HTTP server."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from eylo.common.http_egress import (
    HttpEgressPolicyError,
    HttpOrigin,
    OriginBoundHeaders,
    parse_https_target,
)
from eylo.modules.provider_configs.crypto import (
    EncryptionContext,
    SecretCipher,
    get_secret_cipher,
)
from eylo.modules.provider_configs.masking import apply_secret_patch
from eylo.modules.tools.schemas.executors.mcp import MCP_PROTOCOL_VERSION

MCP_SERVER_CONFIG_KEY = "mcp_server"
MCP_TRANSPORT_PROFILE = "streamable_http"
_RESERVED_PROTOCOL_HEADERS = frozenset(
    {
        "accept",
        "content-type",
        "last-event-id",
        "mcp-protocol-version",
        "mcp-session-id",
    }
)


class MCPServerStorageConfig(BaseModel):
    """Public endpoint metadata plus one authenticated secret envelope."""

    transport: Literal["streamable_http"] = MCP_TRANSPORT_PROFILE
    protocol_version: Literal["2025-06-18"] = MCP_PROTOCOL_VERSION
    url: str = Field(min_length=1, max_length=2048)
    header_names: tuple[str, ...] = Field(max_length=32)
    encrypted_headers: str = Field(min_length=1)

    model_config = ConfigDict(extra="forbid", frozen=True)

    def to_storage(self) -> dict[str, Any]:
        return {MCP_SERVER_CONFIG_KEY: self.model_dump(mode="json")}


@dataclass(frozen=True, slots=True)
class ResolvedMCPServerConfig:
    """Execution-only MCP endpoint and exact-origin secret headers."""

    url: str
    origin: HttpOrigin
    origin_headers: OriginBoundHeaders = field(repr=False)
    protocol_version: str = MCP_PROTOCOL_VERSION


def create_mcp_server_config(
    *,
    organization_id: UUID,
    server_id: UUID,
    revision: int,
    url: str,
    headers: Mapping[str, str | None],
    stored_headers: Mapping[str, str] | None = None,
    cipher: SecretCipher | None = None,
) -> MCPServerStorageConfig:
    """Validate, patch, and encrypt one draft revision without plaintext storage."""
    canonical_url, origin = _canonical_endpoint(url)
    patched = apply_secret_patch(stored_headers or {}, headers)
    bound = _validated_headers(origin, patched)
    encrypted = (cipher or get_secret_cipher()).encrypt(
        bound.values,
        _context(organization_id, server_id, revision),
    )
    return MCPServerStorageConfig(
        url=canonical_url,
        header_names=tuple(sorted(bound.values, key=str.lower)),
        encrypted_headers=encrypted,
    )


def parse_mcp_server_config(config: object) -> MCPServerStorageConfig:
    if not isinstance(config, Mapping) or set(config) != {MCP_SERVER_CONFIG_KEY}:
        raise ValueError("MCP server config is invalid.")
    try:
        parsed = MCPServerStorageConfig.model_validate(config[MCP_SERVER_CONFIG_KEY])
    except ValidationError:
        raise ValueError("MCP server config is invalid.") from None
    canonical_url, _origin = _canonical_endpoint(parsed.url)
    if canonical_url != parsed.url:
        raise ValueError("MCP server URL is not canonical.")
    if tuple(sorted(set(parsed.header_names), key=str.lower)) != parsed.header_names:
        raise ValueError("MCP server header names are invalid.")
    return parsed


def resolve_mcp_server_config(
    config: object,
    *,
    organization_id: UUID,
    server_id: UUID,
    revision: int,
    cipher: SecretCipher | None = None,
) -> ResolvedMCPServerConfig:
    stored = parse_mcp_server_config(config)
    headers = (cipher or get_secret_cipher()).decrypt(
        stored.encrypted_headers,
        _context(organization_id, server_id, revision),
    )
    canonical_url, origin = _canonical_endpoint(stored.url)
    bound = _validated_headers(origin, headers)
    if tuple(sorted(bound.values, key=str.lower)) != stored.header_names:
        raise ValueError("MCP server secret metadata does not match its envelope.")
    return ResolvedMCPServerConfig(
        url=canonical_url,
        origin=origin,
        origin_headers=bound,
    )


def _canonical_endpoint(value: object) -> tuple[str, HttpOrigin]:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("MCP server URL is required.")
    raw = value.strip()
    parts = urlsplit(raw)
    if parts.query:
        raise ValueError("MCP server URL query parameters are unsupported.")
    try:
        origin, path = parse_https_target(raw)
    except HttpEgressPolicyError as error:
        raise ValueError(str(error)) from None
    return f"{origin}{path}", origin


def _validated_headers(
    origin: HttpOrigin,
    headers: Mapping[str, object],
) -> OriginBoundHeaders:
    normalized_names = [str(name).lower() for name in headers]
    if len(set(normalized_names)) != len(normalized_names):
        raise ValueError("MCP authentication header names must be unique.")
    if any(name in _RESERVED_PROTOCOL_HEADERS for name in normalized_names):
        raise ValueError("MCP authentication cannot override protocol headers.")
    if not all(isinstance(value, str) for value in headers.values()):
        raise ValueError("MCP header secrets must be strings.")
    try:
        return OriginBoundHeaders(
            origin=origin,
            values={str(name): value for name, value in headers.items()},
        )
    except HttpEgressPolicyError as error:
        raise ValueError(str(error)) from None


def _context(
    organization_id: UUID,
    server_id: UUID,
    revision: int,
) -> EncryptionContext:
    return EncryptionContext(
        organization_id=organization_id,
        config_id=server_id,
        capability="mcp",
        revision=revision,
    )


__all__ = [
    "MCP_SERVER_CONFIG_KEY",
    "MCP_TRANSPORT_PROFILE",
    "MCPServerStorageConfig",
    "ResolvedMCPServerConfig",
    "create_mcp_server_config",
    "parse_mcp_server_config",
    "resolve_mcp_server_config",
]
