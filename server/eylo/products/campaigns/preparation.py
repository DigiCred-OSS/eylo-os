"""Read-only campaign audience warnings; never an eligibility engine."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from eylo.modules.contacts.domain import ContactLifecycle
from eylo.modules.contacts.service import ContactService
from eylo.products.campaigns.channels import get_channel_adapter
from eylo.products.campaigns.domain import (
    CampaignPreparation,
    CampaignPreparationIssue,
    CampaignPreparationIssueCode,
    CampaignPreparationIssueLevel,
)
from eylo.products.campaigns.repositories import CampaignContactRepository
from eylo.products.campaigns.schemas.indb import CampaignContactInDb

_PAGE_SIZE = 500


class CampaignPreparationService:
    """Describe the filed audience without changing or filtering any row."""

    def __init__(self, session: AsyncSession) -> None:
        self.contacts = CampaignContactRepository(db=session)
        self.organization_contacts = ContactService(db=session)

    async def prepare(
        self,
        *,
        organization_id: UUID,
        campaign_id: UUID,
        channel: str,
    ) -> CampaignPreparation:
        adapter = get_channel_adapter(channel)
        selected_contacts = 0
        preferences_not_enforced = 0
        invalid_channel_addresses = 0
        deletion_pending = 0
        offset = 0

        while True:
            rows = await self.contacts.list_preparation_page(
                organization_id=organization_id,
                campaign_id=campaign_id,
                offset=offset,
                limit=_PAGE_SIZE,
            )
            if not rows:
                break

            contact_ids = list(
                dict.fromkeys(
                    row.contact_id for row in rows if row.contact_id is not None
                )
            )
            contacts = {
                contact.id: contact
                for contact in await self.organization_contacts.list_by_ids(
                    contact_ids,
                    organization_id,
                )
            }
            for row in rows:
                selected_contacts += 1
                if not await adapter.validate_contact(
                    CampaignContactInDb.model_validate(row)
                ):
                    invalid_channel_addresses += 1
                contact = contacts.get(row.contact_id)
                if contact is None:
                    continue
                if contact.preferences:
                    preferences_not_enforced += 1
                if contact.lifecycle is ContactLifecycle.DELETION_PENDING:
                    deletion_pending += 1

            offset += len(rows)
            if len(rows) < _PAGE_SIZE:
                break

        issues = []
        if selected_contacts:
            issues.append(
                CampaignPreparationIssue(
                    code=CampaignPreparationIssueCode.POLICY_NOT_EVALUATED,
                    level=CampaignPreparationIssueLevel.WARNING,
                    affected_contacts=selected_contacts,
                )
            )
        if preferences_not_enforced:
            issues.append(
                CampaignPreparationIssue(
                    code=CampaignPreparationIssueCode.PREFERENCES_NOT_ENFORCED,
                    level=CampaignPreparationIssueLevel.WARNING,
                    affected_contacts=preferences_not_enforced,
                )
            )
        if invalid_channel_addresses:
            issues.append(
                CampaignPreparationIssue(
                    code=CampaignPreparationIssueCode.INVALID_CHANNEL_ADDRESS,
                    level=CampaignPreparationIssueLevel.WARNING,
                    affected_contacts=invalid_channel_addresses,
                )
            )
        if deletion_pending:
            issues.append(
                CampaignPreparationIssue(
                    code=CampaignPreparationIssueCode.CONTACT_DELETION_PENDING,
                    level=CampaignPreparationIssueLevel.BLOCKER,
                    affected_contacts=deletion_pending,
                )
            )
        return CampaignPreparation(
            selected_contacts=selected_contacts,
            issues=tuple(issues),
        )
