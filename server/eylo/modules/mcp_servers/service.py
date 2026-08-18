"""Explicit MCP registration and revision-preserving tool rediscovery."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from eylo.common.contracts.provider_config import ProviderConfigError
from eylo.common.revisions import (
    DefinitionHeaderState,
    DefinitionLifecycle,
    PublishedRevisionState,
)
from eylo.modules.mcp_servers.config import (
    ResolvedMCPServerConfig,
    create_mcp_server_config,
    parse_mcp_server_config,
    resolve_mcp_server_config,
)
from eylo.modules.mcp_servers.models import MCPServerModel, MCPServerRevisionModel
from eylo.modules.provider_configs.crypto import SecretCipherError
from eylo.modules.tools.models import ToolExecutionMode, ToolKind, ToolModel
from eylo.modules.tools.schemas.executors.mcp import (
    MCPToolEffect,
    MCPToolExecutorConfig,
)
from eylo.modules.tools.schemas.indb import ToolCreateSchema, ToolUpdateSchema
from eylo.modules.tools.schemas.platform import PlatformTool
from eylo.modules.tools.services.indb import ToolService

MAX_TOOLS_PER_SERVER = 200
MAX_NAME_LENGTH = 128
MAX_DESCRIPTION_LENGTH = 1024
MAX_SCHEMA_BYTES = 65_536
MAX_AGGREGATE_SCHEMA_BYTES = 262_144
MAX_SCHEMA_DEPTH = 8
MAX_SCHEMA_NODES = 2048
MAX_SCHEMA_CONTAINER_ITEMS = 256
MAX_SCHEMA_STRING_LENGTH = 8192
_ROOT_SCHEMA_KEYS = frozenset(
    {
        "additionalProperties",
        "discriminator",
        "oneOf",
        "properties",
        "required",
        "type",
    }
)
_UNSUPPORTED_SCHEMA_KEYS = frozenset(
    {
        "$defs",
        "$ref",
        "definitions",
        "dependentSchemas",
        "patternProperties",
        "unevaluatedProperties",
    }
)

_SLUG_SAFE = re.compile(r"[^a-z0-9_]+")


class MCPServerError(Exception):
    """The server, transport, or complete discovered definition set is unusable."""


class MCPServerNotFoundError(MCPServerError):
    """The requested MCP server is not visible in the organization."""


@dataclass(frozen=True, slots=True)
class MCPToolDefinition:
    wire_id: str
    name: str
    display_name: str
    description: str
    llm_config: dict[str, Any]
    executor_config: dict[str, Any]
    output_schema: dict[str, Any]
    execution_mode: ToolExecutionMode


@dataclass(frozen=True, slots=True)
class MCPDiscoveryTarget:
    """Locked server revision and its execution-only decrypted config."""

    server: MCPServerModel = dataclass_field(repr=False)
    config: ResolvedMCPServerConfig = dataclass_field(repr=False)


def _slugify(value: str) -> str:
    return _SLUG_SAFE.sub("_", value.strip().lower()).strip("_")


class MCPServerService:
    """Create MCP server drafts and synchronize immutable tool revisions."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._tools = ToolService(db)

    async def register(
        self,
        *,
        organization_id: UUID,
        name: str,
        url: str,
        headers: dict[str, str] | None = None,
    ) -> MCPServerModel:
        """Record an unusable source draft without contacting the server."""
        name = name.strip()
        if not name or len(name) > MAX_NAME_LENGTH:
            raise MCPServerError(
                f"MCP server name must contain 1 to {MAX_NAME_LENGTH} characters."
            )
        slug = _slugify(name)
        if not slug:
            raise MCPServerError("MCP server name must contain letters or numbers.")
        server_id = uuid4()
        try:
            server = create_mcp_server_config(
                organization_id=organization_id,
                server_id=server_id,
                revision=1,
                url=url,
                headers=headers or {},
            )
        except (ProviderConfigError, SecretCipherError, ValueError) as error:
            raise MCPServerError(str(error)) from None
        server_model = MCPServerModel(
            id=server_id,
            organization_id=organization_id,
            name=name,
            slug=slug,
            config=server.to_storage(),
        )
        self._db.add(server_model)
        await self._db.flush()
        return server_model

    async def prepare_discovery(
        self,
        *,
        organization_id: UUID,
        server_id: UUID,
    ) -> MCPDiscoveryTarget:
        """Lock and resolve the exact server revision discovery will contact."""
        server = await self._get(organization_id, server_id, for_update=True)
        config_revision = (
            (server.published_revision or 0) + 1
            if server.draft_dirty
            else server.published_revision
        )
        if config_revision is None:
            raise MCPServerError("MCP server config revision is unavailable.")
        try:
            config = resolve_mcp_server_config(
                server.config,
                organization_id=organization_id,
                server_id=server_id,
                revision=config_revision,
            )
        except (ProviderConfigError, SecretCipherError, ValueError):
            raise MCPServerError("MCP server configuration is unavailable.") from None
        return MCPDiscoveryTarget(server=server, config=config)

    async def synchronize_discovery(
        self,
        *,
        organization_id: UUID,
        target: MCPDiscoveryTarget,
        actor_id: UUID,
        discovered: list[dict[str, Any]],
    ) -> list[ToolModel]:
        """Atomically apply one complete successful `tools/list` result."""
        server = target.server
        if server.organization_id != organization_id:
            raise MCPServerError("MCP discovery target does not match the request.")
        server_id = UUID(str(server.id))
        definitions = _validate_definition_set(server, discovered)

        if server.lifecycle == DefinitionLifecycle.WITHDRAWN.value:
            next_revision = (server.published_revision or 0) + 1
            try:
                rebound = create_mcp_server_config(
                    organization_id=organization_id,
                    server_id=server_id,
                    revision=next_revision,
                    url=target.config.url,
                    headers=target.config.origin_headers.values,
                )
            except (ProviderConfigError, SecretCipherError, ValueError):
                raise MCPServerError("MCP server configuration is unavailable.") from None
            self._edit_server(
                server,
                expected_draft_version=server.draft_version,
                config=rebound.to_storage(),
            )
        server_republished = server.draft_dirty
        if server_republished:
            await self._publish_server(
                server=server,
                expected_draft_version=server.draft_version,
                actor_id=actor_id,
            )

        existing = list(
            (
                await self._db.scalars(
                    select(ToolModel)
                    .where(
                        ToolModel.organization_id == organization_id,
                        ToolModel.mcp_server_id == server_id,
                        ToolModel.deleted.is_(False),
                    )
                    .with_for_update()
                )
            ).all()
        )
        by_wire_id = {row.wire_id: row for row in existing if row.wire_id is not None}
        selected_wire_ids = {definition.wire_id for definition in definitions}

        synchronized: list[ToolModel] = []
        for definition in definitions:
            row = by_wire_id.get(definition.wire_id)
            if row is None:
                created = await self._tools.create_(
                    ToolCreateSchema(
                        organization_id=organization_id,
                        mcp_server_id=server_id,
                        wire_id=definition.wire_id,
                        kind=ToolKind.MCP,
                        name=definition.name,
                        display_name=definition.display_name,
                        description=definition.description,
                        llm_config=definition.llm_config,
                        executor_config=definition.executor_config,
                        output_schema=definition.output_schema,
                        execution_mode=definition.execution_mode,
                    )
                )
                await self._tools.publish(
                    organization_id=organization_id,
                    tool_id=created.id,
                    expected_draft_version=1,
                    actor_id=actor_id,
                )
                row = await self._get_tool(organization_id, created.id)
            elif (
                not _same_definition(row, definition)
                or row.lifecycle == DefinitionLifecycle.WITHDRAWN.value
                or server_republished
            ):
                update_values: dict[str, Any] = {
                    "expected_draft_version": row.draft_version,
                    "name": definition.name,
                    "display_name": definition.display_name,
                    "description": definition.description,
                    "llm_config": definition.llm_config,
                    "executor_config": definition.executor_config,
                    "output_schema": definition.output_schema,
                }
                if definition.execution_mode is ToolExecutionMode.DISABLED:
                    update_values["execution_mode"] = ToolExecutionMode.DISABLED
                await self._tools.update_(
                    organization_id=organization_id,
                    tool_id=UUID(str(row.id)),
                    data=ToolUpdateSchema(**update_values),
                )
                await self._tools.publish(
                    organization_id=organization_id,
                    tool_id=UUID(str(row.id)),
                    expected_draft_version=row.draft_version,
                    actor_id=actor_id,
                )
            synchronized.append(row)

        for row in existing:
            if (
                row.wire_id not in selected_wire_ids
                and row.lifecycle == DefinitionLifecycle.PUBLISHED.value
            ):
                await self._tools.withdraw(
                    organization_id=organization_id,
                    tool_id=UUID(str(row.id)),
                )

        server.discovered_at = datetime.now(timezone.utc)
        server.discovered_tool_count = len(definitions)
        await self._db.flush()
        return synchronized

    async def update(
        self,
        *,
        organization_id: UUID,
        server_id: UUID,
        expected_draft_version: int,
        name: str | None,
        url: str | None,
        header_patch: dict[str, str | None] | None,
    ):
        """Patch one MCP draft and re-encrypt secrets for its next revision."""
        server = await self._get(organization_id, server_id, for_update=True)
        current_revision = (
            (server.published_revision or 0) + 1
            if server.draft_dirty
            else server.published_revision
        )
        if current_revision is None:
            current_revision = 1
        try:
            current = resolve_mcp_server_config(
                server.config,
                organization_id=organization_id,
                server_id=server_id,
                revision=current_revision,
            )
            next_revision = (server.published_revision or 0) + 1
            updated = create_mcp_server_config(
                organization_id=organization_id,
                server_id=server_id,
                revision=next_revision,
                url=url if url is not None else current.url,
                headers=header_patch or {},
                stored_headers=current.origin_headers.values,
            )
        except (ProviderConfigError, SecretCipherError, ValueError) as error:
            raise MCPServerError(str(error)) from None

        normalized_name: str | None = None
        if name is not None:
            normalized_name = name.strip()
            if not normalized_name or len(normalized_name) > MAX_NAME_LENGTH:
                raise MCPServerError(
                    f"MCP server name must contain 1 to {MAX_NAME_LENGTH} characters."
                )
        self._edit_server(
            server,
            expected_draft_version=expected_draft_version,
            config=updated.to_storage(),
            name=normalized_name,
        )
        await self._db.flush()
        return server

    async def list_servers(self, organization_id: UUID) -> list[MCPServerModel]:
        rows = await self._db.scalars(
            select(MCPServerModel).where(
                MCPServerModel.organization_id == organization_id,
                MCPServerModel.deleted.is_(False),
            )
        )
        return list(rows.all())

    async def withdraw(
        self,
        *,
        organization_id: UUID,
        server_id: UUID,
    ) -> MCPServerModel:
        """Stop new grants while preserving exact historical revisions."""
        server = await self._get(organization_id, server_id, for_update=True)
        _apply_header_state(server, _header_state(server).withdraw())
        await self._withdraw_current_tools(
            organization_id=organization_id,
            server_id=server_id,
        )
        await self._db.flush()
        return server

    async def revoke_revision(
        self,
        *,
        organization_id: UUID,
        server_id: UUID,
        revision: int,
        actor_id: UUID,
        reason: str,
    ) -> MCPServerRevisionModel:
        """Emergency-stop one exact server revision and its future tool use."""
        server = await self._get(organization_id, server_id, for_update=True)
        row = await self._db.scalar(
            select(MCPServerRevisionModel)
            .where(
                MCPServerRevisionModel.organization_id == organization_id,
                MCPServerRevisionModel.server_id == server_id,
                MCPServerRevisionModel.revision == revision,
                MCPServerRevisionModel.deleted.is_(False),
            )
            .with_for_update()
        )
        if row is None:
            raise MCPServerNotFoundError("MCP server revision not found.")
        revoked = _revision_state(row).revoke(
            actor_id=actor_id,
            reason=reason,
            at=datetime.now(timezone.utc),
        )
        row.availability = revoked.availability.value
        row.revoked_at = revoked.revoked_at
        row.revoked_by = revoked.revoked_by
        row.revocation_reason = revoked.revocation_reason
        row.cancellation_requested_at = revoked.cancellation_requested_at
        if server.published_revision == revision:
            _apply_header_state(server, _header_state(server).withdraw())
            await self._withdraw_current_tools(
                organization_id=organization_id,
                server_id=server_id,
            )
        await self._db.flush()
        return row

    async def get_revision(
        self,
        *,
        organization_id: UUID,
        server_id: UUID,
        revision: int,
    ) -> MCPServerRevisionModel:
        row = await self._db.scalar(
            select(MCPServerRevisionModel).where(
                MCPServerRevisionModel.organization_id == organization_id,
                MCPServerRevisionModel.server_id == server_id,
                MCPServerRevisionModel.revision == revision,
                MCPServerRevisionModel.deleted.is_(False),
            )
        )
        if row is None:
            raise MCPServerNotFoundError("MCP server revision not found.")
        PublishedRevisionState(
            published_at=row.published_at,
            availability=row.availability,
            revoked_at=row.revoked_at,
            revoked_by=row.revoked_by,
            revocation_reason=row.revocation_reason,
            cancellation_requested_at=row.cancellation_requested_at,
        ).require_available()
        return row

    async def _get(
        self,
        organization_id: UUID,
        server_id: UUID,
        *,
        for_update: bool = False,
    ) -> MCPServerModel:
        statement = select(MCPServerModel).where(
            MCPServerModel.id == server_id,
            MCPServerModel.organization_id == organization_id,
            MCPServerModel.deleted.is_(False),
        )
        if for_update:
            statement = statement.with_for_update()
        server = await self._db.scalar(statement)
        if server is None:
            raise MCPServerNotFoundError("No such MCP server in this organization.")
        return server

    async def _get_tool(self, organization_id: UUID, tool_id: UUID) -> ToolModel:
        row = await self._db.scalar(
            select(ToolModel).where(
                ToolModel.id == tool_id,
                ToolModel.organization_id == organization_id,
            )
        )
        if row is None:
            raise MCPServerError("Discovered MCP tool was not persisted.")
        return row

    async def _withdraw_current_tools(
        self,
        *,
        organization_id: UUID,
        server_id: UUID,
    ) -> None:
        rows = await self._db.scalars(
            select(ToolModel)
            .where(
                ToolModel.organization_id == organization_id,
                ToolModel.mcp_server_id == server_id,
                ToolModel.deleted.is_(False),
            )
            .with_for_update()
        )
        for row in rows.all():
            if row.lifecycle == DefinitionLifecycle.PUBLISHED.value:
                await self._tools.withdraw(
                    organization_id=organization_id,
                    tool_id=UUID(str(row.id)),
                )

    def _edit_server(
        self,
        server: MCPServerModel,
        *,
        expected_draft_version: int,
        config: dict[str, Any],
        name: str | None = None,
    ) -> None:
        state = _header_state(server).edit(
            expected_draft_version=expected_draft_version
        )
        server.config = config
        if name is not None:
            server.name = name
        _apply_header_state(server, state)

    async def _publish_server(
        self,
        *,
        server: MCPServerModel,
        expected_draft_version: int,
        actor_id: UUID,
    ) -> MCPServerRevisionModel:
        try:
            parse_mcp_server_config(server.config)
        except ValueError as error:
            raise MCPServerError("MCP server configuration is unavailable.") from error
        next_revision = (server.published_revision or 0) + 1
        state = _header_state(server).publish(
            revision=next_revision,
            expected_draft_version=expected_draft_version,
        )
        revision = MCPServerRevisionModel(
            organization_id=server.organization_id,
            server_id=server.id,
            revision=next_revision,
            name=server.name,
            slug=server.slug,
            config=server.config,
            published_at=datetime.now(timezone.utc),
            published_by=actor_id,
        )
        self._db.add(revision)
        await self._db.flush()
        _apply_header_state(server, state)
        await self._db.flush()
        return revision


