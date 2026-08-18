"""Persistence access for the `tools` domain."""

from uuid import UUID

from eylo.common.repositories import BaseORMRepository, map_schema_to_model
from eylo.modules.tools.models import ToolModel
from eylo.modules.tools.schemas.indb import ToolCreateSchema


class ToolRepository(BaseORMRepository[ToolModel]):
    """ToolRepository behavior for the "tools" domain."""

    @property
    def model(self) -> type[ToolModel]:
        """Model for the "tools" domain."""
        return ToolModel

    async def create_(self, data: ToolCreateSchema) -> ToolModel:
        """Create for the "tools" domain."""
        tool = map_schema_to_model(ToolModel, data)
        return await self.save_(tool)

    async def list_by_mcp_server(
        self, organization_id: UUID, server_id: UUID
    ) -> list[ToolModel]:
        """List Tools by MCP server."""
        filters = [
            ToolModel.organization_id == organization_id,
            ToolModel.mcp_server_id == server_id,
            ~ToolModel.deleted,
        ]
        return await self.filter_all_(filters)

    async def list_by_ids(
        self,
        tool_ids: list[UUID],
        organization_id: UUID,
    ) -> list[ToolModel]:
        """Bulk fetch tools by IDs within an organization.

        Args:
            tool_ids: List of tool IDs to fetch
            organization_id: Organization ID for access control

        Returns:
            List of tool models matching the IDs

        """
        if not tool_ids:
            return []

        filters = [
            ToolModel.id.in_(tool_ids),
            ToolModel.organization_id == organization_id,
            ~ToolModel.deleted,
        ]
        return await self.filter_all_(filters)
