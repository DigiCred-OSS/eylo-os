"""Redis-backed runtime coordination for conversation request draining.

The database owns durable message/request state. This service owns only the
cross-process runtime claim: which process is currently draining a conversation,
which request it is processing, and whether another committed user message woke it
for another drain pass. Owner tokens make release/update operations safe when Redis
leases expire and another process claims the conversation.
"""

import datetime
from typing import Any
from uuid import UUID

import arrow

from eylo.common.redis import get_redis_client
from eylo.modules.conversations.schemas.runtime_status import (
    ConversationRuntimeClaimResult,
    ConversationRuntimePhase,
    ConversationRuntimeReleaseDecision,
    ConversationRuntimeStatus,
)

CONVERSATION_RUNTIME_STATUS_KEY_PREFIX = "eylo::conversations::runtime_status"
DEFAULT_CONVERSATION_RUNTIME_LEASE_SECONDS = 300
DEFAULT_CONVERSATION_RUNTIME_HEARTBEAT_SECONDS = 30
DEFAULT_CONVERSATION_RUNTIME_STALE_AFTER_SECONDS = (
    DEFAULT_CONVERSATION_RUNTIME_HEARTBEAT_SECONDS * 3
)

_CLAIM_OR_WAKE_SCRIPT = """
-- conversation_runtime_claim_or_wake
local key = KEYS[1]
local ttl = tonumber(ARGV[1])

if redis.call("EXISTS", key) == 0 then
    redis.call(
        "HSET",
        key,
        "organization_id", ARGV[2],
        "conversation_id", ARGV[3],
        "owner_token", ARGV[4],
        "phase", ARGV[5],
        "active_request_id", ARGV[6],
        "active_user_message_id", ARGV[7],
        "started_at", ARGV[8],
        "heartbeat_at", ARGV[9],
        "expires_at", ARGV[10],
        "heartbeat_epoch", ARGV[12],
        "expires_epoch", ARGV[14],
        "wake_requested", "0",
        "pending_count", ARGV[11],
        "last_enqueued_request_id", ARGV[6],
        "last_enqueued_user_message_id", ARGV[7]
    )
    redis.call("EXPIRE", key, ttl)
    return {1, 0, "", ""}
end

local heartbeat_epoch = tonumber(redis.call("HGET", key, "heartbeat_epoch") or "0")
local now_epoch = tonumber(ARGV[12])
local stale_after = tonumber(ARGV[13])

if heartbeat_epoch == 0 or now_epoch - heartbeat_epoch > stale_after then
    local previous_active_request_id = redis.call("HGET", key, "active_request_id") or ""
    local previous_active_user_message_id = redis.call("HGET", key, "active_user_message_id") or ""
    redis.call(
        "HSET",
        key,
        "organization_id", ARGV[2],
        "conversation_id", ARGV[3],
        "owner_token", ARGV[4],
        "phase", ARGV[5],
        "active_request_id", ARGV[6],
        "active_user_message_id", ARGV[7],
        "started_at", ARGV[8],
        "heartbeat_at", ARGV[9],
        "expires_at", ARGV[10],
        "heartbeat_epoch", ARGV[12],
        "expires_epoch", ARGV[14],
        "wake_requested", "0",
        "pending_count", ARGV[11],
        "last_enqueued_request_id", ARGV[6],
        "last_enqueued_user_message_id", ARGV[7]
    )
    redis.call("EXPIRE", key, ttl)
    return {1, 1, previous_active_request_id, previous_active_user_message_id}
end

redis.call(
    "HSET",
    key,
    "wake_requested", "1",
    "last_enqueued_request_id", ARGV[6],
    "last_enqueued_user_message_id", ARGV[7],
    "pending_count", ARGV[11]
)
return {0, 0, "", ""}
"""

_OWNER_UPDATE_SCRIPT = """
-- conversation_runtime_owner_update
local key = KEYS[1]
local ttl = tonumber(ARGV[1])
local owner_token = ARGV[2]

if redis.call("HGET", key, "owner_token") ~= owner_token then
    return 0
end

redis.call(
    "HSET",
    key,
    "phase", ARGV[3],
    "active_request_id", ARGV[4],
    "active_user_message_id", ARGV[5],
    "heartbeat_at", ARGV[6],
    "expires_at", ARGV[7],
    "heartbeat_epoch", ARGV[10],
    "expires_epoch", ARGV[11],
    "pending_count", ARGV[8],
    "wake_requested", ARGV[9]
)
redis.call("EXPIRE", key, ttl)
return 1
"""

