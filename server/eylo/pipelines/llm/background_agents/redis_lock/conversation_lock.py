"""Per-conversation Redis mutex for background agent deduplication.

Prevents the same background agent from processing a conversation twice
concurrently when multiple events arrive in rapid succession.
"""

from contextlib import asynccontextmanager
from uuid import UUID

from eylo.common.redis import get_redis_client


class LockNotAcquired(Exception):
    pass


class ConversationLock:
    def __init__(self, conversation_id: UUID, key_prefix: str, timeout: int = 60):
        self.redis_client = get_redis_client()
        self.lock_key = f"eylo::bg_agents::{key_prefix}::{conversation_id}"
        self.timeout = timeout

    async def acquire(self) -> bool:
        acquired = await self.redis_client.set(
            self.lock_key,
            "1",
            nx=True,
            ex=self.timeout,
        )
        return bool(acquired)

    async def release(self) -> None:
        await self.redis_client.delete(self.lock_key)


@asynccontextmanager
async def lock_conversation(conversation_id: UUID, key_prefix: str, timeout: int = 60):
    """Async context manager that acquires a per-conversation Redis lock.

    Raises LockNotAcquired if the lock is already held.
    """
    lock = ConversationLock(conversation_id, key_prefix, timeout)
    acquired = await lock.acquire()
    try:
        if acquired:
            yield
        else:
            raise LockNotAcquired(
                f"Could not acquire lock for conversation {conversation_id} "
                f"with prefix {key_prefix}"
            )
    finally:
        if acquired:
            await lock.release()
