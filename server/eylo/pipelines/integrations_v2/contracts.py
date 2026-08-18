"""Define curated vendor metadata plus normalized HTTP and auth contracts."""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol

from pydantic import BaseModel

from eylo.modules.integrations_v2.domain.enums import (
    CredentialLocation,
    ToolEffect,
    VendorAuthKind,
)

_ERROR_CODE = re.compile(r"^[a-z][a-z0-9_.-]*$")
_TOOL_NAME = re.compile(r"^[a-z][a-z0-9_]{0,127}$")
_VENDOR_ID = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_HEADER_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9-]{0,63}$")

# Header names a vendor may never declare statically. Credentials belong in the
# origin-bound bucket, which is only sent to the pinned origin; a static header
# is not origin-bound, so allowing these would create a second, unguarded
# credential channel. The transport-owned headers are reserved so a vendor
# cannot change how a body is framed or a reply is parsed.
RESERVED_HEADER_NAMES = frozenset(
    {
        "accept",
        "authorization",
        "content-length",
        "content-type",
        "cookie",
        "host",
        "idempotency-key",
        "proxy-authorization",
        "www-authenticate",
    }
)

MAX_TOOL_DESCRIPTION_CHARS = 5_000
MIN_TOOL_DESCRIPTION_CHARS = 20


class VendorToolError(Exception):
    """Coded curated-tool failure carrying no credential or payload detail.

    Curated tools raise this — never a bare `ValueError` — so the execution
    layer can map failures to a stable agent-visible code without matching on
    message strings.
    """

    def __init__(self, code: str, message: str) -> None:
        if not _ERROR_CODE.fullmatch(code):
            raise ValueError("Curated tool error code must be an identifier.")
        self.code = code
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class VendorResponse:
    """One bounded vendor reply already parsed and size-checked."""

    status_code: int
    data: Any = field(repr=False)

    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 300


class VendorHttpClient(Protocol):
    """Origin-bound vendor transport handed to one curated tool invocation.

    Implementations pin the request to the integration's declared origin and
    inject credentials at the egress boundary. A curated tool supplies a path
    relative to that origin and never a full URL, so it cannot redirect vendor
    credentials to another host.
    """

    async def read(
        self,
        path: str,
        *,
        method: str = "GET",
        query: Mapping[str, Any] | None = None,
        json: Any = None,
    ) -> VendorResponse:
        """Perform a non-mutating vendor request. No outbound receipt is written."""
        ...

    async def mutate(
        self,
        path: str,
        *,
        method: str = "POST",
        query: Mapping[str, Any] | None = None,
        json: Any = None,
    ) -> VendorResponse:
        """Perform a mutating vendor request through the durable outbound owner.

        Each call within one tool invocation takes the next sequence number, so
        two mutations in the same tool get distinct attempt identities and a
        durable replay reproduces the same keys in the same order.

        Raises `VendorToolError("durable_owner_required")` when the tool was not
        declared as `ToolEffect.MUTATION`.
        """
        ...


@dataclass(frozen=True, slots=True)
class VendorAccount:
    """Safe identity of the connection this invocation is acting through.

    A curated tool can say *which* account it acted as without being able to
    read the credential that proves it.
    """

    connection_id: str


@dataclass(frozen=True, slots=True)
class VendorToolContext:
    """Everything one curated tool invocation is permitted to reach."""

    http: VendorHttpClient
    account: VendorAccount
    effect: ToolEffect

    async def read(
        self,
        path: str,
        *,
        method: str = "GET",
        query: Mapping[str, Any] | None = None,
        json: Any = None,
    ) -> VendorResponse:
        return await self.http.read(path, method=method, query=query, json=json)

    async def mutate(
        self,
        path: str,
        *,
        method: str = "POST",
        query: Mapping[str, Any] | None = None,
        json: Any = None,
    ) -> VendorResponse:
        if self.effect is not ToolEffect.MUTATION:
            raise VendorToolError(
                "durable_owner_required",
                "A read-declared curated tool cannot mutate vendor state.",
            )
        return await self.http.mutate(path, method=method, query=query, json=json)


