"""Origin-bound vendor transport for one curated tool invocation.

This is where a curated tool's `ctx.read(...)` becomes a real request. The path
a tool supplies is joined onto the vendor's declared base URL and the result is
pinned by `HttpDestinationPolicy` to that one origin and path subtree, so a tool
that computes a path from vendor content still cannot reach another host.

Reads send directly. Mutations run inside `execute_outbound_attempt`, which owns
the committed `TOOL_USE` effect, the idempotency key, and the retry decision —
there is deliberately no second retry path here.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode
from uuid import UUID

from eylo.common.http_egress import (
    DEFAULT_RESPONSE_BODY_BYTES,
    HttpDestinationPolicy,
    HttpEgressPolicyError,
    HttpEgressRequest,
    HttpEgressResponse,
    HttpOrigin,
    HttpRoutePolicy,
    parse_https_target,
)
from eylo.common.outbound import (
    OutboundAttemptIdentity,
    OutboundAttemptSpec,
    OutboundOwnerKind,
    OutboundSendAuthorization,
    OutboundSendOutcome,
    OutboundSendRetryable,
    OutboundSendSucceeded,
    OutboundSendTerminal,
    OutboundSendUnknown,
    OutboundTransportKind,
)
from eylo.pipelines.outbound.durable_execution import (
    DurableStepContext,
    execute_outbound_attempt,
)
from eylo.sockets.http.transport import SafeHttpTransport

from .contracts import RESERVED_HEADER_NAMES, VendorResponse, VendorToolError
from .credentials import VendorWireAuth

_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
_RETRYABLE_STATUS = frozenset({408, 425, 429, 500, 502, 503, 504})
_MAX_MUTATIONS_PER_CALL = 20

MAX_VENDOR_RESPONSE_BYTES = DEFAULT_RESPONSE_BODY_BYTES


class VendorTransport:
    """Structural port for the socket that actually sends."""

    async def send(self, request: HttpEgressRequest) -> HttpEgressResponse: ...


@dataclass(frozen=True, slots=True)
class DurableMutationOwner:
    """The committed product intent one tool call's mutations belong to."""

    organization_id: UUID
    tool_use_message_id: UUID
    tool_id: UUID
    durable_context: DurableStepContext


class GuardedVendorClient:
    """One invocation's vendor transport, pinned to one origin.

    Instances are per tool call because the mutation sequence counter must
    restart with each committed `TOOL_USE`; two mutations in one call take
    distinct attempt identities, and a durable replay reproduces the same
    sequence in the same order.
    """

    def __init__(
        self,
        *,
        base_url: str,
        auth: VendorWireAuth,
        vendor: str,
        transport: VendorTransport | None = None,
        owner: DurableMutationOwner | None = None,
        static_headers: Mapping[str, str] | None = None,
        total_timeout_seconds: float = 20.0,
    ) -> None:
        try:
            origin, base_path = parse_https_target(base_url)
        except HttpEgressPolicyError as error:
            raise VendorToolError(
                "vendor_base_url_invalid",
                "Vendor base URL is not a valid HTTPS target.",
            ) from error
        self._origin = origin
        self._base_path = base_path.rstrip("/")
        self._policy = HttpDestinationPolicy(
            primary=HttpRoutePolicy(origin=origin, path_prefix=base_path or "/")
        )
        self._auth = auth
        self._vendor = vendor
        self._transport = transport or SafeHttpTransport()
        self._owner = owner
        self._timeout = total_timeout_seconds
        self._mutation_sequence = 0
        self._static_headers = self._checked_static_headers(static_headers)

    @staticmethod
    def _checked_static_headers(
        static_headers: Mapping[str, str] | None,
    ) -> dict[str, str]:
        """Re-check what the vendor spec already validated.

        The spec is the first gate, but the client is reachable directly, so a
        reserved name is refused here too rather than trusted to have been
        caught upstream.
        """
        checked: dict[str, str] = {}
        for name, value in (static_headers or {}).items():
            if name.casefold() in RESERVED_HEADER_NAMES:
                raise VendorToolError(
                    "vendor_header_reserved",
                    f"Header '{name}' cannot be set by a vendor.",
                )
            checked[name] = value
        return checked

    @property
    def origin(self) -> HttpOrigin:
        return self._origin

    async def read(
        self,
        path: str,
        *,
        method: str = "GET",
        query: Mapping[str, Any] | None = None,
        json: Any = None,
    ) -> VendorResponse:
        request = self._build(path, method=method, query=query, payload=json)
        try:
            response = await self._transport.send(request)
        except HttpEgressPolicyError as error:
            raise VendorToolError(
                "vendor_egress_rejected",
                "Vendor request was refused by the egress boundary.",
            ) from error
        except TimeoutError as error:
            raise VendorToolError(
                "vendor_unavailable",
                "Vendor did not answer within the request budget.",
            ) from error
        return _parse(response)

    async def mutate(
        self,
        path: str,
        *,
        method: str = "POST",
        query: Mapping[str, Any] | None = None,
        json: Any = None,
    ) -> VendorResponse:
        if self._owner is None:
            raise VendorToolError(
                "durable_owner_required",
                "A vendor mutation requires a committed tool-use owner.",
            )
        if self._mutation_sequence >= _MAX_MUTATIONS_PER_CALL:
            raise VendorToolError(
                "mutation_budget_exhausted",
                "One curated tool call may not make this many vendor mutations.",
            )
        sequence = self._mutation_sequence
        self._mutation_sequence += 1

        owner = self._owner
        identity = OutboundAttemptIdentity(
            organization_id=owner.organization_id,
            owner_kind=OutboundOwnerKind.TOOL_CALL,
            owner_id=owner.tool_use_message_id,
            operation_key=f"integration.curated.{owner.tool_id.hex}.{sequence}",
        )
        request = self._build(
            path,
            method=method,
            query=query,
            payload=json,
            idempotency_key=identity.provider_idempotency_key,
        )
        spec = OutboundAttemptSpec(
            identity=identity,
            provider_operation=f"integration.curated.{self._vendor}.{sequence}",
            transport_kind=OutboundTransportKind.HTTP,
            destination_origin=str(self._origin),
            request_fingerprint=_fingerprint(request),
        )
        replies: list[VendorResponse] = []

        async def send(
            authorization: OutboundSendAuthorization,
        ) -> OutboundSendOutcome:
            if authorization.attempt_id != identity.attempt_id:
                raise ValueError(
                    "Vendor send authorization belongs to another attempt."
                )
            try:
                response = await self._transport.send(request)
            except HttpEgressPolicyError:
                return OutboundSendTerminal(failure_code="egress_policy_rejected")
            except TimeoutError:
                return OutboundSendUnknown(failure_code="egress_outcome_unconfirmed")
            replies.append(_parse(response))
            return _outcome(request.method, response)

        await execute_outbound_attempt(
            spec=spec,
            context=owner.durable_context,
            sender=send,
        )
        if not replies:
            raise VendorToolError(
                "vendor_outcome_unknown",
                "Vendor mutation completed without a readable reply.",
            )
        return replies[-1]

    def _build(
        self,
        path: str,
        *,
        method: str,
        query: Mapping[str, Any] | None,
        payload: Any,
        idempotency_key: str | None = None,
    ) -> HttpEgressRequest:
        url = self._url(path, query)
        method = method.strip().upper()
        body = b""
        # Vendor-declared headers go in first so the transport's own always
        # win. `CuratedVendorSpec` already refuses credential and transport
        # header names, so this cannot become a second credential channel.
        headers: dict[str, str] = dict(self._static_headers)
        headers["Accept"] = "application/json"
        if payload is not None:
            if method in _SAFE_METHODS:
                raise VendorToolError(
                    "vendor_request_invalid",
                    "A safe-method vendor request cannot carry a body.",
                )
            body = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode()
            headers["Content-Type"] = "application/json"
        if idempotency_key is not None:
            headers["Idempotency-Key"] = idempotency_key
        try:
            return HttpEgressRequest(
                method=method,
                url=url,
                policy=self._policy,
                headers=headers,
                origin_headers=self._auth.origin_headers,
                origin_query=self._auth.origin_query,
                body=body,
                response_body_limit=MAX_VENDOR_RESPONSE_BYTES,
                total_timeout_seconds=self._timeout,
            )
        except HttpEgressPolicyError as error:
            raise VendorToolError(
                "vendor_request_invalid",
                "Vendor request was rejected before reaching the network.",
            ) from error

    def _url(self, path: str, query: Mapping[str, Any] | None) -> str:
        if "://" in path:
            raise VendorToolError(
                "vendor_path_invalid",
                "A curated tool must supply a path, never a full URL.",
            )
        suffix = path if path.startswith("/") else f"/{path}"
        url = f"{self._origin}{self._base_path}{suffix}"
        pairs = _query_pairs(query)
        return f"{url}?{urlencode(pairs)}" if pairs else url