_HEARTBEAT_SCRIPT = """
-- conversation_runtime_heartbeat
local key = KEYS[1]
local ttl = tonumber(ARGV[1])
local owner_token = ARGV[2]

if redis.call("HGET", key, "owner_token") ~= owner_token then
    return 0
end

redis.call(
    "HSET",
    key,
    "heartbeat_at", ARGV[3],
    "expires_at", ARGV[4],
    "heartbeat_epoch", ARGV[5],
    "expires_epoch", ARGV[6]
)
redis.call("EXPIRE", key, ttl)
return 1
"""

_RELEASE_OR_CONTINUE_SCRIPT = """
-- conversation_runtime_release_or_continue
local key = KEYS[1]
local ttl = tonumber(ARGV[1])
local owner_token = ARGV[2]

if redis.call("HGET", key, "owner_token") ~= owner_token then
    return -1
end

if redis.call("HGET", key, "wake_requested") == "1" then
    redis.call(
        "HSET",
        key,
        "phase", ARGV[3],
        "heartbeat_at", ARGV[4],
        "expires_at", ARGV[5],
        "heartbeat_epoch", ARGV[6],
        "expires_epoch", ARGV[7],
        "wake_requested", "0",
        "pending_count", "0"
    )
    redis.call("HDEL", key, "active_request_id", "active_user_message_id")
    redis.call("EXPIRE", key, ttl)
    return 1
end

redis.call("DEL", key)
return 0
"""

_RELEASE_SCRIPT = """
-- conversation_runtime_release
local key = KEYS[1]
local owner_token = ARGV[1]

if redis.call("HGET", key, "owner_token") ~= owner_token then
    return 0
end

redis.call("DEL", key)
return 1
"""


class ConversationRuntimeStatusService:
    """Coordinate the cross-process runtime owner for a conversation."""

    def __init__(
        self,
        redis_client: Any | None = None,
        lease_seconds: int = DEFAULT_CONVERSATION_RUNTIME_LEASE_SECONDS,
        stale_after_seconds: int = DEFAULT_CONVERSATION_RUNTIME_STALE_AFTER_SECONDS,
    ) -> None:
        self.redis_client = redis_client or get_redis_client()
        self.lease_seconds = lease_seconds
        self.stale_after_seconds = stale_after_seconds

    async def claim_or_wake_result(
        self,
        *,
        organization_id: UUID,
        conversation_id: UUID,
        owner_token: str,
        request_id: UUID,
        user_message_id: UUID,
        pending_count: int,
    ) -> ConversationRuntimeClaimResult:
        """Claim the conversation if idle, otherwise mark it for another drain pass."""
        now = arrow.utcnow().datetime
        expires_at = _expires_at(now, self.lease_seconds)
        result = await self.redis_client.eval(
            _CLAIM_OR_WAKE_SCRIPT,
            1,
            self._key(organization_id, conversation_id),
            self.lease_seconds,
            str(organization_id),
            str(conversation_id),
            owner_token,
            ConversationRuntimePhase.PROCESSING.value,
            str(request_id),
            str(user_message_id),
            _serialize_datetime(now),
            _serialize_datetime(now),
            _serialize_datetime(expires_at),
            str(pending_count),
            str(now.timestamp()),
            str(self.stale_after_seconds),
            str(expires_at.timestamp()),
        )
        return _decode_claim_result(result)

    async def claim_or_wake(
        self,
        *,
        organization_id: UUID,
        conversation_id: UUID,
        owner_token: str,
        request_id: UUID,
        user_message_id: UUID,
        pending_count: int,
    ) -> bool:
        """Return whether the conversation was claimed by this caller."""
        result = await self.claim_or_wake_result(
            organization_id=organization_id,
            conversation_id=conversation_id,
            owner_token=owner_token,
            request_id=request_id,
            user_message_id=user_message_id,
            pending_count=pending_count,
        )
        return result.acquired

    async def start_processing(
        self,
        *,
        organization_id: UUID,
        conversation_id: UUID,
        owner_token: str,
        request_id: UUID,
        user_message_id: UUID,
        pending_count: int,
    ) -> bool:
        """Owner-checked update of the active request being processed."""
        now = arrow.utcnow().datetime
        expires_at = _expires_at(now, self.lease_seconds)
        updated = await self.redis_client.eval(
            _OWNER_UPDATE_SCRIPT,
            1,
            self._key(organization_id, conversation_id),
            self.lease_seconds,
            owner_token,
            ConversationRuntimePhase.PROCESSING.value,
            str(request_id),
            str(user_message_id),
            _serialize_datetime(now),
            _serialize_datetime(expires_at),
            str(pending_count),
            "0",
            str(now.timestamp()),
            str(expires_at.timestamp()),
        )
        return bool(updated)

    async def heartbeat(
        self,
        *,
        organization_id: UUID,
        conversation_id: UUID,
        owner_token: str,
    ) -> bool:
        """Refresh the runtime lease if the caller still owns the conversation."""
        now = arrow.utcnow().datetime
        expires_at = _expires_at(now, self.lease_seconds)
        updated = await self.redis_client.eval(
            _HEARTBEAT_SCRIPT,
            1,
            self._key(organization_id, conversation_id),
            self.lease_seconds,
            owner_token,
            _serialize_datetime(now),
            _serialize_datetime(expires_at),
            str(now.timestamp()),
            str(expires_at.timestamp()),
        )
        return bool(updated)

    async def release_or_continue(
        self,
        *,
        organization_id: UUID,
        conversation_id: UUID,
        owner_token: str,
    ) -> ConversationRuntimeReleaseDecision:
        """Release when quiet, or continue draining when another event woke us."""
        now = arrow.utcnow().datetime
        expires_at = _expires_at(now, self.lease_seconds)
        result = await self.redis_client.eval(
            _RELEASE_OR_CONTINUE_SCRIPT,
            1,
            self._key(organization_id, conversation_id),
            self.lease_seconds,
            owner_token,
            ConversationRuntimePhase.DRAINING.value,
            _serialize_datetime(now),
            _serialize_datetime(expires_at),
            str(now.timestamp()),
            str(expires_at.timestamp()),
        )
        if int(result) == 1:
            return ConversationRuntimeReleaseDecision.CONTINUE
        if int(result) == 0:
            return ConversationRuntimeReleaseDecision.RELEASED
        return ConversationRuntimeReleaseDecision.LOST

    async def release(
        self,
        *,
        organization_id: UUID,
        conversation_id: UUID,
        owner_token: str,
    ) -> bool:
        """Delete the runtime status if the caller still owns it."""
        released = await self.redis_client.eval(
            _RELEASE_SCRIPT,
            1,
            self._key(organization_id, conversation_id),
            owner_token,
        )
        return bool(released)

    async def get_status(
        self,
        *,
        organization_id: UUID,
        conversation_id: UUID,
    ) -> ConversationRuntimeStatus | None:
        """Return the shared runtime status for a conversation, if any."""
        data = await self.redis_client.hgetall(
            self._key(organization_id, conversation_id)
        )
        if not data:
            return None
        return ConversationRuntimeStatus.model_validate(_decode_status_hash(data))

    @staticmethod
    def _key(organization_id: UUID, conversation_id: UUID) -> str:
        return (
            f"{CONVERSATION_RUNTIME_STATUS_KEY_PREFIX}::"
            f"{organization_id}::{conversation_id}"
        )


