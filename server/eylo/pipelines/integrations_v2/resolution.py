"""Resolve scoped integration credentials and refresh expiring OAuth grants."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

from eylo.common.http_egress import (
    HttpEgressPolicyError,
    HttpOrigin,
    parse_https_target,
)
from eylo.modules.connections.services.indb import ConnectionService
from eylo.modules.integrations_v2.domain.enums import VendorAuthKind
from eylo.modules.integrations_v2.domain.errors import (
    CredentialUnavailableError,
    VendorNotFoundError,
)
from eylo.modules.integrations_v2.schemas.indb import ToolExecutionGrant

from .contracts import CuratedVendorSpec, VendorAccount
from .credentials import VendorWireAuth, build_vendor_wire_auth
from .registry import CuratedRegistry, load_vendors

NO_AUTH_CONNECTION_ID = "no-auth"


@dataclass(frozen=True, slots=True)
class ResolvedVendorAuth:
    """Everything needed to construct a client for one curated tool call."""

    vendor: CuratedVendorSpec
    base_url: str
    origin: HttpOrigin
    auth: VendorWireAuth
    account: VendorAccount


async def resolve_vendor_auth(
    *,
    grant: ToolExecutionGrant,
    contact_id: UUID | None = None,
    registry: CuratedRegistry | None = None,
    connections: ConnectionService | None = None,
    request_budget_seconds: float = 20.0,
) -> ResolvedVendorAuth:
    """Resolve the credential authorizing one curated tool call.

    Raises `CredentialUnavailableError` when no usable connection exists, which
    callers surface to the agent as `auth_required` rather than as a fault.
    """
    vendor = (registry or load_vendors()).vendor(grant.vendor)
    if vendor is None:
        raise VendorNotFoundError(
            "vendor_not_registered",
            f"This deployment does not carry vendor '{grant.vendor}'.",
        )
    try:
        base_url = vendor.resolve_base_url(grant.instance_url)
        origin, _path = parse_https_target(base_url)
    except (ValueError, HttpEgressPolicyError) as error:
        raise VendorNotFoundError(
            "vendor_base_url_invalid",
            f"Vendor '{grant.vendor}' has no usable base URL for this install.",
        ) from error

    if grant.auth_kind is VendorAuthKind.NO_AUTH:
        return ResolvedVendorAuth(
            vendor=vendor,
            base_url=base_url,
            origin=origin,
            auth=VendorWireAuth(),
            account=VendorAccount(connection_id=NO_AUTH_CONNECTION_ID),
        )

    service = connections or ConnectionService()
    connection = await service.get_active_connection_for_execution(
        integration_id=grant.installation_id,
        organization_id=grant.organization_id,
        contact_id=contact_id,
    )
    if connection is None:
        raise CredentialUnavailableError(
            "auth_required",
            f"No active connection authorizes '{grant.vendor}' for this caller.",
        )
    if _expires_within(connection.credentials_expires_at, request_budget_seconds):
        raise CredentialUnavailableError(
            "auth_required",
            f"The '{grant.vendor}' credential expires inside the request budget.",
        )

    auth = build_vendor_wire_auth(
        auth_kind=grant.auth_kind,
        credentials=connection.credentials,
        origin=origin,
        api_key_placement=vendor.api_key_placement,
    )
    return ResolvedVendorAuth(
        vendor=vendor,
        base_url=base_url,
        origin=origin,
        auth=auth,
        account=VendorAccount(connection_id=str(connection.id)),
    )


def _expires_within(expires_at: datetime | None, budget_seconds: float) -> bool:
    if expires_at is None:
        return False
    if expires_at.tzinfo is None or expires_at.utcoffset() is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    deadline = datetime.now(timezone.utc) + timedelta(seconds=budget_seconds)
    return expires_at <= deadline


__all__ = [
    "NO_AUTH_CONNECTION_ID",
    "ResolvedVendorAuth",
    "resolve_vendor_auth",
]
