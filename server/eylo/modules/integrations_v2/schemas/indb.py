"""Boundary shapes returned by the curated integration module service.

These are the only types that leave the module. No SQLAlchemy model and no
repository object crosses the boundary, so a caller cannot lazy-load a
relationship, mutate a row by accident, or depend on the persistence shape.

They validate shape, not business truth: whether a tool may execute is decided
by the service and the domain, not by a schema.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import ConfigDict, Field

from eylo.common.schemas import EyloBaseSchema

from ..domain.enums import ToolExecutionMode, VendorAuthKind


class InstallationInDb(EyloBaseSchema):
    """One organization's installation of one curated vendor."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    vendor: str
    auth_kind: VendorAuthKind
    instance_url: str | None = None
    oauth_client_id: str | None = None
    oauth_client_secret: str | None = Field(
        default=None,
        repr=False,
        description="Encrypted envelope. Never included in an API response.",
    )
    oauth_tenant: str | None = None
    installed_at: datetime
    installed_by: uuid.UUID


class CuratedToolInDb(EyloBaseSchema):
    """One organization's policy row for one curated tool."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    installation_id: uuid.UUID
    wire_id: str
    execution_mode: ToolExecutionMode


class ToolExecutionGrant(EyloBaseSchema):
    """Everything the execution pipeline needs to run one curated tool.

    Deliberately flat and resolved: the pipeline receives values, not a handle
    it could query further. Policy is not carried: `resolve_for_execution`
    already refused a disabled or approval-gated tool, so by the time a grant
    exists the mode has no reader.
    """

    model_config = ConfigDict(from_attributes=True)

    tool_id: uuid.UUID
    wire_id: str
    vendor: str
    auth_kind: VendorAuthKind
    instance_url: str | None = None
    installation_id: uuid.UUID
    organization_id: uuid.UUID


__all__ = [
    "CuratedToolInDb",
    "InstallationInDb",
    "ToolExecutionGrant",
]
