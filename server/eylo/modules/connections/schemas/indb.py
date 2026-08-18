"""Data contracts for the `connections` domain."""

import datetime
from typing import Dict, Optional, Self
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from eylo.common.schemas import EyloBaseOrganizationModelSchema
from eylo.modules.mappers.enums import ConnectionKind

# Re-export enums from models for use in schemas and services
from ..models import ConnectionStatus

__all__ = [
    "ConnectionStatus",
    "ConnectionModelSchema",
    "ConnectionInDb",
    "ConnectionCreateSchema",
]


class ConnectionModelSchema(EyloBaseOrganizationModelSchema):
    integration_id: UUID = Field(
        ...,
        description="The curated vendor installation this connection authorizes.",
    )
    contact_id: Optional[UUID] = Field(
        None,
        description="The ID of the contact this connection belongs to.",
    )
    connection_kind: ConnectionKind = Field(
        ConnectionKind.ORGANIZATION,
        description="The kind of connection. Can be either ORGANIZATION or CONTACT.",
    )
    status: ConnectionStatus = Field(
        ConnectionStatus.INITIATED,
        description="The status of the connection. Can be either INITIATED, ACTIVE, INACTIVE, FAILED, or REVOKED.",
    )
    credentials: Optional[Dict] = None
    credentials_expires_at: Optional[datetime.datetime] = Field(
        None,
        description="The expiration date of the credentials.",
    )
    last_refresh_success_at: Optional[datetime.datetime] = Field(
        None,
        description="The last time the credentials were successfully refreshed.",
    )
    last_refresh_failure_at: Optional[datetime.datetime] = Field(
        None,
        description="The last time the credentials refresh failed.",
    )
    refresh_attempts: Optional[int] = Field(
        0,
        description="The number of attempts to refresh the credentials.",
    )
    is_refresh_exhausted: Optional[bool] = Field(
        False,
        description="Whether the refresh attempts have been exhausted.",
    )


class ConnectionInDb(ConnectionModelSchema):
    pass


class ConnectionCreateSchema(BaseModel):
    organization_id: UUID = Field(
        ..., description="The ID of the organization this connection belongs to."
    )
    integration_id: UUID = Field(
        ...,
        description="Curated vendor installation this connection authorizes.",
    )
    contact_id: Optional[UUID] = Field(
        None,
        description="The ID of the contact this connection belongs to.",
    )
    connection_kind: ConnectionKind = Field(
        ConnectionKind.ORGANIZATION,
        description="The kind of connection. Can be either ORGANIZATION or CONTACT.",
    )
    status: ConnectionStatus = Field(
        ConnectionStatus.INITIATED,
        description="The status of the connection.",
    )
    credentials: Optional[Dict] = Field(
        None,
        description="Connection credentials (access tokens, etc.)",
    )
    credentials_expires_at: Optional[datetime.datetime] = Field(
        None,
        description="The expiration date of the credentials.",
    )

    @model_validator(mode="after")
    def require_exact_owner(self) -> Self:
        if self.connection_kind is ConnectionKind.CONTACT and self.contact_id is None:
            raise ValueError("CONTACT connections require contact_id.")
        if (
            self.connection_kind is ConnectionKind.ORGANIZATION
            and self.contact_id is not None
        ):
            raise ValueError("ORGANIZATION connections cannot set contact_id.")
        return self
