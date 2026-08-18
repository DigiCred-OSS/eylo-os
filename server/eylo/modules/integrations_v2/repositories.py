"""SQLAlchemy persistence for curated integration organization state.

Repositories load and save rows. They make no policy decision: whether a vendor
may be installed or a tool may execute is the service's and the domain's
business, and nothing here reads or enforces it.

Models returned from here stay inside the module — the service converts them to
schemas before anything crosses the boundary.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from eylo.common.database import get_transaction

from .models import IntegrationV2InstallationModel, IntegrationV2ToolModel


class InstallationRepository:
    """Persistence for one organization's curated vendor installations."""

    def __init__(self, db: AsyncSession | None = None) -> None:
        self._db = db or get_transaction()

    async def get(
        self,
        *,
        organization_id: uuid.UUID,
        installation_id: uuid.UUID,
    ) -> IntegrationV2InstallationModel | None:
        return await self._db.scalar(
            select(IntegrationV2InstallationModel).where(
                IntegrationV2InstallationModel.id == installation_id,
                IntegrationV2InstallationModel.organization_id == organization_id,
                IntegrationV2InstallationModel.deleted.is_(False),
            )
        )

    async def get_by_vendor(
        self,
        *,
        organization_id: uuid.UUID,
        vendor: str,
    ) -> IntegrationV2InstallationModel | None:
        return await self._db.scalar(
            select(IntegrationV2InstallationModel).where(
                IntegrationV2InstallationModel.organization_id == organization_id,
                IntegrationV2InstallationModel.vendor == vendor,
                IntegrationV2InstallationModel.deleted.is_(False),
            )
        )

    async def list_for_organization(
        self,
        *,
        organization_id: uuid.UUID,
    ) -> Sequence[IntegrationV2InstallationModel]:
        result = await self._db.scalars(
            select(IntegrationV2InstallationModel)
            .where(
                IntegrationV2InstallationModel.organization_id == organization_id,
                IntegrationV2InstallationModel.deleted.is_(False),
            )
            .order_by(IntegrationV2InstallationModel.vendor)
        )
        return result.all()

    async def add(
        self,
        installation: IntegrationV2InstallationModel,
    ) -> IntegrationV2InstallationModel:
        self._db.add(installation)
        await self._db.flush()
        return installation


class CuratedToolRepository:
    """Persistence for one organization's curated tool policy rows."""

    def __init__(self, db: AsyncSession | None = None) -> None:
        self._db = db or get_transaction()

    async def get(
        self,
        *,
        organization_id: uuid.UUID,
        tool_id: uuid.UUID,
    ) -> IntegrationV2ToolModel | None:
        return await self._db.scalar(
            select(IntegrationV2ToolModel).where(
                IntegrationV2ToolModel.id == tool_id,
                IntegrationV2ToolModel.organization_id == organization_id,
                IntegrationV2ToolModel.deleted.is_(False),
            )
        )

    async def get_by_wire_id(
        self,
        *,
        organization_id: uuid.UUID,
        wire_id: str,
    ) -> IntegrationV2ToolModel | None:
        return await self._db.scalar(
            select(IntegrationV2ToolModel).where(
                IntegrationV2ToolModel.organization_id == organization_id,
                IntegrationV2ToolModel.wire_id == wire_id,
                IntegrationV2ToolModel.deleted.is_(False),
            )
        )

    async def list_for_installation(
        self,
        *,
        organization_id: uuid.UUID,
        installation_id: uuid.UUID,
    ) -> Sequence[IntegrationV2ToolModel]:
        result = await self._db.scalars(
            select(IntegrationV2ToolModel)
            .where(
                IntegrationV2ToolModel.organization_id == organization_id,
                IntegrationV2ToolModel.installation_id == installation_id,
                IntegrationV2ToolModel.deleted.is_(False),
            )
            .order_by(IntegrationV2ToolModel.wire_id)
        )
        return result.all()

    async def list_by_ids(
        self,
        *,
        organization_id: uuid.UUID,
        tool_ids: list[uuid.UUID],
    ) -> Sequence[IntegrationV2ToolModel]:
        if not tool_ids:
            return []
        result = await self._db.scalars(
            select(IntegrationV2ToolModel)
            .where(
                IntegrationV2ToolModel.organization_id == organization_id,
                IntegrationV2ToolModel.id.in_(tool_ids),
                IntegrationV2ToolModel.deleted.is_(False),
            )
            .order_by(IntegrationV2ToolModel.wire_id)
        )
        return result.all()

    async def add(self, tool: IntegrationV2ToolModel) -> IntegrationV2ToolModel:
        self._db.add(tool)
        await self._db.flush()
        return tool


__all__ = ["CuratedToolRepository", "InstallationRepository"]
