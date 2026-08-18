"""Controller for searching and purchasing phone numbers from providers."""

import logging
from collections.abc import Awaitable, Callable
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from fastapi import HTTPException

from eylo.common.database import start_transaction
from eylo.common.outbound import (
    OutboundAttemptConflict,
    OutboundAttemptIdentity,
    OutboundAttemptSpec,
    OutboundAttemptState,
    OutboundOwnerKind,
    fingerprint_outbound_input,
)
from eylo.modules.telephony.provider_config_domain import (
    ResolvedTelephony,
    TelephonyOperation,
    supports_telephony_operation,
)
from eylo.modules.telephony.schemas import (
    AvailableNumberSchema,
    AvailableNumbersResponseSchema,
    NumberPurchaseRequest,
    NumberSearchParams,
    PhoneNumberApiResponseSchema,
    TelephonyProviderType,
)
from eylo.modules.telephony.services import (
    PhoneNumberProvisioningConflict,
    PhoneNumberService,
)
from eylo.modules.telephony.wiring import build_telephony_config_resolver
from eylo.pipelines.outbound.durable_execution import (
    DurableStepContext,
    OutboundExecutionReceipt,
    OutboundRetryRequested,
    execute_outbound_attempt,
)
from eylo.pipelines.telephony.twilio_rest import TwilioRestClient
from eylo.sockets.telephony.number_clients import (
    ExotelNumberClient,
    PlivoNumberClient,
    VonageNumberClient,
)
from eylo.sockets.telephony.number_purchase import NumberPurchaseClient

logger = logging.getLogger(__name__)


class _InlineDurableContext:
    """DB-fenced send for an HTTP request with a stable purchase identity."""

    async def step(
        self,
        *,
        key: str,
        version: int,
        operation: Callable[[], Awaitable[Any]],
    ) -> Any:
        del key, version
        return await operation()