def _validate_definition_set(
    server: MCPServerModel,
    entries: list[dict[str, Any]],
) -> tuple[MCPToolDefinition, ...]:
    if len(entries) > MAX_TOOLS_PER_SERVER:
        raise MCPServerError(
            f"MCP server returned {len(entries)} tools; limit is "
            f"{MAX_TOOLS_PER_SERVER}. No definitions were changed."
        )
    definitions: list[MCPToolDefinition] = []
    seen_wire_ids: set[str] = set()
    seen_names: set[str] = set()
    aggregate_schema_bytes = 0
    for entry in entries:
        if not isinstance(entry, dict):
            raise MCPServerError("Every MCP tool definition must be an object.")
        wire_id = entry.get("name")
        if not isinstance(wire_id, str) or not wire_id.strip():
            raise MCPServerError("Every MCP tool requires a non-empty protocol name.")
        wire_id = wire_id.strip()
        if len(wire_id) > MAX_NAME_LENGTH:
            raise MCPServerError(
                f"MCP tool name exceeds {MAX_NAME_LENGTH} characters: {wire_id!r}."
            )
        if wire_id in seen_wire_ids:
            raise MCPServerError(f"Duplicate MCP protocol tool name: {wire_id!r}.")
        seen_wire_ids.add(wire_id)

        description = entry.get("description") or (
            f"MCP tool {wire_id} exposed by {server.name}."
        )
        if (
            not isinstance(description, str)
            or len(description) > MAX_DESCRIPTION_LENGTH
        ):
            raise MCPServerError(
                f"MCP tool description exceeds {MAX_DESCRIPTION_LENGTH} characters."
            )
        input_schema, input_bytes = _validated_schema(
            entry.get("input_schema"),
            label=f"MCP tool {wire_id!r} input schema",
        )
        remote_output_schema = entry.get("output_schema")
        if remote_output_schema is None:
            output_schema = {"type": "object", "additionalProperties": True}
            output_bytes = 0
        else:
            output_schema, output_bytes = _validated_schema(
                remote_output_schema,
                label=f"MCP tool {wire_id!r} output schema",
            )
        aggregate_schema_bytes += input_bytes + output_bytes
        if aggregate_schema_bytes > MAX_AGGREGATE_SCHEMA_BYTES:
            raise MCPServerError(
                "MCP discovery schemas exceed the aggregate size limit."
            )
        effect = _declared_effect(entry.get("annotations"), wire_id=wire_id)
        name = _model_name(server, wire_id)
        if name in seen_names:
            raise MCPServerError(f"MCP model-facing tool name collision: {name!r}.")
        seen_names.add(name)
        definitions.append(
            MCPToolDefinition(
                wire_id=wire_id,
                name=name,
                display_name=wire_id,
                description=description,
                llm_config={
                    "name": name,
                    "description": description,
                    "input_schema": input_schema,
                },
                executor_config=MCPToolExecutorConfig(
                    mcp_tool_name=wire_id,
                    effect=effect,
                ).model_dump(mode="json"),
                output_schema=output_schema,
                execution_mode=(
                    ToolExecutionMode.DISABLED
                    if effect is MCPToolEffect.UNSUPPORTED
                    else ToolExecutionMode.AUTO
                ),
            )
        )
    return tuple(definitions)


