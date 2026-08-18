"""Service for managing telephony operations."""

import logging
from datetime import datetime
from typing import Optional
from uuid import UUID

import arrow
from sqlalchemy.ext.asyncio import AsyncSession

from eylo.common.outbound import OutboundAttemptState
from eylo.common.services import EyloBaseService
from eylo.modules.telephony.repositories import (
    PhoneNumberRepository,
    TelephonyCallRepository,
)
from eylo.modules.telephony.schemas import (
    CallDirection,
    CallStatus,
    PhoneNumberCreateSchema,
    PhoneNumberInDb,
    PhoneNumberStatus,
    PhoneNumberUpdateSchema,
    TelephonyCallInDb,
    TelephonyCallStatusUpdateResult,
)

logger = logging.getLogger(__name__)

_TERMINAL_CALL_STATUSES = frozenset(
    {
        CallStatus.COMPLETED.value,
        CallStatus.BUSY.value,
        CallStatus.NO_ANSWER.value,
        CallStatus.FAILED.value,
        CallStatus.CANCELED.value,
    }
)
_CALL_STATUS_ORDER = {
    CallStatus.INITIATED.value: 10,
    CallStatus.RINGING.value: 20,
    CallStatus.IN_PROGRESS.value: 30,
    CallStatus.COMPLETED.value: 40,
    CallStatus.BUSY.value: 40,
    CallStatus.NO_ANSWER.value: 40,
    CallStatus.FAILED.value: 40,
    CallStatus.CANCELED.value: 40,
}


class PhoneNumberProvisioningConflict(Exception):
    """One purchase identity was reused or the number already has an owner."""


class PhoneNumberProvisioningNotFound(Exception):
    """The organization-owned purchase intent is absent."""


