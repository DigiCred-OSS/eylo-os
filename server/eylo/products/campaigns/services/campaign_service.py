"""Campaign service — CRUD, state machine, and contact upload."""

import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from eylo.absurd_work import AbsurdBoundWorkService, DurableState
from eylo.common.revisions import PublishedRevisionState, RevisionConflictError
from eylo.common.services import EyloBaseService
from eylo.modules.agents.services.revisions import AgentRevisionService
from eylo.modules.contacts.domain import ContactActorKind, ContactDeletionPending
from eylo.modules.contacts.schemas.indb import ContactCreateSchema, ContactRef
from eylo.modules.contacts.service import ContactService
from eylo.modules.email_configs.wiring import build_email_config_resolver
from eylo.modules.templates.domain import TemplateKind
from eylo.modules.templates.models import TemplateRevisionModel
from eylo.modules.templates.service import TemplateService
from eylo.products.campaigns.constants import (
    CAMPAIGN_TRANSITIONS,
    DEFAULT_RETRY_POLICY,
    DEFAULT_SCHEDULE_CONFIG,
    CampaignChannel,
    CampaignContactStatus,
    CampaignStatus,
)
from eylo.products.campaigns.domain import CampaignNotFoundError, CampaignPreparation
from eylo.products.campaigns.models import (
    CampaignAttemptModel,
    CampaignContactModel,
    CampaignModel,
    CampaignRevisionModel,
)
from eylo.products.campaigns.preparation import CampaignPreparationService
from eylo.products.campaigns.repositories import (
    CampaignContactRepository,
    CampaignRepository,
)
from eylo.products.campaigns.schemas.api import ContactUploadRow
from eylo.products.campaigns.schemas.indb import (
    CampaignContactCreateSchema,
    CampaignContactInDb,
    CampaignCreateSchema,
    CampaignInDb,
    CampaignUpdateSchema,
)

logger = logging.getLogger(__name__)