def _declared_effect(value: object, *, wire_id: str) -> MCPToolEffect:
    if value is None:
        return MCPToolEffect.UNSUPPORTED
    if not isinstance(value, dict):
        raise MCPServerError(f"MCP tool {wire_id!r} annotations must be an object.")
    for name in (
        "readOnlyHint",
        "destructiveHint",
        "idempotentHint",
        "openWorldHint",
    ):
        if name in value and not isinstance(value[name], bool):
            raise MCPServerError(
                f"MCP tool {wire_id!r} annotation {name!r} must be boolean."
            )
    if value.get("readOnlyHint") is True:
        if value.get("destructiveHint") is True:
            raise MCPServerError(
                f"MCP tool {wire_id!r} declares contradictory effect hints."
            )
        return MCPToolEffect.READ_ONLY
    if value.get("idempotentHint") is True:
        return MCPToolEffect.IDEMPOTENT_MUTATION
    return MCPToolEffect.UNSUPPORTED


def _validated_schema(value: object, *, label: str) -> tuple[dict[str, Any], int]:
    if not isinstance(value, dict) or value.get("type") != "object":
        raise MCPServerError(f"{label} must be an object JSON Schema.")
    unsupported_root = set(value) - _ROOT_SCHEMA_KEYS
    if unsupported_root:
        raise MCPServerError(f"{label} uses unsupported root keywords.")
    properties = value.get("properties", {})
    if not isinstance(properties, dict) or not all(
        isinstance(name, str) and 0 < len(name) <= MAX_NAME_LENGTH
        for name in properties
    ):
        raise MCPServerError(f"{label} properties are invalid.")
    required = value.get("required", [])
    if (
        not isinstance(required, list)
        or not all(isinstance(name, str) for name in required)
        or len(set(required)) != len(required)
        or not set(required).issubset(properties)
    ):
        raise MCPServerError(f"{label} required fields are invalid.")
    nodes = [0]
    _validate_schema_node(value, label=label, depth=0, nodes=nodes)
    try:
        canonical = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError):
        raise MCPServerError(f"{label} is not canonical JSON.") from None
    size = len(canonical.encode("utf-8"))
    if size > MAX_SCHEMA_BYTES:
        raise MCPServerError(f"{label} exceeds the size limit.")
    return json.loads(canonical), size


