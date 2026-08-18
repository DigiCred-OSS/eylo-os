"""API-backed operator commands for the Eylo CLI.

The public FastAPI contract is the command catalog.  A small stable list of
resource names keeps ``eylo --help`` useful while the live OpenAPI document
supplies the actions, parameters, and paths for the selected deployment.
"""

from __future__ import annotations

import json
import mimetypes
import os
import re
import secrets
import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import Request, urlopen
from uuid import UUID

import typer
from rich.console import Console
from rich.table import Table

HTTP_METHODS = frozenset({"get", "post", "put", "patch", "delete"})
RESOURCE_ALIASES = {
    "agent-swarm": "agent-swarms",
    "aggregate": "conversation-aggregates",
    "organizations": "voice-recordings",
    "public": "public-sessions",
    "root": "system",
    "widget": "widget-api",
}
RESOURCE_NOUNS = {
    "agent-swarms": {"agent_swarm", "agent_swarms"},
    "conversation-aggregates": {"aggregate", "aggregates", "conversation_aggregate"},
    "public-sessions": {"public_session", "session"},
    "voice-recordings": {"recording", "recordings"},
    "system": {"system"},
}

# Stable discovery names. The live OpenAPI document remains authoritative for
# actions, parameters, and paths.
API_RESOURCES = (
    "agent-runs",
    "agent-stats",
    "agent-swarms",
    "agents",
    "analytics",
    "auth",
    "calls",
    "campaigns",
    "capabilities",
    "contacts",
    "conversation-aggregates",
    "conversations",
    "curated-connections",
    "curated-integrations",
    "curated-vendors",
    "deletions",
    "email-configs",
    "embedding-configs",
    "events",
    "knowledgebases",
    "llm-configs",
    "mcp-servers",
    "members",
    "memories",
    "memory-configs",
    "messages",
    "objectives",
    "oauth",
    "participants",
    "phone-numbers",
    "provider-onboarding",
    "public-sessions",
    "reranking-configs",
    "sandbox-configs",
    "sandboxes",
    "schedules",
    "storage-configs",
    "stt-configs",
    "system",
    "telephony",
    "telephony-configs",
    "templates",
    "tools",
    "tts-configs",
    "voice",
    "voice-recordings",
    "voice-sessions",
    "webrtc-configs",
    "widget-api",
    "widget-invitations",
)

_SIMPLE_VERBS = {
    "create": "create",
    "delete": "delete",
    "deactivate": "delete",
    "get": "get",
    "list": "list",
    "patch": "update",
    "read": "get",
    "update": "update",
}
_DESTRUCTIVE_WORDS = frozenset(
    {"cancel", "delete", "destroy", "disable", "remove", "revoke", "withdraw"}
)
_PAIR = re.compile(r"^(?P<key>[^=]+)=(?P<value>.*)$", re.DOTALL)
_PATH_PARAMETER = re.compile(r"\{([^{}]+)\}")


class CliUsageError(RuntimeError):
    """The command is incomplete or contradicts the API contract."""


class ApiTransportError(RuntimeError):
    """The target API could not be reached."""


class ApiResponseError(RuntimeError):
    """The API returned a non-success response."""

    def __init__(self, status_code: int, method: str, path: str, detail: str):
        self.status_code = status_code
        self.method = method
        self.path = path
        self.detail = detail
        super().__init__(f"HTTP {status_code}: {detail}")


@dataclass(frozen=True, slots=True)
class CliOverrides:
    base_url: str | None = None
    organization_id: str | None = None
    token: str | None = None


@dataclass(frozen=True, slots=True)
class CliConfig:
    base_url: str | None
    organization_id: str | None
    token: str | None

    def require_base_url(self) -> str:
        if self.base_url is None:
            raise CliUsageError(
                "API target missing. Run: eylo configure --base-url https://api.example.com"
            )
        return self.base_url

    def require_organization_id(self) -> str:
        if self.organization_id is None:
            raise CliUsageError(
                "Organization missing. Run: eylo configure --organization-id <uuid>"
            )
        return self.organization_id


@dataclass(frozen=True, slots=True)
class Operation:
    resource: str
    action: str
    handler_name: str
    operation_id: str
    method: str
    path: str
    summary: str
    parameters: tuple[dict[str, Any], ...]
    request_body: dict[str, Any] | None
    security: tuple[dict[str, Any], ...]
    required_inputs: tuple[str, ...]

    @property
    def path_parameters(self) -> tuple[str, ...]:
        return tuple(_PATH_PARAMETER.findall(self.path))

    @property
    def destructive(self) -> bool:
        if self.method == "DELETE":
            return True
        words = set(self.handler_name.split("_"))
        return bool(words & _DESTRUCTIVE_WORDS)

    @property
    def aliases(self) -> frozenset[str]:
        return frozenset(
            {
                self.action,
                self.handler_name.replace("_", "-"),
                self.operation_id,
            }
        )


