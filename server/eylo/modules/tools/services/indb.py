"""Application service for organization tool definition revisions."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional, Type
from uuid import UUID

from sqlalchemy import select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from eylo.common.database import get_transaction
from eylo.common.repositories import map_schema_to_model
from eylo.common.revisions import DefinitionHeaderState, PublishedRevisionState
from eylo.common.services import EyloBaseService
from eylo.modules.mcp_servers.models import MCPServerModel, MCPServerRevisionModel
from eylo.modules.tools.domain import (
    DefinitionNotFoundError,
    InvalidDefinitionDraftError,
)
from eylo.modules.tools.models import ToolModel, ToolRevisionModel
from eylo.modules.tools.repositories import ToolRepository
from eylo.modules.tools.schemas.executors.mcp import (
    validate_mcp_tool_executor_config,
)
from eylo.modules.tools.schemas.indb import ToolCreateSchema, ToolInDb, ToolUpdateSchema
from eylo.modules.tools.schemas.platform import PlatformTool

logger = logging.getLogger(__name__)


class ToolService(EyloBaseService[ToolInDb]):
    """Own mutable org tool drafts and immutable exact dispatch payloads."""

    @property
    def schema(self) -> Type[ToolInDb]:
        return ToolInDb

    @property
    def repository(self) -> ToolRepository:
        return self._repository

    @repository.setter
    def repository(self, value: ToolRepository):
        self._repository = value

    def __init__(self, db: Optional[AsyncSession] = None):
        self._db = db or get_transaction()
        self._repository = ToolRepository(db=self._db)

    async def create_(self, data: ToolCreateSchema) -> ToolInDb:
        new_tool = await self.repository.create_(data)
        return ToolInDb.model_validate(new_tool)

    async def get_header(self, *, organization_id: UUID, tool_id: UUID) -> ToolInDb:
        return ToolInDb.model_validate(
            await self._header(organization_id=organization_id, tool_id=tool_id)
        )

    async def update_(
        self,
        *,
        organization_id: UUID,
        tool_id: UUID,
        data: ToolUpdateSchema,
    ) -> ToolInDb:
        row = await self._header(
            organization_id=organization_id,
            tool_id=tool_id,
            for_update=True,
        )
        state = _header_state(row).edit(
            expected_draft_version=data.expected_draft_version
        )
        values = data.model_dump(exclude_unset=True)
        values.pop("expected_draft_version")
        for field, value in values.items():
            if hasattr(value, "model_dump"):
                value = value.model_dump(mode="json", by_alias=True, exclude_none=True)
            setattr(row, field, value)
        _validate_publishable(row, require_executor=False)
        _apply_header_state(row, state)
        await self._db.flush()
        return ToolInDb.model_validate(row)

    async def publish(
        self,
        *,
        organization_id: UUID,
        tool_id: UUID,
        expected_draft_version: int,
        actor_id: UUID | None,
    ) -> ToolRevisionModel:
        row = await self._header(
            organization_id=organization_id,
            tool_id=tool_id,
            for_update=True,
        )
        _validate_publishable(row, require_executor=True)
        mcp_server_revision: int | None = None
        if row.mcp_server_id is not None:
            mcp_server_revision = await self._resolve_mcp_server_revision(
                organization_id=organization_id,
                server_id=UUID(str(row.mcp_server_id)),
            )
        next_revision = (row.published_revision or 0) + 1
        state = _header_state(row).publish(
            revision=next_revision,
            expected_draft_version=expected_draft_version,
        )
        revision = ToolRevisionModel(
            organization_id=row.organization_id,
            tool_id=row.id,
            revision=next_revision,
            mcp_server_revision=mcp_server_revision,
            **_tool_values(row),
            published_at=datetime.now(timezone.utc),
            published_by=actor_id,
        )
        self._db.add(revision)
        await self._db.flush()
        _apply_header_state(row, state)
        await self._db.flush()
        return revision

    async def resolve_for_new_work(
        self,
        *,
        organization_id: UUID,
        tool_id: UUID,
    ) -> ToolRevisionModel:
        header = await self._header(
            organization_id=organization_id,
            tool_id=tool_id,
        )
        revision = _header_state(header).revision_for_new_work()
        return await self.get_revision(
            organization_id=organization_id,
            tool_id=tool_id,
            revision=revision,
        )

    async def get_revision(
        self,
        *,
        organization_id: UUID,
        tool_id: UUID,
        revision: int,
        require_available: bool = True,
        for_update: bool = False,
    ) -> ToolRevisionModel:
        statement = select(ToolRevisionModel).where(
            ToolRevisionModel.organization_id == organization_id,
            ToolRevisionModel.tool_id == tool_id,
            ToolRevisionModel.revision == revision,
            ToolRevisionModel.deleted.is_(False),
        )
        if for_update:
            statement = statement.with_for_update()
        row = await self._db.scalar(statement)
        if row is None:
            raise DefinitionNotFoundError("Tool revision not found.")
        if require_available:
            _revision_state(row).require_available()
        return row

    async def list_exact(
        self,
        *,
        organization_id: UUID,
        refs: list[tuple[UUID, int]],
    ) -> list[ToolInDb]:
        if not refs:
            return []
        rows = list(
            (
                await self._db.scalars(
                    select(ToolRevisionModel).where(
                        ToolRevisionModel.organization_id == organization_id,
                        tuple_(
                            ToolRevisionModel.tool_id, ToolRevisionModel.revision
                        ).in_(refs),
                        ToolRevisionModel.deleted.is_(False),
                    )
                )
            ).all()
        )
        by_ref = {(row.tool_id, row.revision): row for row in rows}
        if len(by_ref) != len(set(refs)):
            raise DefinitionNotFoundError("Tool revision not found.")
        resolved: list[ToolInDb] = []
        for ref in refs:
            row = by_ref[ref]
            _revision_state(row).require_available()
            resolved.append(_revision_to_schema(row))
        return resolved

    async def withdraw(
        self,
        *,
        organization_id: UUID,
        tool_id: UUID,
    ) -> ToolInDb:
        row = await self._header(
            organization_id=organization_id,
            tool_id=tool_id,
            for_update=True,
        )
        _apply_header_state(row, _header_state(row).withdraw())
        await self._db.flush()
        return ToolInDb.model_validate(row)

    async def revoke(
        self,
        *,
        organization_id: UUID,
        tool_id: UUID,
        revision: int,
        actor_id: UUID,
        reason: str,
    ) -> ToolRevisionModel:
        header = await self._header(
            organization_id=organization_id,
            tool_id=tool_id,
            for_update=True,
        )
        row = await self.get_revision(
            organization_id=organization_id,
            tool_id=tool_id,
            revision=revision,
            require_available=False,
            for_update=True,
        )
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
        if header.published_revision == revision:
            _apply_header_state(header, _header_state(header).withdraw())
        await self._db.flush()
        return row

    async def list_by_ids(
        self,
        tool_ids: list[UUID],
        organization_id: UUID,
    ) -> list[ToolInDb]:
        tools = await self.repository.list_by_ids(
            tool_ids=tool_ids,
            organization_id=organization_id,
        )
        return self.orm_to_schema_list(tools)

    async def list_by_organization_id(self, organization_id: UUID) -> list[ToolInDb]:
        rows = await self.repository.filter_(
            [
                self.repository.model.organization_id == organization_id,
                self.repository.model.deleted.is_(False),
            ]
        )
        return self.orm_to_schema_list(rows)

    async def list_by_mcp_server(
        self, organization_id: UUID, server_id: UUID
    ) -> list[ToolInDb]:
        rows = await self.repository.list_by_mcp_server(
            organization_id, server_id
        )
        return self.orm_to_schema_list(rows)

    async def ensure_system_tool_exists(
        self, tool_id: UUID, organization_id: UUID
    ) -> ToolInDb | None:
        """Materialize and publish a selected first-party system tool."""
        existing = await self.repository.get_(tool_id)
        if existing is not None:
            if UUID(str(existing.organization_id)) != organization_id:
                return None
            if existing.published_revision is None:
                await self.publish(
                    organization_id=organization_id,
                    tool_id=tool_id,
                    expected_draft_version=existing.draft_version,
                    actor_id=None,
                )
            return ToolInDb.model_validate(existing)

        from eylo.modules.tools.models import ToolKind
        from eylo.modules.tools.services.tool_register import (
            system_tool_id,
            system_tools_registry,
        )

        matched_name = next(
            (
                name
                for name in system_tools_registry.registered_tools
                if system_tool_id(name, organization_id) == tool_id
            ),
            None,
        )
        if matched_name is None:
            return None
        tool_func = system_tools_registry.registered_tools[matched_name]
        data = ToolCreateSchema(
            name=matched_name,
            kind=ToolKind.SYSTEM,
            display_name=matched_name.replace("_", " ").title(),
            description=tool_func.__doc__ or f"Run {matched_name}.",
            mcp_server_id=None,
            llm_config=system_tools_registry.get_llm_config(matched_name),
            executor_config={},
            organization_id=organization_id,
        )
        model = map_schema_to_model(ToolModel, data)
        model.id = tool_id
        self._db.add(model)
        await self._db.flush()
        await self.publish(
            organization_id=organization_id,
            tool_id=tool_id,
            expected_draft_version=1,
            actor_id=None,
        )
        logger.info("Materialized system tool '%s' (%s)", matched_name, tool_id)
        return ToolInDb.model_validate(model)

    async def _header(
        self,
        *,
        organization_id: UUID,
        tool_id: UUID,
        for_update: bool = False,
    ) -> ToolModel:
        statement = select(ToolModel).where(
            ToolModel.id == tool_id,
            ToolModel.organization_id == organization_id,
            ToolModel.deleted.is_(False),
        )
        if for_update:
            statement = statement.with_for_update()
        row = await self._db.scalar(statement)
        if row is None:
            raise DefinitionNotFoundError("Tool not found.")
        return row

    async def _resolve_mcp_server_revision(
        self,
        *,
        organization_id: UUID,
        server_id: UUID,
    ) -> int:
        server = await self._db.scalar(
            select(MCPServerModel).where(
                MCPServerModel.id == server_id,
                MCPServerModel.organization_id == organization_id,
                MCPServerModel.deleted.is_(False),
            )
        )
        if server is None:
            raise DefinitionNotFoundError("MCP server not found.")
        revision = DefinitionHeaderState(
            lifecycle=server.lifecycle,
            published_revision=server.published_revision,
            draft_version=server.draft_version,
            draft_dirty=server.draft_dirty,
        ).revision_for_new_work()
        revision_row = await self._db.scalar(
            select(MCPServerRevisionModel).where(
                MCPServerRevisionModel.server_id == server_id,
                MCPServerRevisionModel.revision == revision,
                MCPServerRevisionModel.organization_id == organization_id,
                MCPServerRevisionModel.deleted.is_(False),
            )
        )
        if revision_row is None:
            raise DefinitionNotFoundError("MCP server revision not found.")
        PublishedRevisionState(
            published_at=revision_row.published_at,
            availability=revision_row.availability,
            revoked_at=revision_row.revoked_at,
            revoked_by=revision_row.revoked_by,
            revocation_reason=revision_row.revocation_reason,
            cancellation_requested_at=revision_row.cancellation_requested_at,
        ).require_available()
        return revision


def _validate_publishable(row: ToolModel, *, require_executor: bool) -> None:
    try:
        llm = PlatformTool.model_validate(row.llm_config)
    except Exception as error:
        raise InvalidDefinitionDraftError("Tool llm_config is invalid.") from error
    if not llm.name.strip() or not llm.description.strip():
        raise InvalidDefinitionDraftError(
            "Tool llm_config requires a name and description."
        )
    schema = llm.input_schema.to_json_schema()
    if schema.get("type") != "object":
        raise InvalidDefinitionDraftError("Tool input schema must be an object.")
    if (
        require_executor
        and not row.executor_config
        and _enum_value(row.kind)
        not in {
            "LOCAL",
            "SYSTEM",
        }
    ):
        raise InvalidDefinitionDraftError("Executable tool requires executor_config.")
    if require_executor and _enum_value(row.kind) == "MCP":
        if row.mcp_server_id is None:
            raise InvalidDefinitionDraftError(
                "MCP tool requires a published MCP server."
            )
        try:
            validate_mcp_tool_executor_config(row.executor_config)
        except (TypeError, ValueError) as error:
            raise InvalidDefinitionDraftError(
                "Tool executor_config is invalid."
            ) from error


def _enum_value(value: object) -> str:
    return str(value.value) if hasattr(value, "value") else str(value)


def _header_state(row: ToolModel) -> DefinitionHeaderState:
    return DefinitionHeaderState(
        lifecycle=row.lifecycle,
        published_revision=row.published_revision,
        draft_version=row.draft_version,
        draft_dirty=row.draft_dirty,
    )


def _apply_header_state(row: ToolModel, state: DefinitionHeaderState) -> None:
    row.lifecycle = state.lifecycle.value
    row.published_revision = state.published_revision
    row.draft_version = state.draft_version
    row.draft_dirty = state.draft_dirty


def _revision_state(row: ToolRevisionModel) -> PublishedRevisionState:
    return PublishedRevisionState(
        published_at=row.published_at,
        availability=row.availability,
        revoked_at=row.revoked_at,
        revoked_by=row.revoked_by,
        revocation_reason=row.revocation_reason,
        cancellation_requested_at=row.cancellation_requested_at,
    )


def _tool_values(row: ToolModel | ToolRevisionModel) -> dict[str, object]:
    return {
        "name": row.name,
        "slug": row.slug,
        "kind": _enum_value(row.kind),
        "display_name": row.display_name,
        "description": row.description,
        "llm_config": row.llm_config,
        "executor_config": row.executor_config,
        "output_schema": row.output_schema,
        "execution_mode": row.execution_mode,
        "wire_id": row.wire_id,
        "mcp_server_id": row.mcp_server_id,
    }


def _executable_tool_values(row: ToolRevisionModel) -> dict[str, object]:
    """Project runtime-owned tool schemas from the same code that executes them."""
    values = _tool_values(row)
    kind = _enum_value(row.kind)
    if kind not in {"LOCAL", "SYSTEM"}:
        return values

    from eylo.modules.tools.services.tool_register import (
        local_tools_registry,
        system_tools_registry,
    )

    registry = system_tools_registry if kind == "SYSTEM" else local_tools_registry
    tool_func = registry.registered_tools.get(row.slug)
    if tool_func is None:
        raise DefinitionNotFoundError(f"{kind.title()} tool executor not found.")
    values["description"] = tool_func.__doc__ or row.description
    values["llm_config"] = registry.get_llm_config(row.slug)
    return values


def _revision_to_schema(row: ToolRevisionModel) -> ToolInDb:
    return ToolInDb.model_validate(
        {
            "id": row.tool_id,
            "organization_id": row.organization_id,
            **_executable_tool_values(row),
            "mcp_server_revision": row.mcp_server_revision,
            "lifecycle": "published",
            "published_revision": row.revision,
            "draft_version": row.revision,
            "draft_dirty": False,
        }
    )


__all__ = ["ToolService"]
