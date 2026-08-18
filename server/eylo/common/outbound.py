"""Vendor-neutral identity and lifecycle vocabulary for external effects."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar, TypeAlias
from uuid import NAMESPACE_URL, UUID, uuid5

OUTBOUND_OPERATION_MAX_LENGTH = 192
OUTBOUND_FAILURE_CODE_MAX_LENGTH = 128
OUTBOUND_PROVIDER_REFERENCE_MAX_LENGTH = 320
OUTBOUND_DESTINATION_ORIGIN_MAX_LENGTH = 512
OUTBOUND_REQUEST_FINGERPRINT_LENGTH = 64

_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_.-]*$")
_FINGERPRINT = re.compile(r"^[0-9a-f]{64}$")
_ATTEMPT_NAMESPACE = uuid5(NAMESPACE_URL, "https://eylo.ai/outbound-attempt/v1")


class OutboundOwnerKind(StrEnum):
    """Stable product records that may own one external effect."""

    TOOL_CALL = "tool_call"
    CONVERSATION_MESSAGE = "conversation_message"
    CAMPAIGN_ATTEMPT = "campaign_attempt"
    VOICE_RECORDING = "voice_recording"
    TELEPHONY_CALL = "telephony_call"
    PHONE_NUMBER = "phone_number"
    TELEPHONY_OPERATION = "telephony_operation"
    WEBRTC_NEGOTIATION = "webrtc_negotiation"


class OutboundTransportKind(StrEnum):
    """Wire family used by an operation, not its product/provider identity."""

    HTTP = "http"
    PROVIDER_SDK = "provider_sdk"
    OBJECT_STORAGE = "object_storage"
    WEBSOCKET = "websocket"


class OutboundAttemptState(StrEnum):
    """Honest last-known state of one logical mutating external effect."""

    PREPARED = "prepared"
    IN_FLIGHT = "in_flight"
    SUCCEEDED = "succeeded"
    RETRYABLE = "retryable"
    TERMINAL = "terminal"
    UNKNOWN = "unknown"
    CANCELLED = "cancelled"


OUTBOUND_FINAL_STATES = frozenset(
    {
        OutboundAttemptState.SUCCEEDED,
        OutboundAttemptState.TERMINAL,
        OutboundAttemptState.CANCELLED,
    }
)


class OutboundAttemptError(Exception):
    """Base error for the shared external-effect boundary."""


class OutboundAttemptNotFound(OutboundAttemptError):
    """The attempt is absent from the caller's organization scope."""


class OutboundAttemptConflict(OutboundAttemptError):
    """A stable owner identity was reused for different effect input."""


class OutboundAttemptNotSendable(OutboundAttemptError):
    """Current durable state does not authorize another provider send."""


class OutboundAttemptReconciliationRequired(OutboundAttemptNotSendable):
    """A prior send is ambiguous and must not be repeated."""


class OutboundAttemptCancelled(OutboundAttemptNotSendable):
    """Cancellation fenced this effect before another send."""


@dataclass(frozen=True, slots=True)
class OutboundSendAuthorization:
    """The only stable attempt fields a socket needs to authorize one send."""

    attempt_id: UUID
    provider_idempotency_key: str

    def __post_init__(self) -> None:
        if self.provider_idempotency_key != f"eylo_{self.attempt_id.hex}":
            raise ValueError("Outbound provider idempotency key is not canonical.")


@dataclass(frozen=True, slots=True)
class OutboundSendSucceeded:
    """The provider accepted the requested effect."""

    state: ClassVar[OutboundAttemptState] = OutboundAttemptState.SUCCEEDED
    provider_reference: str | None = None
    status_code: int | None = None

    def __post_init__(self) -> None:
        _validate_outcome_values(
            provider_reference=self.provider_reference,
            status_code=self.status_code,
        )


@dataclass(frozen=True, slots=True)
class _OutboundSendFailure:
    failure_code: str
    provider_reference: str | None = None
    status_code: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "failure_code", require_failure_code(self.failure_code)
        )
        _validate_outcome_values(
            provider_reference=self.provider_reference,
            status_code=self.status_code,
        )


@dataclass(frozen=True, slots=True)
class OutboundSendRetryable(_OutboundSendFailure):
    """The provider confirmed this exact send may be attempted again."""

    state: ClassVar[OutboundAttemptState] = OutboundAttemptState.RETRYABLE


@dataclass(frozen=True, slots=True)
class OutboundSendTerminal(_OutboundSendFailure):
    """The provider rejected the effect without safe retry."""

    state: ClassVar[OutboundAttemptState] = OutboundAttemptState.TERMINAL


@dataclass(frozen=True, slots=True)
class OutboundSendUnknown(_OutboundSendFailure):
    """The effect may have happened and requires provider reconciliation."""

    state: ClassVar[OutboundAttemptState] = OutboundAttemptState.UNKNOWN