@dataclass(frozen=True, slots=True)
class ApiResponse:
    status_code: int
    data: Any


class ConfigStore:
    """Persist non-secret config separately from one mode-0600 credential file."""

    def __init__(self, root: Path | None = None):
        configured_root = os.getenv("EYLO_CONFIG_DIR")
        self.root = root or (
            Path(configured_root).expanduser()
            if configured_root
            else Path.home() / ".config" / "eylo"
        )
        self.config_path = self.root / "config.json"
        self.credentials_path = self.root / "credentials.json"

    def load(self, overrides: CliOverrides | None = None) -> CliConfig:
        overrides = overrides or CliOverrides()
        config = self._read_json(self.config_path)
        credentials = self._read_credentials()
        base_url = (
            overrides.base_url
            or os.getenv("EYLO_BASE_URL")
            or _optional_string(config.get("base_url"))
        )
        organization_id = (
            overrides.organization_id
            or os.getenv("EYLO_ORGANIZATION_ID")
            or _optional_string(config.get("organization_id"))
        )
        token = (
            overrides.token
            or os.getenv("EYLO_TOKEN")
            or _optional_string(credentials.get("access_token"))
        )
        if base_url is not None:
            base_url = normalize_base_url(base_url)
        if organization_id is not None:
            organization_id = normalize_organization_id(organization_id)
        return CliConfig(base_url, organization_id, token)

    def update_config(
        self,
        *,
        base_url: str | None = None,
        organization_id: str | None = None,
        clear_organization: bool = False,
    ) -> CliConfig:
        current = self._read_json(self.config_path)
        if base_url is not None:
            current["base_url"] = normalize_base_url(base_url)
        if organization_id is not None:
            current["organization_id"] = normalize_organization_id(organization_id)
        elif clear_organization:
            current.pop("organization_id", None)
        self._write_json(self.config_path, current, mode=0o600)
        return self.load()

    def save_token(self, token: str) -> None:
        if not token:
            raise CliUsageError("The API returned an empty access token.")
        self._write_json(
            self.credentials_path,
            {"access_token": token},
            mode=0o600,
        )

    def clear_token(self) -> None:
        try:
            self.credentials_path.unlink()
        except FileNotFoundError:
            pass

    def _read_credentials(self) -> dict[str, Any]:
        if not self.credentials_path.exists():
            return {}
        mode = stat.S_IMODE(self.credentials_path.stat().st_mode)
        if mode & 0o077:
            raise CliUsageError(
                f"Credential file is too permissive ({mode:o}). "
                f"Run: chmod 600 {self.credentials_path}"
            )
        return self._read_json(self.credentials_path)

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        try:
            value = json.loads(path.read_text())
        except FileNotFoundError:
            return {}
        except (OSError, json.JSONDecodeError) as error:
            raise CliUsageError(f"Unable to read CLI config {path}: {error}") from None
        if not isinstance(value, dict):
            raise CliUsageError(f"CLI config must contain a JSON object: {path}")
        return value

    def _write_json(self, path: Path, value: Mapping[str, Any], *, mode: int) -> None:
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(self.root, 0o700)
        payload = json.dumps(value, indent=2, sort_keys=True) + "\n"
        temporary_name: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                dir=self.root,
                prefix=f".{path.name}.",
                delete=False,
            ) as temporary:
                temporary_name = temporary.name
                temporary.write(payload)
                temporary.flush()
                os.fchmod(temporary.fileno(), mode)
            os.replace(temporary_name, path)
            temporary_name = None
        finally:
            if temporary_name is not None:
                Path(temporary_name).unlink(missing_ok=True)