@dataclass(frozen=True, slots=True)
class ApiKeyPlacement:
    """Where one vendor expects its API key, and how it prefixes the value.

    This is vendor knowledge, not organization configuration, so it is declared
    in vendor code rather than stored per install. Linear, for example, sends a
    personal API key as the raw `Authorization` value with no `Bearer` prefix,
    and getting that wrong is a per-vendor fact no operator should have to know.
    """

    location: CredentialLocation
    name: str
    value_prefix: str = ""

    def __post_init__(self) -> None:
        if not self.name.strip() or self.name != self.name.strip():
            raise ValueError("API key placement name is invalid.")


@dataclass(frozen=True, slots=True)
class InstanceUrlRequirement:
    """A vendor whose origin belongs to the customer, not the vendor.

    Atlassian is the archetype: every organization reaches Jira and Confluence
    at its own `https://<site>.atlassian.net`. Such a vendor declares this
    instead of a `base_url`, and each installation supplies the origin.

    The supplied origin is still pinned by the egress policy exactly as a static
    one is, so a curated tool cannot address anything outside the instance an
    operator configured.
    """

    label: str
    placeholder: str
    description: str
    path_suffix: str = ""

    def __post_init__(self) -> None:
        if not self.label.strip():
            raise ValueError("Instance URL requirement needs a label.")
        if self.path_suffix and not self.path_suffix.startswith("/"):
            raise ValueError("Instance URL path suffix must start with '/'.")


@dataclass(frozen=True, slots=True)
class VendorOAuthConfig:
    """Everything about a vendor's OAuth flow that the vendor itself decides."""

    authorization_url: str
    token_url: str
    scopes: tuple[str, ...]
    scope_delimiter: str = " "
    pkce: bool = False
    authorization_params: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if not self.authorization_url.startswith("https://"):
            raise ValueError("OAuth authorization URL must be HTTPS.")
        if not self.token_url.startswith("https://"):
            raise ValueError("OAuth token URL must be HTTPS.")

    @property
    def requires_tenant(self) -> bool:
        """Whether the provider's endpoints are per-tenant, like Microsoft's."""
        return "{tenant}" in self.authorization_url or "{tenant}" in self.token_url


