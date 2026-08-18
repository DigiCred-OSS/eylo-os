"""Widget surface for end users authorizing curated vendors.

The person here is a contact talking to an agent, not an operator in the
console. They authenticate with a widget session, and the `contact_id` comes
from that session rather than from the request — otherwise one contact could
start a flow that binds a connection to another.

Authorization is grant-bound: a contact may only authorize a vendor their
agent's pinned revision actually uses. Without that, any contact could
mint an authorization URL for any vendor the organization installed.
"""

from __future__ import annotations

from urllib.parse import urlsplit
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from eylo.common.database import register_ephemeral_event_post_txn, start_transaction
from eylo.common.revisions import DefinitionRevisionError
from eylo.events.py_events.emitter import emit_ephemeral
from eylo.events.schema.py_events.connections import (
    ConnectionStartedEvent,
    ConnectionSuccessEvent,
)
from eylo.modules.agents.exceptions import AgentNotFoundError
from eylo.modules.agents.services.revisions import AgentRevisionService
from eylo.modules.auth.dependencies.widget_auth import get_current_contact
from eylo.modules.auth.schemas.widget import CurrentContactSchema
from eylo.modules.connections.services.indb import ConnectionService
from eylo.modules.conversations.exceptions import ConversationNotFound
from eylo.pipelines.conversation.widget_authority import (
    resolve_widget_conversation_authority,
)

from ..constants import APP_TAG
from ..domain.enums import VendorAuthKind
from ..schemas.api import (
    AuthorizationRedirectSchema,
    ConnectionSchema,
    WidgetAgentCuratedCapabilitiesSchema,
    WidgetConnectCredentialRequestSchema,
    WidgetCuratedCapabilitiesRequestSchema,
    WidgetCuratedIntegrationSchema,
    WidgetCuratedToolGroupSchema,
    WidgetCuratedToolSchema,
)
from ..services.installations import CuratedIntegrationService

widget_router = APIRouter(
    prefix="/widget/{organization_id}/curated-connections",
    tags=[APP_TAG],
)


@widget_router.get(
    "/capabilities",
    response_model=list[WidgetCuratedToolGroupSchema],
)
async def widget_list_curated_capabilities(
    organization_id: UUID,
    agent_id: UUID = Query(..., description="Published Agent shown by the widget."),
    contact: CurrentContactSchema = Depends(get_current_contact),
):
    """List curated tools pinned to one available published Agent revision."""
    if contact.organization_id != organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    async with start_transaction(ro=True) as db:
        capabilities = await _capabilities_by_agent(
            db=db,
            organization_id=organization_id,
            contact_id=contact.contact_id,
            agent_ids=[agent_id],
        )
    return capabilities[agent_id]


@widget_router.post(
    "/bulk-capabilities",
    response_model=list[WidgetAgentCuratedCapabilitiesSchema],
)
async def widget_list_bulk_curated_capabilities(
    organization_id: UUID,
    payload: WidgetCuratedCapabilitiesRequestSchema,
    contact: CurrentContactSchema = Depends(get_current_contact),
):
    """List curated capability groups for the visible Agent catalogue."""
    if contact.organization_id != organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    async with start_transaction(ro=True) as db:
        capabilities = await _capabilities_by_agent(
            db=db,
            organization_id=organization_id,
            contact_id=contact.contact_id,
            agent_ids=payload.agent_ids,
        )
    return [
        WidgetAgentCuratedCapabilitiesSchema(
            agent_id=agent_id,
            integrations=capabilities[agent_id],
        )
        for agent_id in payload.agent_ids
    ]


