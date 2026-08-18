"""HTTP translation for organization tool definition revisions."""

from uuid import UUID

from fastapi import HTTPException, status

from eylo.common.contracts.provider_config import Capability
from eylo.common.database import start_transaction
from eylo.common.revisions import DefinitionRevisionError
from eylo.modules.auth.schemas import CurrentUserSchema
from eylo.modules.tools.domain import (
    DefinitionDomainError,
    DefinitionNotFoundError,
    InvalidDefinitionDraftError,
)
from eylo.modules.tools.schemas.api import (
    ToolCreateRequestSchema,
    ToolFilterSchema,
    ToolListResponseSchema,
    ToolResponseSchema,
    ToolRevisionResponseSchema,
    ToolUpdateRequestSchema,
)
from eylo.modules.tools.schemas.indb import ToolCreateSchema, ToolInDb, ToolUpdateSchema
from eylo.modules.tools.services.indb import ToolService


class ToolController:
    @property
    def service(self) -> ToolService:
        """Resolve the service only after the method opens its DB transaction."""
        return ToolService()

    @staticmethod
    def _require_organization(tool: ToolInDb, organization_id: UUID) -> None:
        if tool.organization_id != organization_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    async def list_system_catalog(
        self, organization_id: UUID
    ) -> ToolListResponseSchema:
        from eylo.modules.tools.services.tool_register import system_tools_registry

        async with start_transaction(ro=True):
            items = system_tools_registry.list_catalog(
                organization_id,
                capabilities=await _ready_capabilities(organization_id),
            )
            return ToolListResponseSchema(
                items=[ToolResponseSchema.model_validate(item) for item in items]
            )

    async def list_provider_catalog(
        self,
        organization_id: UUID,
        capability: Capability,
    ) -> ToolListResponseSchema:
        """List code-owned Agent tools associated with one provider capability."""
        from eylo.modules.tools.services.tool_register import system_tools_registry

        items = system_tools_registry.list_catalog(
            organization_id,
            provider_capability=capability,
        )
        return ToolListResponseSchema(
            items=[ToolResponseSchema.model_validate(item) for item in items]
        )

    async def create_tool(
        self, organization_id: UUID, request: ToolCreateRequestSchema
    ) -> ToolResponseSchema:
        async with start_transaction():
            tool = await self.service.create_(
                ToolCreateSchema.model_validate(
                    {
                        **request.model_dump(exclude={"organization_id"}),
                        "organization_id": organization_id,
                    }
                )
            )
            return ToolResponseSchema.model_validate(tool)

    async def get_tool(
        self, tool_id: UUID, current_user: CurrentUserSchema
    ) -> ToolResponseSchema:
        try:
            async with start_transaction(ro=True):
                tool = await self.service.get_header(
                    organization_id=current_user.organization_id,
                    tool_id=tool_id,
                )
                return ToolResponseSchema.model_validate(tool)
        except DefinitionNotFoundError as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from error

    async def list_tools(
        self,
        organization_id: UUID,
        mcp_server_id: UUID | None = None,
        filters: ToolFilterSchema | None = None,
    ) -> ToolListResponseSchema:
        async with start_transaction(ro=True):
            if filters and filters.tool_ids:
                rows = await self.service.list_by_ids(
                    tool_ids=filters.tool_ids,
                    organization_id=organization_id,
                )
            elif mcp_server_id:
                rows = await self.service.list_by_mcp_server(
                    organization_id, mcp_server_id
                )
            else:
                rows = await self.service.list_by_organization_id(organization_id)
            return ToolListResponseSchema(
                items=[ToolResponseSchema.model_validate(row) for row in rows]
            )

    async def update_tool(
        self,
        tool_id: UUID,
        organization_id: UUID,
        request: ToolUpdateRequestSchema,
    ) -> ToolResponseSchema:
        try:
            async with start_transaction():
                updated = await self.service.update_(
                    organization_id=organization_id,
                    tool_id=tool_id,
                    data=ToolUpdateSchema.model_validate(request),
                )
                return ToolResponseSchema.model_validate(updated)
        except DefinitionNotFoundError as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from error
        except DefinitionRevisionError as error:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error))
        except InvalidDefinitionDraftError as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(error),
            )

    async def publish_tool(
        self,
        *,
        tool_id: UUID,
        organization_id: UUID,
        expected_draft_version: int,
        actor_id: UUID,
    ) -> ToolRevisionResponseSchema:
        try:
            async with start_transaction():
                revision = await self.service.publish(
                    organization_id=organization_id,
                    tool_id=tool_id,
                    expected_draft_version=expected_draft_version,
                    actor_id=actor_id,
                )
                return ToolRevisionResponseSchema.model_validate(revision)
        except DefinitionNotFoundError as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from error
        except DefinitionRevisionError as error:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error))
        except InvalidDefinitionDraftError as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(error),
            )

    async def withdraw_tool(
        self, *, tool_id: UUID, organization_id: UUID
    ) -> ToolResponseSchema:
        try:
            async with start_transaction():
                tool = await self.service.withdraw(
                    organization_id=organization_id,
                    tool_id=tool_id,
                )
                return ToolResponseSchema.model_validate(tool)
        except DefinitionNotFoundError as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from error
        except DefinitionRevisionError as error:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error))

    async def revoke_tool(
        self,
        *,
        tool_id: UUID,
        revision: int,
        organization_id: UUID,
        actor_id: UUID,
        reason: str,
    ) -> ToolRevisionResponseSchema:
        try:
            async with start_transaction():
                row = await self.service.revoke(
                    organization_id=organization_id,
                    tool_id=tool_id,
                    revision=revision,
                    actor_id=actor_id,
                    reason=reason,
                )
                return ToolRevisionResponseSchema.model_validate(row)
        except DefinitionNotFoundError as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from error
        except (DefinitionRevisionError, DefinitionDomainError) as error:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error))

    async def delete_tool(self, tool_id: UUID, organization_id: UUID):
        """Project HTTP deletion onto the domain's non-destructive withdrawal."""
        await self.withdraw_tool(tool_id=tool_id, organization_id=organization_id)
        return {"status": "success", "message": "Tool withdrawn successfully"}


async def _ready_capabilities(organization_id) -> set:
    from eylo.common.database import get_transaction
    from eylo.modules.provider_configs.capabilities import ready_capabilities

    return set(
        await ready_capabilities(
            get_transaction(),
            organization_id,
        )
    )


__all__ = ["ToolController"]
