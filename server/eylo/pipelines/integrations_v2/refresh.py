"""Renew expiring OAuth credentials for curated vendor connections.

Token URLs and tenant behavior come from the vendor registry. Client
credentials belong to the organization installation. The connection module
stores authorization state without importing the vendor registry.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from uuid import UUID

from eylo.common.database import register_ephemeral_event_post_txn
from eylo.common.http_egress import (
    HttpDestinationPolicy,
    HttpEgressPolicyError,
    HttpEgressRequest,
    HttpRoutePolicy,
    parse_https_target,
)
from eylo.events.schema.py_events.connections import ConnectionExpiredEvent
from eylo.modules.connections.repositories import ConnectionRepository
from eylo.modules.connections.schemas.indb import ConnectionInDb, ConnectionStatus
from eylo.modules.integrations_v2.repositories import InstallationRepository
from eylo.modules.integrations_v2.schemas.indb import InstallationInDb
from eylo.sockets.http.transport import SafeHttpTransport

from .http_client import VendorTransport
from .oauth import decrypt_client_secret
from .registry import CuratedRegistry, load_vendors

logger = logging.getLogger(__name__)

REFRESH_WINDOW_MINUTES = 10
MAX_REFRESH_ATTEMPTS = 5


@dataclass(frozen=True, slots=True)
class RefreshOutcome:
    """What one refresh cycle did, for the periodic task's log line."""

    refreshed: tuple[UUID, ...]
    failed: tuple[UUID, ...]

    @property
    def considered(self) -> int:
        return len(self.refreshed) + len(self.failed)


async def refresh_expiring_curated_connections(
    *,
    registry: CuratedRegistry | None = None,
    transport: VendorTransport | None = None,
    window_minutes: int = REFRESH_WINDOW_MINUTES,
) -> RefreshOutcome:
    """Renew every curated connection expiring inside the window."""
    registry = registry or load_vendors()
    connections = ConnectionRepository()
    installations = InstallationRepository()
    threshold = datetime.now(timezone.utc) + timedelta(minutes=window_minutes)

    rows = await connections.get_expiring_connections(threshold)
    refreshed: list[UUID] = []
    failed: list[UUID] = []

    for row in rows:
        connection = ConnectionInDb.model_validate(row)
        connection_id = UUID(str(connection.id))
        try:
            renewed = await _refresh_one(
                connection=connection,
                registry=registry,
                installations=installations,
                transport=transport,
            )
        except _RefreshError as error:
            # Degrade, do not propagate: one unrenewable connection must not
            # stop the rest of the cycle. Log only the internal stable code;
            # never render the exception or a provider response.
            failure_code = error.code
            logger.warning(
                "[CuratedRefresh] connection=%s not renewed code=%s",
                connection_id,
                failure_code,
            )
            await _record_failure(
                connections,
                row,
                exhausted=error.exhausted,
                reason=failure_code,
                vendor=error.vendor,
            )
            failed.append(connection_id)
            continue

        row.credentials = renewed.credentials
        row.credentials_expires_at = renewed.expires_at
        row.last_refresh_success_at = datetime.now(timezone.utc)
        row.refresh_attempts = 0
        row.is_refresh_exhausted = False
        await connections.save_(row)
        refreshed.append(connection_id)

    return RefreshOutcome(refreshed=tuple(refreshed), failed=tuple(failed))


@dataclass(frozen=True, slots=True)
class _RenewedCredential:
    credentials: dict
    expires_at: datetime | None


class _RefreshError(Exception):
    """A coded renewal failure and whether it can ever succeed."""

    def __init__(
        self, code: str, *, exhausted: bool = False, vendor: str | None = None
    ) -> None:
        self.code = code
        self.exhausted = exhausted
        # Known once the installation is resolved; None for failures that occur
        # before that, where there is no vendor to name.
        self.vendor = vendor
        super().__init__(code)