class PhoneNumberService(EyloBaseService[PhoneNumberInDb]):
    @property
    def schema(self) -> type[PhoneNumberInDb]:
        return PhoneNumberInDb

    @property
    def repository(self) -> PhoneNumberRepository:
        return self._repository

    def __init__(self, db: Optional[AsyncSession] = None):
        self._repository = PhoneNumberRepository(db)

    async def create(
        self, organization_id: UUID, request: PhoneNumberCreateSchema
    ) -> PhoneNumberInDb:
        entity = await self.repository.create(organization_id, request)
        return self.orm_to_schema(entity)

    async def prepare_provisioning(
        self,
        *,
        phone_number_id: UUID,
        organization_id: UUID,
        number: str,
        label: str | None,
        provider: str,
        provider_config_id: UUID,
        provider_config_revision: int,
    ) -> PhoneNumberInDb:
        entity = await self.repository.prepare_provisioning(
            phone_number_id=phone_number_id,
            organization_id=organization_id,
            number=number,
            label=label,
            provider=provider,
            provider_config_id=provider_config_id,
            provider_config_revision=provider_config_revision,
        )
        if entity is None:
            raise PhoneNumberProvisioningConflict("Phone number is already registered.")
        expected = (
            organization_id,
            number,
            label,
            provider,
            provider_config_id,
            provider_config_revision,
        )
        actual = (
            UUID(str(entity.organization_id)),
            entity.number,
            entity.label,
            entity.provider,
            UUID(str(entity.provider_config_id)),
            entity.provider_config_revision,
        )
        if entity.deleted or actual != expected:
            raise PhoneNumberProvisioningConflict(
                "Idempotency-Key was already used for a different purchase."
            )
        return self.orm_to_schema(entity)

    async def get_by_id_in_organization(
        self,
        *,
        phone_number_id: UUID,
        organization_id: UUID,
    ) -> PhoneNumberInDb | None:
        entity = await self.repository.get_by_id_in_organization(
            phone_number_id=phone_number_id,
            organization_id=organization_id,
        )
        return self.orm_to_schema(entity) if entity else None

    async def apply_provisioning_outcome(
        self,
        *,
        phone_number_id: UUID,
        organization_id: UUID,
        state: OutboundAttemptState,
        provider_reference: str | None,
        failure_code: str | None,
    ) -> PhoneNumberInDb:
        """Project one durable provider outcome onto the purchase intent."""
        entity = await self.repository.get_by_id_in_organization(
            phone_number_id=phone_number_id,
            organization_id=organization_id,
            for_update=True,
        )
        if entity is None:
            raise PhoneNumberProvisioningNotFound(
                "Phone-number purchase intent not found."
            )

        if state is OutboundAttemptState.SUCCEEDED:
            entity.status = PhoneNumberStatus.ACTIVE
            entity.provider_reference = provider_reference or entity.number
            entity.provisioning_failure_code = None
        elif state is OutboundAttemptState.RETRYABLE:
            entity.status = PhoneNumberStatus.PROVISIONING
            entity.provider_reference = None
            entity.provisioning_failure_code = None
        elif state is OutboundAttemptState.UNKNOWN:
            entity.status = PhoneNumberStatus.PROVISIONING_UNKNOWN
            entity.provider_reference = provider_reference
            entity.provisioning_failure_code = (
                failure_code or "number_purchase_unconfirmed"
            )
        elif state is OutboundAttemptState.TERMINAL:
            entity.status = PhoneNumberStatus.PROVISIONING_FAILED
            entity.provider_reference = provider_reference
            entity.provisioning_failure_code = (
                failure_code or "number_purchase_rejected"
            )
        else:
            raise ValueError(f"Unsupported provisioning outcome: {state.value}.")

        entity = await self.repository.save_(entity)
        return self.orm_to_schema(entity)

    async def update(
        self, phone_number_id: UUID, request: PhoneNumberUpdateSchema
    ) -> PhoneNumberInDb:
        entity = await self.repository.update(phone_number_id, request)
        return self.orm_to_schema(entity)

    async def soft_delete(self, phone_number_id: UUID) -> PhoneNumberInDb:
        entity = await self.repository.soft_delete(phone_number_id)
        return self.orm_to_schema(entity)

    async def list_by_organization(
        self,
        organization_id: UUID,
        limit: int = 100,
        offset: int = 0,
        provider: str | None = None,
    ) -> list[PhoneNumberInDb]:
        filters = [self.repository.model.organization_id == organization_id]
        filters.append(self.repository.model.deleted.is_(False))
        if provider:
            filters.append(self.repository.model.provider == provider)
        return self.orm_to_schema_list(
            await self.repository.filter_(
                filters=filters,
                limit=limit,
                offset=offset,
                order_by=[self.repository.model.created_at.desc()],
            )
        )

    async def count_by_organization(
        self, organization_id: UUID, provider: str | None = None
    ) -> int:
        filters = [self.repository.model.organization_id == organization_id]
        filters.append(self.repository.model.deleted.is_(False))
        if provider:
            filters.append(self.repository.model.provider == provider)
        return await self.repository.count_(filters=filters)

    async def get_by_number(self, number: str) -> PhoneNumberInDb | None:
        entity = await self.repository.get_by_("number", number)
        if not entity:
            return None
        return self.orm_to_schema(entity)

    async def get_by_outbound_agent_id(
        self,
        outbound_agent_id: str,
        organization_id: UUID | None = None,
    ) -> PhoneNumberInDb | None:
        if organization_id is not None:
            entity = await self.repository.get_active_by_outbound_agent_id(
                organization_id=organization_id,
                outbound_agent_id=UUID(str(outbound_agent_id)),
            )
            return self.orm_to_schema(entity) if entity else None
        entity = await self.repository.get_by_("outbound_agent_id", outbound_agent_id)
        if not entity or entity.deleted or entity.status != PhoneNumberStatus.ACTIVE:
            return None
        return self.orm_to_schema(entity)

    async def get_by_label(self, label: str) -> PhoneNumberInDb | None:
        """Get phone number by label."""
        entity = await self.repository.get_by_("label", label)
        if not entity:
            return None
        return self.orm_to_schema(entity)


