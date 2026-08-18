"""API-facing schemas for campaigns (camelCase)."""

import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import ConfigDict, Field, field_validator

from eylo.common.schemas import (
    EyloBaseApiSchema,
    EyloBaseRequestSchema,
    EyloBaseResponseSchema,
    PaginatedResponseSchema,
)
from eylo.products.campaigns.domain import (
    CampaignPreparation,
    CampaignPreparationIssueCode,
    CampaignPreparationIssueLevel,
)

_PREPARATION_MESSAGES = {
    CampaignPreparationIssueCode.POLICY_NOT_EVALUATED: (
        "Every selected contact stays in the filed audience and receives an "
        "attempt record. Consent, suppression, jurisdiction, and local-time "
        "policy are not evaluated in V1."
    ),
    CampaignPreparationIssueCode.PREFERENCES_NOT_ENFORCED: (
        "Stored contact preferences are shown as data and do not filter outreach."
    ),
    CampaignPreparationIssueCode.INVALID_CHANNEL_ADDRESS: (
        "The channel cannot attempt these addresses; each attempt will record "
        "a technical rejection."
    ),
    CampaignPreparationIssueCode.CONTACT_DELETION_PENDING: (
        "Deletion-pending contacts cannot enter new campaign work."
    ),
}

# --- Campaign request schemas ---


class CampaignCreateRequest(EyloBaseRequestSchema):
    name: str = Field(..., min_length=1, max_length=256)
    description: Optional[str] = None
    channel: str = Field(default="voice", pattern="^(voice|email|widget)$")
    channel_config: Dict[str, Any] = Field(default_factory=dict)
    agent_id: UUID
    initial_message_template_id: Optional[UUID] = None
    schedule_config: Optional[Dict[str, Any]] = None
    retry_policy: Optional[Dict[str, Any]] = None
    concurrency_limit: int = Field(default=5, ge=1, le=50)


class CampaignUpdateRequest(EyloBaseRequestSchema):
    expected_revision: int = Field(..., ge=1)
    name: Optional[str] = Field(None, min_length=1, max_length=256)
    description: Optional[str] = None
    channel: Optional[str] = Field(None, pattern="^(voice|email|widget)$")
    channel_config: Optional[Dict[str, Any]] = None
    agent_id: Optional[UUID] = None
    initial_message_template_id: Optional[UUID] = None
    schedule_config: Optional[Dict[str, Any]] = None
    retry_policy: Optional[Dict[str, Any]] = None
    concurrency_limit: Optional[int] = Field(None, ge=1, le=50)


class CampaignRevisionRevokeRequest(EyloBaseRequestSchema):
    reason: str = Field(..., min_length=1, max_length=2000)


# --- Campaign response schemas ---


class CampaignResponse(EyloBaseResponseSchema):
    model_config = ConfigDict(from_attributes=True)

    name: str
    description: Optional[str] = None
    status: str
    channel: str = "voice"
    channel_config: Dict[str, Any] = {}
    agent_id: UUID
    agent_revision: int
    published_revision: int
    active_revision: Optional[int] = None
    initial_message_template_id: Optional[UUID] = None
    initial_message_template_revision: Optional[int] = None
    schedule_config: Dict[str, Any] = {}
    retry_policy: Dict[str, Any] = {}
    concurrency_limit: int = 5
    total_contacts: int = 0
    completed_contacts: int = 0
    failed_contacts: int = 0
    started_at: Optional[datetime.datetime] = None
    completed_at: Optional[datetime.datetime] = None
    organization_id: Optional[UUID] = None


class CampaignsPaginated(PaginatedResponseSchema):
    data: List[CampaignResponse]


class CampaignPreparationIssueResponse(EyloBaseApiSchema):
    code: CampaignPreparationIssueCode
    level: CampaignPreparationIssueLevel
    affected_contacts: int
    message: str


class CampaignPreparationResponse(EyloBaseApiSchema):
    campaign_id: UUID
    selected_contacts: int
    warning_facts: int
    blocking_facts: int
    issues: List[CampaignPreparationIssueResponse]

    @classmethod
    def from_domain(
        cls,
        *,
        campaign_id: UUID,
        preparation: CampaignPreparation,
    ) -> "CampaignPreparationResponse":
        return cls(
            campaign_id=campaign_id,
            selected_contacts=preparation.selected_contacts,
            warning_facts=preparation.warning_facts,
            blocking_facts=preparation.blocking_facts,
            issues=[
                CampaignPreparationIssueResponse(
                    code=issue.code,
                    level=issue.level,
                    affected_contacts=issue.affected_contacts,
                    message=_PREPARATION_MESSAGES[issue.code],
                )
                for issue in preparation.issues
            ],
        )


# --- Campaign contact request schemas ---


class ContactUploadRow(EyloBaseApiSchema):
    contact_address: str = Field(..., min_length=1)
    name: Optional[str] = None
    variables: Dict[str, Any] = {}


class CampaignContactsUploadRequest(EyloBaseRequestSchema):
    contacts: List[ContactUploadRow] = Field(..., min_length=1)


class CampaignContactsSelectRequest(EyloBaseRequestSchema):
    """Select existing contacts by ID to add to a campaign."""

    contact_ids: List[UUID] | UUID

    @field_validator("contact_ids", mode="after")
    def validate_contact_ids(cls, v):
        if isinstance(v, UUID):
            return [v]
        return v


# --- Campaign contact response schemas ---


class CampaignContactResponse(EyloBaseResponseSchema):
    model_config = ConfigDict(from_attributes=True)

    campaign_id: UUID
    campaign_revision: Optional[int] = None
    contact_id: Optional[UUID] = None
    contact_address: str
    status: str
    attempt_count: int = 0
    last_attempt_at: Optional[datetime.datetime] = None
    next_retry_at: Optional[datetime.datetime] = None
    last_tracking_id: Optional[str] = None
    last_outcome_reason: Optional[str] = None
    variables: Dict[str, Any] = {}
    organization_id: Optional[UUID] = None


class CampaignContactsPaginated(PaginatedResponseSchema):
    data: List[CampaignContactResponse]


# --- Analytics schema ---


class CampaignAnalyticsResponse(EyloBaseApiSchema):
    campaign_id: UUID
    total_contacts: int = 0
    completed: int = 0
    failed: int = 0
    pending: int = 0
    retry: int = 0
    skipped: int = 0
    connect_rate: float = 0.0
    avg_duration_seconds: Optional[float] = None
    outcome_distribution: Dict[str, int] = {}


# --- Filter schema ---


class CampaignFilterSchema(EyloBaseApiSchema):
    status: Optional[str] = None