def _validate_schema_node(
    value: object,
    *,
    label: str,
    depth: int,
    nodes: list[int],
) -> None:
    if depth > MAX_SCHEMA_DEPTH:
        raise MCPServerError(f"{label} exceeds the depth limit.")
    nodes[0] += 1
    if nodes[0] > MAX_SCHEMA_NODES:
        raise MCPServerError(f"{label} exceeds the node limit.")
    if isinstance(value, dict):
        if len(value) > MAX_SCHEMA_CONTAINER_ITEMS or set(value) & (
            _UNSUPPORTED_SCHEMA_KEYS
        ):
            raise MCPServerError(f"{label} uses an unsupported schema shape.")
        if not all(isinstance(key, str) for key in value):
            raise MCPServerError(f"{label} keys must be strings.")
        for child in value.values():
            _validate_schema_node(
                child,
                label=label,
                depth=depth + 1,
                nodes=nodes,
            )
        return
    if isinstance(value, list):
        if len(value) > MAX_SCHEMA_CONTAINER_ITEMS:
            raise MCPServerError(f"{label} contains too many items.")
        for child in value:
            _validate_schema_node(
                child,
                label=label,
                depth=depth + 1,
                nodes=nodes,
            )
        return
    if isinstance(value, str) and len(value) > MAX_SCHEMA_STRING_LENGTH:
        raise MCPServerError(f"{label} contains an oversized string.")
    if value is not None and not isinstance(value, str | int | float | bool):
        raise MCPServerError(f"{label} contains an unsupported value.")


