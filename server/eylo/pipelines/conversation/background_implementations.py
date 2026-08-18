"""Execute registered first-party background Agent implementations."""

from __future__ import annotations

import logging
from typing import Awaitable, Callable

logger = logging.getLogger(__name__)


async def _locked(context, lock_name: str, worker) -> bool:
    """Run `worker` under the conversation lock this built-in has always used.

    `LockNotAcquired` means a concurrent run holds it. That is not an error and
    not work done: it reports False, which the caller records as SKIPPED.
    """
    from eylo.pipelines.llm.background_agents.redis_lock.conversation_lock import (
        LockNotAcquired,
        lock_conversation,
    )

    try:
        async with lock_conversation(context.conversation.id, lock_name):
            return await worker(context)
    except LockNotAcquired:
        logger.debug(
            "%s already running for conversation %s",
            lock_name,
            context.conversation.id,
        )
        return False


async def _run_title_generator(context) -> bool:
    from eylo.pipelines.llm.background_agents.title_generator.agent import (
        process_title_generation_request,
    )

    return await _locked(context, "title_gen", process_title_generation_request)


async def _run_summary_generator(context) -> bool:
    from eylo.pipelines.llm.background_agents.summary_generator.agent import (
        process_context_management_request,
    )

    return await _locked(context, "ctx_mgmt", process_context_management_request)


# Slug -> adapter. Keys must match `modules.agents.implementations`, which is
# what write-time validation checks against; a test pins that they agree, so a
# slug can never be accepted at write time and unresolvable at dispatch.
IMPLEMENTATION_RUNNERS: dict[str, Callable[[object], Awaitable[bool]]] = {
    "title_generator": _run_title_generator,
    "summary_generator": _run_summary_generator,
}


async def run_implementation(slug: str, context) -> bool:
    """Run a first-party implementation. True when it did work.

    False means it looked and found nothing to do, which the caller records as
    `SKIPPED` — not a failure. Exceptions propagate so `_mark_task_failed`
    records them.
    """
    runner = IMPLEMENTATION_RUNNERS.get(slug)
    if runner is None:
        raise ValueError(f"No runtime registered for implementation {slug!r}.")
    return await runner(context)
