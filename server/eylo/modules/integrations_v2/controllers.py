"""Transport translation for the curated integration surface.

Controllers are composition adapters. This one is the single place that reads
the curated registry — which lives in `pipelines/` — and turns it into the
`CuratedVendorOffer` value the domain accepts. Inbound routes and controllers
are the permitted composition edge from modules to pipelines.

Nothing here decides policy. Domain errors carry codes; this layer only chooses
which HTTP status each code deserves.
"""

from __future__ import annotations

import html
import json
import uuid
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

from fastapi import HTTPException, status
from fastapi.responses import HTMLResponse

from eylo.common.database import start_transaction
from eylo.common.revisions import DefinitionRevisionError

from .domain.enums import ToolExecutionMode, VendorAuthKind
from .domain.errors import (
    IntegrationAlreadyInstalledError,
    IntegrationsV2Error,
    ToolBindingUnavailableError,
    VendorNotFoundError,
)
from .domain.offers import CuratedVendorOffer
from .schemas.api import (
    AuthorizationRedirectSchema,
    ConnectionAggregateSchema,
    ConnectionOwnerSummarySchema,
    ConnectionSchema,
    CuratedToolCatalogSchema,
    CuratedVendorDetailSchema,
    CuratedVendorSummarySchema,
    InstallationSchema,
    InstalledToolSchema,
)
from .services.installations import CuratedIntegrationService

if TYPE_CHECKING:
    from eylo.modules.connections.schemas.indb import ConnectionInDb
    from eylo.modules.contacts.schemas.indb import ContactInDb
    from eylo.pipelines.integrations_v2.contracts import CuratedToolSpec

_NOT_FOUND_CODES = frozenset(
    {
        "vendor_not_registered",
        "vendor_not_installed",
        "tool_not_found",
        "tool_binding_unavailable",
    }
)