def _model_name(server: MCPServerModel, wire_id: str) -> str:
    prefix = f"mcp_{str(server.id).replace('-', '')[:12]}_"
    digest = hashlib.sha256(wire_id.encode()).hexdigest()[:12]
    slug = _slugify(wire_id) or "tool"
    available = MAX_NAME_LENGTH - len(prefix) - len(digest) - 1
    return f"{prefix}{slug[:available]}_{digest}"


def _same_definition(row: ToolModel, definition: MCPToolDefinition) -> bool:
    return all(
        (
            row.name == definition.name,
            row.display_name == definition.display_name,
            row.description == definition.description,
            PlatformTool.model_validate(row.llm_config)
            == PlatformTool.model_validate(definition.llm_config),
            row.executor_config == definition.executor_config,
            row.output_schema == definition.output_schema,
        )
    )


def _header_state(server: MCPServerModel) -> DefinitionHeaderState:
    return DefinitionHeaderState(
        lifecycle=server.lifecycle,
        published_revision=server.published_revision,
        draft_version=server.draft_version,
        draft_dirty=server.draft_dirty,
    )


def _revision_state(row: MCPServerRevisionModel) -> PublishedRevisionState:
    return PublishedRevisionState(
        published_at=row.published_at,
        availability=row.availability,
        revoked_at=row.revoked_at,
        revoked_by=row.revoked_by,
        revocation_reason=row.revocation_reason,
        cancellation_requested_at=row.cancellation_requested_at,
    )


def _apply_header_state(
    server: MCPServerModel,
    state: DefinitionHeaderState,
) -> None:
    server.lifecycle = state.lifecycle.value
    server.published_revision = state.published_revision
    server.draft_version = state.draft_version
    server.draft_dirty = state.draft_dirty


def redacted_server(server: MCPServerModel) -> dict[str, Any]:
    config = parse_mcp_server_config(server.config)
    return {
        "id": str(server.id),
        "name": server.name,
        "slug": server.slug,
        "url": config.url,
        "transport": config.transport,
        "protocol_version": config.protocol_version,
        "auth_mode": "headers" if config.header_names else "none",
        "header_names": list(config.header_names),
        "lifecycle": server.lifecycle,
        "published_revision": server.published_revision,
        "draft_version": server.draft_version,
        "draft_dirty": server.draft_dirty,
        "discovered_at": (
            server.discovered_at.isoformat()
            if server.discovered_at is not None
            else None
        ),
        "discovered_tool_count": server.discovered_tool_count,
    }


__all__ = [
    "MCPDiscoveryTarget",
    "MCPServerError",
    "MCPServerNotFoundError",
    "MCPServerService",
    "redacted_server",
]
