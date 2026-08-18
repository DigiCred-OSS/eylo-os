"""DNS-pinned, redirect-aware HTTPX adapter for explicit public destinations."""

from __future__ import annotations

import asyncio
import ipaddress
import socket
from collections.abc import AsyncIterator, Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlencode, urljoin, urlsplit, urlunsplit

import httpx

from eylo.common.http_egress import (
    MAX_RESPONSE_HEADERS,
    MAX_RESPONSE_HEADER_BYTES,
    HttpEgressPolicyError,
    HttpEgressRequest,
    HttpEgressResponse,
    HttpOrigin,
)

_REDIRECT_STATUS = frozenset({301, 302, 303, 307, 308})
_CONTENT_HEADERS = frozenset(
    {
        "content-encoding",
        "content-language",
        "content-length",
        "content-location",
        "content-type",
    }
)


class DnsResolver(Protocol):
    """Resolve every address presented for one exact host and port."""

    async def resolve(self, host: str, port: int) -> Sequence[str]: ...


@dataclass(frozen=True, slots=True)
class ResolvedHttpTarget:
    """A validated address plus the configured TLS/HTTP authority."""

    origin: HttpOrigin
    address: str


class AsyncioDnsResolver:
    """Use the process resolver once; the transport then connects to its exact IP."""

    async def resolve(self, host: str, port: int) -> Sequence[str]:
        try:
            info = await asyncio.get_running_loop().getaddrinfo(
                host,
                port,
                family=socket.AF_UNSPEC,
                type=socket.SOCK_STREAM,
            )
        except OSError as error:
            raise HttpEgressPolicyError(
                "dns_resolution_failed",
                "HTTP destination DNS resolution failed.",
            ) from error
        return tuple(entry[4][0] for entry in info)


class _PinnedRequestStream(httpx.AsyncByteStream):
    """Preserve HTTPX's async request-body contract while changing the target."""

    def __init__(self, stream: httpx.AsyncByteStream) -> None:
        self._stream = stream

    async def __aiter__(self) -> AsyncIterator[bytes]:
        async for chunk in self._stream:
            yield chunk


