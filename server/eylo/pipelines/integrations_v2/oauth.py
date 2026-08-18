"""OAuth authorization for curated vendor installations.

The vendor registry owns endpoints, scopes, delimiters, extra
authorization parameters, and whether PKCE is required, so all of that comes
from the registry. The organization supplies only what is genuinely its own —
a client id, a client secret, and a tenant where the provider is per-tenant.

This keeps provider-owned protocol details out of organization configuration.
"""

from __future__ import annotations

import base64
import hashlib
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from uuid import UUID

from eylo.common.database import start_transaction
from eylo.common.http_egress import (
    HttpDestinationPolicy,
    HttpEgressPolicyError,
    HttpEgressRequest,
    HttpRoutePolicy,
    parse_https_target,
)
from eylo.events.py_events.emitter import emit_ephemeral
from eylo.events.schema.py_events.connections import (
    ConnectionFailedEvent,
    ConnectionSuccessEvent,
)
from eylo.modules.connections.repositories.oauth_state import OAuthStateRepository
from eylo.modules.connections.schemas.indb import (
    ConnectionCreateSchema,
    ConnectionKind,
    ConnectionStatus,
)
from eylo.modules.connections.schemas.oauth import OAuthStateCreateSchema
from eylo.modules.connections.services.indb import ConnectionService
from eylo.modules.integrations_v2.constants import OAUTH_CALLBACK_PATH
from eylo.modules.integrations_v2.domain.errors import (
    IntegrationsV2Error,
    VendorNotFoundError,
)
from eylo.modules.integrations_v2.repositories import InstallationRepository
from eylo.modules.integrations_v2.schemas.indb import InstallationInDb
from eylo.modules.provider_configs.crypto import get_secret_cipher
from eylo.sockets.http.transport import SafeHttpTransport

from .contracts import CuratedVendorSpec
from .http_client import VendorTransport
from .registry import CuratedRegistry, load_vendors

STATE_TTL_MINUTES = 10
_SECRET_LABEL = "curated_oauth_client_secret"


def default_callback_url() -> str:
    """The one redirect URI every curated vendor's OAuth app registers."""
    from eylo.common.config import settings

    if settings.OAUTH_CALLBACK_URL:
        return settings.OAUTH_CALLBACK_URL
    return f"{settings.API_BASE_URL.rstrip('/')}{OAUTH_CALLBACK_PATH}"


class CuratedOAuthError(IntegrationsV2Error):
    """The authorization flow cannot proceed for this installation."""


@dataclass(frozen=True, slots=True)
class AuthorizationRedirect:
    """Where to send the user, and the state that will identify their return."""

    authorization_url: str
    redirect_uri: str
    state: str


def encrypt_client_secret(secret: str) -> str:
    return get_secret_cipher().encrypt_field(secret, context_label=_SECRET_LABEL)


def decrypt_client_secret(envelope: str) -> str:
    return get_secret_cipher().decrypt_field(envelope, context_label=_SECRET_LABEL)


async def begin_authorization(
    *,
    installation: InstallationInDb,
    vendor: CuratedVendorSpec,
    contact_id: UUID | None = None,
    states: OAuthStateRepository | None = None,
) -> AuthorizationRedirect:
    """Build the provider consent URL for one installation."""
    oauth = _require_oauth(vendor, installation)
    redirect_uri = default_callback_url()
    state_token = secrets.token_urlsafe(32)
    verifier, challenge = _pkce_pair() if oauth.pkce else (None, None)

    await (states or OAuthStateRepository()).create_state(
        OAuthStateCreateSchema(
            state=state_token,
            organization_id=installation.organization_id,
            integration_id=installation.id,
            contact_id=contact_id,
            redirect_uri=redirect_uri,
            code_verifier=verifier,
            expires_at=datetime.now(timezone.utc)
            + timedelta(minutes=STATE_TTL_MINUTES),
        )
    )

    params: dict[str, str] = {
        "client_id": installation.oauth_client_id or "",
        "redirect_uri": redirect_uri,
        "state": state_token,
        "response_type": "code",
    }
    # A vendor with no scope model — Notion grants capabilities at consent
    # instead — must not be sent an empty `scope`, which some providers reject.
    if oauth.scopes:
        params["scope"] = oauth.scope_delimiter.join(oauth.scopes)
    if challenge is not None:
        params["code_challenge"] = challenge
        params["code_challenge_method"] = "S256"
    for key, value in oauth.authorization_params:
        params.setdefault(key, value)

    return AuthorizationRedirect(
        authorization_url=(
            f"{_tenanted(oauth.authorization_url, installation)}?{urlencode(params)}"
        ),
        redirect_uri=redirect_uri,
        state=state_token,
    )