class CuratedIntegrationController:
    """Translate curated integration requests and results."""

    async def list_vendors(
        self,
        *,
        organization_id: uuid.UUID,
    ) -> list[CuratedVendorSummarySchema]:
        registry = self._registry()
        async with start_transaction():
            installed = {
                row.vendor
                for row in await CuratedIntegrationService().list_installations(
                    organization_id=organization_id
                )
            }
        return [
            self._vendor_summary(spec, registry, installed)
            for spec in registry.vendors()
        ]

    async def get_vendor(
        self,
        *,
        organization_id: uuid.UUID,
        vendor: str,
    ) -> CuratedVendorDetailSchema:
        registry = self._registry()
        spec = registry.vendor(vendor)
        if spec is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Curated vendor not found.",
            )
        async with start_transaction():
            installed = {
                row.vendor
                for row in await CuratedIntegrationService().list_installations(
                    organization_id=organization_id
                )
            }
        summary = self._vendor_summary(spec, registry, installed)
        return CuratedVendorDetailSchema(
            **summary.model_dump(by_alias=False),
            tools=[
                CuratedToolCatalogSchema(
                    wire_id=tool.wire_id,
                    name=tool.name,
                    agent_name=tool.qualified_name,
                    display_name=tool.display_name,
                    description=tool.description,
                    effect=tool.effect,
                    scopes=list(tool.scopes),
                )
                for tool in registry.tools_for(vendor)
            ],
        )

    async def install_vendor(
        self,
        *,
        organization_id: uuid.UUID,
        vendor: str,
        auth_kind: VendorAuthKind,
        actor_id: uuid.UUID,
        instance_url: str | None = None,
        oauth_client_id: str | None = None,
        oauth_client_secret: str | None = None,
        oauth_tenant: str | None = None,
    ) -> InstallationSchema:
        from eylo.pipelines.integrations_v2.oauth import encrypt_client_secret

        offer, spec = self._offer(vendor)
        if auth_kind is VendorAuthKind.OAUTH2:
            if not oauth_client_id or not oauth_client_secret:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="OAuth installs require your own client id and secret.",
                )
            if spec.oauth is not None and spec.oauth.requires_tenant and not oauth_tenant:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"{spec.display_name} requires a tenant identifier.",
                )
            oauth_client_secret = encrypt_client_secret(oauth_client_secret)
        elif oauth_client_id or oauth_client_secret or oauth_tenant:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="OAuth app fields apply only to an oauth2 install.",
            )
        try:
            async with start_transaction():
                installation = await CuratedIntegrationService().install_vendor(
                    organization_id=organization_id,
                    offer=offer,
                    auth_kind=auth_kind,
                    actor_id=actor_id,
                    instance_url=instance_url,
                    oauth_client_id=oauth_client_id,
                    oauth_client_secret=oauth_client_secret,
                    oauth_tenant=oauth_tenant,
                )
        except IntegrationsV2Error as error:
            raise self._http_error(error) from None
        return InstallationSchema(
            id=installation.id,
            vendor=installation.vendor,
            display_name=spec.display_name,
            auth_kind=installation.auth_kind,
            instance_url=installation.instance_url,
            oauth_client_id=installation.oauth_client_id,
            oauth_tenant=installation.oauth_tenant,
            installed_at=installation.installed_at,
            installed_by=installation.installed_by,
        )

    async def list_installations(
        self,
        *,
        organization_id: uuid.UUID,
    ) -> list[InstallationSchema]:
        registry = self._registry()
        async with start_transaction():
            rows = await CuratedIntegrationService().list_installations(
                organization_id=organization_id
            )
        return [
            InstallationSchema(
                id=row.id,
                vendor=row.vendor,
                display_name=(
                    spec.display_name
                    if (spec := registry.vendor(row.vendor)) is not None
                    else row.vendor
                ),
                auth_kind=row.auth_kind,
                instance_url=row.instance_url,
                oauth_client_id=row.oauth_client_id,
                oauth_tenant=row.oauth_tenant,
                installed_at=row.installed_at,
                installed_by=row.installed_by,
            )
            for row in rows
        ]

    async def list_connections(
        self,
        *,
        organization_id: uuid.UUID,
    ) -> list[ConnectionSchema]:
        """List curated connections without allowing credential projection."""
        from eylo.modules.connections.services.indb import ConnectionService

        registry = self._registry()
        async with start_transaction(ro=True) as session:
            service = CuratedIntegrationService(session)
            installations = await service.list_installations(
                organization_id=organization_id
            )
            connections = await ConnectionService(session).list_by_organization(
                organization_id=organization_id
            )
        vendors = {row.id: row.vendor for row in installations}
        result: list[ConnectionSchema] = []
        for connection in connections:
            vendor = vendors.get(connection.integration_id)
            spec = registry.vendor(vendor) if vendor is not None else None
            result.append(
                ConnectionSchema(
                    id=connection.id,
                    vendor=vendor or "unknown",
                    display_name=spec.display_name if spec is not None else vendor,
                    connection_kind=connection.connection_kind.value,
                    status=connection.status.value,
                    contact_id=connection.contact_id,
                    credentials_expires_at=connection.credentials_expires_at,
                    created_at=connection.created_at,
                    updated_at=connection.updated_at,
                )
            )
        return result

    async def list_connection_aggregates(
        self,
        *,
        organization_id: uuid.UUID,
    ) -> list[ConnectionAggregateSchema]:
        """List connections with tenant-scoped, human-readable owners."""
        from eylo.modules.connections.services.indb import ConnectionService
        from eylo.modules.contacts.service import ContactService
        from eylo.modules.organizations.services import OrganizationService

        registry = self._registry()
        async with start_transaction(ro=True) as session:
            installations = await CuratedIntegrationService(
                session
            ).list_installations(organization_id=organization_id)
            connections = await ConnectionService(session).list_by_organization(
                organization_id=organization_id
            )
            contact_ids = [
                connection.contact_id
                for connection in connections
                if connection.contact_id is not None
            ]
            contacts = await ContactService(session).list_by_ids(
                contact_ids,
                organization_id,
            )
            organization = await OrganizationService(session).get_(organization_id)

        vendors = {row.id: row.vendor for row in installations}
        contacts_by_id = {contact.id: contact for contact in contacts}
        result: list[ConnectionAggregateSchema] = []
        for connection in connections:
            vendor = vendors.get(connection.integration_id)
            spec = registry.vendor(vendor) if vendor is not None else None
            owner = self._connection_owner_summary(
                connection=connection,
                organization_id=organization_id,
                organization_name=organization.name,
                contacts_by_id=contacts_by_id,
            )
            result.append(
                ConnectionAggregateSchema(
                    id=connection.id,
                    vendor=vendor or "unknown",
                    display_name=spec.display_name if spec is not None else vendor,
                    connection_kind=connection.connection_kind,
                    status=connection.status,
                    contact_id=connection.contact_id,
                    credentials_expires_at=connection.credentials_expires_at,
                    created_at=connection.created_at,
                    updated_at=connection.updated_at,
                    owner=owner,
                )
            )
        return result

    @staticmethod
    def _connection_owner_summary(
        *,
        connection: ConnectionInDb,
        organization_id: uuid.UUID,
        organization_name: str,
        contacts_by_id: dict[uuid.UUID, ContactInDb],
    ) -> ConnectionOwnerSummarySchema:
        if connection.contact_id is None:
            return ConnectionOwnerSummarySchema(
                id=organization_id,
                kind=connection.connection_kind,
                display_name=organization_name,
            )

        contact = contacts_by_id.get(connection.contact_id)
        candidates = (
            contact.name if contact is not None else None,
            contact.external_id if contact is not None else None,
            str(contact.primary_email) if contact and contact.primary_email else None,
            contact.primary_phone if contact is not None else None,
        )
        display_name = next(
            (
                candidate.strip()
                for candidate in candidates
                if candidate is not None and candidate.strip()
            ),
            f"Unnamed contact · …{str(connection.contact_id)[-8:]}",
        )
        return ConnectionOwnerSummarySchema(
            id=connection.contact_id,
            kind=connection.connection_kind,
            display_name=display_name,
        )

    async def delete_connection(
        self,
        *,
        organization_id: uuid.UUID,
        connection_id: uuid.UUID,
    ) -> None:
        """Delete one curated connection without exposing cross-tenant existence."""
        from eylo.modules.connections.services.indb import ConnectionService

        async with start_transaction() as session:
            deleted = await ConnectionService(session).delete_connection(
                organization_id=organization_id,
                connection_id=connection_id,
            )
        if not deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    async def list_vendor_tools(
        self,
        *,
        organization_id: uuid.UUID,
        vendor: str,
    ) -> list[InstalledToolSchema]:
        """Every curated tool for one installed vendor, with its live policy.

        Tools with no row yet report the default `auto`: a materialized row and
        an unmaterialized one behave identically until an operator changes
        something, and showing that difference would only invite questions
        about an implementation detail.
        """
        registry = self._registry()
        offer, _spec = self._offer(vendor)
        async with start_transaction():
            service = CuratedIntegrationService()
            installation = next(
                (
                    row
                    for row in await service.list_installations(
                        organization_id=organization_id
                    )
                    if row.vendor == vendor
                ),
                None,
            )
            if installation is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Curated vendor is not installed.",
                )
            rows = await service.list_tools(
                organization_id=organization_id,
                tool_ids=[
                    curated_tool_id(spec.wire_id, organization_id)
                    for spec in registry.tools_for(vendor)
                ],
            )
        modes = {row.wire_id: row.execution_mode for row in rows}
        return [
            InstalledToolSchema(
                id=curated_tool_id(spec.wire_id, organization_id),
                wire_id=spec.wire_id,
                name=spec.name,
                agent_name=spec.qualified_name,
                display_name=spec.display_name,
                description=spec.description,
                effect=spec.effect,
                execution_mode=modes.get(spec.wire_id, ToolExecutionMode.AUTO),
            )
            for spec in registry.tools_for(vendor)
            if offer.carries(spec.wire_id)
        ]

    async def set_execution_mode(
        self,
        *,
        organization_id: uuid.UUID,
        vendor: str,
        tool_name: str,
        execution_mode: ToolExecutionMode,
    ) -> InstalledToolSchema:
        offer, _spec = self._offer(vendor)
        wire_id = f"{vendor}.{tool_name}"
        registry = self._registry()
        spec = registry.tool(wire_id)
        if spec is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Curated tool not found.",
            )
        try:
            async with start_transaction():
                row = await CuratedIntegrationService().set_execution_mode(
                    organization_id=organization_id,
                    offer=offer,
                    wire_id=wire_id,
                    execution_mode=execution_mode,
                )
        except IntegrationsV2Error as error:
            raise self._http_error(error) from None
        return InstalledToolSchema(
            id=row.id,
            wire_id=row.wire_id,
            name=spec.name,
            agent_name=spec.qualified_name,
            display_name=spec.display_name,
            description=spec.description,
            effect=spec.effect,
            execution_mode=row.execution_mode,
        )

    async def connect_with_credential(
        self,
        *,
        organization_id: uuid.UUID,
        vendor: str,
        api_key: str | None,
        username: str | None,
        password: str | None,
        contact_id: uuid.UUID | None,
    ) -> ConnectionSchema:
        """Store a directly-entered credential for a non-OAuth vendor."""
        from eylo.modules.connections.schemas.indb import (
            ConnectionCreateSchema,
            ConnectionKind,
            ConnectionStatus,
        )
        from eylo.modules.connections.services.indb import ConnectionService

        _offer, spec = self._offer(vendor)
        async with start_transaction():
            installation = await self._installation(organization_id, vendor)
            credentials = _credential_values(installation.auth_kind, api_key, username, password)
            connection = await ConnectionService().create_(
                ConnectionCreateSchema(
                    organization_id=organization_id,
                    integration_id=installation.id,
                    contact_id=contact_id,
                    connection_kind=(
                        ConnectionKind.CONTACT
                        if contact_id is not None
                        else ConnectionKind.ORGANIZATION
                    ),
                    status=ConnectionStatus.ACTIVE,
                    credentials=credentials,
                )
            )
        return ConnectionSchema(
            id=connection.id,
            vendor=spec.vendor,
            display_name=spec.display_name,
            connection_kind=connection.connection_kind.value,
            status=connection.status.value,
            contact_id=connection.contact_id,
            credentials_expires_at=connection.credentials_expires_at,
            created_at=connection.created_at,
            updated_at=connection.updated_at,
        )

    async def begin_authorization(
        self,
        *,
        organization_id: uuid.UUID,
        vendor: str,
        contact_id: uuid.UUID | None,
    ) -> AuthorizationRedirectSchema:
        from eylo.pipelines.integrations_v2.oauth import begin_authorization

        _offer, spec = self._offer(vendor)
        async with start_transaction():
            installation = await self._installation(organization_id, vendor)
            try:
                redirect = await begin_authorization(
                    installation=installation,
                    vendor=spec,
                    contact_id=contact_id,
                )
            except IntegrationsV2Error as error:
                raise self._http_error(error) from None
        return AuthorizationRedirectSchema(
            authorization_url=redirect.authorization_url,
            callback_origin=_origin(redirect.redirect_uri),
            state=redirect.state,
        )

    async def complete_authorization(
        self,
        *,
        organization_id: uuid.UUID,
        vendor: str,
        code: str,
        state: str,
    ) -> ConnectionSchema:
        from eylo.pipelines.integrations_v2.oauth import complete_authorization

        _offer, spec = self._offer(vendor)
        async with start_transaction():
            installation = await self._installation(organization_id, vendor)
            try:
                connection_id = await complete_authorization(
                    code=code, state=state, installation=installation, vendor=spec
                )
            except IntegrationsV2Error as error:
                raise self._http_error(error) from None
        return ConnectionSchema(
            id=connection_id,
            vendor=spec.vendor,
            connection_kind="ORGANIZATION",
            status="ACTIVE",
        )

    async def grant_tool_to_agent(
        self,
        *,
        organization_id: uuid.UUID,
        agent_id: uuid.UUID,
        vendor: str,
        tool_name: str,
        expected_draft_version: int,
    ) -> InstalledToolSchema:
        """Grant one curated tool to an agent's draft.

        The tool row is materialized first, because `agent_tools.curated_tool_id`
        has a foreign key: a grant cannot reference a policy row that does not
        exist yet.
        """
        from eylo.modules.agents.exceptions import AgentNotFoundError
        from eylo.modules.agents.services.indb import AgentService, AgentToolService
        from eylo.modules.agents.services.revisions import AgentRevisionService

        offer, _spec = self._offer(vendor)
        registry = self._registry()
        wire_id = f"{vendor}.{tool_name}"
        spec = registry.tool(wire_id)
        if spec is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Curated tool not found.",
            )
        try:
            async with start_transaction() as session:
                try:
                    await AgentService(session).get_by_organization_and_id(
                        organization_id=organization_id,
                        pk=agent_id,
                    )
                except AgentNotFoundError:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND
                    ) from None
                try:
                    row = await CuratedIntegrationService().ensure_tool(
                        organization_id=organization_id,
                        offer=offer,
                        wire_id=wire_id,
                    )
                except IntegrationsV2Error as error:
                    raise self._http_error(error) from None
                service = AgentToolService(session)
                await self._require_unique_model_name(
                    service=service,
                    organization_id=organization_id,
                    agent_id=agent_id,
                    registry=registry,
                    candidate=spec.qualified_name,
                    candidate_tool_id=row.id,
                )
                if row.id not in await service.list_curated_tool_ids(agent_id):
                    await service.grant_curated_tool(
                        agent_id=agent_id,
                        organization_id=organization_id,
                        curated_tool_id=row.id,
                    )
                    await AgentRevisionService(session).mark_draft_changed(
                        organization_id=organization_id,
                        agent_id=agent_id,
                        expected_draft_version=expected_draft_version,
                    )
        except DefinitionRevisionError as error:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(error),
            ) from error
        return InstalledToolSchema(
            id=row.id,
            wire_id=row.wire_id,
            name=spec.name,
            agent_name=spec.qualified_name,
            display_name=spec.display_name,
            description=spec.description,
            effect=spec.effect,
            execution_mode=row.execution_mode,
        )

    async def revoke_tool_from_agent(
        self,
        *,
        organization_id: uuid.UUID,
        agent_id: uuid.UUID,
        vendor: str,
        tool_name: str,
        expected_draft_version: int,
    ) -> None:
        from eylo.modules.agents.exceptions import AgentNotFoundError
        from eylo.modules.agents.services.indb import AgentService, AgentToolService
        from eylo.modules.agents.services.revisions import AgentRevisionService

        try:
            async with start_transaction() as session:
                try:
                    await AgentService(session).get_by_organization_and_id(
                        organization_id=organization_id,
                        pk=agent_id,
                    )
                except AgentNotFoundError:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND
                    ) from None
                service = AgentToolService(session)
                removed = await service.revoke_curated_tool(
                    agent_id=agent_id,
                    curated_tool_id=curated_tool_id(
                        f"{vendor}.{tool_name}", organization_id
                    ),
                )
                if removed:
                    await AgentRevisionService(session).mark_draft_changed(
                        organization_id=organization_id,
                        agent_id=agent_id,
                        expected_draft_version=expected_draft_version,
                    )
        except DefinitionRevisionError as error:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(error),
            ) from error
        if not removed:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="This agent does not have that curated tool.",
            )

    async def replace_agent_tools(
        self,
        *,
        organization_id: uuid.UUID,
        agent_id: uuid.UUID,
        tool_ids: list[uuid.UUID],
        expected_draft_version: int,
    ) -> list[InstalledToolSchema]:
        """Atomically replace one Agent draft's exact curated-tool grants."""
        from eylo.modules.agents.exceptions import AgentNotFoundError
        from eylo.modules.agents.services.indb import AgentService, AgentToolService
        from eylo.modules.agents.services.revisions import AgentRevisionService

        registry = self._registry()
        try:
            async with start_transaction() as session:
                try:
                    await AgentService(session).get_by_organization_and_id(
                        organization_id=organization_id,
                        pk=agent_id,
                    )
                except AgentNotFoundError:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND
                    ) from None

                curated_service = CuratedIntegrationService(session)
                installed_vendors = {
                    installation.vendor
                    for installation in await curated_service.list_installations(
                        organization_id=organization_id
                    )
                }
                available: dict[
                    uuid.UUID, tuple[CuratedVendorOffer, CuratedToolSpec]
                ] = {}
                for vendor in installed_vendors:
                    offer, _vendor_spec = self._offer(vendor)
                    for spec in registry.tools_for(vendor):
                        if offer.carries(spec.wire_id):
                            available[
                                curated_tool_id(spec.wire_id, organization_id)
                            ] = (offer, spec)

                requested = []
                for tool_id in dict.fromkeys(tool_ids):
                    candidate = available.get(tool_id)
                    if candidate is not None:
                        requested.append(candidate)
                        continue
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=(
                            "Curated tool is not available to this organization."
                        ),
                    )

                agent_tool_service = AgentToolService(session)
                selected_rows = []
                for offer, spec in requested:
                    try:
                        row = await curated_service.ensure_tool(
                            organization_id=organization_id,
                            offer=offer,
                            wire_id=spec.wire_id,
                        )
                    except IntegrationsV2Error as error:
                        raise self._http_error(error) from None
                    await self._require_unique_model_name(
                        service=agent_tool_service,
                        organization_id=organization_id,
                        agent_id=agent_id,
                        registry=registry,
                        candidate=spec.qualified_name,
                        candidate_tool_id=row.id,
                    )
                    selected_rows.append((row, spec))

                current_ids = set(
                    await agent_tool_service.list_curated_tool_ids(agent_id)
                )
                selected_ids = {row.id for row, _spec in selected_rows}
                if current_ids != selected_ids:
                    for curated_tool_id_value in current_ids - selected_ids:
                        await agent_tool_service.revoke_curated_tool(
                            agent_id=agent_id,
                            curated_tool_id=curated_tool_id_value,
                        )
                    for curated_tool_id_value in selected_ids - current_ids:
                        await agent_tool_service.grant_curated_tool(
                            agent_id=agent_id,
                            organization_id=organization_id,
                            curated_tool_id=curated_tool_id_value,
                        )
                    await AgentRevisionService(session).mark_draft_changed(
                        organization_id=organization_id,
                        agent_id=agent_id,
                        expected_draft_version=expected_draft_version,
                    )
        except DefinitionRevisionError as error:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(error),
            ) from error

        return [
            InstalledToolSchema(
                id=row.id,
                wire_id=row.wire_id,
                name=spec.name,
                agent_name=spec.qualified_name,
                display_name=spec.display_name,
                description=spec.description,
                effect=spec.effect,
                execution_mode=row.execution_mode,
            )
            for row, spec in selected_rows
        ]

    async def list_agent_tools(
        self,
        *,
        organization_id: uuid.UUID,
        agent_id: uuid.UUID,
    ) -> list[InstalledToolSchema]:
        from eylo.modules.agents.exceptions import AgentNotFoundError
        from eylo.modules.agents.services.indb import AgentService, AgentToolService

        registry = self._registry()
        async with start_transaction() as session:
            try:
                await AgentService(session).get_by_organization_and_id(
                    organization_id=organization_id,
                    pk=agent_id,
                )
            except AgentNotFoundError:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from None
            granted = await AgentToolService(session).list_curated_tool_ids(agent_id)
            rows = await CuratedIntegrationService().list_tools(
                organization_id=organization_id, tool_ids=granted
            )
        results: list[InstalledToolSchema] = []
        for row in rows:
            spec = registry.tool(row.wire_id)
            if spec is None:
                continue
            results.append(
                InstalledToolSchema(
                    id=row.id,
                    wire_id=row.wire_id,
                    name=spec.name,
                    agent_name=spec.qualified_name,
                    display_name=spec.display_name,
                    description=spec.description,
                    effect=spec.effect,
                    execution_mode=row.execution_mode,
                )
            )
        return results

    async def _require_unique_model_name(
        self,
        *,
        service,
        organization_id: uuid.UUID,
        agent_id: uuid.UUID,
        registry,
        candidate: str,
        candidate_tool_id: uuid.UUID,
    ) -> None:
        """Refuse a grant that would give one agent two tools of the same name.

        The model picks a tool by name, so a duplicate makes the agent's whole
        tool list unresolvable. Caught here, where the operator can act on it,
        rather than at run time.
        """
        taken: set[str] = set()
        for tool in await service.list_tools_for_agent(agent_id, organization_id):
            name = getattr(tool.llm_config, "name", None)
            if isinstance(name, str) and name:
                taken.add(name)
        for granted_id in await service.list_curated_tool_ids(agent_id):
            if granted_id == candidate_tool_id:
                continue
            for row in await CuratedIntegrationService().list_tools(
                organization_id=organization_id, tool_ids=[granted_id]
            ):
                spec = registry.tool(row.wire_id)
                if spec is not None:
                    taken.add(spec.qualified_name)
        if candidate in taken:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"This agent already has a tool named '{candidate}'.",
            )

    async def complete_public_authorization(
        self,
        *,
        code: str | None,
        state: str,
        error: str | None = None,
    ) -> HTMLResponse:
        """Finish an authorization for a user who has no console session.

        The person landing here is an end user who just approved access at the
        provider. They are not an operator: no bearer token, no organization in
        the URL. The state row carries the whole context, which is what OAuth
        state is for, and it is consumed either way so a code cannot be replayed.
        """
        from eylo.pipelines.integrations_v2.oauth import (
            complete_authorization_from_state,
        )

        if error:
            return _completion_page(
                ok=False,
                message="Authorization was declined at the provider.",
            )
        if not code:
            return _completion_page(
                ok=False, message="The provider returned no authorization code."
            )
        try:
            connection_id, vendor = await complete_authorization_from_state(
                code=code, state=state
            )
        except IntegrationsV2Error as failure:
            return _completion_page(ok=False, message=str(failure))
        return _completion_page(
            ok=True,
            message=f"{vendor} is connected.",
            connection_id=connection_id,
            vendor=vendor,
        )

    async def _installation(self, organization_id: uuid.UUID, vendor: str):
        rows = await CuratedIntegrationService().list_installations(
            organization_id=organization_id
        )
        for row in rows:
            if row.vendor == vendor:
                return row
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Curated vendor is not installed.",
        )

    def _registry(self):
        from eylo.pipelines.integrations_v2.registry import load_vendors

        return load_vendors()

    def _offer(self, vendor: str):
        registry = self._registry()
        spec = registry.vendor(vendor)
        if spec is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Curated vendor not found.",
            )
        return (
            CuratedVendorOffer(
                vendor=spec.vendor,
                supported_auth_kinds=frozenset(spec.auth_kinds),
                wire_ids=frozenset(
                    tool.wire_id for tool in registry.tools_for(vendor)
                ),
                requires_instance_url=spec.requires_instance_url,
            ),
            spec,
        )

    @staticmethod
    def _vendor_summary(spec, registry, installed: set[str]):
        return CuratedVendorSummarySchema(
            vendor=spec.vendor,
            display_name=spec.display_name,
            description=spec.description,
            categories=list(spec.categories),
            auth_kinds=list(spec.auth_kinds),
            homepage_url=spec.homepage_url,
            requires_instance_url=spec.requires_instance_url,
            requires_oauth_app=spec.oauth is not None,
            requires_oauth_tenant=bool(spec.oauth and spec.oauth.requires_tenant),
            instance_url_label=(
                spec.instance_url.label if spec.instance_url else None
            ),
            instance_url_placeholder=(
                spec.instance_url.placeholder if spec.instance_url else None
            ),
            tool_count=len(registry.tools_for(spec.vendor)),
            installed=spec.vendor in installed,
        )

    @staticmethod
    def _http_error(error: IntegrationsV2Error) -> HTTPException:
        if isinstance(error, IntegrationAlreadyInstalledError):
            code = status.HTTP_409_CONFLICT
        elif isinstance(error, (VendorNotFoundError, ToolBindingUnavailableError)):
            code = (
                status.HTTP_404_NOT_FOUND
                if error.code in _NOT_FOUND_CODES
                else status.HTTP_400_BAD_REQUEST
            )
        else:
            code = status.HTTP_400_BAD_REQUEST
        return HTTPException(status_code=code, detail=str(error))