async def _capabilities_by_agent(
    *,
    db,
    organization_id: UUID,
    contact_id: UUID,
    agent_ids: list[UUID],
) -> dict[UUID, list[WidgetCuratedToolGroupSchema]]:
    """Build one connection-aware capability projection for each Agent."""
    requested_ids = list(dict.fromkeys(agent_ids))
    revisions = AgentRevisionService(db)
    available = await revisions.list_available_for_widget(
        organization_id=organization_id,
        agent_ids=requested_ids,
    )
    revision_by_agent = {revision.agent_id: revision for revision in available}
    if len(revision_by_agent) != len(requested_ids):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    grants_by_agent: dict[UUID, set[UUID]] = {}
    for agent_id in requested_ids:
        revision = revision_by_agent[agent_id]
        grants_by_agent[agent_id] = set(
            await revisions.list_curated_tool_ids(
                organization_id=organization_id,
                agent_id=agent_id,
                revision=revision.revision,
            )
        )

    all_grants = set().union(*grants_by_agent.values()) if grants_by_agent else set()
    service = CuratedIntegrationService(db)
    offerable_rows = (
        await service.list_offerable_tools(
            organization_id=organization_id,
            tool_ids=list(all_grants),
        )
        if all_grants
        else []
    )
    installations = {
        installation.id: installation
        for installation in await service.list_installations(
            organization_id=organization_id
        )
    }

    from eylo.pipelines.integrations_v2.registry import load_vendors

    registry = load_vendors()
    connection_service = ConnectionService(db)
    connection_by_installation = {}
    used_installation_ids = {
        row.installation_id
        for row in offerable_rows
        if row.installation_id in installations
    }
    for installation_id in used_installation_ids:
        connection_by_installation[installation_id] = (
            await connection_service.get_active_connection_for_execution(
                integration_id=installation_id,
                organization_id=organization_id,
                contact_id=contact_id,
            )
        )

    result: dict[UUID, list[WidgetCuratedToolGroupSchema]] = {}
    for agent_id in requested_ids:
        grouped_rows: dict[UUID, list] = {}
        for row in offerable_rows:
            if (
                row.id in grants_by_agent[agent_id]
                and row.installation_id in installations
                and registry.tool(row.wire_id) is not None
            ):
                grouped_rows.setdefault(row.installation_id, []).append(row)

        groups: list[WidgetCuratedToolGroupSchema] = []
        for installation_id, tool_rows in grouped_rows.items():
            installation = installations[installation_id]
            vendor = registry.vendor(installation.vendor)
            if vendor is None:
                continue
            connection = connection_by_installation[installation_id]
            no_auth = installation.auth_kind is VendorAuthKind.NO_AUTH
            groups.append(
                WidgetCuratedToolGroupSchema(
                    integration=WidgetCuratedIntegrationSchema(
                        id=installation.id,
                        name=installation.vendor,
                        slug=installation.vendor,
                        display_name=vendor.display_name,
                        description=vendor.description,
                        auth_kind=installation.auth_kind,
                        connection_kind=(
                            connection.connection_kind.value
                            if connection is not None
                            else "ORGANIZATION"
                            if no_auth
                            else "CONTACT"
                        ),
                        has_active_connection=no_auth or connection is not None,
                        vendor=installation.vendor,
                    ),
                    tools=[
                        WidgetCuratedToolSchema(
                            id=row.id,
                            name=spec.qualified_name,
                            slug=spec.qualified_name,
                            display_name=spec.display_name,
                            description=spec.description,
                        )
                        for row in tool_rows
                        if (spec := registry.tool(row.wire_id)) is not None
                    ],
                )
            )
        result[agent_id] = sorted(
            groups,
            key=lambda group: group.integration.display_name.casefold(),
        )
    return result