async def complete_authorization(
    *,
    code: str,
    state: str,
    installation: InstallationInDb,
    vendor: CuratedVendorSpec,
    states: OAuthStateRepository | None = None,
    connections: ConnectionService | None = None,
    transport: VendorTransport | None = None,
) -> UUID:
    """Exchange the authorization code and store the resulting connection.

    The state row is consumed in its own committed transaction *before* the
    exchange is attempted. Doing it in the same transaction looked correct and
    was not: any later failure rolled the deletion back, leaving the state alive
    and the authorization code replayable. A one-time token has to be spent the
    moment it is presented, whatever happens next.
    """
    async with start_transaction():
        consumed = states or OAuthStateRepository()
        stored = await consumed.consume_by_state(state)
        if stored is None or stored.integration_id != installation.id:
            raise CuratedOAuthError(
                "oauth_state_invalid", "Authorization state is unknown."
            )
        expired = stored.is_expired()
        redirect_uri = stored.redirect_uri or default_callback_url()
        code_verifier = stored.code_verifier
        contact_id = stored.contact_id

    if expired:
        raise CuratedOAuthError(
            "oauth_state_expired", "Authorization state has expired."
        )

    oauth = _require_oauth(vendor, installation)
    tokens = await _exchange(
        code=code,
        token_url=_tenanted(oauth.token_url, installation),
        installation=installation,
        redirect_uri=redirect_uri,
        code_verifier=code_verifier,
        transport=transport,
    )

    access_token = tokens.get("access_token")
    if not isinstance(access_token, str) or not access_token:
        raise CuratedOAuthError(
            "oauth_token_invalid", "The provider returned no access token."
        )
    credentials: dict[str, object] = {"access_token": access_token}
    for optional in ("refresh_token", "token_type", "scope"):
        if isinstance(tokens.get(optional), str):
            credentials[optional] = tokens[optional]

    expires_at = None
    if isinstance(tokens.get("expires_in"), int):
        expires_at = datetime.now(timezone.utc) + timedelta(
            seconds=int(tokens["expires_in"])
        )

    async with start_transaction():
        connection = await (connections or ConnectionService()).create_(
            ConnectionCreateSchema(
                organization_id=installation.organization_id,
                integration_id=installation.id,
                contact_id=contact_id,
                connection_kind=(
                    ConnectionKind.CONTACT
                    if contact_id is not None
                    else ConnectionKind.ORGANIZATION
                ),
                status=ConnectionStatus.ACTIVE,
                credentials=credentials,
                credentials_expires_at=expires_at,
            )
        )
        return UUID(str(connection.id))