def _query_pairs(query: Mapping[str, Any] | None) -> list[tuple[str, str]]:
    if not query:
        return []
    pairs: list[tuple[str, str]] = []
    for name, value in query.items():
        if value is None:
            continue
        if isinstance(value, bool):
            pairs.append((str(name), "true" if value else "false"))
        elif isinstance(value, (str, int, float)):
            pairs.append((str(name), str(value)))
        elif isinstance(value, (list, tuple)):
            pairs.extend((str(name), str(item)) for item in value if item is not None)
        else:
            raise VendorToolError(
                "vendor_query_invalid",
                "Vendor query values must be scalars or scalar lists.",
            )
    return pairs


def _parse(response: HttpEgressResponse) -> VendorResponse:
    """Read one bounded vendor reply without leaking headers to the tool."""
    if not response.body:
        return VendorResponse(status_code=response.status_code, data=None)
    media = _media_type(response)
    if media and media != "application/json" and not media.endswith("+json"):
        raise VendorToolError(
            "vendor_media_unsupported",
            "Vendor returned a media type curated tools do not accept.",
        )
    try:
        data = json.loads(response.body)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        raise VendorToolError(
            "vendor_response_invalid",
            "Vendor returned a body that is not valid JSON.",
        ) from error
    return VendorResponse(status_code=response.status_code, data=data)


def _media_type(response: HttpEgressResponse) -> str:
    values = response.header_values("content-type")
    if not values:
        return ""
    return values[0].split(";", 1)[0].strip().lower()


def _outcome(method: str, response: HttpEgressResponse) -> OutboundSendOutcome:
    if 200 <= response.status_code < 300:
        return OutboundSendSucceeded(status_code=response.status_code)
    if response.status_code in _RETRYABLE_STATUS:
        failure = f"vendor_http_{response.status_code}"
        if method in _SAFE_METHODS or method in {"PUT", "DELETE"}:
            return OutboundSendRetryable(failure_code=failure)
        return OutboundSendUnknown(failure_code=failure)
    return OutboundSendTerminal(failure_code=f"vendor_http_{response.status_code}")


def _fingerprint(request: HttpEgressRequest) -> str:
    digest = hashlib.sha256()
    digest.update(request.method.encode())
    digest.update(b"\0")
    digest.update(request.url.encode())
    digest.update(b"\0")
    digest.update(request.body)
    return digest.hexdigest()


__all__ = [
    "MAX_VENDOR_RESPONSE_BYTES",
    "DurableMutationOwner",
    "GuardedVendorClient",
    "VendorTransport",
]
