"""Published configuration contract for REST-backed tools."""

from __future__ import annotations

import re
from collections.abc import Mapping
from enum import Enum
from typing import Any
from urllib.parse import parse_qsl, urlsplit

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from eylo.common.http_egress import (
    DEFAULT_RESPONSE_BODY_BYTES,
    MAX_RESPONSE_BODY_BYTES,
    MAX_TOTAL_TIMEOUT_SECONDS,
    HttpEgressPolicyError,
    parse_https_target,
)

_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,127}$")
_HEADER_NAME = re.compile(r"^[!#$%&'*+.^_`|~0-9A-Za-z-]+$")
_PLACEHOLDER = re.compile(
    r"\{\{([A-Za-z][A-Za-z0-9_]*)\}\}|\{([A-Za-z][A-Za-z0-9_]*)\}"
)
_READ_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
_RESERVED_PUBLIC_HEADERS = frozenset(
    {
        "authorization",
        "content-length",
        "cookie",
        "host",
        "proxy-authorization",
        "transfer-encoding",
    }
)
_CONFIG_FIELDS = frozenset(
    {
        "bodyParams",
        "body_params",
        "graphqlQuery",
        "graphqlVariables",
        "graphql_query",
        "graphql_variables",
        "headers",
        "idempotency_header",
        "method",
        "params",
        "pathParams",
        "path_params",
        "payload",
        "provider_reference_header",
        "queryParams",
        "query_params",
        "response_body_limit",
        "total_timeout_seconds",
        "url",
    }
)