class CampaignService(EyloBaseService[CampaignInDb]):
    """Campaign CRUD, state machine, and contact management."""

    def __init__(self, db: AsyncSession | None = None) -> None:
        self._campaign_repo = CampaignRepository(db=db)
        self._contact_repo = CampaignContactRepository(db=db)
        self._org_contact_service = ContactService(db=db)

    @property
    def schema(self) -> type[CampaignInDb]:
        return CampaignInDb

    @property
    def repository(self) -> CampaignRepository:
        return self._campaign_repo

    # ── CRUD ────────────────────────────────────────────────

    async def create_campaign(
        self,
        organization_id: UUID,
        name: str,
        agent_id: UUID,
        description: Optional[str] = None,
        channel: str = "voice",
        channel_config: Optional[Dict[str, Any]] = None,
        initial_message_template_id: Optional[UUID] = None,
        schedule_config: Optional[Dict[str, Any]] = None,
        retry_policy: Optional[Dict[str, Any]] = None,
        concurrency_limit: int = 5,
        published_by: UUID | None = None,
    ) -> CampaignInDb:
        """Create a draft campaign whose revision 1 pins exact dependencies."""
        from eylo.products.campaigns.constants import CHANNEL_DEFAULT_RETRY_POLICY

        initial_message_template_id = (
            None
            if initial_message_template_id is None
            else UUID(str(initial_message_template_id))
        )
        agent_revision = await AgentRevisionService(
            self._campaign_repo.db_session
        ).resolve_for_new_work(
            organization_id=organization_id,
            agent_id=agent_id,
            for_update=True,
        )
        template_revision = await self._pin_template_for_new_work(
            organization_id=organization_id,
            template_id=initial_message_template_id,
        )
        channel_config = await self._pin_channel_config_for_new_revision(
            organization_id=organization_id,
            channel=channel,
            channel_config=channel_config,
        )

        request = CampaignCreateSchema(
            organization_id=organization_id,
            name=name,
            agent_id=agent_id,
            agent_revision=agent_revision.revision,
            description=description,
            channel=channel,
            channel_config=channel_config,
            initial_message_template_id=initial_message_template_id,
            initial_message_template_revision=(
                template_revision.revision if template_revision is not None else None
            ),
            schedule_config=schedule_config or DEFAULT_SCHEDULE_CONFIG,
            retry_policy=retry_policy
            or CHANNEL_DEFAULT_RETRY_POLICY.get(channel, DEFAULT_RETRY_POLICY),
            concurrency_limit=concurrency_limit,
        )
        campaign = await self._campaign_repo.create(organization_id, request)
        self._campaign_repo.db_session.add(
            self._revision_from_campaign(
                campaign,
                revision=1,
                published_by=published_by,
            )
        )
        await self._campaign_repo.db_session.flush()
        logger.info(
            "Campaign created: id=%s org=%s agent=%s",
            campaign.id,
            organization_id,
            agent_id,
        )
        return self.orm_to_schema(campaign)

    async def get_campaign(
        self,
        campaign_id: UUID,
        *,
        organization_id: UUID | None = None,
    ) -> CampaignInDb:
        if organization_id is None:
            return await self.get_(campaign_id)
        campaign = await self._campaign_repo.get_scoped(
            organization_id=organization_id,
            campaign_id=campaign_id,
        )
        if campaign is None:
            raise CampaignNotFoundError("Campaign not found.")
        return self.orm_to_schema(campaign)

    async def update_campaign(
        self,
        campaign_id: UUID,
        request: CampaignUpdateSchema,
        *,
        organization_id: UUID,
        published_by: UUID | None = None,
    ) -> CampaignInDb:
        """Append a complete campaign definition after optimistic locking."""
        campaign = await self._campaign_repo.get_scoped(
            organization_id=organization_id,
            campaign_id=campaign_id,
            for_update=True,
        )
        if campaign is None:
            raise CampaignNotFoundError("Campaign not found.")
        if campaign.status not in (
            CampaignStatus.DRAFT.value,
            CampaignStatus.PAUSED.value,
        ):
            raise ValueError(
                f"Cannot update campaign in {campaign.status} status. "
                "Only DRAFT or PAUSED campaigns can be edited."
            )
        if campaign.published_revision != request.expected_revision:
            raise RevisionConflictError(
                expected=request.expected_revision,
                actual=campaign.published_revision,
            )

        fields = request.model_fields_set
        if "agent_id" in fields:
            agent_id = request.agent_id
            if agent_id is None:
                raise ValueError("A campaign requires an agent.")
            agent = await AgentRevisionService(
                self._campaign_repo.db_session
            ).resolve_for_new_work(
                organization_id=organization_id,
                agent_id=agent_id,
                for_update=True,
            )
            campaign.agent_id = agent_id
            campaign.agent_revision = agent.revision

        if "initial_message_template_id" in fields:
            template = await self._pin_template_for_new_work(
                organization_id=organization_id,
                template_id=request.initial_message_template_id,
            )
            campaign.initial_message_template_id = request.initial_message_template_id
            campaign.initial_message_template_revision = (
                template.revision if template is not None else None
            )

        for field in (
            "name",
            "description",
            "channel",
            "channel_config",
            "schedule_config",
            "retry_policy",
            "concurrency_limit",
        ):
            if field in fields:
                setattr(campaign, field, getattr(request, field))

        if {"channel", "channel_config"} & fields:
            campaign.channel_config = await self._pin_channel_config_for_new_revision(
                organization_id=organization_id,
                channel=campaign.channel,
                channel_config=campaign.channel_config,
            )

        revision = campaign.published_revision + 1
        campaign.published_revision = revision
        self._campaign_repo.db_session.add(
            self._revision_from_campaign(
                campaign,
                revision=revision,
                published_by=published_by,
            )
        )
        await self._campaign_repo.db_session.flush()
        return self.orm_to_schema(campaign)

    async def delete_campaign(self, campaign_id: UUID) -> None:
        """Soft-delete a campaign. Only DRAFT or CANCELED campaigns."""
        campaign = await self.get_(campaign_id)
        if campaign.status not in (
            CampaignStatus.DRAFT.value,
            CampaignStatus.CANCELED.value,
        ):
            logger.warning(
                "Campaign delete rejected: id=%s status=%s",
                campaign_id,
                campaign.status,
            )
            raise ValueError(
                f"Cannot delete campaign in {campaign.status} status. "
                "Only DRAFT or CANCELED campaigns can be deleted."
            )
        orm_entity = await self._campaign_repo.get_(campaign_id)
        await self._campaign_repo.delete_(orm_entity)
        logger.info("Campaign deleted: id=%s", campaign_id)

    async def list_campaigns(
        self,
        organization_id: UUID,
        status: Optional[str] = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[List[CampaignInDb], int]:
        """List campaigns for an org with pagination. Returns (items, total)."""
        campaigns = await self._campaign_repo.list_by_organization(
            organization_id, status=status, offset=offset, limit=limit
        )
        total = await self._campaign_repo.count_by_organization(
            organization_id, status=status
        )
        return [self.orm_to_schema(c) for c in campaigns], total

    # ── State Machine ───────────────────────────────────────

    async def transition(
        self, campaign_id: UUID, target: CampaignStatus
    ) -> CampaignInDb:
        """Transition campaign to a new status with validation."""
        campaign = await self.get_(campaign_id)
        current = CampaignStatus(campaign.status)

        allowed = CAMPAIGN_TRANSITIONS.get(current, set())
        if target not in allowed:
            logger.warning(
                "Invalid campaign transition: id=%s %s → %s",
                campaign_id,
                current.value,
                target.value,
            )
            raise ValueError(
                f"Invalid transition: {current.value} → {target.value}. "
                f"Allowed: {[s.value for s in allowed]}"
            )

        extra_fields: Dict[str, Any] = {}
        if target == CampaignStatus.RUNNING and not campaign.started_at:
            extra_fields["started_at"] = datetime.now(timezone.utc)
        elif target in (CampaignStatus.COMPLETED, CampaignStatus.CANCELED):
            extra_fields["completed_at"] = datetime.now(timezone.utc)

        updated = await self._campaign_repo.update_status(
            campaign_id, target, **extra_fields
        )
        logger.info(
            "Campaign %s transitioned: %s → %s",
            campaign_id,
            current.value,
            target.value,
        )
        return self.orm_to_schema(updated)

    async def start(
        self,
        campaign_id: UUID,
        *,
        organization_id: UUID,
    ) -> CampaignInDb:
        """Activate exactly the current campaign definition revision."""
        campaign = await self._campaign_repo.get_scoped(
            organization_id=organization_id,
            campaign_id=campaign_id,
            for_update=True,
        )
        if campaign is None:
            raise CampaignNotFoundError("Campaign not found.")
        current = CampaignStatus(campaign.status)
        if CampaignStatus.RUNNING not in CAMPAIGN_TRANSITIONS.get(current, set()):
            raise ValueError(f"Cannot start campaign in {campaign.status} status.")
        revision = await self._campaign_repo.get_revision(
            organization_id=organization_id,
            campaign_id=campaign_id,
            revision=campaign.published_revision,
            for_update=True,
        )
        if revision is None:
            raise CampaignNotFoundError("Campaign definition revision not found.")
        PublishedRevisionState(
            availability=revision.availability,
            published_at=revision.published_at,
            revoked_at=revision.revoked_at,
            revoked_by=revision.revoked_by,
            revocation_reason=revision.revocation_reason,
            cancellation_requested_at=revision.cancellation_requested_at,
        ).require_available()

        preparation = await self._prepare_audience(
            organization_id=organization_id,
            campaign_id=campaign_id,
            channel=revision.channel,
        )
        if preparation.selected_contacts == 0:
            logger.warning(
                "Campaign start rejected: id=%s reason=no_contacts", campaign_id
            )
            raise ValueError("Cannot start a campaign with no contacts.")
        if preparation.blocking_facts:
            raise ContactDeletionPending(
                "Deletion-pending contacts cannot enter new campaign work."
            )
        logger.info(
            "Campaign preparation: id=%s selected=%d warning_facts=%d codes=%s",
            campaign_id,
            preparation.selected_contacts,
            preparation.warning_facts,
            [issue.code.value for issue in preparation.issues],
        )

        agents = AgentRevisionService(self._campaign_repo.db_session)
        await agents.resolve_for_new_work(
            organization_id=organization_id,
            agent_id=revision.agent_id,
            for_update=True,
        )
        await agents.get_revision(
            organization_id=organization_id,
            agent_id=revision.agent_id,
            revision=revision.agent_revision,
            for_update=True,
        )
        if revision.initial_message_template_id is not None:
            templates = TemplateService(self._campaign_repo.db_session)
            await templates.resolve_for_new_work(
                organization_id=organization_id,
                template_id=revision.initial_message_template_id,
                for_update=True,
            )
            template = await templates.get_revision(
                organization_id=organization_id,
                template_id=revision.initial_message_template_id,
                revision=revision.initial_message_template_revision,
                for_update=True,
            )
            if template.kind != TemplateKind.CAMPAIGN_MESSAGE.value:
                raise ValueError("Campaign message template kind is required.")

        # Channel-specific validation via adapter
        from eylo.products.campaigns.channels import get_channel_adapter

        campaign_view = self.orm_to_schema(campaign)
        adapter = get_channel_adapter(revision.channel)
        errors = await adapter.validate_campaign(campaign_view)
        if errors:
            logger.warning(
                "Campaign start rejected: id=%s channel=%s errors=%s",
                campaign_id,
                revision.channel,
                errors,
            )
            raise ValueError(errors[0])

        campaign.status = CampaignStatus.RUNNING.value
        campaign.active_revision = revision.revision
        if campaign.started_at is None:
            campaign.started_at = datetime.now(timezone.utc)
        await self._campaign_repo.db_session.flush()
        return self.orm_to_schema(campaign)

    async def prepare_campaign(
        self,
        campaign_id: UUID,
        *,
        organization_id: UUID,
    ) -> CampaignPreparation:
        """Return UI warnings without changing campaign or audience state."""
        campaign = await self._campaign_repo.get_scoped(
            organization_id=organization_id,
            campaign_id=campaign_id,
        )
        if campaign is None:
            raise CampaignNotFoundError("Campaign not found.")
        revision = await self._campaign_repo.get_revision(
            organization_id=organization_id,
            campaign_id=campaign_id,
            revision=campaign.published_revision,
        )
        if revision is None:
            raise CampaignNotFoundError("Campaign definition revision not found.")
        return await self._prepare_audience(
            organization_id=organization_id,
            campaign_id=campaign_id,
            channel=revision.channel,
        )

    async def _prepare_audience(
        self,
        *,
        organization_id: UUID,
        campaign_id: UUID,
        channel: str,
    ) -> CampaignPreparation:
        return await CampaignPreparationService(self._campaign_repo.db_session).prepare(
            organization_id=organization_id,
            campaign_id=campaign_id,
            channel=channel,
        )

    async def pause(self, campaign_id: UUID) -> CampaignInDb:
        campaign = await self.transition(campaign_id, CampaignStatus.PAUSED)
        await self._fence_unstarted_attempts(
            campaign_id=campaign_id,
            organization_id=campaign.organization_id,
            contact_status=CampaignContactStatus.PENDING,
        )
        return campaign

    async def cancel(self, campaign_id: UUID) -> CampaignInDb:
        campaign = await self.transition(campaign_id, CampaignStatus.CANCELED)
        await self._fence_unstarted_attempts(
            campaign_id=campaign_id,
            organization_id=campaign.organization_id,
            contact_status=CampaignContactStatus.CANCELLED,
        )
        return campaign

    async def revoke_revision(
        self,
        campaign_id: UUID,
        revision: int,
        *,
        organization_id: UUID,
        actor_id: UUID,
        reason: str,
    ) -> CampaignRevisionModel:
        """Emergency-revoke exact campaign authority and stop new dispatch."""
        campaign = await self._campaign_repo.get_scoped(
            organization_id=organization_id,
            campaign_id=campaign_id,
            for_update=True,
        )
        row = await self._campaign_repo.get_revision(
            organization_id=organization_id,
            campaign_id=campaign_id,
            revision=revision,
            for_update=True,
        )
        if campaign is None or row is None:
            raise CampaignNotFoundError("Campaign revision not found.")
        revoked = PublishedRevisionState(
            availability=row.availability,
            published_at=row.published_at,
            revoked_at=row.revoked_at,
            revoked_by=row.revoked_by,
            revocation_reason=row.revocation_reason,
            cancellation_requested_at=row.cancellation_requested_at,
        ).revoke(
            actor_id=actor_id,
            reason=reason,
            at=datetime.now(timezone.utc),
        )
        row.availability = revoked.availability.value
        row.revoked_at = revoked.revoked_at
        row.revoked_by = revoked.revoked_by
        row.revocation_reason = revoked.revocation_reason
        row.cancellation_requested_at = revoked.cancellation_requested_at
        if revision in {campaign.published_revision, campaign.active_revision}:
            campaign.status = CampaignStatus.CANCELED.value
            campaign.completed_at = datetime.now(timezone.utc)
            await self._fence_unstarted_attempts(
                campaign_id=campaign_id,
                organization_id=organization_id,
                contact_status=CampaignContactStatus.CANCELLED,
            )
        else:
            await self._fence_unstarted_attempts(
                campaign_id=campaign_id,
                organization_id=organization_id,
                contact_status=CampaignContactStatus.PENDING,
                revision=revision,
            )
        await self._campaign_repo.db_session.flush()
        return row

    async def _fence_unstarted_attempts(
        self,
        *,
        campaign_id: UUID,
        organization_id: UUID,
        contact_status: CampaignContactStatus,
        revision: int | None = None,
    ) -> None:
        """Cancel filed work before its provider boundary; preserve running work."""
        query = (
            select(CampaignAttemptModel)
            .where(
                CampaignAttemptModel.campaign_id == campaign_id,
                CampaignAttemptModel.organization_id == organization_id,
                CampaignAttemptModel.state == DurableState.PENDING,
                CampaignAttemptModel.deleted.is_(False),
            )
            .order_by(CampaignAttemptModel.created_at.asc())
            .with_for_update()
        )
        if revision is not None:
            query = query.where(CampaignAttemptModel.campaign_revision == revision)
        attempts = list((await self._campaign_repo.db_session.scalars(query)).all())
        if not attempts:
            return

        contact_ids = {attempt.campaign_contact_id for attempt in attempts}
        contacts = list(
            (
                await self._campaign_repo.db_session.scalars(
                    select(CampaignContactModel)
                    .where(
                        CampaignContactModel.id.in_(contact_ids),
                        CampaignContactModel.campaign_id == campaign_id,
                        CampaignContactModel.organization_id == organization_id,
                        CampaignContactModel.deleted.is_(False),
                    )
                    .with_for_update()
                )
            ).all()
        )
        contacts_by_id = {contact.id: contact for contact in contacts}
        work = AbsurdBoundWorkService(
            CampaignAttemptModel,
            self._campaign_repo.db_session,
        )
        for attempt in attempts:
            await work.cancel(
                work_id=attempt.id,
                organization_id=organization_id,
            )
            contact = contacts_by_id.get(attempt.campaign_contact_id)
            if (
                contact is not None
                and contact.status == CampaignContactStatus.QUEUED.value
            ):
                contact.status = contact_status.value

    # ── Contact Upload ──────────────────────────────────────

    async def upload_contacts(
        self,
        campaign_id: UUID,
        organization_id: UUID,
        rows: List[ContactUploadRow],
    ) -> int:
        """Process contact upload rows: find-or-create contacts, then bulk-insert
        into campaign_contacts. Returns the number of contacts added.

        Deduplicates by contact_address within the upload batch.
        """
        campaign = await self.get_(campaign_id)
        if campaign.status not in (
            CampaignStatus.DRAFT.value,
            CampaignStatus.PAUSED.value,
        ):
            raise ValueError("Can only add contacts to DRAFT or PAUSED campaigns.")

        seen_addresses: set[str] = set()
        create_schemas: List[CampaignContactCreateSchema] = []

        for row in rows:
            address = row.contact_address.strip()
            if address in seen_addresses:
                continue
            seen_addresses.add(address)

            # Find or create the org-level contact using channel-appropriate field
            channel = campaign.channel or CampaignChannel.VOICE.value
            contact_id = await self._resolve_org_contact(
                organization_id, channel, address, row.name
            )

            # Build variables dict from the row (excluding address/name)
            variables = row.variables or {}

            create_schemas.append(
                CampaignContactCreateSchema(
                    contact_address=address,
                    contact_id=contact_id,
                    variables=variables,
                )
            )

        if not create_schemas:
            return 0

        count = await self._contact_repo.bulk_create(
            campaign_id, organization_id, create_schemas
        )

        # Update total_contacts counter
        current = await self.get_(campaign_id)
        new_total = (current.total_contacts or 0) + count
        await self._campaign_repo.set_total_contacts(campaign_id, new_total)

        logger.info("Uploaded %d contacts to campaign %s", count, campaign_id)
        return count

    # ── Channel-Aware Contact Helpers ──────────────────────────

    async def _resolve_org_contact(
        self,
        organization_id: UUID,
        channel: str,
        address: str,
        name: Optional[str] = None,
    ) -> UUID:
        """Resolve one active contact or create it through canonical identity."""
        create_kwargs: Dict[str, Any] = {
            "organization_id": organization_id,
            "name": name,
        }
        if channel == CampaignChannel.VOICE.value:
            create_kwargs["primary_phone"] = address
        elif channel == CampaignChannel.EMAIL.value:
            create_kwargs["primary_email"] = address
        else:
            create_kwargs["primary_email"] = address

        resolution = await self._org_contact_service.resolve_or_create(
            ContactCreateSchema(**create_kwargs),
            actor_kind=ContactActorKind.SYSTEM,
        )
        assert resolution.contact is not None
        return resolution.contact.id

    @staticmethod
    def _extract_contact_address(contact: Any, channel: str) -> str:
        """Best-effort address extraction for the given channel.

        Returns whatever identifiers are available. The campaign does NOT
        gate on address presence — the channel adapter validates at dispatch
        time and records a reason if the contact lacks required fields.
        """
        if channel == CampaignChannel.VOICE.value:
            return getattr(contact, "primary_phone", None) or ""
        elif channel == CampaignChannel.EMAIL.value:
            return getattr(contact, "primary_email", None) or ""
        else:
            # Widget: any identifier works
            return (
                getattr(contact, "external_id", None)
                or getattr(contact, "primary_email", None)
                or getattr(contact, "primary_phone", None)
                or ""
            )

    # ── Select Existing Contacts ──────────────────────────────

    async def select_contacts(
        self,
        campaign_id: UUID,
        organization_id: UUID,
        contact_ids: List[UUID],
    ) -> int:
        """Add existing org contacts to a campaign by their IDs.
        Returns the number of contacts added (skips duplicates).
        """
        campaign = await self.get_(campaign_id)
        if campaign.status not in (
            CampaignStatus.DRAFT.value,
            CampaignStatus.PAUSED.value,
        ):
            raise ValueError("Can only add contacts to DRAFT or PAUSED campaigns.")

        channel = campaign.channel or CampaignChannel.VOICE.value

        create_schemas = await self._build_selected_contacts(
            organization_id=organization_id,
            contact_ids=contact_ids,
            channel=channel,
        )

        if not create_schemas:
            return 0

        count = await self._contact_repo.bulk_create(
            campaign_id, organization_id, create_schemas
        )

        # Update total_contacts
        current = await self.get_(campaign_id)
        new_total = (current.total_contacts or 0) + count
        await self._campaign_repo.set_total_contacts(campaign_id, new_total)

        logger.info("Selected %d contacts for campaign %s", count, campaign_id)
        return count

    async def _build_selected_contacts(
        self,
        *,
        organization_id: UUID,
        contact_ids: List[UUID],
        channel: str,
    ) -> List[CampaignContactCreateSchema]:
        """Build rows only after every selected contact passes the active fence."""
        selected: List[CampaignContactCreateSchema] = []
        for contact_id in contact_ids:
            contact = await self._org_contact_service.require_active(
                ContactRef(
                    organization_id=organization_id,
                    contact_id=contact_id,
                )
            )

            address = self._extract_contact_address(contact, channel)

            selected.append(
                CampaignContactCreateSchema(
                    contact_address=address,
                    contact_id=contact_id,
                    variables={"name": contact.name or ""},
                )
            )
        return selected

    # ── Immutable definition loading/rendering ──────────────

    async def get_definition_revision(
        self,
        *,
        organization_id: UUID,
        campaign_id: UUID,
        revision: int,
    ) -> CampaignRevisionModel:
        row = await self._campaign_repo.get_revision(
            organization_id=organization_id,
            campaign_id=campaign_id,
            revision=revision,
        )
        if row is None:
            raise CampaignNotFoundError("Campaign definition revision not found.")
        PublishedRevisionState(
            availability=row.availability,
            published_at=row.published_at,
            revoked_at=row.revoked_at,
            revoked_by=row.revoked_by,
            revocation_reason=row.revocation_reason,
            cancellation_requested_at=row.cancellation_requested_at,
        ).require_available()
        return row

    async def render_initial_message(
        self,
        definition: CampaignRevisionModel,
        variables: Dict[str, Any],
    ) -> Optional[str]:
        if definition.initial_message_template_id is None:
            return None
        templates = TemplateService(self._campaign_repo.db_session)
        template = await templates.get_revision(
            organization_id=definition.organization_id,
            template_id=definition.initial_message_template_id,
            revision=definition.initial_message_template_revision,
        )
        variable_names = {
            item["name"] for item in template.variable_schema.get("variables", [])
        }
        values = {name: variables[name] for name in variable_names if name in variables}
        from eylo.modules.templates.domain import TemplateConsumerKind

        rendered = await templates.render_exact(
            organization_id=definition.organization_id,
            template_id=definition.initial_message_template_id,
            revision=definition.initial_message_template_revision,
            consumer_kind=TemplateConsumerKind.CAMPAIGN_MESSAGE,
            values=values,
        )
        return rendered.text

    async def require_execution_authority(
        self,
        definition: CampaignRevisionModel,
    ) -> None:
        """Reject emergency-revoked agent authority before any channel effect."""
        await AgentRevisionService(self._campaign_repo.db_session).get_revision(
            organization_id=definition.organization_id,
            agent_id=definition.agent_id,
            revision=definition.agent_revision,
        )

    async def _pin_template_for_new_work(
        self,
        *,
        organization_id: UUID,
        template_id: UUID | None,
    ) -> TemplateRevisionModel | None:
        if template_id is None:
            return None
        row = await TemplateService(
            self._campaign_repo.db_session
        ).resolve_for_new_work(
            organization_id=organization_id,
            template_id=template_id,
            for_update=True,
        )
        if row.kind != TemplateKind.CAMPAIGN_MESSAGE.value:
            raise ValueError("Campaigns require a campaign_message template.")
        return row

    async def _pin_channel_config_for_new_revision(
        self,
        *,
        organization_id: UUID,
        channel: str,
        channel_config: Dict[str, Any] | None,
    ) -> Dict[str, Any]:
        """Pin mutable channel authority while creating an immutable revision."""
        config = dict(channel_config or {})
        if channel != CampaignChannel.EMAIL.value:
            return config
        raw_id = config.get("provider_config_id")
        try:
            provider_config_id = UUID(str(raw_id))
        except (TypeError, ValueError):
            config.pop("provider_config_revision", None)
            return config
        resolved = await build_email_config_resolver(
            self._campaign_repo.db_session
        ).resolve(
            organization_id,
            provider_config_id=provider_config_id,
        )
        config["provider_config_id"] = str(resolved.provider_config_id)
        config["provider_config_revision"] = resolved.provider_config_revision
        return config

    @staticmethod
    def _revision_from_campaign(
        campaign: CampaignModel,
        *,
        revision: int,
        published_by: UUID | None,
    ) -> CampaignRevisionModel:
        return CampaignRevisionModel(
            organization_id=campaign.organization_id,
            campaign_id=campaign.id,
            revision=revision,
            name=campaign.name,
            description=campaign.description,
            channel=campaign.channel,
            channel_config=dict(campaign.channel_config or {}),
            agent_id=campaign.agent_id,
            agent_revision=campaign.agent_revision,
            initial_message_template_id=campaign.initial_message_template_id,
            initial_message_template_revision=(
                campaign.initial_message_template_revision
            ),
            schedule_config=dict(campaign.schedule_config or {}),
            retry_policy=dict(campaign.retry_policy or {}),
            concurrency_limit=campaign.concurrency_limit,
            published_at=datetime.now(timezone.utc),
            published_by=published_by,
        )

    @staticmethod
    def render_template(
        template: Optional[str],
        variables: Dict[str, Any],
    ) -> Optional[str]:
        """Substitute simple ``{{variable}}`` placeholders without conditions."""
        if not template:
            return None

        def replace(match: re.Match[str]) -> str:
            key = match.group(1).strip()
            return str(variables.get(key, match.group(0)))

        return re.sub(r"\{\{(\s*\w+\s*)\}\}", replace, template)

    # ── Analytics Helpers ───────────────────────────────────

    async def get_contact_status_summary(self, campaign_id: UUID) -> dict[str, int]:
        """Get a {status: count} breakdown for all contacts in a campaign."""
        return await self._contact_repo.count_by_status(campaign_id)

    async def get_outcome_distribution(self, campaign_id: UUID) -> dict[str, int]:
        """Get {ended_reason: count} for completed/failed contacts."""
        return await self._contact_repo.outcome_distribution(campaign_id)

    # ── Contact Queries ─────────────────────────────────────

    async def list_contacts(
        self,
        campaign_id: UUID,
        status: Optional[str] = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[List[CampaignContactInDb], int]:
        contacts = await self._contact_repo.list_by_campaign(
            campaign_id, status=status, offset=offset, limit=limit
        )
        total = await self._contact_repo.count_by_campaign(campaign_id, status=status)
        return [CampaignContactInDb.model_validate(c) for c in contacts], total
