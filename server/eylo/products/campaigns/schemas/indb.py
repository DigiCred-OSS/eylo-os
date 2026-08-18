"""Internal database schemas for campaigns."""

import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from eylo.common.schemas import EyloBaseOrganizationModelSchema


class CampaignModelSchema(EyloBaseOrganizationModelSchema):
    name: str
    description: Optional[str] = None
    status: str = "draft"
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


class CampaignInDb(CampaignModelSchema):
    model_config = ConfigDict(from_attributes=True)


class CampaignCreateSchema(BaseModel):
    organization_id: UUID
    name: str
    description: Optional[str] = None
    channel: str = "voice"
    channel_config: Dict[str, Any] = {}
    agent_id: UUID
    agent_revision: int
    published_revision: int = 1
    active_revision: Optional[int] = None
    initial_message_template_id: Optional[UUID] = None
    initial_message_template_revision: Optional[int] = None
    schedule_config: Optional[Dict[str, Any]] = None
    retry_policy: Optional[Dict[str, Any]] = None
    concurrency_limit: int = 5


class CampaignUpdateSchema(BaseModel):
    expected_revision: int
    name: Optional[str] = None
    description: Optional[str] = None
    channel: Optional[str] = None
    channel_config: Optional[Dict[str, Any]] = None
    agent_id: Optional[UUID] = None
    initial_message_template_id: Optional[UUID] = None
    schedule_config: Optional[Dict[str, Any]] = None
    retry_policy: Optional[Dict[str, Any]] = None
    concurrency_limit: Optional[int] = None


class CampaignContactModelSchema(EyloBaseOrganizationModelSchema):
    campaign_id: UUID
    campaign_revision: Optional[int] = None
    contact_id: Optional[UUID] = None
    contact_address: str
    status: str = "pending"
    attempt_count: int = 0
    last_attempt_at: Optional[datetime.datetime] = None
    next_retry_at: Optional[datetime.datetime] = None
    last_tracking_id: Optional[str] = None
    last_outcome_reason: Optional[str] = None
    variables: Dict[str, Any] = {}


class CampaignContactInDb(CampaignContactModelSchema):
    model_config = ConfigDict(from_attributes=True)


class CampaignContactCreateSchema(BaseModel):
    contact_address: str
    contact_id: Optional[UUID] = None
    variables: Dict[str, Any] = {}


class CampaignContactBulkCreateSchema(BaseModel):
    """Schema for bulk-creating campaign contacts from CSV upload."""

    contacts: List[CampaignContactCreateSchema]