class ApiClient:
    """Small synchronous HTTP boundary used by every API-backed CLI command."""

    def __init__(self, config: CliConfig, *, timeout: float = 30.0):
        self.config = config
        self.timeout = timeout

    def openapi(self) -> dict[str, Any]:
        response = self.request("GET", "/openapi.json", authenticated=False)
        if not isinstance(response.data, dict):
            raise ApiTransportError(
                "Target /openapi.json did not return a JSON object."
            )
        return response.data

    def request(
        self,
        method: str,
        path: str,
        *,
        query: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        json_body: Any = None,
        form: Mapping[str, Any] | None = None,
        uploads: Mapping[str, Path] | None = None,
        authenticated: bool,
    ) -> ApiResponse:
        base_url = self.config.require_base_url()
        url = f"{base_url}{path}"
        if query:
            url = f"{url}?{urlencode(query, doseq=True)}"

        request_headers = {"Accept": "application/json"}
        if authenticated:
            if self.config.token is None:
                raise CliUsageError("Login required. Run: eylo auth login")
            request_headers["Authorization"] = f"Bearer {self.config.token}"
        if headers:
            request_headers.update(headers)

        body: bytes | None = None
        if uploads:
            body, content_type = encode_multipart(form or {}, uploads)
            request_headers["Content-Type"] = content_type
        elif form is not None:
            body = urlencode(form, doseq=True).encode()
            request_headers["Content-Type"] = "application/x-www-form-urlencoded"
        elif json_body is not None:
            body = json.dumps(json_body).encode()
            request_headers["Content-Type"] = "application/json"

        request = Request(url, data=body, headers=request_headers, method=method)
        try:
            with urlopen(request, timeout=self.timeout) as response:
                raw = response.read()
                return ApiResponse(
                    response.status, decode_response(raw, response.headers)
                )
        except HTTPError as error:
            raw = error.read()
            detail = error_detail(decode_response(raw, error.headers))
            raise ApiResponseError(error.code, method, path, detail) from None
        except (TimeoutError, URLError, OSError) as error:
            reason = getattr(error, "reason", error)
            raise ApiTransportError(f"Unable to reach {base_url}: {reason}") from None


def normalize_base_url(value: str) -> str:
    candidate = value.strip().rstrip("/")
    parsed = urlsplit(candidate)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise CliUsageError("Base URL must be an absolute http:// or https:// URL.")
    if parsed.username is not None or parsed.password is not None:
        raise CliUsageError("Base URL must not contain credentials.")
    local_hosts = {"127.0.0.1", "::1", "localhost"}
    if parsed.scheme == "http" and parsed.hostname not in local_hosts:
        raise CliUsageError("Remote API targets must use HTTPS.")
    if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        raise CliUsageError(
            "Base URL must be an origin without a path, query, or fragment."
        )
    return candidate


def normalize_organization_id(value: str) -> str:
    try:
        return str(UUID(value.strip()))
    except ValueError:
        raise CliUsageError("Organization ID must be a UUID.") from None


def resource_for_path(path: str) -> str:
    relative = path.removeprefix("/api/")
    if relative.startswith("{organization_id}/"):
        relative = relative.removeprefix("{organization_id}/")
    literal = relative.split("/", maxsplit=1)[0] or "root"
    return RESOURCE_ALIASES.get(literal, literal)


def operations_from_openapi(schema: Mapping[str, Any]) -> tuple[Operation, ...]:
    discovered: list[dict[str, Any]] = []
    for path, path_item in schema.get("paths", {}).items():
        if not isinstance(path_item, dict):
            continue
        shared_parameters = tuple(path_item.get("parameters", ()))
        for method, definition in path_item.items():
            if method not in HTTP_METHODS or not isinstance(definition, dict):
                continue
            operation_id = str(definition.get("operationId") or f"{method}_{path}")
            handler_name = operation_id.split("_api_", maxsplit=1)[0]
            discovered.append(
                {
                    "resource": resource_for_path(path),
                    "handler_name": handler_name,
                    "operation_id": operation_id,
                    "method": method.upper(),
                    "path": path,
                    "summary": str(definition.get("summary") or handler_name),
                    "parameters": shared_parameters
                    + tuple(definition.get("parameters", ())),
                    "request_body": definition.get("requestBody"),
                    "security": tuple(definition.get("security", ())),
                    "required_inputs": required_input_hints(
                        schema,
                        shared_parameters + tuple(definition.get("parameters", ())),
                        definition.get("requestBody"),
                    ),
                }
            )

    candidates = [
        preferred_action(item["resource"], item["handler_name"], item["method"])
        for item in discovered
    ]
    counts: dict[tuple[str, str], int] = {}
    for item, candidate in zip(discovered, candidates, strict=True):
        key = (item["resource"], candidate)
        counts[key] = counts.get(key, 0) + 1

    operations: list[Operation] = []
    used: set[tuple[str, str]] = set()
    for item, candidate in zip(discovered, candidates, strict=True):
        action = candidate
        if counts[(item["resource"], candidate)] > 1:
            action = item["handler_name"].replace("_", "-")
        key = (item["resource"], action)
        if key in used:
            action = f"{action}-{item['method'].lower()}"
            key = (item["resource"], action)
        if key in used:
            raise CliUsageError(
                f"Ambiguous API operation mapping for {item['method']} {item['path']}"
            )
        used.add(key)
        operations.append(Operation(action=action, **item))
    return tuple(sorted(operations, key=lambda item: (item.resource, item.action)))