class RestExecutorConfigError(ValueError):
    """Coded safe failure for one unpublishable REST executor config."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


class JsonAPIMethod(str, Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"
    OPTIONS = "OPTIONS"
    HEAD = "HEAD"


class JsonAPIExecutorParamsSchema(BaseModel):
    """Typed storage/API surface for one REST executor operation."""

    url: str = Field(min_length=1)
    method: JsonAPIMethod = JsonAPIMethod.GET
    headers: dict[str, str] = Field(default_factory=dict)
    payload: Any = Field(default_factory=dict)
    params: dict[str, Any] = Field(default_factory=dict)
    path_params: list[str] = Field(default_factory=list, alias="pathParams")
    query_params: list[str] = Field(default_factory=list, alias="queryParams")
    body_params: list[str] = Field(default_factory=list, alias="bodyParams")
    graphql_query: str | None = Field(default=None, alias="graphqlQuery")
    graphql_variables: list[str] = Field(
        default_factory=list,
        alias="graphqlVariables",
    )
    idempotency_header: str | None = None
    provider_reference_header: str | None = None
    response_body_limit: int = Field(
        default=DEFAULT_RESPONSE_BODY_BYTES,
        ge=1,
        le=MAX_RESPONSE_BODY_BYTES,
    )
    total_timeout_seconds: float = Field(
        default=20.0,
        gt=0,
        le=MAX_TOTAL_TIMEOUT_SECONDS,
    )

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        use_enum_values=True,
    )


def validate_json_api_executor_config(
    config: object,
) -> JsonAPIExecutorParamsSchema:
    """Return the canonical publish/runtime view of one REST operation config."""
    if not isinstance(config, Mapping):
        raise _error("config_invalid", "REST operation config must be an object.")
    if "auth_injection" in config:
        raise _error(
            "auth_authority_conflict",
            "REST operation auth placement must come from integration auth.",
        )
    if set(config) - _CONFIG_FIELDS:
        raise _error(
            "config_field_unsupported",
            "REST operation contains unsupported config fields.",
        )
    try:
        operation = JsonAPIExecutorParamsSchema.model_validate(config)
    except ValidationError:
        raise _error("config_invalid", "REST operation config is invalid.") from None
    _validate_operation(operation)
    return operation


def _validate_operation(operation: JsonAPIExecutorParamsSchema) -> None:
    parts = urlsplit(operation.url)
    if _contains_placeholder(parts.scheme) or _contains_placeholder(parts.netloc):
        raise _error(
            "destination_template_invalid",
            "REST destination authority cannot be dynamic.",
        )
    if _contains_placeholder(parts.query) or parts.fragment:
        raise _error(
            "destination_template_invalid",
            "REST destination query and fragment cannot be templated.",
        )
    try:
        parse_https_target(operation.url)
    except HttpEgressPolicyError as error:
        raise _error(error.code, str(error)) from None

    path_placeholders = _placeholder_names(parts.path)
    _require_unique_names(operation.path_params)
    _require_unique_names(operation.query_params)
    _require_unique_names(operation.body_params)
    _require_unique_names(operation.graphql_variables)
    if (
        set(path_placeholders) != set(operation.path_params)
        or len(path_placeholders) != len(operation.path_params)
        or _contains_invalid_brace(_PLACEHOLDER.sub("", parts.path))
    ):
        raise _error(
            "path_contract_invalid",
            "REST path placeholders must exactly match declared path params.",
        )

    _validate_headers(
        operation.headers,
        idempotency_header=operation.idempotency_header,
        provider_reference_header=operation.provider_reference_header,
    )
    _validate_query_authority(
        configured_query=parts.query,
        static_params=operation.params,
        dynamic_names=operation.query_params,
    )
    if set(_json_placeholder_names(operation.payload)) - set(operation.body_params):
        raise _error(
            "payload_contract_invalid",
            "REST payload placeholders must be declared body params.",
        )

    method = str(operation.method)
    if method in _READ_METHODS and (
        operation.body_params or operation.payload not in ({}, None)
    ):
        raise _error(
            "read_body_unsupported",
            "REST read operation cannot declare a request body.",
        )
    if operation.graphql_query is not None and method != JsonAPIMethod.POST.value:
        raise _error(
            "graphql_method_invalid",
            "GraphQL integration operations require POST.",
        )
    if operation.graphql_query is None and operation.graphql_variables:
        raise _error(
            "graphql_config_invalid",
            "GraphQL variables require a GraphQL query.",
        )


def _validate_headers(
    headers: dict[str, str],
    *,
    idempotency_header: str | None,
    provider_reference_header: str | None,
) -> None:
    normalized: set[str] = set()
    for name in headers:
        lowered = _validated_header_name(name)
        if lowered in normalized:
            raise _error(
                "headers_invalid",
                "REST header names must be unique ignoring case.",
            )
        if lowered in _RESERVED_PUBLIC_HEADERS:
            raise _error(
                "auth_authority_conflict",
                "REST auth and transport headers cannot be public config.",
            )
        normalized.add(lowered)

    for name in (idempotency_header, provider_reference_header):
        if name is not None:
            _validated_header_name(name)
    if idempotency_header is not None and idempotency_header.lower() in normalized:
        raise _error(
            "idempotency_header_conflict",
            "REST idempotency header cannot also be public config.",
        )

    content_types = [
        value for name, value in headers.items() if name.lower() == "content-type"
    ]
    if content_types:
        media_type = content_types[0].split(";", 1)[0].strip().lower()
        if media_type != "application/json":
            raise _error(
                "request_media_unsupported",
                "REST request bodies support application/json only.",
            )


def _validated_header_name(value: object) -> str:
    if not isinstance(value, str) or not _HEADER_NAME.fullmatch(value):
        raise _error("header_name_invalid", "REST header name is invalid.")
    return value.lower()


def _validate_query_authority(
    *,
    configured_query: str,
    static_params: dict[str, Any],
    dynamic_names: list[str],
) -> None:
    configured_names = {
        name for name, _value in parse_qsl(configured_query, keep_blank_values=True)
    }
    static_names = set(static_params)
    dynamic = set(dynamic_names)
    if configured_names & static_names or (configured_names | static_names) & dynamic:
        raise _error(
            "query_authority_conflict",
            "REST query names must have one configured authority.",
        )
    for name, value in static_params.items():
        if not _NAME.fullmatch(name):
            raise _error("query_invalid", "REST query name is invalid.")
        values = value if isinstance(value, list | tuple) else (value,)
        if not all(
            item is None or isinstance(item, str | int | float | bool)
            for item in values
        ):
            raise _error("query_invalid", "REST query value is invalid.")


def _require_unique_names(names: list[str]) -> None:
    if len(names) != len(set(names)) or not all(
        _NAME.fullmatch(name) for name in names
    ):
        raise _error("parameter_names_invalid", "REST parameter names are invalid.")


def _contains_placeholder(value: str) -> bool:
    return bool(_PLACEHOLDER.search(value) or _contains_invalid_brace(value))


def _contains_invalid_brace(value: str) -> bool:
    return "{" in value or "}" in value


def _placeholder_names(value: str) -> tuple[str, ...]:
    return tuple(
        match.group(1) or match.group(2) for match in _PLACEHOLDER.finditer(value)
    )


def _json_placeholder_names(value: object) -> tuple[str, ...]:
    if isinstance(value, dict):
        return tuple(
            name for item in value.values() for name in _json_placeholder_names(item)
        )
    if isinstance(value, list):
        return tuple(name for item in value for name in _json_placeholder_names(item))
    if isinstance(value, str):
        return _placeholder_names(value)
    return ()


def _error(code: str, message: str) -> RestExecutorConfigError:
    return RestExecutorConfigError(code, message)


__all__ = [
    "JsonAPIExecutorParamsSchema",
    "JsonAPIMethod",
    "RestExecutorConfigError",
    "validate_json_api_executor_config",
]