def _expires_at(
    now: datetime.datetime,
    lease_seconds: int,
) -> datetime.datetime:
    return now + datetime.timedelta(seconds=lease_seconds)


def _serialize_datetime(value: datetime.datetime) -> str:
    return value.isoformat()


def _decode_status_hash(data: dict[Any, Any]) -> dict[str, Any]:
    decoded: dict[str, Any] = {}
    uuid_fields = {
        "active_request_id",
        "active_user_message_id",
        "last_enqueued_request_id",
        "last_enqueued_user_message_id",
    }
    for raw_key, raw_value in data.items():
        key = _decode_redis_value(raw_key)
        value = _decode_redis_value(raw_value)
        if key in uuid_fields and not value:
            decoded[key] = None
            continue
        if key == "wake_requested":
            decoded[key] = value == "1" or value is True
            continue
        if key == "pending_count":
            decoded[key] = int(value or 0)
            continue
        if key in {"heartbeat_epoch", "expires_epoch"}:
            decoded[key] = float(value) if value else None
            continue
        decoded[key] = value
    return decoded


def _decode_claim_result(result: Any) -> ConversationRuntimeClaimResult:
    values = list(result or [])
    acquired = bool(int(_decode_redis_value(values[0]))) if values else False
    stale_takeover = (
        bool(int(_decode_redis_value(values[1]))) if len(values) > 1 else False
    )
    previous_active_request_id = (
        _decode_redis_value(values[2]) if len(values) > 2 else None
    )
    previous_active_user_message_id = (
        _decode_redis_value(values[3]) if len(values) > 3 else None
    )
    return ConversationRuntimeClaimResult(
        acquired=acquired,
        stale_takeover=stale_takeover,
        previous_active_request_id=previous_active_request_id or None,
        previous_active_user_message_id=previous_active_user_message_id or None,
    )


def _decode_redis_value(value: Any) -> Any:
    if isinstance(value, bytes):
        return value.decode()
    return value
