"""Pure contracts for bounded HTTPS egress to explicitly declared routes."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping
from urllib.parse import parse_qsl, unquote, urlsplit

MAX_REQUEST_BODY_BYTES = 1_048_576
MAX_RESPONSE_BODY_BYTES = 8_388_608
DEFAULT_RESPONSE_BODY_BYTES = 1_048_576
MAX_REQUEST_HEADERS = 100
MAX_REQUEST_HEADER_BYTES = 32_768
MAX_RESPONSE_HEADERS = 200
MAX_RESPONSE_HEADER_BYTES = 65_536
MAX_REDIRECTS = 5
MAX_TOTAL_TIMEOUT_SECONDS = 60.0

_METHODS = frozenset({"DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"})
_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_.-]*$")
_HEADER_NAME = re.compile(r"^[!#$%&'*+.^_`|~0-9A-Za-z-]+$")
_QUERY_NAME = re.compile(r"^[A-Za-z0-9_.~-]{1,128}$")
_FORBIDDEN_ALL_HEADERS = frozenset(
    {
        "connection",
        "content-length",
        "host",
        "proxy-connection",
        "set-cookie",
        "transfer-encoding",
        "upgrade",
    }
)
_ORIGIN_BOUND_PUBLIC_HEADERS = frozenset(
    {"authorization", "cookie", "proxy-authorization"}
)


class HttpEgressPolicyError(ValueError):
    """A safe allowlisted category without destination or credential detail."""

    def __init__(self, code: str, message: str) -> None:
        if not _IDENTIFIER.fullmatch(code):
            raise ValueError("HTTP egress error code must be an identifier.")
        self.code = code
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class HttpOrigin:
    """Canonical HTTPS origin used for both routing and credential audience."""

    host: str
    port: int = 443
    scheme: str = "https"

    def __post_init__(self) -> None:
        if self.scheme != "https":
            raise HttpEgressPolicyError(
                "scheme_not_allowed",
                "External HTTP transport requires HTTPS.",
            )
        host = _normalize_host(self.host)
        if not 1 <= self.port <= 65535:
            raise HttpEgressPolicyError(
                "port_not_allowed",
                "External HTTP destination port is invalid.",
            )
        object.__setattr__(self, "host", host)

    @classmethod
    def parse(cls, value: str) -> HttpOrigin:
        parsed = _split_url(value)
        if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
            raise HttpEgressPolicyError(
                "origin_invalid",
                "Configured HTTP origin cannot include a path, query or fragment.",
            )
        return cls(
            scheme=parsed.scheme.lower(),
            host=_hostname(parsed),
            port=_port(parsed),
        )

    @property
    def authority(self) -> str:
        host = f"[{self.host}]" if ":" in self.host else self.host
        return host if self.port == 443 else f"{host}:{self.port}"

    def __str__(self) -> str:
        return f"https://{self.authority}"


@dataclass(frozen=True, slots=True)
class HttpRoutePolicy:
    """One declared origin and the path subtree authorized on it."""

    origin: HttpOrigin
    path_prefix: str = "/"

    def __post_init__(self) -> None:
        object.__setattr__(self, "path_prefix", _validated_path(self.path_prefix))

    def allows_path(self, path: str) -> bool:
        candidate = _validated_path(path)
        prefix = self.path_prefix
        if prefix == "/" or candidate == prefix:
            return True
        boundary = prefix if prefix.endswith("/") else f"{prefix}/"
        return candidate.startswith(boundary)


@dataclass(frozen=True, slots=True)
class HttpDestinationPolicy:
    """Initial route plus explicit redirect reach and hop bound."""

    primary: HttpRoutePolicy
    redirect_routes: tuple[HttpRoutePolicy, ...] = ()
    max_redirects: int = 0

    def __post_init__(self) -> None:
        if not 0 <= self.max_redirects <= MAX_REDIRECTS:
            raise HttpEgressPolicyError(
                "redirect_limit_invalid",
                f"Redirect limit must be between 0 and {MAX_REDIRECTS}.",
            )
        origins = [route.origin for route in self.redirect_routes]
        if len(origins) != len(set(origins)):
            raise HttpEgressPolicyError(
                "redirect_route_duplicate",
                "Redirect routes must have unique origins.",
            )

    def require_target(self, url: str, *, redirect: bool) -> HttpOrigin:
        origin, path = parse_https_target(url)
        if origin == self.primary.origin and self.primary.allows_path(path):
            return origin
        if redirect:
            for route in self.redirect_routes:
                if origin == route.origin and route.allows_path(path):
                    return origin
        raise HttpEgressPolicyError(
            "destination_not_allowed",
            "HTTP destination is outside the configured operation authority.",
        )


@dataclass(frozen=True, slots=True)
class OriginBoundHeaders:
    """Credentials/idempotency headers that may reach one exact origin only."""

    origin: HttpOrigin
    values: Mapping[str, str] = field(repr=False)

    def __post_init__(self) -> None:
        values = _validated_headers(self.values, public=False)
        object.__setattr__(self, "values", MappingProxyType(values))


@dataclass(frozen=True, slots=True)
class OriginBoundQuery:
    """Credential query values injected only while sending to one exact origin."""

    origin: HttpOrigin
    values: Mapping[str, str] = field(repr=False)

    def __post_init__(self) -> None:
        values: dict[str, str] = {}
        for raw_name, raw_value in self.values.items():
            name = str(raw_name).strip()
            value = str(raw_value)
            if not _QUERY_NAME.fullmatch(name) or not value or len(value) > 4096:
                raise HttpEgressPolicyError(
                    "credential_query_invalid",
                    "Origin-bound HTTP query credential is invalid.",
                )
            if "\r" in value or "\n" in value:
                raise HttpEgressPolicyError(
                    "credential_query_invalid",
                    "Origin-bound HTTP query credential is invalid.",
                )
            values[name] = value
        if not values:
            raise HttpEgressPolicyError(
                "credential_query_invalid",
                "Origin-bound HTTP query credentials cannot be empty.",
            )
        object.__setattr__(self, "values", MappingProxyType(values))


@dataclass(frozen=True, slots=True)
class HttpEgressRequest:
    """One already constructed request with bounded in-memory inputs."""

    method: str
    url: str
    policy: HttpDestinationPolicy
    headers: Mapping[str, str] = field(default_factory=dict)
    origin_headers: OriginBoundHeaders | None = field(default=None, repr=False)
    origin_query: OriginBoundQuery | None = field(default=None, repr=False)
    body: bytes = field(default=b"", repr=False)
    response_body_limit: int = DEFAULT_RESPONSE_BODY_BYTES
    total_timeout_seconds: float = 20.0

    def __post_init__(self) -> None:
        method = self.method.strip().upper()
        if method not in _METHODS:
            raise HttpEgressPolicyError(
                "method_not_allowed",
                "HTTP method is not supported by the egress boundary.",
            )
        if len(self.body) > MAX_REQUEST_BODY_BYTES:
            raise HttpEgressPolicyError(
                "request_body_too_large",
                "HTTP request body exceeds the egress limit.",
            )
        if not 1 <= self.response_body_limit <= MAX_RESPONSE_BODY_BYTES:
            raise HttpEgressPolicyError(
                "response_limit_invalid",
                "HTTP response body limit is outside the supported range.",
            )
        if not 0 < self.total_timeout_seconds <= MAX_TOTAL_TIMEOUT_SECONDS:
            raise HttpEgressPolicyError(
                "timeout_invalid",
                "HTTP total timeout is outside the supported range.",
            )
        initial_origin = self.policy.require_target(self.url, redirect=False)
        headers = _validated_headers(self.headers, public=True)
        if self.origin_headers is not None:
            if self.origin_headers.origin != initial_origin:
                raise HttpEgressPolicyError(
                    "credential_origin_mismatch",
                    "Origin-bound HTTP headers do not match the initial destination.",
                )
            overlap = {name.lower() for name in headers} & {
                name.lower() for name in self.origin_headers.values
            }
            if overlap:
                raise HttpEgressPolicyError(
                    "header_authority_conflict",
                    "HTTP header cannot be both public and origin-bound.",
                )
        if self.origin_query is not None:
            if self.origin_query.origin != initial_origin:
                raise HttpEgressPolicyError(
                    "credential_origin_mismatch",
                    "Origin-bound HTTP query does not match the initial destination.",
                )
            public_names = {
                name
                for name, _value in parse_qsl(
                    urlsplit(self.url).query,
                    keep_blank_values=True,
                )
            }
            if public_names & set(self.origin_query.values):
                raise HttpEgressPolicyError(
                    "query_authority_conflict",
                    "HTTP query value cannot be both public and origin-bound.",
                )
        object.__setattr__(self, "method", method)
        object.__setattr__(self, "headers", MappingProxyType(headers))


@dataclass(frozen=True, slots=True)
class HttpEgressResponse:
    """Bounded transport result; it carries no request URL or credential."""

    status_code: int
    final_origin: HttpOrigin
    headers: tuple[tuple[str, str], ...]
    body: bytes = field(repr=False)
    redirect_count: int = 0

    def header_values(self, name: str) -> tuple[str, ...]:
        expected = name.lower()
        return tuple(value for key, value in self.headers if key.lower() == expected)


def parse_https_target(value: str) -> tuple[HttpOrigin, str]:
    """Parse and normalize a complete target without resolving DNS."""
    parsed = _split_url(value)
    if parsed.username is not None or parsed.password is not None:
        raise HttpEgressPolicyError(
            "userinfo_not_allowed",
            "HTTP destination user-info is not allowed.",
        )
    if parsed.fragment:
        raise HttpEgressPolicyError(
            "fragment_not_allowed",
            "HTTP destination fragments are not allowed.",
        )
    origin = HttpOrigin(
        scheme=parsed.scheme.lower(),
        host=_hostname(parsed),
        port=_port(parsed),
    )
    return origin, _validated_path(parsed.path or "/")


def _split_url(value: str):
    try:
        parsed = urlsplit(value)
        parsed.port
    except (TypeError, ValueError) as error:
        raise HttpEgressPolicyError(
            "url_invalid",
            "HTTP destination URL is invalid.",
        ) from error
    if not parsed.scheme or not parsed.netloc:
        raise HttpEgressPolicyError(
            "url_invalid",
            "HTTP destination requires an absolute URL.",
        )
    return parsed


def _hostname(parsed) -> str:
    if parsed.hostname is None:
        raise HttpEgressPolicyError(
            "host_missing",
            "HTTP destination requires a hostname.",
        )
    return _normalize_host(parsed.hostname)


def _normalize_host(value: str) -> str:
    host = value.strip().rstrip(".").lower()
    if not host or "%" in host:
        raise HttpEgressPolicyError(
            "host_invalid",
            "HTTP destination hostname is invalid.",
        )
    try:
        return host.encode("idna").decode("ascii")
    except UnicodeError as error:
        raise HttpEgressPolicyError(
            "host_invalid",
            "HTTP destination hostname is invalid.",
        ) from error


def _port(parsed) -> int:
    return parsed.port or 443


def _validated_path(value: str) -> str:
    if not value.startswith("/") or "\\" in value:
        raise HttpEgressPolicyError(
            "path_invalid",
            "HTTP destination path is invalid.",
        )
    lowered = value.lower()
    if "%2f" in lowered or "%5c" in lowered:
        raise HttpEgressPolicyError(
            "path_separator_encoded",
            "Encoded path separators are not allowed.",
        )
    decoded = unquote(value)
    if any(segment in {".", ".."} for segment in decoded.split("/")):
        raise HttpEgressPolicyError(
            "path_traversal",
            "HTTP destination path traversal is not allowed.",
        )
    return value


def _validated_headers(
    values: Mapping[str, str],
    *,
    public: bool,
) -> dict[str, str]:
    if len(values) > MAX_REQUEST_HEADERS:
        raise HttpEgressPolicyError(
            "request_headers_too_large",
            "HTTP request has too many headers.",
        )
    result: dict[str, str] = {}
    total = 0
    for raw_name, raw_value in values.items():
        name = str(raw_name).strip()
        value = str(raw_value)
        lowered = name.lower()
        if not _HEADER_NAME.fullmatch(name):
            raise HttpEgressPolicyError(
                "request_header_invalid",
                "HTTP request header name is invalid.",
            )
        if "\r" in value or "\n" in value:
            raise HttpEgressPolicyError(
                "request_header_invalid",
                "HTTP request header value is invalid.",
            )
        if lowered in _FORBIDDEN_ALL_HEADERS or (
            public and lowered in _ORIGIN_BOUND_PUBLIC_HEADERS
        ):
            raise HttpEgressPolicyError(
                "public_header_not_allowed",
                "Sensitive or hop-by-hop HTTP header must not be public.",
            )
        total += len(name.encode("utf-8")) + len(value.encode("utf-8"))
        result[name] = value
    if total > MAX_REQUEST_HEADER_BYTES:
        raise HttpEgressPolicyError(
            "request_headers_too_large",
            "HTTP request headers exceed the egress limit.",
        )
    return result


__all__ = [
    "DEFAULT_RESPONSE_BODY_BYTES",
    "HttpDestinationPolicy",
    "HttpEgressPolicyError",
    "HttpEgressRequest",
    "HttpEgressResponse",
    "HttpOrigin",
    "HttpRoutePolicy",
    "MAX_REDIRECTS",
    "MAX_REQUEST_BODY_BYTES",
    "MAX_RESPONSE_BODY_BYTES",
    "OriginBoundHeaders",
    "OriginBoundQuery",
    "parse_https_target",
]