@dataclass(frozen=True, slots=True)
class CuratedVendorSpec:
    """One vendor's registry identity and connection surface.

    Exactly one of `base_url` and `instance_url` is set. Either way, curated
    tools address paths relative to the resolved origin and never a full URL,
    so a tool cannot send vendor credentials to another host.
    """

    vendor: str
    display_name: str
    description: str
    auth_kinds: tuple[VendorAuthKind, ...]
    base_url: str | None = None
    instance_url: InstanceUrlRequirement | None = None
    categories: tuple[str, ...] = ()
    homepage_url: str | None = None
    api_key_placement: ApiKeyPlacement | None = None
    oauth: VendorOAuthConfig | None = None
    static_headers: tuple[tuple[str, str], ...] = ()
    """Non-secret headers this vendor's API requires on every request.

    Notion is the archetype: it rejects any request without `Notion-Version`.
    That is vendor knowledge, not organization configuration, so it is declared
    here rather than retyped per install. Credential and transport headers are
    refused — see `RESERVED_HEADER_NAMES`.
    """

    def __post_init__(self) -> None:
        if not _VENDOR_ID.fullmatch(self.vendor):
            raise ValueError("Curated vendor id is invalid.")
        for name, value in self.static_headers:
            if not _HEADER_NAME.fullmatch(name):
                raise ValueError(f"Static header name '{name}' is invalid.")
            if name.casefold() in RESERVED_HEADER_NAMES:
                raise ValueError(
                    f"Static header '{name}' is reserved and cannot be declared."
                )
            if not value.strip() or value != value.strip():
                raise ValueError(f"Static header '{name}' has an invalid value.")
            if "\n" in value or "\r" in value:
                raise ValueError(f"Static header '{name}' may not span lines.")
        if not self.display_name.strip():
            raise ValueError("Curated vendor display name is required.")
        if not self.auth_kinds:
            raise ValueError("Curated vendor must declare at least one auth kind.")
        if len(set(self.auth_kinds)) != len(self.auth_kinds):
            raise ValueError("Curated vendor auth kinds must be unique.")
        if VendorAuthKind.API_KEY in self.auth_kinds and self.api_key_placement is None:
            raise ValueError(
                "Curated vendor supporting API keys must declare their placement."
            )
        if bool(self.base_url) == bool(self.instance_url):
            raise ValueError(
                "Curated vendor must declare exactly one of base_url or instance_url."
            )
        if VendorAuthKind.OAUTH2 in self.auth_kinds and self.oauth is None:
            raise ValueError(
                "Curated vendor supporting OAuth2 must declare its OAuth config."
            )

    @property
    def requires_instance_url(self) -> bool:
        return self.instance_url is not None

    def resolve_base_url(self, instance_url: str | None) -> str:
        """Effective origin for one installation of this vendor."""
        if self.base_url is not None:
            return self.base_url
        if not instance_url:
            raise ValueError(f"Vendor '{self.vendor}' requires an instance URL.")
        suffix = self.instance_url.path_suffix if self.instance_url else ""
        return f"{instance_url.rstrip('/')}{suffix}"


CuratedToolCallable = Callable[[Any, VendorToolContext], Awaitable[Any]]


@dataclass(frozen=True, slots=True)
class CuratedToolSpec:
    """One curated tool's published contract and its implementation.

    `input_model` is the single source of the agent-visible input schema. It is
    a Pydantic model rather than a hand-written JSON Schema so the validated
    Python type and the published contract cannot drift apart.
    """

    vendor: str
    name: str
    display_name: str
    description: str
    effect: ToolEffect
    input_model: type[BaseModel]
    handler: CuratedToolCallable = field(repr=False)
    scopes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not _VENDOR_ID.fullmatch(self.vendor):
            raise ValueError("Curated tool vendor id is invalid.")
        if not _TOOL_NAME.fullmatch(self.name):
            raise ValueError("Curated tool name is invalid.")
        if not self.display_name.strip():
            raise ValueError("Curated tool display name is required.")
        description = self.description.strip()
        if not (
            MIN_TOOL_DESCRIPTION_CHARS <= len(description) <= MAX_TOOL_DESCRIPTION_CHARS
        ):
            raise ValueError(
                "Curated tool description must explain the tool to a model."
            )
        if not issubclass(self.input_model, BaseModel):
            raise ValueError("Curated tool input model must be a Pydantic model.")

    @property
    def wire_id(self) -> str:
        """Stable binding to this exact registered callable.

        This id binds the installed row to its exact registry callable. Curated
        tools are stored separately from platform and MCP tool definitions, so
        the id does not need a transport namespace prefix.
        """
        return f"{self.vendor}.{self.name}"

    @property
    def qualified_name(self) -> str:
        return f"{self.vendor}_{self.name}"


__all__ = [
    "ApiKeyPlacement",
    "CredentialLocation",
    "CuratedToolCallable",
    "CuratedToolSpec",
    "CuratedVendorSpec",
    "InstanceUrlRequirement",
    "MAX_TOOL_DESCRIPTION_CHARS",
    "MIN_TOOL_DESCRIPTION_CHARS",
    "RESERVED_HEADER_NAMES",
    "ToolEffect",
    "VendorAccount",
    "VendorAuthKind",
    "VendorOAuthConfig",
    "VendorHttpClient",
    "VendorResponse",
    "VendorToolContext",
    "VendorToolError",
]