def required_input_hints(
    openapi: Mapping[str, Any],
    parameters: Sequence[Mapping[str, Any]],
    request_body: Mapping[str, Any] | None,
) -> tuple[str, ...]:
    """Describe required non-path input using operator-facing CLI flags."""
    hints: list[str] = []
    for parameter in parameters:
        if not parameter.get("required") or parameter.get("in") == "path":
            continue
        location = str(parameter.get("in"))
        name = str(parameter.get("name"))
        flag = {"query": "--query", "header": "--header"}.get(location)
        if flag:
            hints.append(f"{flag} {name}=VALUE")

    if not request_body or not request_body.get("required"):
        return tuple(hints)
    content = request_body.get("content", {})
    for content_type, option in (
        ("application/json", "--set"),
        ("application/x-www-form-urlencoded", "--form"),
        ("multipart/form-data", "--form/--upload"),
    ):
        media = content.get(content_type)
        if not isinstance(media, Mapping):
            continue
        body_schema = resolve_openapi_schema(openapi, media.get("schema", {}))
        required = body_schema.get("required", ())
        if required:
            hints.extend(f"{option} {name}=VALUE" for name in required)
        else:
            hints.append(f"{option} BODY")
        break
    return tuple(hints)


def resolve_openapi_schema(
    openapi: Mapping[str, Any], raw_schema: Mapping[str, Any]
) -> dict[str, Any]:
    """Resolve the local refs/allOf needed to display body requirements."""
    reference = raw_schema.get("$ref")
    if reference:
        prefix = "#/components/schemas/"
        if not str(reference).startswith(prefix):
            return dict(raw_schema)
        name = str(reference).removeprefix(prefix)
        components = openapi.get("components", {}).get("schemas", {})
        target = components.get(name, {})
        return resolve_openapi_schema(openapi, target)
    if not raw_schema.get("allOf"):
        return dict(raw_schema)
    merged: dict[str, Any] = {"type": "object", "properties": {}, "required": []}
    for part in raw_schema["allOf"]:
        resolved = resolve_openapi_schema(openapi, part)
        merged["properties"].update(resolved.get("properties", {}))
        merged["required"].extend(resolved.get("required", ()))
    return merged


def preferred_action(resource: str, handler_name: str, method: str) -> str:
    cleaned = handler_name.removesuffix("_route")
    if cleaned == "list_all":
        return "list"
    if cleaned == "read_one":
        return "get"
    if cleaned in {"create", "update", "cancel"}:
        return cleaned

    nouns = set(RESOURCE_NOUNS.get(resource, ()))
    normalized_resource = resource.replace("-", "_")
    nouns.update({normalized_resource, normalized_resource.removesuffix("s")})
    for verb, action in _SIMPLE_VERBS.items():
        for noun in nouns:
            if cleaned == f"{verb}_{noun}":
                if action == "update" and method == "PUT":
                    return "replace"
                return action
    return cleaned.replace("_", "-")


def select_operation(
    operations: Sequence[Operation], resource: str, action: str
) -> Operation:
    matches = [
        operation
        for operation in operations
        if operation.resource == resource and action in operation.aliases
    ]
    if not matches:
        available = ", ".join(
            operation.action
            for operation in operations
            if operation.resource == resource
        )
        raise CliUsageError(
            f"Unknown {resource} action '{action}'. Available: {available or 'none'}"
        )
    if len(matches) > 1:
        choices = ", ".join(operation.action for operation in matches)
        raise CliUsageError(f"Ambiguous action '{action}'. Choose one of: {choices}")
    return matches[0]


