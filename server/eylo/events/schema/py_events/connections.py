"""Connection-related event schemas."""

from typing import Optional
from uuid import UUID

from pydantic import Field

from eylo.events.schema.py_events.base import BaseEvent


class ConnectionExpiredEvent(BaseEvent):
    """Event emitted when a connection token refresh fails and connection expires.

    This event is triggered when:
    - Token refresh fails after maximum retry attempts
    - Refresh token is invalid or revoked
    - User needs to re-authorize the connection
    """

    connection_id: UUID = Field(..., description="ID of the expired connection")
    organization_id: UUID = Field(..., description="Organization ID")
    integration_id: UUID = Field(
        ..., description="Curated vendor installation ID"
    )
    vendor: Optional[str] = Field(
        None, description="Curated vendor id, so a consumer can name it to the user"
    )
    contact_id: Optional[UUID] = Field(
        None, description="Contact ID who owns the connection"
    )
    reason: str = Field(..., description="Reason for expiration")


class ConnectionStartedEvent(BaseEvent):
    """Event emitted when OAuth flow is initiated for a connection.

    This event is triggered when a contact starts the OAuth authorization flow.
    """

    integration_id: UUID = Field(
        ..., description="Curated vendor installation ID"
    )
    vendor: Optional[str] = Field(None, description="Curated vendor id")
    contact_id: UUID = Field(..., description="Contact ID initiating the connection")
    organization_id: UUID = Field(..., description="Organization ID")


class ConnectionSuccessEvent(BaseEvent):
    """Event emitted when a connection is successfully established.

    This event is triggered after successful OAuth callback and token exchange.
    """

    connection_id: UUID = Field(..., description="ID of the created connection")
    contact_id: UUID = Field(..., description="Contact ID who owns the connection")
    organization_id: UUID = Field(..., description="Organization ID")
    integration_name: str = Field(..., description="Name of the integration")
    integration_id: UUID = Field(
        ..., description="Curated vendor installation ID for matching"
    )
    vendor: Optional[str] = Field(None, description="Curated vendor id")


class ConnectionFailedEvent(BaseEvent):
    """Event emitted when a connection attempt fails.

    This event is triggered when OAuth flow fails or token exchange errors.
    """

    contact_id: UUID = Field(..., description="Contact ID who attempted the connection")
    organization_id: UUID = Field(..., description="Organization ID")
    integration_name: str = Field(..., description="Name of the integration")
    error: str = Field(..., description="Error message describing the failure")
    integration_id: UUID = Field(
        ..., description="Curated vendor installation ID for matching"
    )
    vendor: Optional[str] = Field(None, description="Curated vendor id")
