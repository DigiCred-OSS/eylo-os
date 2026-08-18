"""Schemas for the telephony module."""

import re
from datetime import datetime
from enum import Enum
from typing import List, Optional, Self
from uuid import UUID

from pydantic import (
    ConfigDict,
    Field,
    SkipValidation,
    field_validator,
    model_validator,
)

from eylo.common.schemas import (
    EyloBaseApiSchema,
    EyloBaseOrganizationModelSchema,
    EyloBaseRequestSchema,
    EyloBaseResponseSchema,
    EyloBaseSchema,
    PaginatedResponseSchema,
)
from eylo.modules.telephony.provider_config_domain import (
    TelephonyOperation,
    TelephonyProvider,
)


class PhoneNumberStatus(str, Enum):
    """Enum for phone number status."""

    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    PROVISIONING = "PROVISIONING"
    PROVISIONING_UNKNOWN = "PROVISIONING_UNKNOWN"
    PROVISIONING_FAILED = "PROVISIONING_FAILED"


class CallDirection(str, Enum):
    """Direction of a telephony call."""

    INBOUND = "inbound"
    OUTBOUND = "outbound"


class CallStatus(str, Enum):
    """Status of a telephony call."""

    INITIATED = "initiated"
    RINGING = "ringing"
    IN_PROGRESS = "in-progress"
    COMPLETED = "completed"
    BUSY = "busy"
    NO_ANSWER = "no-answer"
    FAILED = "failed"
    CANCELED = "canceled"


class PhoneNumberInDb(EyloBaseOrganizationModelSchema):
    """Schema for phone number data as it is in the database."""

    number: str
    label: Optional[str] = None
    status: PhoneNumberStatus
    provider: str
    provider_config_id: UUID
    provider_config_revision: int = Field(gt=0)
    provider_reference: Optional[str] = None
    provisioning_failure_code: Optional[str] = None
    inbound_agent_id: Optional[UUID] = None
    outbound_agent_id: Optional[UUID] = None


class PhoneNumberApiResponseSchema(PhoneNumberInDb, EyloBaseResponseSchema):
    """Schema for phone number API responses."""

    pass


class PhoneNumbersPaginated(PaginatedResponseSchema):
    """Paginated response schema for phone numbers."""

    data: List[PhoneNumberApiResponseSchema]


class PhoneNumberCreateSchema(EyloBaseRequestSchema):
    """Schema for creating a new phone number."""

    number: str
    label: Optional[str] = None
    provider: str
    provider_config_id: UUID
    provider_config_revision: int = Field(gt=0)
    inbound_agent_id: Optional[UUID] = None
    outbound_agent_id: Optional[UUID] = None

    @field_validator("number")
    def validate_phone_number(cls, v):
        if not re.match(r"^\+[1-9]\d{1,14}$", v):
            raise ValueError("Invalid phone number format")
        return v


class PhoneNumberUpdateSchema(EyloBaseRequestSchema):
    """Schema for updating an existing phone number."""

    label: Optional[str] = None
    status: Optional[PhoneNumberStatus] = None
    inbound_agent_id: Optional[UUID] = None
    outbound_agent_id: Optional[UUID] = None

    @field_validator("status")
    @classmethod
    def validate_operator_status(
        cls,
        value: Optional[PhoneNumberStatus],
    ) -> Optional[PhoneNumberStatus]:
        if value not in {
            None,
            PhoneNumberStatus.ACTIVE,
            PhoneNumberStatus.INACTIVE,
        }:
            raise ValueError("Provisioning status is controlled by the platform.")
        return value


# --- Telephony Call schemas ---


class TelephonyCallInDb(EyloBaseOrganizationModelSchema):
    """Schema for telephony call data as it is in the database."""

    call_sid: Optional[str] = None
    stream_sid: Optional[str] = None
    provider: str
    provider_config_id: UUID
    provider_config_revision: int = Field(gt=0)
    direction: str
    status: str
    from_number: Optional[str] = None
    to_number: Optional[str] = None
    ended_reason: Optional[str] = None
    agent_id: Optional[UUID] = None
    agent_revision: Optional[int] = Field(default=None, gt=0)
    conversation_id: Optional[UUID] = None
    user_session_id: Optional[UUID] = None
    campaign_id: Optional[UUID] = None
    campaign_contact_id: Optional[UUID] = None
    campaign_attempt_id: Optional[UUID] = None
    phone_number_id: Optional[UUID] = None
    voice_session_id: Optional[UUID] = None
    started_at: Optional[datetime] = None
    connected_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    duration_seconds: Optional[int] = None
    provider_status: Optional[str] = None
    media_claimed_at: Optional[datetime] = None
    opener_delivery_status: str = "not_requested"
    opener_delivered_at: Optional[datetime] = None
    status_history: list[dict] = Field(default_factory=list)
    recording_id: Optional[UUID] = None
    recording_url: Optional[str] = None
    transcript_id: Optional[UUID] = None
    transcript_url: Optional[str] = None
    transfer_status: str = "none"
    transfer_to: Optional[str] = None
    transfer_reason: Optional[str] = None
    transferred_at: Optional[datetime] = None
    transfer_metadata: dict = Field(default_factory=dict)
    cost_amount: Optional[float] = None
    cost_currency: Optional[str] = None
    latency_metrics: dict = Field(default_factory=dict)
    provider_metadata: dict = Field(default_factory=dict)
    analysis_metadata: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def exact_agent_ref(self) -> Self:
        if (self.agent_id is None) != (self.agent_revision is None):
            raise ValueError(
                "Telephony calls require a complete exact agent reference."
            )
        return self


