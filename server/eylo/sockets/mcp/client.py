"""Bounded MCP 2025-06-18 client over the shared HTTPS egress contract.

This adapter implements only the protocol surface Eylo uses: Streamable HTTP,
initialization, paginated tool discovery, and text-only tool calls. It performs
one wire attempt per request. Durable retry and ambiguous-delivery decisions
belong to the pipeline because only that layer knows the tool's declared effect.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol

from eylo.common.http_egress import (
    HttpDestinationPolicy,
    HttpEgressPolicyError,
    HttpEgressRequest,
    HttpEgressResponse,
    HttpRoutePolicy,
    OriginBoundHeaders,
    parse_https_target,
)

PROTOCOL_VERSION = "2025-06-18"
DEFAULT_TIMEOUT_SECONDS = 30.0

MAX_DISCOVERY_RESPONSE_BYTES = 524_288
MAX_TOOL_RESULT_BYTES = 65_536
MAX_INITIALIZE_RESPONSE_BYTES = 131_072
MAX_TOOL_PAGES = 20
MAX_TOOLS = 200
MAX_CURSOR_LENGTH = 1_024
MAX_SESSION_ID_LENGTH = 1_024
MAX_JSON_DEPTH = 32
MAX_JSON_NODES = 20_000
MAX_JSON_STRING_BYTES = 524_288

_RETRYABLE_STATUS = frozenset({408, 425, 429, 500, 502, 503, 504})
_PRE_WIRE_RETRYABLE_ERRORS = frozenset(
    {"dns_resolution_empty", "dns_resolution_failed"}
)
_POST_WIRE_POLICY_ERRORS = frozenset(
    {"response_body_too_large", "response_headers_too_large"}
)


class MCPHttpTransport(Protocol):
    """Execute one request through the platform's bounded HTTP boundary."""

    async def send(self, request: HttpEgressRequest) -> HttpEgressResponse: ...


class MCPDeliveryState(StrEnum):
    """What the client can prove about one failed request's delivery."""

    NOT_SENT = "not_sent"
    UNKNOWN = "unknown"
    SENT = "sent"