class TelephonyCallService(EyloBaseService[TelephonyCallInDb]):
    """Service for managing telephony call records."""

    @property
    def schema(self) -> type[TelephonyCallInDb]:
        return TelephonyCallInDb

    @property
    def repository(self) -> TelephonyCallRepository:
        return self._repository

    def __init__(self, db: Optional[AsyncSession] = None):
        self._repository = TelephonyCallRepository(db)

    async def get_by_organization(
        self,
        call_id: UUID,
        organization_id: UUID,
    ) -> TelephonyCallInDb | None:
        """Resolve one call only inside its owning organization."""
        rows = await self.repository.filter_(
            filters=[
                self.repository.model.id == call_id,
                self.repository.model.organization_id == organization_id,
                self.repository.model.deleted.is_(False),
            ],
            limit=1,
        )
        return self.orm_to_schema(rows[0]) if rows else None

    async def create_call(
        self,
        organization_id: UUID,
        call_sid: str | None,
        provider: str,
        provider_config_id: UUID,
        provider_config_revision: int,
        call_id: UUID | None = None,
        direction: str = CallDirection.OUTBOUND,
        from_number: Optional[str] = None,
        to_number: Optional[str] = None,
        agent_id: Optional[UUID] = None,
        agent_revision: Optional[int] = None,
        conversation_id: Optional[UUID] = None,
        user_session_id: Optional[UUID] = None,
        campaign_id: Optional[UUID] = None,
        campaign_contact_id: Optional[UUID] = None,
        campaign_attempt_id: Optional[UUID] = None,
        phone_number_id: Optional[UUID] = None,
    ) -> TelephonyCallInDb:
        """Create a new call record when a call starts."""
        from eylo.modules.telephony.models import TelephonyCallModel

        values = dict(
            organization_id=organization_id,
            call_sid=call_sid,
            provider=provider,
            provider_config_id=provider_config_id,
            provider_config_revision=provider_config_revision,
            direction=direction,
            status=CallStatus.INITIATED,
            from_number=from_number,
            to_number=to_number,
            agent_id=agent_id,
            agent_revision=agent_revision,
            conversation_id=conversation_id,
            user_session_id=user_session_id,
            campaign_id=campaign_id,
            campaign_contact_id=campaign_contact_id,
            campaign_attempt_id=campaign_attempt_id,
            phone_number_id=phone_number_id,
            started_at=arrow.utcnow().datetime,
        )
        if call_id is not None:
            values["id"] = call_id
        entity = TelephonyCallModel(**values)
        saved = await self.repository.save_(entity)
        logger.info(
            "Call record created: call_id=%s provider=%s direction=%s campaign=%s",
            saved.id,
            provider,
            direction,
            campaign_id,
        )
        return self.orm_to_schema(saved)

    async def update_status(
        self,
        call_sid: str,
        status: str,
        provider_status: Optional[str] = None,
        ended_reason: Optional[str] = None,
        ended_at: Optional[datetime] = None,
        connected_at: Optional[datetime] = None,
        duration_seconds: Optional[int] = None,
        conversation_id: Optional[UUID] = None,
        source: str = "runtime",
    ) -> Optional[TelephonyCallInDb]:
        """Update call status and optional fields by call_sid."""
        result = await self.update_status_with_result(
            call_sid=call_sid,
            status=status,
            provider_status=provider_status,
            ended_reason=ended_reason,
            ended_at=ended_at,
            connected_at=connected_at,
            duration_seconds=duration_seconds,
            conversation_id=conversation_id,
            source=source,
        )
        return result.call

    async def update_status_with_result(
        self,
        call_sid: str,
        status: str,
        organization_id: UUID | None = None,
        provider_status: Optional[str] = None,
        ended_reason: Optional[str] = None,
        ended_at: Optional[datetime] = None,
        connected_at: Optional[datetime] = None,
        duration_seconds: Optional[int] = None,
        conversation_id: Optional[UUID] = None,
        source: str = "runtime",
    ) -> TelephonyCallStatusUpdateResult:
        """Update call status and report whether the update changed lifecycle state."""
        status_value = status.value if isinstance(status, CallStatus) else str(status)
        entity = await self.repository.get_by_call_sid_for_update(
            call_sid,
            organization_id,
        )
        if not entity:
            logger.warning("Call not found for update: call_sid=%s", call_sid)
            return TelephonyCallStatusUpdateResult(
                call=None,
                incoming_status=status_value,
                ignored=True,
            )

        previous_status = entity.status
        previous_status_value = (
            previous_status.value
            if isinstance(previous_status, CallStatus)
            else str(previous_status)
        )
        if previous_status_value in _TERMINAL_CALL_STATUSES:
            changed_fields: list[str] = []
            conflicts: list[str] = []

            def enrich(
                field: str,
                value,
                *,
                authoritative: bool = False,
            ) -> None:
                if value is None:
                    return
                current = getattr(entity, field)
                if current is None or (authoritative and current != value):
                    setattr(entity, field, value)
                    changed_fields.append(field)
                elif current != value:
                    conflicts.append(field)

            provider_authoritative = source == "provider_callback"
            enrich(
                "provider_status",
                provider_status,
                authoritative=provider_authoritative,
            )
            enrich(
                "ended_reason",
                ended_reason,
                authoritative=provider_authoritative,
            )
            enrich("ended_at", ended_at)
            enrich("connected_at", connected_at)
            enrich(
                "duration_seconds",
                duration_seconds,
                authoritative=provider_authoritative,
            )
            enrich("conversation_id", conversation_id)
            if status_value != previous_status_value:
                conflicts.append("status")
            if changed_fields or conflicts:
                entity.status_history = [
                    *(entity.status_history or []),
                    {
                        "status": previous_status_value,
                        "incoming_status": status_value,
                        "source": source,
                        "enriched_fields": changed_fields,
                        "conflicts": conflicts,
                        "observed_at": arrow.utcnow().isoformat(),
                    },
                ]
            if changed_fields or conflicts:
                entity = await self.repository.partial_update_(entity)
            logger.info(
                "Terminal call enrichment processed: call_sid=%s source=%s changed=%s conflicts=%s",
                call_sid,
                source,
                changed_fields,
                conflicts,
            )
            return TelephonyCallStatusUpdateResult(
                call=self.orm_to_schema(entity),
                previous_status=previous_status_value,
                incoming_status=status_value,
                ignored=not changed_fields,
            )
        if _CALL_STATUS_ORDER.get(status_value, 0) < _CALL_STATUS_ORDER.get(
            previous_status_value, 0
        ):
            logger.info(
                "Ignoring stale call status update: call_sid=%s previous=%s incoming=%s",
                call_sid,
                previous_status,
                status,
            )
            return TelephonyCallStatusUpdateResult(
                call=self.orm_to_schema(entity),
                previous_status=previous_status_value,
                incoming_status=status_value,
                ignored=True,
            )

        entity.status = status_value
        entity.provider_status = provider_status or entity.provider_status
        history_entry = {
            "status": status_value,
            "provider_status": provider_status,
            "previous_status": previous_status_value,
            "source": source,
            "observed_at": arrow.utcnow().isoformat(),
        }
        entity.status_history = [*(entity.status_history or []), history_entry]
        if ended_reason is not None:
            entity.ended_reason = ended_reason
        if ended_at is not None:
            entity.ended_at = ended_at
        if connected_at is not None:
            entity.connected_at = connected_at
        if duration_seconds is not None:
            entity.duration_seconds = duration_seconds
        if conversation_id is not None:
            entity.conversation_id = conversation_id

        updated = await self.repository.partial_update_(entity)
        return TelephonyCallStatusUpdateResult(
            call=self.orm_to_schema(updated),
            previous_status=previous_status_value,
            incoming_status=status_value,
            status_changed=previous_status_value != status_value,
            entered_terminal_status=status_value in _TERMINAL_CALL_STATUSES,
        )

    async def mark_transfer_requested(
        self,
        call_sid: str,
        transfer_to: str,
        reason: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> Optional[TelephonyCallInDb]:
        """Persist transfer request details for an active call."""
        entity = await self.repository.get_by_call_sid(call_sid)
        if not entity:
            logger.warning("Call not found for transfer update: call_sid=%s", call_sid)
            return None
        entity.transfer_status = "transferring"
        entity.transfer_to = transfer_to
        entity.transfer_reason = reason
        entity.transfer_metadata = {
            **(entity.transfer_metadata or {}),
            **(metadata or {}),
        }
        updated = await self.repository.partial_update_(entity)
        return self.orm_to_schema(updated)

    async def mark_transfer_completed(
        self,
        call_sid: str,
        transfer_to: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> Optional[TelephonyCallInDb]:
        """Persist transfer completion details for a call."""
        entity = await self.repository.get_by_call_sid(call_sid)
        if not entity:
            logger.warning(
                "Call not found for transfer completion: call_sid=%s", call_sid
            )
            return None
        entity.transfer_status = "transferred"
        entity.transfer_to = transfer_to or entity.transfer_to
        entity.transferred_at = arrow.utcnow().datetime
        entity.transfer_metadata = {
            **(entity.transfer_metadata or {}),
            **(metadata or {}),
        }
        updated = await self.repository.partial_update_(entity)
        return self.orm_to_schema(updated)

    async def get_by_call_sid(self, call_sid: str) -> Optional[TelephonyCallInDb]:
        """Get a call record by provider call SID."""
        entity = await self.repository.get_by_call_sid(call_sid)
        if not entity:
            return None
        return self.orm_to_schema(entity)

    async def get_by_call_sid_for_organization(
        self,
        *,
        call_sid: str,
        organization_id: UUID,
    ) -> Optional[TelephonyCallInDb]:
        """Load one organization-owned call for live control authorization."""
        entity = await self.repository.get_by_call_sid(
            call_sid,
            organization_id=organization_id,
        )
        if not entity:
            return None
        return self.orm_to_schema(entity)

    async def list_by_organization(
        self,
        organization_id: UUID,
        limit: int = 20,
        offset: int = 0,
        status: Optional[str] = None,
        direction: Optional[str] = None,
        campaign_id: Optional[UUID] = None,
        conversation_id: Optional[UUID] = None,
    ) -> list[TelephonyCallInDb]:
        return self.orm_to_schema_list(
            await self.repository.list_by_organization(
                organization_id=organization_id,
                limit=limit,
                offset=offset,
                status=status,
                direction=direction,
                campaign_id=campaign_id,
                conversation_id=conversation_id,
            )
        )

    async def count_by_organization(
        self,
        organization_id: UUID,
        status: Optional[str] = None,
        direction: Optional[str] = None,
        campaign_id: Optional[UUID] = None,
        conversation_id: Optional[UUID] = None,
    ) -> int:
        return await self.repository.count_by_organization(
            organization_id=organization_id,
            status=status,
            direction=direction,
            campaign_id=campaign_id,
            conversation_id=conversation_id,
        )