class TelephonyCallStatusUpdateResult(EyloBaseSchema):
    """Result of applying a provider call-status update."""

    call: Optional[SkipValidation[TelephonyCallInDb]] = None
    previous_status: Optional[str] = None
    incoming_status: str
    status_changed: bool = False
    ignored: bool = False
    entered_terminal_status: bool = False


class TelephonyCallApiResponseSchema(EyloBaseResponseSchema):
    """Minimal public projection backed by canonical call writers."""

    model_config = ConfigDict(from_attributes=True)

    organization_id: UUID
    call_sid: Optional[str] = None
    provider: str
    provider_config_id: UUID
    provider_config_revision: int
    direction: str
    status: str
    from_number: Optional[str] = None
    to_number: Optional[str] = None
    ended_reason: Optional[str] = None
    agent_id: Optional[UUID] = None
    agent_revision: Optional[int] = None
    conversation_id: Optional[UUID] = None
    campaign_id: Optional[UUID] = None
    campaign_contact_id: Optional[UUID] = None
    campaign_attempt_id: Optional[UUID] = None
    phone_number_id: Optional[UUID] = None
    voice_session_id: Optional[UUID] = None
    started_at: Optional[datetime] = None
    connected_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    duration_seconds: Optional[int] = None
    provider_status: Optional[str] = None
    opener_delivery_status: str
    opener_delivered_at: Optional[datetime] = None
    transfer_status: str
    transfer_to: Optional[str] = None
    transfer_reason: Optional[str] = None
    transferred_at: Optional[datetime] = None


class TelephonyCallsPaginated(PaginatedResponseSchema):
    """Paginated response schema for telephony calls."""

    data: List[TelephonyCallApiResponseSchema]


# --- Telephony Provider Config schemas ---


TelephonyProviderType = TelephonyProvider


class ProviderConfigApiResponseSchema(EyloBaseApiSchema):
    """Secret-safe telephony config lifecycle response."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    provider: str
    name: str
    revision: int = Field(gt=0)
    enabled: bool
    configured: bool
    verified: bool
    ready: bool
    verified_at: datetime | None
    config: dict[str, object]
    secrets: dict[str, str]
    operations: dict[TelephonyOperation, bool]


class ProviderConfigCreateSchema(EyloBaseApiSchema):
    model_config = ConfigDict(extra="forbid")

    provider: TelephonyProvider
    name: str = Field(min_length=1)
    config: dict[str, object]
    secrets: dict[str, str]


class ProviderConfigUpdateSchema(EyloBaseApiSchema):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1)
    config: dict[str, object] | None = None
    secrets: dict[str, str | None] | None = None
    enabled: bool | None = None

    @model_validator(mode="after")
    def validate_patch(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("At least one field must be supplied.")
        for field_name in self.model_fields_set:
            if getattr(self, field_name) is None:
                raise ValueError(f"{field_name} cannot be null.")
        return self


class ProviderConfigVerificationResponse(EyloBaseApiSchema):
    model_config = ConfigDict(extra="forbid")

    verified: bool = True
    provider: str
    revision: int = Field(gt=0)
    verified_at: datetime


# --- Number search & purchase schemas ---


class NumberType(str, Enum):
    """Types of phone numbers available from providers."""

    LOCAL = "Local"
    TOLL_FREE = "TollFree"
    MOBILE = "Mobile"


class NumberSearchParams(EyloBaseRequestSchema):
    """Query parameters for searching available numbers."""

    country: str
    number_type: NumberType = NumberType.LOCAL
    area_code: Optional[str] = None
    contains: Optional[str] = None
    limit: int = 20

    @field_validator("country")
    def validate_country(cls, v: str) -> str:
        if len(v) != 2 or not v.isalpha():
            raise ValueError("Country must be a 2-letter ISO code (e.g. US, GB)")
        return v.upper()

    @field_validator("limit")
    def validate_limit(cls, v: int) -> int:
        return max(1, min(v, 30))


class AvailableNumberSchema(EyloBaseRequestSchema):
    """A single available phone number from a provider search."""

    phone_number: str
    friendly_name: str
    locality: Optional[str] = None
    region: Optional[str] = None
    country: Optional[str] = None
    capabilities: dict = Field(default_factory=dict)


class AvailableNumbersResponseSchema(EyloBaseRequestSchema):
    """Response containing available numbers from a provider search."""

    provider: str
    country: str
    numbers: List[AvailableNumberSchema]


class NumberPurchaseRequest(EyloBaseRequestSchema):
    """Request to purchase a phone number from a provider."""

    phone_number: str
    label: Optional[str] = None
    country_code: Optional[str] = None

    @field_validator("phone_number")
    def validate_phone_number(cls, v: str) -> str:
        if not re.match(r"^\+[1-9]\d{1,14}$", v):
            raise ValueError("Invalid phone number format — must be E.164")
        return v

    @field_validator("country_code")
    def validate_country_code(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if len(v) != 2 or not v.isalpha():
            raise ValueError("Country code must be a 2-letter ISO code (e.g. US, GB)")
        return v.upper()
