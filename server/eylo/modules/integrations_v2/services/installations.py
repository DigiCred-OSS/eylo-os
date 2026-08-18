"""The curated integration module service.

This is the module's only exit. Every method returns a schema; no SQLAlchemy
model and no repository object crosses the boundary.

The service owns the invariants that outlive any one caller — a vendor is
installed once per organization, an auth kind must be one the deployment can
actually execute, a tool row may only exist under an installation that carries
its binding, and a disabled tool does not run. Enforcing those here rather than
in a route is what stops the CLI, the console, and the agent loop from each
getting a different answer.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from eylo.common.database import get_transaction
from eylo.common.http_egress import HttpEgressPolicyError, HttpOrigin

from ..domain.enums import ToolExecutionMode, VendorAuthKind
from ..domain.errors import (
    IntegrationAlreadyInstalledError,
    ToolApprovalRequiredError,
    ToolBindingUnavailableError,
    ToolExecutionBlockedError,
    VendorNotFoundError,
)
from ..domain.identity import curated_tool_id
from ..domain.offers import CuratedVendorOffer
from ..models import IntegrationV2InstallationModel, IntegrationV2ToolModel
from ..repositories import CuratedToolRepository, InstallationRepository
from ..schemas.indb import CuratedToolInDb, InstallationInDb, ToolExecutionGrant


class CuratedIntegrationService:
    """Install curated vendors and resolve their tools for one organization."""

    def __init__(self, db: AsyncSession | None = None) -> None:
        self._db = db or get_transaction()
        self._installations = InstallationRepository(self._db)
        self._tools = CuratedToolRepository(self._db)

    async def install_vendor(
        self,
        *,
        organization_id: uuid.UUID,
        offer: CuratedVendorOffer,
        auth_kind: VendorAuthKind,
        actor_id: uuid.UUID,
        instance_url: str | None = None,
        oauth_client_id: str | None = None,
        oauth_client_secret: str | None = None,
        oauth_tenant: str | None = None,
    ) -> InstallationInDb:
        """Install one curated vendor for an organization.

        `offer` describes what the running deployment can execute. Taking it as
        a value rather than reading a registry keeps the domain unaware of
        `pipelines/`, and makes "this build cannot run that vendor" a checkable
        precondition instead of a runtime surprise.
        """
        instance_url = _validated_instance_url(offer, instance_url)
        if not offer.supports(auth_kind):
            raise VendorNotFoundError(
                "vendor_auth_unsupported",
                f"Vendor '{offer.vendor}' does not support {auth_kind.value}.",
            )
        existing = await self._installations.get_by_vendor(
            organization_id=organization_id,
            vendor=offer.vendor,
        )
        if existing is not None:
            raise IntegrationAlreadyInstalledError(
                "vendor_already_installed",
                f"Vendor '{offer.vendor}' is already installed.",
            )

        installation = await self._installations.add(
            IntegrationV2InstallationModel(
                organization_id=organization_id,
                vendor=offer.vendor,
                auth_kind=auth_kind.value,
                instance_url=instance_url,
                oauth_client_id=oauth_client_id,
                oauth_client_secret=oauth_client_secret,
                oauth_tenant=oauth_tenant,
                installed_at=datetime.now(timezone.utc),
                installed_by=actor_id,
            )
        )
        return InstallationInDb.model_validate(installation)

    async def list_installations(
        self,
        *,
        organization_id: uuid.UUID,
    ) -> list[InstallationInDb]:
        rows = await self._installations.list_for_organization(
            organization_id=organization_id
        )
        return [InstallationInDb.model_validate(row) for row in rows]

    async def ensure_tool(
        self,
        *,
        organization_id: uuid.UUID,
        offer: CuratedVendorOffer,
        wire_id: str,
    ) -> CuratedToolInDb:
        """Materialize one curated tool's policy row, creating it if absent.

        Called when an agent binds a tool or an operator sets its policy. The
        row's id is derived from the organization and wire id, so it is the same
        id a caller could compute before the row existed.

        Fails closed when this deployment does not carry the binding: a row
        pointing at a callable that cannot run would only defer the failure to
        the moment an agent tried to use it.
        """
        if not offer.carries(wire_id):
            raise ToolBindingUnavailableError(
                "tool_binding_unavailable",
                f"This deployment does not carry '{wire_id}'.",
            )
        existing = await self._tools.get_by_wire_id(
            organization_id=organization_id,
            wire_id=wire_id,
        )
        if existing is not None:
            return CuratedToolInDb.model_validate(existing)

        installation = await self._installations.get_by_vendor(
            organization_id=organization_id,
            vendor=offer.vendor,
        )
        if installation is None:
            raise VendorNotFoundError(
                "vendor_not_installed",
                f"Vendor '{offer.vendor}' is not installed for this organization.",
            )

        tool = IntegrationV2ToolModel(
            id=curated_tool_id(wire_id, organization_id),
            organization_id=organization_id,
            installation_id=installation.id,
            wire_id=wire_id,
            execution_mode=ToolExecutionMode.AUTO.value,
        )
        return CuratedToolInDb.model_validate(await self._tools.add(tool))

    async def set_execution_mode(
        self,
        *,
        organization_id: uuid.UUID,
        offer: CuratedVendorOffer,
        wire_id: str,
        execution_mode: ToolExecutionMode,
    ) -> CuratedToolInDb:
        """Set operator policy for one curated tool, materializing it if needed."""
        await self.ensure_tool(
            organization_id=organization_id,
            offer=offer,
            wire_id=wire_id,
        )
        row = await self._tools.get_by_wire_id(
            organization_id=organization_id,
            wire_id=wire_id,
        )
        if row is None:
            raise ToolBindingUnavailableError(
                "tool_binding_unavailable",
                f"Curated tool '{wire_id}' is unavailable.",
            )
        row.execution_mode = execution_mode.value
        await self._db.flush()
        return CuratedToolInDb.model_validate(row)

    async def list_tools(
        self,
        *,
        organization_id: uuid.UUID,
        tool_ids: list[uuid.UUID],
    ) -> list[CuratedToolInDb]:
        """Every materialized curated tool row, whatever its policy.

        The operator surface, unlike the agent surface, must see a disabled
        tool — otherwise the console shows it as `auto` and the operator cannot
        tell that they turned it off.
        """
        if not tool_ids:
            return []
        rows = await self._tools.list_by_ids(
            organization_id=organization_id,
            tool_ids=tool_ids,
        )
        return [CuratedToolInDb.model_validate(row) for row in rows]

    async def list_offerable_tools(
        self,
        *,
        organization_id: uuid.UUID,
        tool_ids: list[uuid.UUID],
    ) -> list[CuratedToolInDb]:
        """Curated tools that may be offered to a model, in stable order.

        Disabled tools are omitted rather than offered and then refused. A tool
        an agent can see is a tool it will eventually try, and spending a turn
        to be told no is worse than never having been shown it.

        Approval-gated tools stay in the list: the point of approval is that the
        model may ask, and a human decides.
        """
        if not tool_ids:
            return []
        rows = await self._tools.list_by_ids(
            organization_id=organization_id,
            tool_ids=tool_ids,
        )
        return [
            CuratedToolInDb.model_validate(row)
            for row in rows
            if ToolExecutionMode(row.execution_mode) is not ToolExecutionMode.DISABLED
        ]

    async def resolve_for_execution(
        self,
        *,
        organization_id: uuid.UUID,
        tool_id: uuid.UUID,
    ) -> ToolExecutionGrant:
        """Authorize one curated tool call and return what the pipeline needs.

        Policy is read live rather than pinned to a revision: a curated tool's
        definition is code and cannot change under a running deployment, so the
        only mutable fact is whether an operator still permits the call — and a
        tool disabled a moment ago should not run now.
        """
        tool = await self._tools.get(
            organization_id=organization_id,
            tool_id=tool_id,
        )
        if tool is None:
            raise ToolBindingUnavailableError(
                "tool_not_found",
                "Curated tool is not available to this organization.",
            )

        mode = ToolExecutionMode(tool.execution_mode)
        if mode is ToolExecutionMode.DISABLED:
            raise ToolExecutionBlockedError(
                "tool_execution_blocked",
                "Operator policy disables this curated tool.",
            )
        if mode is ToolExecutionMode.REQUIRES_APPROVAL:
            raise ToolApprovalRequiredError(
                "tool_approval_required",
                "This curated tool requires approval before execution.",
            )

        installation = await self._installations.get(
            organization_id=organization_id,
            installation_id=uuid.UUID(str(tool.installation_id)),
        )
        if installation is None:
            raise VendorNotFoundError(
                "vendor_not_installed",
                "The vendor for this curated tool is no longer installed.",
            )

        return ToolExecutionGrant(
            tool_id=uuid.UUID(str(tool.id)),
            wire_id=tool.wire_id,
            vendor=installation.vendor,
            auth_kind=VendorAuthKind(installation.auth_kind),
            instance_url=installation.instance_url,
            installation_id=uuid.UUID(str(installation.id)),
            organization_id=organization_id,
        )


def _validated_instance_url(
    offer: CuratedVendorOffer,
    instance_url: str | None,
) -> str | None:
    """Check a customer-supplied origin before it is ever used as a destination.

    Rejected here rather than at egress: an operator typing a bad URL should be
    told at install time, not by a tool call failing later. The egress guard
    still validates it independently every request.
    """
    if not offer.requires_instance_url:
        if instance_url:
            raise VendorNotFoundError(
                "instance_url_unsupported",
                f"Vendor '{offer.vendor}' has a fixed origin.",
            )
        return None
    if not instance_url or not instance_url.strip():
        raise VendorNotFoundError(
            "instance_url_required",
            f"Vendor '{offer.vendor}' requires an instance URL.",
        )
    try:
        origin = HttpOrigin.parse(instance_url.strip())
    except HttpEgressPolicyError as error:
        raise VendorNotFoundError(
            "instance_url_invalid",
            "Instance URL must be an HTTPS origin without a path or query.",
        ) from error
    return str(origin)


__all__ = ["CuratedIntegrationService"]