async def complete_authorization_from_state(
    *,
    code: str,
    state: str,
    registry: CuratedRegistry | None = None,
    states: OAuthStateRepository | None = None,
) -> tuple[UUID, str]:
    """Complete an authorization knowing only the code and the state.

    This is the entry point a provider redirect can actually reach. The end
    user arriving here is a contact authorizing access on their own behalf —
    they have no session in the operator console and no organization in the
    URL — so the state row is the only thing that identifies the flow, which is
    exactly the property OAuth state is for.

    Returns the new connection id and the vendor it authorizes.
    """
    repository = states or OAuthStateRepository()
    async with start_transaction():
        stored = await repository.get_by_state(state)
        if stored is None:
            raise CuratedOAuthError(
                "oauth_state_invalid", "Authorization state is unknown."
            )
        installation_row = await InstallationRepository().get(
            organization_id=UUID(str(stored.organization_id)),
            installation_id=UUID(str(stored.integration_id)),
        )
        if installation_row is None:
            # Consume the state: it can never complete, and leaving it alive
            # only keeps an authorization code replayable.
            await repository.consume_by_state(state)
            raise CuratedOAuthError(
                "installation_removed",
                "The vendor installation this authorization belongs to is gone.",
            )
        installation = InstallationInDb.model_validate(installation_row)
        contact_id = UUID(str(stored.contact_id)) if stored.contact_id else None
        organization_id = UUID(str(stored.organization_id))

    vendor = (registry or load_vendors()).vendor(installation.vendor)
    if vendor is None:
        async with start_transaction():
            await repository.consume_by_state(state)
        raise VendorNotFoundError(
            "vendor_not_registered",
            f"This deployment no longer carries '{installation.vendor}'.",
        )

    # Notify the widget and the end user's conversation about the outcome.
    try:
        connection_id = await complete_authorization(
            code=code,
            state=state,
            installation=installation,
            vendor=vendor,
            states=repository,
        )
    except IntegrationsV2Error as failure:
        if contact_id is not None:
            emit_ephemeral(
                ConnectionFailedEvent(
                    contact_id=contact_id,
                    organization_id=organization_id,
                    integration_name=vendor.display_name,
                    error=str(failure),
                    integration_id=installation.id,
                    vendor=installation.vendor,
                )
            )
        raise
    if contact_id is not None:
        emit_ephemeral(
            ConnectionSuccessEvent(
                connection_id=connection_id,
                contact_id=contact_id,
                organization_id=organization_id,
                integration_name=vendor.display_name,
                integration_id=installation.id,
                vendor=installation.vendor,
            )
        )
    return connection_id, installation.vendor


async def _exchange(
    *,
    code: str,
    token_url: str,
    installation: InstallationInDb,
    redirect_uri: str,
    code_verifier: str | None,
    transport: VendorTransport | None,
) -> dict[str, object]:
    import json

    if not installation.oauth_client_id or not installation.oauth_client_secret:
        raise CuratedOAuthError(
            "oauth_app_missing",
            "This installation has no OAuth client credentials configured.",
        )
    form: dict[str, str] = {
        "grant_type": "authorization_code",
        "code": code,
        "client_id": installation.oauth_client_id,
        "client_secret": decrypt_client_secret(installation.oauth_client_secret),
        "redirect_uri": redirect_uri,
    }
    if code_verifier:
        form["code_verifier"] = code_verifier

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
        raise CuratedOAuthError(
            "oauth_endpoint_unreachable",
            "The provider token endpoint could not be reached safely.",
        ) from error

    if response.status_code != 200:
        raise CuratedOAuthError(
            "oauth_exchange_rejected",
            "The provider rejected the authorization code exchange.",
        )
    try:
        payload = json.loads(response.body)
    except ValueError as error:
        raise CuratedOAuthError(
            "oauth_token_invalid", "The provider returned an unreadable token response."
        ) from error
    if not isinstance(payload, dict):
        raise CuratedOAuthError(
            "oauth_token_invalid", "The provider returned an unreadable token response."
        )
    return payload


def _require_oauth(vendor: CuratedVendorSpec, installation: InstallationInDb):
    if vendor.oauth is None:
        raise VendorNotFoundError(
            "vendor_oauth_unsupported",
            f"Vendor '{vendor.vendor}' does not support OAuth.",
        )
    if not installation.oauth_client_id or not installation.oauth_client_secret:
        raise CuratedOAuthError(
            "oauth_app_missing",
            "This installation has no OAuth client credentials configured.",
        )
    return vendor.oauth


def _tenanted(url: str, installation: InstallationInDb) -> str:
    if "{tenant}" not in url:
        return url
    tenant = installation.oauth_tenant
    if not isinstance(tenant, str) or not _TENANT.fullmatch(tenant.strip()):
        raise CuratedOAuthError(
            "oauth_tenant_invalid",
            "This vendor requires a valid OAuth tenant.",
        )
    return url.replace("{tenant}", tenant.strip())


_TENANT = re.compile(r"^[A-Za-z0-9._-]{1,128}$")


def _pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)[:128]
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return verifier, challenge


__all__ = [
    "AuthorizationRedirect",
    "complete_authorization_from_state",
    "default_callback_url",
    "CuratedOAuthError",
    "STATE_TTL_MINUTES",
    "begin_authorization",
    "complete_authorization",
    "decrypt_client_secret",
    "encrypt_client_secret",
]