OutboundSendOutcome: TypeAlias = (
    OutboundSendSucceeded
    | OutboundSendRetryable
    | OutboundSendTerminal
    | OutboundSendUnknown
)


@dataclass(frozen=True, slots=True)
class OutboundAttemptIdentity:
    """Deterministic identity under one organization-owned product record."""

    organization_id: UUID
    owner_kind: OutboundOwnerKind
    owner_id: UUID
    operation_key: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "operation_key",
            _require_identifier(
                self.operation_key,
                field="operation_key",
                max_length=OUTBOUND_OPERATION_MAX_LENGTH,
            ),
        )

    @property
    def attempt_id(self) -> UUID:
        seed = ":".join(
            (
                str(self.organization_id),
                self.owner_kind.value,
                str(self.owner_id),
                self.operation_key,
            )
        )
        return uuid5(_ATTEMPT_NAMESPACE, seed)

    @property
    def provider_idempotency_key(self) -> str:
        """Opaque stable value safe to send only through a declared provider slot."""
        return f"eylo_{self.attempt_id.hex}"


@dataclass(frozen=True, slots=True)
class OutboundAttemptSpec:
    """Immutable safe audit fields agreed before the first network send."""

    identity: OutboundAttemptIdentity
    provider_operation: str
    transport_kind: OutboundTransportKind
    destination_origin: str
    request_fingerprint: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "provider_operation",
            _require_identifier(
                self.provider_operation,
                field="provider_operation",
                max_length=OUTBOUND_OPERATION_MAX_LENGTH,
            ),
        )
        origin = self.destination_origin.strip()
        if not origin or len(origin) > OUTBOUND_DESTINATION_ORIGIN_MAX_LENGTH:
            raise ValueError(
                "destination_origin must be a non-empty bounded normalized origin."
            )
        object.__setattr__(self, "destination_origin", origin)
        if not _FINGERPRINT.fullmatch(self.request_fingerprint):
            raise ValueError(
                "request_fingerprint must be a lowercase SHA-256 hex value."
            )


def fingerprint_outbound_input(value: object) -> str:
    """Hash canonical JSON without retaining request content in the ledger."""
    try:
        encoded = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise ValueError(
            "Outbound fingerprint input must be canonical JSON."
        ) from error
    return hashlib.sha256(encoded).hexdigest()


def require_failure_code(value: str) -> str:
    """Validate one allowlisted category, never arbitrary provider/error prose."""
    return _require_identifier(
        value,
        field="failure_code",
        max_length=OUTBOUND_FAILURE_CODE_MAX_LENGTH,
    )


def _validate_outcome_values(
    *,
    provider_reference: str | None,
    status_code: int | None,
) -> None:
    if provider_reference is not None:
        normalized = provider_reference.strip()
        if (
            not normalized
            or normalized != provider_reference
            or len(normalized) > OUTBOUND_PROVIDER_REFERENCE_MAX_LENGTH
        ):
            raise ValueError("provider_reference must be normalized and bounded.")
    if status_code is not None and not 100 <= status_code <= 599:
        raise ValueError("status_code must be an HTTP status between 100 and 599.")


def _require_identifier(value: str, *, field: str, max_length: int) -> str:
    normalized = value.strip()
    if (
        not normalized
        or len(normalized) > max_length
        or not _IDENTIFIER.fullmatch(normalized)
    ):
        raise ValueError(
            f"{field} must match {_IDENTIFIER.pattern!r} and be at most "
            f"{max_length} characters."
        )
    return normalized


__all__ = [
    "OUTBOUND_DESTINATION_ORIGIN_MAX_LENGTH",
    "OUTBOUND_FAILURE_CODE_MAX_LENGTH",
    "OUTBOUND_FINAL_STATES",
    "OUTBOUND_OPERATION_MAX_LENGTH",
    "OUTBOUND_PROVIDER_REFERENCE_MAX_LENGTH",
    "OUTBOUND_REQUEST_FINGERPRINT_LENGTH",
    "OutboundAttemptCancelled",
    "OutboundAttemptConflict",
    "OutboundAttemptError",
    "OutboundAttemptIdentity",
    "OutboundAttemptNotFound",
    "OutboundAttemptNotSendable",
    "OutboundAttemptReconciliationRequired",
    "OutboundAttemptSpec",
    "OutboundAttemptState",
    "OutboundOwnerKind",
    "OutboundSendAuthorization",
    "OutboundSendOutcome",
    "OutboundSendRetryable",
    "OutboundSendSucceeded",
    "OutboundSendTerminal",
    "OutboundSendUnknown",
    "OutboundTransportKind",
    "fingerprint_outbound_input",
    "require_failure_code",
]