def build_request(
    operation: Operation,
    config: CliConfig,
    identifiers: Sequence[str],
    *,
    data: str | None,
    data_file: Path | None,
    set_values: Sequence[str],
    query_values: Sequence[str],
    header_values: Sequence[str],
    form_values: Sequence[str],
    upload_values: Sequence[str],
) -> tuple[str, dict[str, Any]]:
    path_values: dict[str, str] = {}
    remaining_path_parameters = list(operation.path_parameters)
    if "organization_id" in remaining_path_parameters:
        path_values["organization_id"] = config.require_organization_id()
        remaining_path_parameters.remove("organization_id")
    if len(identifiers) != len(remaining_path_parameters):
        expected = " ".join(f"<{name}>" for name in remaining_path_parameters)
        raise CliUsageError(
            f"{operation.resource} {operation.action} expects IDs: {expected or 'none'}"
        )
    path_values.update(zip(remaining_path_parameters, identifiers, strict=True))
    path = operation.path
    for name, value in path_values.items():
        path = path.replace(f"{{{name}}}", quote(str(value), safe=""))

    query = parse_pairs(query_values, "query")
    headers = {
        key: str(value) for key, value in parse_pairs(header_values, "header").items()
    }
    form = parse_pairs(form_values, "form") if form_values else None
    uploads = parse_uploads(upload_values)
    validate_required_parameters(operation, query, headers)

    json_body = load_json_body(data, data_file)
    if set_values:
        if json_body is None:
            json_body = {}
        if not isinstance(json_body, dict):
            raise CliUsageError("--set requires a JSON object body.")
        for key, raw_value in parse_raw_pairs(set_values, "set"):
            set_nested(json_body, key, coerce_value(raw_value))

    if operation.request_body and operation.request_body.get("required"):
        if json_body is None and form is None and not uploads:
            raise CliUsageError(
                f"{operation.resource} {operation.action} requires a body. "
                "Use --set key=value, --data JSON, --data-file PATH, or --form."
            )

    return path, {
        "query": query or None,
        "headers": headers or None,
        "json_body": json_body,
        "form": form,
        "uploads": uploads or None,
        "authenticated": bool(operation.security),
    }


def validate_required_parameters(
    operation: Operation,
    query: Mapping[str, Any],
    headers: Mapping[str, Any],
) -> None:
    missing: list[str] = []
    normalized_headers = {key.lower() for key in headers}
    for parameter in operation.parameters:
        if not parameter.get("required"):
            continue
        name = str(parameter.get("name"))
        location = parameter.get("in")
        if location == "query" and name not in query:
            missing.append(f"--query {name}=VALUE")
        elif location == "header" and name.lower() not in normalized_headers:
            missing.append(f"--header {name}=VALUE")
    if missing:
        raise CliUsageError("Missing required input: " + ", ".join(missing))


def load_json_body(data: str | None, data_file: Path | None) -> Any:
    if data is not None and data_file is not None:
        raise CliUsageError("Use only one of --data or --data-file.")
    if data_file is not None:
        try:
            data = data_file.read_text()
        except OSError as error:
            raise CliUsageError(f"Unable to read {data_file}: {error}") from None
    if data is None:
        return None
    try:
        return json.loads(data)
    except json.JSONDecodeError as error:
        raise CliUsageError(f"Invalid JSON body: {error.msg}") from None