def _completion_page(
    *,
    ok: bool,
    message: str,
    connection_id: uuid.UUID | None = None,
    vendor: str | None = None,
) -> HTMLResponse:
    """A minimal page for the end user, plus a postMessage for widget hosts."""
    safe = html.escape(message)
    status_text = "Connected" if ok else "Not connected"
    post_message = json.dumps(
        {
            "type": "eylo:curated-oauth",
            "ok": ok,
            "connectionId": str(connection_id) if connection_id else None,
            "vendor": vendor,
            "error": None if ok else message[:500],
        }
    ).replace("</", "<\\/")
    return HTMLResponse(
        status_code=200 if ok else 400,
        content=(
            "<!doctype html><meta charset='utf-8'>"
            f"<title>{status_text}</title>"
            "<body style=\"font:16px system-ui;margin:3rem;text-align:center\">"
            f"<h1>{status_text}</h1><p>{safe}</p>"
            "<p>You can close this window.</p>"
            "<script>if(window.opener){window.opener.postMessage("
            f"{post_message},'*');"
            "setTimeout(function(){window.close()},2000);}</script>"
            "</body>"
        ),
    )


def _origin(url: str) -> str:
    parsed = urlsplit(url)
    return f"{parsed.scheme}://{parsed.netloc}"


def _credential_values(
    auth_kind: VendorAuthKind,
    api_key: str | None,
    username: str | None,
    password: str | None,
) -> dict[str, str]:
    """Validate that the fields supplied match the auth kind that was installed."""
    if auth_kind is VendorAuthKind.API_KEY:
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This vendor was installed with api_key auth; api_key is required.",
            )
        return {"api_key": api_key}
    if auth_kind is VendorAuthKind.BASIC:
        if not username or not password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This vendor was installed with basic auth; username and password are required.",
            )
        return {"username": username, "password": password}
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="This vendor was installed with oauth2; use the authorization flow.",
    )


def curated_tool_id(wire_id: str, organization_id: uuid.UUID) -> uuid.UUID:
    from .domain.identity import curated_tool_id as derive

    return derive(wire_id, organization_id)


__all__ = ["CuratedIntegrationController"]