@widget_router.get("/oauth/initiate", response_model=AuthorizationRedirectSchema)
async def widget_initiate_curated_oauth(
    organization_id: UUID,
    vendor: str = Query(..., min_length=1, description="Curated vendor id."),
    conversation_id: UUID = Query(..., description="Contact-owned conversation."),
    contact: CurrentContactSchema = Depends(get_current_contact),
):
    """Return the consent URL for a vendor this contact's agent actually uses."""
    if contact.organization_id != organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    from eylo.pipelines.integrations_v2.oauth import begin_authorization
    async with start_transaction(ro=True) as db:
        installation, spec = await _require_curated_vendor_access(
            db=db,
            organization_id=organization_id,
            vendor=vendor,
            contact=contact,
            conversation_id=conversation_id,
        )
    if installation.auth_kind is not VendorAuthKind.OAUTH2:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)

    async with start_transaction():
        redirect = await begin_authorization(
            installation=installation,
            vendor=spec,
            contact_id=contact.contact_id,
        )
        register_ephemeral_event_post_txn(
            ConnectionStartedEvent(
                integration_id=installation.id,
                vendor=vendor,
                contact_id=contact.contact_id,
                organization_id=organization_id,
            )
        )
    return AuthorizationRedirectSchema(
        authorization_url=redirect.authorization_url,
        callback_origin=(
            f"{urlsplit(redirect.redirect_uri).scheme}://"
            f"{urlsplit(redirect.redirect_uri).netloc}"
        ),
        state=redirect.state,
    )


@widget_router.post(
    "/{vendor}/connect",
    response_model=ConnectionSchema,
    status_code=status.HTTP_201_CREATED,
)
async def widget_connect_curated_credential(
    organization_id: UUID,
    vendor: str,
    payload: WidgetConnectCredentialRequestSchema,
    conversation_id: UUID = Query(..., description="Contact-owned conversation."),
    contact: CurrentContactSchema = Depends(get_current_contact),
):
    """Bind a direct credential to the current contact, never a request-supplied id."""
    if contact.organization_id != organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    async with start_transaction(ro=True) as db:
        installation, spec = await _require_curated_vendor_access(
            db=db,
            organization_id=organization_id,
            vendor=vendor,
            contact=contact,
            conversation_id=conversation_id,
        )
    if installation.auth_kind not in {VendorAuthKind.API_KEY, VendorAuthKind.BASIC}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)

    from ..controllers import CuratedIntegrationController

    connection = await CuratedIntegrationController().connect_with_credential(
        organization_id=organization_id,
        vendor=vendor,
        api_key=payload.api_key,
        username=payload.username,
        password=payload.password,
        contact_id=contact.contact_id,
    )
    emit_ephemeral(
        ConnectionSuccessEvent(
            connection_id=connection.id,
            contact_id=contact.contact_id,
            organization_id=organization_id,
            integration_name=spec.display_name,
            integration_id=installation.id,
            vendor=vendor,
        )
    )
    return connection


async def _require_curated_vendor_access(
    *,
    db,
    organization_id: UUID,
    vendor: str,
    contact: CurrentContactSchema,
    conversation_id: UUID,
):
    """Resolve an installed vendor only for this contact-owned Agent chat."""
    from eylo.pipelines.integrations_v2.registry import load_vendors

    registry = load_vendors()
    spec = registry.vendor(vendor)
    if spec is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    try:
        authority = await resolve_widget_conversation_authority(
            organization_id=organization_id,
            contact_id=contact.contact_id,
            conversation_id=conversation_id,
            session=db,
        )
        revisions = AgentRevisionService(db)
        await revisions.get_revision(
            organization_id=organization_id,
            agent_id=authority.agent_id,
            revision=authority.agent_revision,
        )
    except (
        AgentNotFoundError,
        ConversationNotFound,
        DefinitionRevisionError,
    ) as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from error
    granted = await revisions.list_curated_tool_ids(
        organization_id=organization_id,
        agent_id=authority.agent_id,
        revision=authority.agent_revision,
    )
    service = CuratedIntegrationService(db)
    rows = await service.list_offerable_tools(
        organization_id=organization_id,
        tool_ids=granted,
    )
    if not any(row.wire_id.startswith(f"{vendor}.") for row in rows):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return installation, spec


__all__ = ["widget_router"]