class NumberManagementController:
    """Orchestrates available-number search and purchase across providers."""

    async def search_available_numbers(
        self,
        organization_id: UUID,
        provider_config_id: UUID,
        params: NumberSearchParams,
    ) -> AvailableNumbersResponseSchema:
        """Search using one explicit ready carrier-account config."""
        resolved = await self.resolve_config(organization_id, provider_config_id)
        provider = resolved.provider.value
        credentials = resolved.as_provider_config().adapter_settings()
        self._require_operation(resolved, TelephonyOperation.SEARCH_NUMBERS)

        dispatch = {
            TelephonyProviderType.TWILIO: self._search_twilio,
            TelephonyProviderType.PLIVO: self._search_plivo,
            TelephonyProviderType.VONAGE: self._search_vonage,
            TelephonyProviderType.EXOTEL: self._search_exotel,
        }
        handler = dispatch.get(TelephonyProviderType(provider))
        if not handler:
            raise HTTPException(501, f"Search not implemented for {provider}")

        return await handler(credentials, params, provider)

    async def resolve_config(
        self,
        organization_id: UUID,
        provider_config_id: UUID,
    ) -> ResolvedTelephony:
        async with start_transaction(ro=True) as db:
            return await build_telephony_config_resolver(db).resolve(
                organization_id,
                provider_config_id=provider_config_id,
            )

    async def purchase_number(
        self,
        *,
        organization_id: UUID,
        provider_config_id: UUID,
        request: NumberPurchaseRequest,
        idempotency_key: str,
        durable_context: DurableStepContext | None = None,
    ) -> PhoneNumberApiResponseSchema:
        """Persist intent, execute one charged effect, then project its outcome."""
        phone_number_id = self.purchase_identity(
            organization_id=organization_id,
            idempotency_key=idempotency_key,
        )
        try:
            resolved = await self._prepare_purchase(
                phone_number_id=phone_number_id,
                organization_id=organization_id,
                provider_config_id=provider_config_id,
                request=request,
            )
        except PhoneNumberProvisioningConflict as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

        client = self._purchase_client(resolved)
        profile = client.purchase_profile()
        spec = OutboundAttemptSpec(
            identity=OutboundAttemptIdentity(
                organization_id=organization_id,
                owner_kind=OutboundOwnerKind.PHONE_NUMBER,
                owner_id=phone_number_id,
                operation_key="telephony.number.purchase",
            ),
            provider_operation=profile.provider_operation,
            transport_kind=profile.transport_kind,
            destination_origin=profile.destination_origin,
            request_fingerprint=fingerprint_outbound_input(
                {
                    "phone_number_id": str(phone_number_id),
                    "phone_number": request.phone_number,
                    "label": request.label,
                    "country_code": request.country_code,
                    "provider": resolved.provider.value,
                    "provider_config_id": str(resolved.provider_config_id),
                    "provider_config_revision": resolved.provider_config_revision,
                }
            ),
        )

        async def send(authorization):
            return await client.purchase_number(
                request.phone_number,
                authorization=authorization,
                country=request.country_code,
            )

        try:
            receipt = await execute_outbound_attempt(
                spec=spec,
                context=durable_context or _InlineDurableContext(),
                sender=send,
            )
        except OutboundRetryRequested as error:
            await self._project_purchase(
                phone_number_id, organization_id, error.receipt
            )
            raise HTTPException(
                status_code=503,
                detail="Carrier asked Eylo to retry this purchase.",
                headers={"Retry-After": "5"},
            ) from error
        except OutboundAttemptConflict as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

        phone_number = await self._project_purchase(
            phone_number_id,
            organization_id,
            receipt,
        )
        if receipt.state is OutboundAttemptState.SUCCEEDED:
            return PhoneNumberApiResponseSchema.model_validate(phone_number)
        if receipt.state is OutboundAttemptState.UNKNOWN:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Carrier purchase outcome is unconfirmed; reconciliation is "
                    "required before another purchase attempt."
                ),
            )
        if receipt.state is OutboundAttemptState.TERMINAL:
            raise HTTPException(
                status_code=502,
                detail="Carrier rejected the phone-number purchase.",
            )
        raise HTTPException(
            status_code=409, detail="Phone-number purchase is not active."
        )

    async def _prepare_purchase(
        self,
        *,
        phone_number_id: UUID,
        organization_id: UUID,
        provider_config_id: UUID,
        request: NumberPurchaseRequest,
    ) -> ResolvedTelephony:
        async with start_transaction() as db:
            service = PhoneNumberService(db=db)
            existing = await service.get_by_id_in_organization(
                phone_number_id=phone_number_id,
                organization_id=organization_id,
            )
            resolver = build_telephony_config_resolver(db)
            if existing is None:
                resolved = await resolver.resolve(
                    organization_id,
                    provider_config_id=provider_config_id,
                )
                self._require_operation(
                    resolved,
                    TelephonyOperation.PURCHASE_NUMBER,
                )
                self._require_provider_purchase_input(resolved, request)
                await service.prepare_provisioning(
                    phone_number_id=phone_number_id,
                    organization_id=organization_id,
                    number=request.phone_number,
                    label=request.label,
                    provider=resolved.provider.value,
                    provider_config_id=resolved.provider_config_id,
                    provider_config_revision=resolved.provider_config_revision,
                )
                return resolved

            if existing.provider_config_id != provider_config_id:
                raise PhoneNumberProvisioningConflict(
                    "Idempotency-Key was already used with a different carrier config."
                )
            resolved = await resolver.resolve_pinned(
                organization_id,
                provider_config_id=existing.provider_config_id,
                revision=existing.provider_config_revision,
            )
            self._require_operation(resolved, TelephonyOperation.PURCHASE_NUMBER)
            self._require_provider_purchase_input(resolved, request)
            await service.prepare_provisioning(
                phone_number_id=phone_number_id,
                organization_id=organization_id,
                number=request.phone_number,
                label=request.label,
                provider=resolved.provider.value,
                provider_config_id=resolved.provider_config_id,
                provider_config_revision=resolved.provider_config_revision,
            )
            return resolved

    async def _project_purchase(
        self,
        phone_number_id: UUID,
        organization_id: UUID,
        receipt: OutboundExecutionReceipt,
    ):
        async with start_transaction() as db:
            return await PhoneNumberService(db=db).apply_provisioning_outcome(
                phone_number_id=phone_number_id,
                organization_id=organization_id,
                state=receipt.state,
                provider_reference=receipt.provider_reference,
                failure_code=receipt.failure_code,
            )

    @staticmethod
    def purchase_identity(*, organization_id: UUID, idempotency_key: str) -> UUID:
        normalized_key = idempotency_key.strip()
        if not normalized_key or len(normalized_key) > 255:
            raise HTTPException(
                status_code=400,
                detail="A bounded Idempotency-Key header is required.",
            )
        return uuid5(
            NAMESPACE_URL,
            f"eylo:phone-number-purchase:v1:{organization_id}:{normalized_key}",
        )

    # --- Twilio ---

    async def _search_twilio(
        self,
        credentials: dict,
        params: NumberSearchParams,
        provider: str,
    ) -> AvailableNumbersResponseSchema:
        client = TwilioRestClient(
            account_sid=credentials["account_sid"],
            auth_token=credentials["auth_token"],
        )
        raw = await client.search_available_numbers(
            country=params.country,
            number_type=params.number_type.value,
            area_code=params.area_code,
            contains=params.contains,
            limit=params.limit,
        )
        numbers = [
            AvailableNumberSchema(
                phone_number=n.get("phone_number", ""),
                friendly_name=n.get("friendly_name", ""),
                locality=n.get("locality"),
                region=n.get("region"),
                country=n.get("iso_country"),
                capabilities={
                    k: v for k, v in (n.get("capabilities") or {}).items() if v is True
                },
            )
            for n in raw
        ]
        return AvailableNumbersResponseSchema(
            provider=provider, country=params.country, numbers=numbers
        )

    # --- Plivo ---

    async def _search_plivo(
        self,
        credentials: dict,
        params: NumberSearchParams,
        provider: str,
    ) -> AvailableNumbersResponseSchema:
        client = PlivoNumberClient(
            auth_id=credentials["auth_id"],
            auth_token=credentials["auth_token"],
        )
        raw = await client.search_available_numbers(
            country=params.country,
            number_type=params.number_type.value,
            pattern=params.area_code or params.contains,
            limit=params.limit,
        )
        numbers = [
            AvailableNumberSchema(
                phone_number=f"+{n.get('number', '')}",
                friendly_name=n.get("number", ""),
                locality=n.get("city"),
                region=n.get("region"),
                country=n.get("country"),
                capabilities={
                    cap: True
                    for cap in ["voice", "sms", "mms"]
                    if n.get(cap) == "enabled" or n.get(f"{cap}_enabled") is True
                },
            )
            for n in raw
        ]
        return AvailableNumbersResponseSchema(
            provider=provider, country=params.country, numbers=numbers
        )

    # --- Vonage ---

    async def _search_vonage(
        self,
        credentials: dict,
        params: NumberSearchParams,
        provider: str,
    ) -> AvailableNumbersResponseSchema:
        client = VonageNumberClient(
            api_key=credentials["api_key"],
            api_secret=credentials["api_secret"],
        )
        raw = await client.search_available_numbers(
            country=params.country,
            number_type=params.number_type.value,
            pattern=params.area_code or params.contains,
            limit=params.limit,
        )
        numbers = [
            AvailableNumberSchema(
                phone_number=f"+{n.get('msisdn', '')}",
                friendly_name=n.get("msisdn", ""),
                locality=None,
                region=None,
                country=n.get("country"),
                capabilities={feat.lower(): True for feat in (n.get("features") or [])},
            )
            for n in raw
        ]
        return AvailableNumbersResponseSchema(
            provider=provider, country=params.country, numbers=numbers
        )

    # --- Exotel ---

    async def _search_exotel(
        self,
        credentials: dict,
        params: NumberSearchParams,
        provider: str,
    ) -> AvailableNumbersResponseSchema:
        client = ExotelNumberClient(
            api_key=credentials["api_key"],
            api_token=credentials["api_token"],
            account_sid=credentials["account_sid"],
            subdomain=credentials["subdomain"],
        )
        raw = await client.search_available_numbers(
            country=params.country,
            number_type=params.number_type.value,
            pattern=params.area_code or params.contains,
            limit=params.limit,
        )
        numbers = [
            AvailableNumberSchema(
                phone_number=n.get("phone_number", ""),
                friendly_name=n.get("friendly_name", ""),
                locality=None,
                region=n.get("region"),
                country=n.get("country"),
                capabilities={
                    name: enabled
                    for name, enabled in (n.get("capabilities") or {}).items()
                    if enabled is True
                },
            )
            for n in raw
        ]
        return AvailableNumbersResponseSchema(
            provider=provider,
            country=params.country,
            numbers=numbers,
        )

    @staticmethod
    def _purchase_client(resolved: ResolvedTelephony) -> NumberPurchaseClient:
        credentials = resolved.as_provider_config().adapter_settings()
        if resolved.provider is TelephonyProviderType.TWILIO:
            return TwilioRestClient(
                account_sid=credentials["account_sid"],
                auth_token=credentials["auth_token"],
            )
        if resolved.provider is TelephonyProviderType.PLIVO:
            return PlivoNumberClient(
                auth_id=credentials["auth_id"],
                auth_token=credentials["auth_token"],
            )
        if resolved.provider is TelephonyProviderType.VONAGE:
            return VonageNumberClient(
                api_key=credentials["api_key"],
                api_secret=credentials["api_secret"],
            )
        if resolved.provider is TelephonyProviderType.EXOTEL:
            return ExotelNumberClient(
                api_key=credentials["api_key"],
                api_token=credentials["api_token"],
                account_sid=credentials["account_sid"],
                subdomain=credentials["subdomain"],
            )
        raise HTTPException(
            status_code=501,
            detail=f"Purchase not implemented for {resolved.provider.value}.",
        )

    @staticmethod
    def _require_provider_purchase_input(
        resolved: ResolvedTelephony,
        request: NumberPurchaseRequest,
    ) -> None:
        if (
            resolved.provider is TelephonyProviderType.VONAGE
            and request.country_code is None
        ):
            raise HTTPException(
                status_code=422,
                detail="country_code is required for Vonage number purchase.",
            )

    @staticmethod
    def _require_operation(
        resolved: ResolvedTelephony,
        operation: TelephonyOperation,
    ) -> None:
        if supports_telephony_operation(resolved.provider, operation):
            return
        raise HTTPException(
            status_code=501,
            detail={
                "code": "UNSUPPORTED",
                "operation": operation.value,
                "provider": resolved.provider.value,
            },
        )