class MCPError(Exception):
    """Safe typed MCP failure with no provider-controlled text."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        delivery: MCPDeliveryState,
        retryable: bool = False,
        status_code: int | None = None,
        rpc_code: int | None = None,
        method: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.delivery = delivery
        self.retryable = retryable
        self.status_code = status_code
        self.rpc_code = rpc_code
        self.method = method


@dataclass(frozen=True, slots=True)
class MCPTool:
    """One server-declared tool contract."""

    name: str
    description: str
    input_schema: dict[str, Any] = field(default_factory=dict)
    output_schema: dict[str, Any] | None = None
    annotations: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class MCPToolResult:
    """Text-only result from one completed `tools/call`."""

    text: str = field(repr=False)
    is_error: bool = False


class MCPClient:
    """One org-scoped MCP session over one exact HTTPS endpoint."""

    def __init__(
        self,
        *,
        url: str,
        origin_headers: OriginBoundHeaders,
        transport: MCPHttpTransport,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        client_name: str = "eylo",
    ) -> None:
        origin, path = parse_https_target(url)
        if origin_headers.origin != origin:
            raise HttpEgressPolicyError(
                "credential_origin_mismatch",
                "MCP credentials do not match the configured server origin.",
            )
        self._url = url
        self._origin = origin
        self._configured_headers = origin_headers
        self._transport = transport
        self._policy = HttpDestinationPolicy(
            primary=HttpRoutePolicy(origin=origin, path_prefix=path),
            max_redirects=0,
        )
        self._timeout = timeout_seconds
        self._client_name = client_name
        self._session_id: str | None = None
        self._initialized = False
        self._next_id = 0

    async def list_tools(self) -> list[MCPTool]:
        """Return the complete bounded tool catalog, following MCP cursors."""
        await self._initialize()
        tools: list[MCPTool] = []
        seen_names: set[str] = set()
        seen_cursors: set[str] = set()
        cursor: str | None = None

        for _page in range(MAX_TOOL_PAGES):
            params = {"cursor": cursor} if cursor is not None else {}
            result = await self._call(
                "tools/list",
                params,
                response_body_limit=MAX_DISCOVERY_RESPONSE_BYTES,
            )
            entries = result.get("tools")
            if not isinstance(entries, list):
                raise _protocol_error("tools_list_invalid")
            for entry in entries:
                tool = _tool_of(entry)
                if tool.name in seen_names:
                    raise _protocol_error("tool_name_duplicate")
                seen_names.add(tool.name)
                tools.append(tool)
                if len(tools) > MAX_TOOLS:
                    raise _protocol_error("tool_count_exceeded")

            cursor = _next_cursor(result)
            if cursor is None:
                return tools
            if cursor in seen_cursors:
                raise _protocol_error("pagination_cursor_repeated")
            seen_cursors.add(cursor)

        raise _protocol_error("pagination_limit_exceeded")

    async def call_tool(
        self,
        name: str,
        arguments: Mapping[str, Any],
    ) -> MCPToolResult:
        """Invoke one tool exactly once after the session handshake."""
        if not isinstance(name, str) or not name:
            raise _request_error("tool_name_invalid")
        if not isinstance(arguments, Mapping):
            raise _request_error("tool_arguments_invalid")
        await self._initialize()
        result = await self._call(
            "tools/call",
            {"name": name, "arguments": dict(arguments)},
            response_body_limit=MAX_TOOL_RESULT_BYTES,
        )
        return _tool_result_of(result)

    async def _initialize(self) -> None:
        if self._initialized:
            return

        try:
            request_id = self._request_id()
            response = await self._post(
                {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": PROTOCOL_VERSION,
                        "capabilities": {},
                        "clientInfo": {
                            "name": self._client_name,
                            "version": "0.1.0",
                        },
                    },
                },
                response_body_limit=MAX_INITIALIZE_RESPONSE_BYTES,
            )
            result = _result_of(_decode_response(response, request_id))
            if result.get("protocolVersion") != PROTOCOL_VERSION:
                raise _protocol_error("protocol_version_unsupported")
            capabilities = result.get("capabilities")
            if not isinstance(capabilities, dict) or not isinstance(
                capabilities.get("tools"), dict
            ):
                raise _protocol_error("tools_capability_missing")
            if not isinstance(result.get("serverInfo"), dict):
                raise _protocol_error("server_info_invalid")
            self._session_id = _session_id_of(response)
        except MCPError as error:
            error.method = error.method or "initialize"
            raise

        await self._send_initialized_notification()
        self._initialized = True

    async def _send_initialized_notification(self) -> None:
        try:
            response = await self._post(
                {"jsonrpc": "2.0", "method": "notifications/initialized"},
                response_body_limit=1,
            )
            if response.status_code != 202 or response.body:
                raise MCPError(
                    "notification_rejected",
                    "MCP server did not accept the initialized notification.",
                    delivery=MCPDeliveryState.SENT,
                    status_code=response.status_code,
                )
        except MCPError as error:
            error.method = error.method or "notifications/initialized"
            raise

    async def _call(
        self,
        method: str,
        params: dict[str, Any],
        *,
        response_body_limit: int,
    ) -> dict[str, Any]:
        request_id = self._request_id()
        try:
            response = await self._post(
                {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "method": method,
                    "params": params,
                },
                response_body_limit=response_body_limit,
            )
            return _result_of(_decode_response(response, request_id))
        except MCPError as error:
            error.method = error.method or method
            raise

    async def _post(
        self,
        payload: dict[str, Any],
        *,
        response_body_limit: int,
    ) -> HttpEgressResponse:
        try:
            body = json.dumps(
                payload,
                ensure_ascii=False,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
        except (TypeError, ValueError):
            raise _request_error("request_json_invalid") from None

        public_headers = {
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        }
        if self._initialized or self._session_id is not None:
            public_headers["MCP-Protocol-Version"] = PROTOCOL_VERSION

        origin_values = dict(self._configured_headers.values)
        if self._session_id is not None:
            origin_values["Mcp-Session-Id"] = self._session_id
        try:
            request = HttpEgressRequest(
                method="POST",
                url=self._url,
                policy=self._policy,
                headers=public_headers,
                origin_headers=OriginBoundHeaders(
                    origin=self._origin,
                    values=origin_values,
                ),
                body=body,
                response_body_limit=response_body_limit,
                total_timeout_seconds=self._timeout,
            )
            response = await self._transport.send(request)
        except HttpEgressPolicyError as error:
            raise _egress_error(error) from None
        except TimeoutError:
            raise MCPError(
                "egress_outcome_unconfirmed",
                "MCP request delivery could not be confirmed.",
                delivery=MCPDeliveryState.UNKNOWN,
                retryable=True,
            ) from None

        if response.status_code != 200 and payload.get("id") is not None:
            raise _http_error(response.status_code)
        return response

    def _request_id(self) -> int:
        self._next_id += 1
        return self._next_id


def _decode_response(
    response: HttpEgressResponse,
    request_id: int,
) -> dict[str, Any]:
    content_types = response.header_values("Content-Type")
    if len(content_types) != 1:
        raise _protocol_error("content_type_invalid")
    media_type = content_types[0].partition(";")[0].strip().lower()
    if media_type == "application/json":
        message = _load_json(response.body)
        return _matching_response(message, request_id)
    if media_type == "text/event-stream":
        matches: list[dict[str, Any]] = []
        for data in _sse_data(response.body):
            message = _load_json(data)
            if _is_server_request(message):
                raise _protocol_error("server_request_unsupported")
            if _has_matching_id(message, request_id):
                matches.append(_matching_response(message, request_id))
        if len(matches) != 1:
            raise _protocol_error("response_match_invalid")
        return matches[0]
    raise _protocol_error("content_type_unsupported")


def _load_json(body: bytes) -> Any:
    try:
        value = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise _protocol_error("response_json_invalid") from None
    _validate_json_shape(value)
    return value


def _validate_json_shape(value: Any) -> None:
    nodes = 0
    stack: list[tuple[Any, int]] = [(value, 1)]
    while stack:
        current, depth = stack.pop()
        nodes += 1
        if nodes > MAX_JSON_NODES or depth > MAX_JSON_DEPTH:
            raise _protocol_error("response_structure_exceeded")
        if isinstance(current, str):
            if len(current.encode("utf-8")) > MAX_JSON_STRING_BYTES:
                raise _protocol_error("response_string_exceeded")
        elif isinstance(current, float) and not math.isfinite(current):
            raise _protocol_error("response_number_invalid")
        elif isinstance(current, list):
            stack.extend((item, depth + 1) for item in current)
        elif isinstance(current, dict):
            stack.extend((item, depth + 1) for item in current.values())


def _matching_response(message: Any, request_id: int) -> dict[str, Any]:
    if not isinstance(message, dict):
        raise _protocol_error("response_envelope_invalid")
    if _is_server_request(message):
        raise _protocol_error("server_request_unsupported")
    if message.get("jsonrpc") != "2.0" or not _has_matching_id(message, request_id):
        raise _protocol_error("response_envelope_invalid")
    return message


def _is_server_request(message: Any) -> bool:
    return (
        isinstance(message, dict)
        and isinstance(message.get("method"), str)
        and "id" in message
    )


def _has_matching_id(message: Any, request_id: int) -> bool:
    return (
        isinstance(message, dict)
        and type(message.get("id")) is type(request_id)
        and message.get("id") == request_id
    )


def _result_of(message: dict[str, Any]) -> dict[str, Any]:
    if "error" in message:
        error = message["error"]
        rpc_code = error.get("code") if isinstance(error, dict) else None
        raise MCPError(
            "mcp_rpc_error",
            "MCP server returned a JSON-RPC error.",
            delivery=MCPDeliveryState.SENT,
            rpc_code=(
                rpc_code
                if isinstance(rpc_code, int) and not isinstance(rpc_code, bool)
                else None
            ),
        )
    result = message.get("result")
    if not isinstance(result, dict):
        raise _protocol_error("response_result_invalid")
    return result


def _sse_data(body: bytes) -> tuple[bytes, ...]:
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError:
        raise _protocol_error("response_sse_invalid") from None
    events: list[bytes] = []
    data_lines: list[str] = []
    for line in text.splitlines():
        if not line:
            if data_lines:
                events.append("\n".join(data_lines).encode("utf-8"))
                data_lines = []
            continue
        if line.startswith("data:"):
            data_lines.append(line[5:].lstrip(" "))
    if data_lines:
        events.append("\n".join(data_lines).encode("utf-8"))
    if not events:
        raise _protocol_error("response_sse_empty")
    return tuple(events)


def _session_id_of(response: HttpEgressResponse) -> str | None:
    values = response.header_values("Mcp-Session-Id")
    if not values:
        return None
    if len(values) != 1:
        raise _protocol_error("session_id_invalid")
    session_id = values[0]
    if (
        not session_id
        or len(session_id) > MAX_SESSION_ID_LENGTH
        or any(
            ord(character) < 0x21 or ord(character) > 0x7E for character in session_id
        )
    ):
        raise _protocol_error("session_id_invalid")
    return session_id


def _next_cursor(result: dict[str, Any]) -> str | None:
    if "nextCursor" not in result:
        return None
    cursor = result["nextCursor"]
    if not isinstance(cursor, str) or not cursor or len(cursor) > MAX_CURSOR_LENGTH:
        raise _protocol_error("pagination_cursor_invalid")
    return cursor


def _tool_of(entry: Any) -> MCPTool:
    if not isinstance(entry, dict):
        raise _protocol_error("tool_definition_invalid")
    name = entry.get("name")
    description = entry.get("description", "")
    input_schema = entry.get("inputSchema")
    output_schema = entry.get("outputSchema")
    annotations = entry.get("annotations", {})
    if (
        not isinstance(name, str)
        or not name
        or not isinstance(description, str)
        or not isinstance(input_schema, dict)
        or (output_schema is not None and not isinstance(output_schema, dict))
        or not isinstance(annotations, dict)
    ):
        raise _protocol_error("tool_definition_invalid")
    return MCPTool(
        name=name,
        description=description,
        input_schema=input_schema,
        output_schema=output_schema,
        annotations=annotations,
    )


def _tool_result_of(result: dict[str, Any]) -> MCPToolResult:
    if "structuredContent" in result:
        raise _protocol_error("structured_result_unsupported")
    content = result.get("content")
    if not isinstance(content, list):
        raise _protocol_error("tool_content_invalid")
    parts: list[str] = []
    size = 0
    for block in content:
        if not isinstance(block, dict) or block.get("type") != "text":
            raise _protocol_error("tool_content_unsupported")
        text = block.get("text")
        if not isinstance(text, str):
            raise _protocol_error("tool_content_invalid")
        size += len(text.encode("utf-8"))
        if size > MAX_TOOL_RESULT_BYTES:
            raise _protocol_error("tool_result_exceeded")
        parts.append(text)
    is_error = result.get("isError", False)
    if not isinstance(is_error, bool):
        raise _protocol_error("tool_error_flag_invalid")
    return MCPToolResult(text="\n".join(parts), is_error=is_error)


def _http_error(status_code: int) -> MCPError:
    return MCPError(
        "http_status_error",
        "MCP server rejected the request.",
        delivery=MCPDeliveryState.SENT,
        retryable=status_code in _RETRYABLE_STATUS,
        status_code=status_code,
    )


def _egress_error(error: HttpEgressPolicyError) -> MCPError:
    if error.code in _PRE_WIRE_RETRYABLE_ERRORS:
        return MCPError(
            "egress_unavailable",
            "MCP server is temporarily unavailable.",
            delivery=MCPDeliveryState.NOT_SENT,
            retryable=True,
        )
    if error.code in _POST_WIRE_POLICY_ERRORS:
        delivery = MCPDeliveryState.SENT
    elif error.code == "transport_failed":
        delivery = MCPDeliveryState.UNKNOWN
    else:
        delivery = MCPDeliveryState.NOT_SENT
    return MCPError(
        "egress_policy_rejected"
        if delivery is MCPDeliveryState.NOT_SENT
        else "egress_outcome_unconfirmed",
        "MCP request failed at the outbound boundary.",
        delivery=delivery,
        retryable=delivery is not MCPDeliveryState.NOT_SENT,
    )


def _request_error(code: str) -> MCPError:
    return MCPError(
        code,
        "MCP request is invalid.",
        delivery=MCPDeliveryState.NOT_SENT,
    )


def _protocol_error(code: str) -> MCPError:
    return MCPError(
        code,
        "MCP server returned an unsupported protocol response.",
        delivery=MCPDeliveryState.SENT,
    )


__all__ = [
    "MCPClient",
    "MCPDeliveryState",
    "MCPError",
    "MCPHttpTransport",
    "MCPTool",
    "MCPToolResult",
    "PROTOCOL_VERSION",
]