def parse_pairs(values: Sequence[str], label: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, raw_value in parse_raw_pairs(values, label):
        value = coerce_value(raw_value)
        existing = result.get(key)
        if existing is None:
            result[key] = value
        elif isinstance(existing, list):
            existing.append(value)
        else:
            result[key] = [existing, value]
    return result


def parse_raw_pairs(values: Sequence[str], label: str) -> list[tuple[str, str]]:
    parsed: list[tuple[str, str]] = []
    for value in values:
        match = _PAIR.match(value)
        if match is None or not match.group("key").strip():
            raise CliUsageError(f"--{label} expects KEY=VALUE: {value!r}")
        parsed.append((match.group("key").strip(), match.group("value")))
    return parsed


def parse_uploads(values: Sequence[str]) -> dict[str, Path]:
    uploads: dict[str, Path] = {}
    for key, value in parse_raw_pairs(values, "upload"):
        path = Path(value).expanduser()
        if not path.is_file():
            raise CliUsageError(f"Upload file does not exist: {path}")
        uploads[key] = path
    return uploads


def coerce_value(value: str) -> Any:
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def set_nested(target: dict[str, Any], dotted_key: str, value: Any) -> None:
    parts = dotted_key.split(".")
    if any(not part for part in parts):
        raise CliUsageError(f"Invalid dotted body key: {dotted_key!r}")
    current = target
    for part in parts[:-1]:
        nested = current.setdefault(part, {})
        if not isinstance(nested, dict):
            raise CliUsageError(
                f"Body key conflicts with an existing value: {dotted_key}"
            )
        current = nested
    current[parts[-1]] = value


def encode_multipart(
    fields: Mapping[str, Any], uploads: Mapping[str, Path]
) -> tuple[bytes, str]:
    boundary = f"eylo-{secrets.token_hex(16)}"
    chunks: list[bytes] = []
    for name, value in fields.items():
        values = value if isinstance(value, list) else [value]
        for item in values:
            chunks.extend(
                [
                    f"--{boundary}\r\n".encode(),
                    f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(),
                    str(item).encode(),
                    b"\r\n",
                ]
            )
    for name, path in uploads.items():
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        chunks.extend(
            [
                f"--{boundary}\r\n".encode(),
                (
                    f'Content-Disposition: form-data; name="{name}"; '
                    f'filename="{path.name}"\r\n'
                ).encode(),
                f"Content-Type: {content_type}\r\n\r\n".encode(),
                path.read_bytes(),
                b"\r\n",
            ]
        )
    chunks.append(f"--{boundary}--\r\n".encode())
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


def decode_response(raw: bytes, headers: Mapping[str, Any]) -> Any:
    if not raw:
        return None
    content_type = str(headers.get("Content-Type", ""))
    if "json" in content_type:
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass
    return raw.decode(errors="replace")


def error_detail(data: Any) -> str:
    if isinstance(data, dict):
        detail = data.get("detail", data)
    else:
        detail = data
    rendered = (
        json.dumps(detail, ensure_ascii=False)
        if not isinstance(detail, str)
        else detail
    )
    return rendered[:2000]


def render_data(console: Console, data: Any, *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(data, indent=2, sort_keys=True, default=str))
        return
    rows, metadata = table_rows(data)
    if rows:
        columns = table_columns(rows)
        table = Table(show_header=True, header_style="bold")
        for column in columns:
            table.add_column(column)
        for row in rows:
            table.add_row(*(compact_value(row.get(column)) for column in columns))
        console.print(table)
        if metadata:
            console.print(f"[dim]{metadata}[/]")
        return
    if data is None:
        console.print("[green]Done.[/]")
    elif isinstance(data, str):
        console.print(data)
    else:
        console.print_json(data=data, default=str)


def table_rows(data: Any) -> tuple[list[dict[str, Any]], str | None]:
    if isinstance(data, list) and all(isinstance(item, dict) for item in data):
        return data, f"{len(data)} item(s)"
    if isinstance(data, dict):
        for key in ("data", "items", "results"):
            value = data.get(key)
            if isinstance(value, list) and all(
                isinstance(item, dict) for item in value
            ):
                metadata = ", ".join(
                    f"{name}={compact_value(item)}"
                    for name, item in data.items()
                    if name != key and not isinstance(item, (dict, list))
                )
                return value, metadata or f"{len(value)} item(s)"
    return [], None


def table_columns(rows: Sequence[Mapping[str, Any]]) -> list[str]:
    preferred = [
        "id",
        "name",
        "slug",
        "status",
        "lifecycle",
        "created_at",
        "updated_at",
    ]
    available = {key for row in rows[:20] for key in row}
    columns = [column for column in preferred if column in available]
    columns.extend(sorted(available - set(columns)))
    return columns[:10]


def compact_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        rendered = json.dumps(value, default=str, separators=(",", ":"))
    else:
        rendered = str(value)
    return rendered if len(rendered) <= 80 else f"{rendered[:77]}..."


def print_actions(
    console: Console,
    operations: Iterable[Operation],
    resource: str,
    *,
    as_json: bool,
) -> None:
    selected = [operation for operation in operations if operation.resource == resource]
    if as_json:
        render_data(
            console,
            [
                {
                    "action": operation.action,
                    "method": operation.method,
                    "path": operation.path,
                    "identifiers": [
                        name
                        for name in operation.path_parameters
                        if name != "organization_id"
                    ],
                    "required_inputs": list(operation.required_inputs),
                    "destructive": operation.destructive,
                    "summary": operation.summary,
                }
                for operation in selected
            ],
            as_json=True,
        )
        return
    table = Table(title=resource, show_header=True, header_style="bold")
    table.add_column("Action")
    table.add_column("Method")
    table.add_column("Path / required IDs")
    table.add_column("Required input")
    table.add_column("Summary")
    for operation in selected:
        ids = [name for name in operation.path_parameters if name != "organization_id"]
        suffix = " " + " ".join(f"<{name}>" for name in ids) if ids else ""
        table.add_row(
            operation.action,
            operation.method,
            f"{operation.path}{suffix}",
            "\n".join(operation.required_inputs) or "—",
            operation.summary,
        )
    console.print(table)


def execute_resource(
    *,
    console: Console,
    store: ConfigStore,
    overrides: CliOverrides,
    resource: str,
    action: str,
    identifiers: Sequence[str],
    data: str | None,
    data_file: Path | None,
    set_values: Sequence[str],
    query_values: Sequence[str],
    header_values: Sequence[str],
    form_values: Sequence[str],
    upload_values: Sequence[str],
    yes: bool,
    as_json: bool,
    timeout: float,
) -> None:
    config = store.load(overrides)
    if resource == "auth" and action == "status":
        render_data(
            console,
            resolve_auth_status(config, timeout=timeout),
            as_json=as_json,
        )
        return
    if resource == "auth" and action == "logout" and config.base_url is None:
        store.clear_token()
        render_data(console, {"authenticated": False}, as_json=as_json)
        return

    client = ApiClient(config, timeout=timeout)
    operations = operations_from_openapi(client.openapi())
    if action in {"actions", "help"}:
        print_actions(console, operations, resource, as_json=as_json)
        return
    operation = select_operation(operations, resource, action)

    if resource == "auth" and operation.action in {"login", "register"}:
        data, set_values = interactive_auth_body(
            operation.action, data, data_file, set_values
        )
    path, request_options = build_request(
        operation,
        config,
        identifiers,
        data=data,
        data_file=data_file,
        set_values=set_values,
        query_values=query_values,
        header_values=header_values,
        form_values=form_values,
        upload_values=upload_values,
    )
    if operation.destructive and not yes:
        typer.confirm(
            f"Run {operation.method} {path}? This action may be irreversible.",
            abort=True,
        )
    response = client.request(operation.method, path, **request_options)

    if resource == "auth" and operation.action == "login":
        complete_login(console, store, overrides, response.data, timeout, as_json)
        return
    if resource == "auth" and operation.action == "logout":
        store.clear_token()
        render_data(console, {"authenticated": False}, as_json=as_json)
        return
    render_data(console, response.data, as_json=as_json)


def interactive_auth_body(
    action: str,
    data: str | None,
    data_file: Path | None,
    set_values: Sequence[str],
) -> tuple[str | None, Sequence[str]]:
    if data is not None or data_file is not None or set_values:
        return data, set_values
    email = typer.prompt("Email")
    password_label = "New password" if action == "register" else "Password"
    password = typer.prompt(password_label, hide_input=True)
    return json.dumps({"email": email, "password": password}), ()


def complete_login(
    console: Console,
    store: ConfigStore,
    overrides: CliOverrides,
    data: Any,
    timeout: float,
    as_json: bool,
) -> None:
    access_token = response_field(data, "access_token")
    if not isinstance(access_token, str):
        raise ApiTransportError("Login response did not contain an access token.")
    store.save_token(access_token)
    authenticated = store.load(
        CliOverrides(overrides.base_url, overrides.organization_id)
    )
    me = (
        ApiClient(authenticated, timeout=timeout)
        .request("GET", "/api/auth/me", authenticated=True)
        .data
    )
    organization_id = response_field(me, "organization_id")
    if organization_id:
        store.update_config(organization_id=str(organization_id))
    summary = {
        "authenticated": True,
        "email": response_field(me, "email"),
        "organization_id": organization_id,
    }
    render_data(console, summary, as_json=as_json)


def resolve_auth_status(config: CliConfig, *, timeout: float) -> dict[str, Any]:
    status: dict[str, Any] = {
        "base_url": config.base_url,
        "organization_id": config.organization_id,
        "authenticated": False,
    }
    if config.base_url is None or config.token is None:
        return status

    try:
        me = (
            ApiClient(config, timeout=timeout)
            .request("GET", "/api/auth/me", authenticated=True)
            .data
        )
    except ApiResponseError as error:
        if error.status_code == 401:
            return status
        raise

    status["authenticated"] = True
    status["email"] = response_field(me, "email")
    status["organization_id"] = (
        response_field(me, "organization_id") or config.organization_id
    )
    return status


def render_config_status(console: Console, config: CliConfig, *, as_json: bool) -> None:
    render_data(
        console,
        {
            "base_url": config.base_url,
            "organization_id": config.organization_id,
            "credential_stored": config.token is not None,
        },
        as_json=as_json,
    )


def _optional_string(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def response_field(data: Any, snake_name: str) -> Any:
    if not isinstance(data, dict):
        return None
    camel_name = snake_name.split("_")[0] + "".join(
        part.title() for part in snake_name.split("_")[1:]
    )
    return data.get(snake_name, data.get(camel_name))


def context_overrides(context: typer.Context) -> CliOverrides:
    value = context.ensure_object(dict).get("api_overrides")
    return value if isinstance(value, CliOverrides) else CliOverrides()


def register_api_commands(app: typer.Typer, console: Console) -> None:
    """Register stable resource entrypoints backed by the live API contract."""

    @app.command(name="configure", help="Set or show the target Eylo API context")
    def configure_command(
        context: typer.Context,
        base_url: str | None = typer.Option(None, "--base-url", help="API origin"),
        organization_id: str | None = typer.Option(
            None, "--organization-id", "--org-id", help="Default organization UUID"
        ),
        clear_organization: bool = typer.Option(
            False, "--clear-organization", help="Remove the saved organization"
        ),
        as_json: bool = typer.Option(
            False, "--json", help="Emit machine-readable JSON"
        ),
    ) -> None:
        store = ConfigStore()
        try:
            if (
                base_url is not None
                or organization_id is not None
                or clear_organization
            ):
                config = store.update_config(
                    base_url=base_url,
                    organization_id=organization_id,
                    clear_organization=clear_organization,
                )
            else:
                config = store.load(context_overrides(context))
            render_config_status(console, config, as_json=as_json)
        except (CliUsageError, ApiTransportError, ApiResponseError) as error:
            fail(console, error)

    @app.command(name="api-surface", help="List resources exposed by the target API")
    def api_surface_command(
        context: typer.Context,
        as_json: bool = typer.Option(
            False, "--json", help="Emit machine-readable JSON"
        ),
        timeout: float = typer.Option(30.0, "--timeout", min=0.1),
    ) -> None:
        try:
            config = ConfigStore().load(context_overrides(context))
            operations = operations_from_openapi(
                ApiClient(config, timeout=timeout).openapi()
            )
            counts = {
                resource: sum(
                    operation.resource == resource for operation in operations
                )
                for resource in sorted({operation.resource for operation in operations})
            }
            render_data(console, counts, as_json=as_json)
        except (CliUsageError, ApiTransportError, ApiResponseError) as error:
            fail(console, error)

    for resource in API_RESOURCES:
        app.command(
            name=resource,
            help=f"Call {resource} API actions (use: eylo {resource} actions)",
        )(resource_command(resource, console))


def resource_command(resource: str, console: Console):
    def command(
        context: typer.Context,
        action: str = typer.Argument("actions", help="Action shown by 'actions'"),
        identifiers: list[str] = typer.Argument(
            None, help="Path IDs in the order shown by the actions table"
        ),
        data: str | None = typer.Option(None, "--data", "-d", help="JSON request body"),
        data_file: Path | None = typer.Option(
            None, "--data-file", help="Read the JSON request body from a file"
        ),
        set_values: list[str] = typer.Option(
            None, "--set", help="Set a JSON body field (repeatable KEY=VALUE)"
        ),
        query_values: list[str] = typer.Option(
            None, "--query", "-q", help="Set a query value (repeatable KEY=VALUE)"
        ),
        header_values: list[str] = typer.Option(
            None, "--header", "-H", help="Set a request header (repeatable KEY=VALUE)"
        ),
        form_values: list[str] = typer.Option(
            None, "--form", help="Set a form field (repeatable KEY=VALUE)"
        ),
        upload_values: list[str] = typer.Option(
            None, "--upload", help="Upload a file (repeatable FIELD=PATH)"
        ),
        yes: bool = typer.Option(
            False, "--yes", "-y", help="Confirm destructive action"
        ),
        as_json: bool = typer.Option(
            False, "--json", help="Emit machine-readable JSON"
        ),
        timeout: float = typer.Option(30.0, "--timeout", min=0.1),
    ) -> None:
        try:
            execute_resource(
                console=console,
                store=ConfigStore(),
                overrides=context_overrides(context),
                resource=resource,
                action=action,
                identifiers=identifiers or (),
                data=data,
                data_file=data_file,
                set_values=set_values or (),
                query_values=query_values or (),
                header_values=header_values or (),
                form_values=form_values or (),
                upload_values=upload_values or (),
                yes=yes,
                as_json=as_json,
                timeout=timeout,
            )
        except (CliUsageError, ApiTransportError, ApiResponseError) as error:
            fail(console, error)

    command.__name__ = f"{resource.replace('-', '_')}_api_command"
    command.__doc__ = f"Call one {resource} operation from the live API contract."
    return command


def fail(console: Console, error: Exception) -> None:
    if isinstance(error, ApiResponseError):
        console.print(f"[bold red]API error {error.status_code}:[/] {error.detail}")
    else:
        console.print(f"[bold red]Error:[/] {error}")
    raise typer.Exit(code=1)
