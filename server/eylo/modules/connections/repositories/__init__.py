"""Persistence access for the `connections` domain."""

from datetime import datetime
from typing import List, Type
from uuid import UUID

from sqlalchemy import case, delete, or_, select

from eylo.common.repositories import BaseORMRepository, map_schema_to_model
from eylo.modules.connections.models import (
    ConnectionKind,
    ConnectionModel,
    ConnectionStatus,
)
from eylo.modules.connections.schemas.indb import (
    ConnectionCreateSchema,
)


class ConnectionRepository(BaseORMRepository[ConnectionModel]):
    @property
    def model(self) -> Type[ConnectionModel]:
        return ConnectionModel

    async def create_(self, data: ConnectionCreateSchema) -> ConnectionModel:
        """Create a new connection in the database.

        Ownership and installation constraints are enforced by both the input
        schema and composite database foreign keys.
        """
        conn = map_schema_to_model(ConnectionModel, data)
        return await self.save_(conn)

    async def list_by_organization(
        self,
        organization_id: UUID,
        integration_id: UUID | None = None,
        status: ConnectionStatus | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> List[ConnectionModel]:
        """List all connections for an organization with pagination.

        Args:
            organization_id: Organization to filter by
            integration_id: Optional integration filter
            status: Optional status filter (e.g., "ACTIVE")
            offset: Number of records to skip (for pagination)
            limit: Maximum number of records to return

        Returns:
            List of matching connections

        """
        stmt = select(ConnectionModel).where(
            ConnectionModel.organization_id == organization_id,
            ConnectionModel.deleted.is_(False),
        )

        if integration_id:
            stmt = stmt.where(ConnectionModel.integration_id == integration_id)

        if status:
            stmt = stmt.where(ConnectionModel.status == status)

        stmt = stmt.order_by(ConnectionModel.created_at.desc())
        stmt = stmt.offset(offset).limit(limit)

        result = await self.db_session.execute(stmt)
        return list(result.scalars().all())

    async def get_for_deletion(
        self,
        *,
        organization_id: UUID,
        connection_id: UUID,
    ) -> ConnectionModel | None:
        """Lock one visible connection inside its owning organization."""
        result = await self.db_session.execute(
            select(ConnectionModel)
            .where(
                ConnectionModel.id == connection_id,
                ConnectionModel.organization_id == organization_id,
                ConnectionModel.deleted.is_(False),
            )
            .with_for_update()
        )
        return result.scalar_one_or_none()

    async def get_active_connection_for_execution(
        self,
        integration_id: UUID,
        organization_id: UUID,
        contact_id: UUID | None = None,
    ) -> ConnectionModel | None:
        """Get the best active curated vendor connection for execution.

        Args:
            integration_id: Curated vendor installation to find a connection for
            organization_id: Organization context
            contact_id: Optional contact context

        Returns:
            Active connection or None

        """
        return await self._active_connection_for_execution(
            ConnectionModel.integration_id == integration_id,
            organization_id=organization_id,
            contact_id=contact_id,
        )

    async def _active_connection_for_execution(
        self,
        owner_clause,
        *,
        organization_id: UUID,
        contact_id: UUID | None,
    ) -> ConnectionModel | None:
        """Select one active connection under an owner, contact level first."""
        stmt = select(ConnectionModel).where(
            owner_clause,
            ConnectionModel.organization_id == organization_id,
            ConnectionModel.status == ConnectionStatus.ACTIVE,
            ConnectionModel.deleted.is_(False),
        )

        if contact_id:
            # Find either CONTACT connection for this user OR ORGANIZATION connection
            stmt = stmt.where(
                or_(
                    ConnectionModel.contact_id == contact_id,
                    ConnectionModel.connection_kind == ConnectionKind.ORGANIZATION,
                )
            )
        else:
            # Only ORGANIZATION connections allowed if no contact context
            stmt = stmt.where(
                ConnectionModel.connection_kind == ConnectionKind.ORGANIZATION
            )

        stmt = stmt.order_by(
            case(
                (ConnectionModel.connection_kind == ConnectionKind.CONTACT, 0),
                else_=1,
            ),
            ConnectionModel.updated_at.desc(),
            ConnectionModel.id.desc(),
        ).limit(1)
        return await self.db_session.scalar(stmt)

    async def get_expiring_connections(
        self,
        expiry_threshold: datetime,
    ) -> List[ConnectionModel]:
        """Get active OAuth2 connections that are expiring soon and need refresh.

        Returns connections where:
        - status is ACTIVE
        - credentials_expires_at exists and is before threshold
        - is_refresh_exhausted is False
        - refresh_token exists in credentials

        Args:
            expiry_threshold: DateTime threshold (e.g. NOW() + 10 minutes)

        Returns:
            List of connections needing token refresh

        """
        stmt = (
            select(ConnectionModel)
            .where(
                ConnectionModel.status == ConnectionStatus.ACTIVE,
                ConnectionModel.deleted.is_(False),
                ConnectionModel.credentials_expires_at.isnot(None),
                ConnectionModel.credentials_expires_at < expiry_threshold,
                ConnectionModel.is_refresh_exhausted.is_not(True),
            )
            .order_by(ConnectionModel.credentials_expires_at.asc())
            .with_for_update(skip_locked=True)
        )

        result = await self.db_session.execute(stmt)
        connections = list(result.scalars().all())

        # Filter to only those with refresh_token in credentials
        return [
            conn
            for conn in connections
            if (conn.credentials or {}).get("refresh_token") is not None
        ]

    async def delete_old_invalidated_connections(
        self, cutoff_date: datetime
    ) -> List[UUID]:
        """Delete connections with invalidated statuses older than cutoff date.

        Deletes connections where:
        - status is REVOKED, FAILED, or INACTIVE
        - updated_at is before cutoff_date
        - Returns list of deleted connection IDs

        ACTIVE connections are never deleted (fresh tokens kept forever).

        Args:
            cutoff_date: Delete connections updated before this date

        Returns:
            List of deleted connection IDs

        """
        # First fetch the connections to get their IDs
        select_stmt = select(ConnectionModel.id).where(
            ConnectionModel.status.notin_(
                [
                    ConnectionStatus.ACTIVE,
                ]
            ),
            ConnectionModel.updated_at < cutoff_date,
            ConnectionModel.connection_kind == ConnectionKind.CONTACT,
        )

        result = await self.db_session.execute(select_stmt)
        connection_ids = [row[0] for row in result.all()]

        if not connection_ids:
            return []

        # Delete the connections
        delete_stmt = delete(ConnectionModel).where(
            ConnectionModel.id.in_(connection_ids)
        )

        await self.db_session.execute(delete_stmt)

        return connection_ids

    async def list_by_ids(
        self,
        connection_ids: list[UUID],
        organization_id: UUID,
    ) -> list[ConnectionModel]:
        """Bulk fetch connections by IDs within an organization.

        Args:
            connection_ids: List of connection IDs to fetch
            organization_id: Organization ID for access control

        Returns:
            List of connection models matching the IDs

        """
        if not connection_ids:
            return []

        filters = [
            self.model.id.in_(connection_ids),
            self.model.organization_id == organization_id,
        ]
        return await self.filter_all_(filters=filters)
