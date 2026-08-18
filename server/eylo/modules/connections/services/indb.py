"""Application services for the `connections` domain."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from eylo.common.services import EyloBaseService
from eylo.modules.connections.schemas.indb import ConnectionInDb
from eylo.modules.contacts.schemas.indb import ContactRef
from eylo.modules.contacts.service import ContactService

from ..models import ConnectionStatus
from ..repositories import ConnectionRepository
from ..schemas.indb import ConnectionCreateSchema

logger = logging.getLogger(__name__)


class ConnectionService(EyloBaseService[ConnectionInDb]):
    """ConnectionService behavior for the "connections" domain."""

    @property
    def schema(self) -> type[ConnectionInDb]:
        """Schema for the "connections" domain."""
        return ConnectionInDb

    @property
    def repository(self) -> ConnectionRepository:
        """Repository for the "connections" domain."""
        return self._repository or ConnectionRepository()

    @repository.setter
    def repository(self, value: ConnectionRepository):
        """Repository for the "connections" domain."""
        self._repository = value

    def __init__(self, db: Optional[AsyncSession] = None):
        """Initialize Connection Service."""
        self._repository = ConnectionRepository(db=db)

    async def create_(self, data: ConnectionCreateSchema) -> ConnectionInDb:
        """Create for the "connections" domain."""
        if data.contact_id is not None:
            await ContactService(self.repository.db_session).require_active(
                ContactRef(
                    organization_id=data.organization_id,
                    contact_id=data.contact_id,
                ),
                for_update=True,
            )
        entity = await self.repository.create_(data)
        if entity:
            return ConnectionInDb.model_validate(entity)
        raise ValueError("Connection not found")

    async def list_by_organization(
        self,
        organization_id,
        integration_id=None,
        status: str | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> list[ConnectionInDb]:
        """List connections for an organization with pagination.

        Args:
            organization_id: Organization to filter by
            integration_id: Optional integration filter
            status: Optional status filter
            offset: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of connections

        """
        connections = await self.repository.list_by_organization(
            organization_id=organization_id,
            integration_id=integration_id,
            status=status,
            offset=offset,
            limit=limit,
        )
        return [ConnectionInDb.model_validate(conn) for conn in connections]

    async def list_by_ids(
        self,
        connection_ids: list[UUID],
        organization_id: UUID,
    ) -> list[ConnectionInDb]:
        """Bulk fetch connections by IDs within an organization.

        Args:
            connection_ids: List of connection IDs to fetch
            organization_id: Organization ID for access control

        Returns:
            List of connection schema objects matching the provided IDs

        """
        connections = await self.repository.list_by_ids(
            connection_ids=connection_ids,
            organization_id=organization_id,
        )
        return self.orm_to_schema_list(connections)

    async def delete_connection(
        self,
        *,
        organization_id: UUID,
        connection_id: UUID,
    ) -> bool:
        """Purge and hide one connection while retaining its audit row."""
        connection = await self.repository.get_for_deletion(
            organization_id=organization_id,
            connection_id=connection_id,
        )
        if connection is None:
            return False

        connection.status = ConnectionStatus.REVOKED
        connection.credentials = {}
        connection.credentials_expires_at = None
        await self.repository.delete_(connection)
        return True

    async def get_active_connection_for_execution(
        self,
        integration_id,
        organization_id,
        contact_id=None,
    ) -> ConnectionInDb | None:
        """Get active connection for tool execution.

        Looks for an active connection that can be used for executing tools.
        Checks both CONTACT-level and ORGANIZATION-level connections.

        Args:
            integration_id: Integration to find connection for
            organization_id: Organization context
            contact_id: Optional contact ID for CONTACT-level connections

        Returns:
            Active connection if found, None otherwise

        """
        connection = await self.repository.get_active_connection_for_execution(
            integration_id=integration_id,
            organization_id=organization_id,
            contact_id=contact_id,
        )

        if connection:
            return ConnectionInDb.model_validate(connection)

        return None

    async def cleanup_old_invalidated_connections(
        self, retention_days: int = 30
    ) -> tuple[int, list[str]]:
        """Cleanup Old Invalidated Connections."""
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=retention_days)

        deleted_connections = await self.repository.delete_old_invalidated_connections(
            cutoff_date=cutoff_date
        )

        return len(deleted_connections), [str(cid) for cid in deleted_connections]