class PinnedAsyncHTTPTransport(httpx.AsyncBaseTransport):
    """Connect by validated IP while preserving configured Host and TLS SNI."""

    def __init__(
        self,
        target: ResolvedHttpTarget,
        *,
        inner: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.target = target
        self._inner = inner or httpx.AsyncHTTPTransport()

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        if not isinstance(request.stream, httpx.AsyncByteStream):
            raise TypeError(
                "PinnedAsyncHTTPTransport requires an async request stream."
            )
        extensions = dict(request.extensions)
        extensions["sni_hostname"] = self.target.origin.host
        headers = httpx.Headers(request.headers)
        headers["Host"] = self.target.origin.authority
        pinned = httpx.Request(
            method=request.method,
            url=request.url.copy_with(host=self.target.address),
            headers=headers,
            content=_PinnedRequestStream(request.stream),
            extensions=extensions,
        )
        response = await self._inner.handle_async_request(pinned)
        response.request = request
        return response

    async def aclose(self) -> None:
        await self._inner.aclose()


TransportFactory = Callable[[ResolvedHttpTarget], httpx.AsyncBaseTransport]


class SafeHttpTransport:
    """Execute one bounded request; policy errors happen before unsafe connect."""

    def __init__(
        self,
        *,
        resolver: DnsResolver | None = None,
        transport_factory: TransportFactory | None = None,
    ) -> None:
        self._resolver = resolver or AsyncioDnsResolver()
        self._transport_factory = transport_factory or PinnedAsyncHTTPTransport

    async def send(self, request: HttpEgressRequest) -> HttpEgressResponse:
        try:
            async with asyncio.timeout(request.total_timeout_seconds):
                return await self._send(request)
        except TimeoutError:
            raise

    async def _send(self, request: HttpEgressRequest) -> HttpEgressResponse:
        current_url = request.url
        method = request.method
        body = request.body
        headers = dict(request.headers)
        redirect_count = 0

        while True:
            origin = request.policy.require_target(
                current_url,
                redirect=redirect_count > 0,
            )
            target = await self._resolve(origin)
            hop_headers = dict(headers)
            if (
                request.origin_headers is not None
                and request.origin_headers.origin == origin
            ):
                hop_headers.update(request.origin_headers.values)
            wire_url = current_url
            if (
                request.origin_query is not None
                and request.origin_query.origin == origin
            ):
                wire_url = _with_origin_query(
                    current_url,
                    request.origin_query.values,
                )

            try:
                response = await self._send_hop(
                    target=target,
                    method=method,
                    url=wire_url,
                    headers=hop_headers,
                    body=body,
                    response_body_limit=request.response_body_limit,
                )
            except httpx.HTTPError:
                raise HttpEgressPolicyError(
                    "transport_failed",
                    "HTTP transport failed.",
                ) from None
            location = _redirect_location(response)
            if location is None or request.policy.max_redirects == 0:
                return HttpEgressResponse(
                    status_code=response.status_code,
                    final_origin=origin,
                    headers=response.headers,
                    body=response.body,
                    redirect_count=redirect_count,
                )
            if redirect_count >= request.policy.max_redirects:
                raise HttpEgressPolicyError(
                    "redirect_limit_exceeded",
                    "HTTP redirect count exceeded the configured operation limit.",
                )

            current_url = urljoin(current_url, location)
            redirect_count += 1
            request.policy.require_target(current_url, redirect=True)
            method, body, headers = _redirect_request(
                method, body, headers, response.status_code
            )

    async def _resolve(self, origin: HttpOrigin) -> ResolvedHttpTarget:
        try:
            literal = ipaddress.ip_address(origin.host)
        except ValueError:
            answers = await self._resolver.resolve(origin.host, origin.port)
        else:
            answers = (str(literal),)
        validated = _validated_addresses(answers)
        return ResolvedHttpTarget(origin=origin, address=validated[0])

    async def _send_hop(
        self,
        *,
        target: ResolvedHttpTarget,
        method: str,
        url: str,
        headers: dict[str, str],
        body: bytes,
        response_body_limit: int,
    ) -> HttpEgressResponse:
        transport = self._transport_factory(target)
        timeout = httpx.Timeout(20.0, connect=10.0, read=20.0, write=20.0, pool=5.0)
        async with httpx.AsyncClient(
            transport=transport,
            follow_redirects=False,
            timeout=timeout,
            trust_env=False,
            limits=httpx.Limits(max_connections=1, max_keepalive_connections=0),
        ) as client:
            async with client.stream(
                method,
                url,
                headers=headers,
                content=body,
            ) as response:
                response_headers = _bounded_response_headers(response.headers)
                content = await _bounded_body(response, response_body_limit)
                return HttpEgressResponse(
                    status_code=response.status_code,
                    final_origin=target.origin,
                    headers=response_headers,
                    body=content,
                )


def _validated_addresses(values: Sequence[str]) -> tuple[str, ...]:
    if not values:
        raise HttpEgressPolicyError(
            "dns_resolution_empty",
            "HTTP destination DNS resolution returned no addresses.",
        )
    parsed: set[ipaddress.IPv4Address | ipaddress.IPv6Address] = set()
    for value in values:
        try:
            address = ipaddress.ip_address(value)
        except ValueError as error:
            raise HttpEgressPolicyError(
                "dns_answer_invalid",
                "HTTP destination DNS returned an invalid address.",
            ) from error
        if not _is_public(address):
            raise HttpEgressPolicyError(
                "destination_not_public",
                "HTTP destination resolved to a non-public address.",
            )
        parsed.add(address)
    return tuple(
        str(address)
        for address in sorted(parsed, key=lambda item: (item.version, int(item)))
    )


def _is_public(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return bool(
        address.is_global
        and not address.is_private
        and not address.is_loopback
        and not address.is_link_local
        and not address.is_multicast
        and not address.is_reserved
        and not address.is_unspecified
    )


def _bounded_response_headers(headers: httpx.Headers) -> tuple[tuple[str, str], ...]:
    entries = tuple(headers.multi_items())
    total = sum(
        len(name.encode("utf-8")) + len(value.encode("utf-8"))
        for name, value in entries
    )
    if len(entries) > MAX_RESPONSE_HEADERS or total > MAX_RESPONSE_HEADER_BYTES:
        raise HttpEgressPolicyError(
            "response_headers_too_large",
            "HTTP response headers exceed the egress limit.",
        )
    return entries


async def _bounded_body(response: httpx.Response, limit: int) -> bytes:
    chunks: list[bytes] = []
    size = 0
    async for chunk in response.aiter_bytes():
        size += len(chunk)
        if size > limit:
            raise HttpEgressPolicyError(
                "response_body_too_large",
                "HTTP response body exceeds the configured operation limit.",
            )
        chunks.append(chunk)
    return b"".join(chunks)


def _redirect_location(response: HttpEgressResponse) -> str | None:
    if response.status_code not in _REDIRECT_STATUS:
        return None
    values = response.header_values("location")
    if len(values) != 1 or not values[0].strip():
        raise HttpEgressPolicyError(
            "redirect_location_invalid",
            "HTTP redirect requires one valid Location header.",
        )
    return values[0].strip()


def _redirect_request(
    method: str,
    body: bytes,
    headers: dict[str, str],
    status_code: int,
) -> tuple[str, bytes, dict[str, str]]:
    if status_code == 303 and method != "HEAD":
        return "GET", b"", _without_content_headers(headers)
    if status_code in {301, 302} and method == "POST":
        return "GET", b"", _without_content_headers(headers)
    return method, body, headers


def _without_content_headers(headers: dict[str, str]) -> dict[str, str]:
    return {
        key: value
        for key, value in headers.items()
        if key.lower() not in _CONTENT_HEADERS
    }


def _with_origin_query(url: str, values: Mapping[str, str]) -> str:
    parts = urlsplit(url)
    encoded = urlencode(tuple(values.items()))
    query = f"{parts.query}&{encoded}" if parts.query else encoded
    return urlunsplit((parts.scheme, parts.netloc, parts.path, query, ""))


__all__ = [
    "AsyncioDnsResolver",
    "DnsResolver",
    "PinnedAsyncHTTPTransport",
    "ResolvedHttpTarget",
    "SafeHttpTransport",
    "TransportFactory",
]