async def _refresh_one(
    *,
    connection: ConnectionInDb,
    registry: CuratedRegistry,
    installations: InstallationRepository,
    transport: VendorTransport | None,
) -> _RenewedCredential:
    row = await installations.get(
        organization_id=UUID(str(connection.organization_id)),
        installation_id=UUID(str(connection.integration_id)),
    )
    if row is None:
        raise _RefreshError("installation_removed", exhausted=True)
    installation = InstallationInDb.model_validate(row)

    name = installation.vendor
    vendor = registry.vendor(name)
    if vendor is None or vendor.oauth is None:
        raise _RefreshError("vendor_no_longer_carried", exhausted=True, vendor=name)
    if not installation.oauth_client_id or not installation.oauth_client_secret:
        raise _RefreshError("oauth_app_missing", exhausted=True, vendor=name)

    # Selection already excludes rows without a refresh token, so there is no
    # guard here: adding one would imply a case this path can reach.
    refresh_token = str((connection.credentials or {})["refresh_token"])

    token_url = vendor.oauth.token_url.replace(
        "{tenant}", installation.oauth_tenant or ""
    )
    try:
        payload = await _post_refresh(
            token_url=token_url,
            client_id=installation.oauth_client_id,
            client_secret=decrypt_client_secret(installation.oauth_client_secret),
            refresh_token=refresh_token,
            transport=transport,
        )
    except _RefreshError as error:
        error.vendor = name
        raise

    access_token = payload.get("access_token")
    if not isinstance(access_token, str) or not access_token:
        raise _RefreshError("no_access_token_returned", vendor=name)

    credentials = dict(connection.credentials or {})
    credentials["access_token"] = access_token
    # Providers rotate refresh tokens inconsistently. Keep the previous one
    # unless a new one is issued, or the next cycle has nothing to present.
    for optional in ("refresh_token", "token_type", "scope"):
        value = payload.get(optional)
        if isinstance(value, str) and value:
            credentials[optional] = value

    expires_at = None
    if isinstance(payload.get("expires_in"), int):
        expires_at = datetime.now(timezone.utc) + timedelta(
            seconds=int(payload["expires_in"])
        )
    return _RenewedCredential(credentials=credentials, expires_at=expires_at)


async def _post_refresh(
    *,
    token_url: str,
    client_id: str,
    client_secret: str,
    refresh_token: str,
    transport: VendorTransport | None,
) -> dict:
    form = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": client_id,
        "client_secret": client_secret,
    }
    try:
        origin, path = parse_https_target(token_url)
        request = HttpEgressRequest(
            method="POST",
            url=token_url,
            policy=HttpDestinationPolicy(
                primary=HttpRoutePolicy(origin=origin, path_prefix=path),
                max_redirects=0,
            ),
            headers={
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            body=urlencode(form).encode("utf-8"),
            response_body_limit=262_144,
            total_timeout_seconds=20.0,
        )
        response = await (transport or SafeHttpTransport()).send(request)
    except (HttpEgressPolicyError, TimeoutError) as error:
        raise _RefreshError("token_endpoint_unreachable") from error

    if response.status_code == 400:
        # A refresh token the provider has revoked never becomes valid again.
        raise _RefreshError("refresh_token_rejected", exhausted=True)
    if response.status_code != 200:
        raise _RefreshError(f"token_endpoint_http_{response.status_code}")
    try:
        payload = json.loads(response.body)
    except ValueError as error:
        raise _RefreshError("token_response_unreadable") from error
    if not isinstance(payload, dict):
        raise _RefreshError("token_response_unreadable")
    return payload


async def _record_failure(
    connections: ConnectionRepository,
    row,
    *,
    exhausted: bool,
    reason: str,
    vendor: str | None,
) -> None:
    """Record one failed renewal, and announce it if the connection is finished.

    A connection that can no longer be renewed is not just a log line: the
    organization has to reauthorize, and nothing else in the system can know
    that unless it is told. Curated connections emit `ConnectionExpiredEvent`
    so the existing connection presentation path can request reauthorization.
    """
    attempts = int(row.refresh_attempts or 0) + 1
    row.refresh_attempts = attempts
    row.last_refresh_failure_at = datetime.now(timezone.utc)
    finished = exhausted or attempts >= MAX_REFRESH_ATTEMPTS
    if finished:
        row.is_refresh_exhausted = True
        row.status = ConnectionStatus.FAILED
    await connections.save_(row)

    if finished and row.organization_id:
        register_ephemeral_event_post_txn(
            ConnectionExpiredEvent(
                connection_id=UUID(str(row.id)),
                organization_id=UUID(str(row.organization_id)),
                integration_id=UUID(str(row.integration_id)),
                vendor=vendor,
                contact_id=(UUID(str(row.contact_id)) if row.contact_id else None),
                reason=f"Curated credential could not be renewed: {reason}.",
            )
        )


__all__ = [
    "MAX_REFRESH_ATTEMPTS",
    "REFRESH_WINDOW_MINUTES",
    "RefreshOutcome",
    "refresh_expiring_curated_connections",
]
